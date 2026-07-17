#!/usr/bin/env python3
"""Stage a held-out dataset, deploy perception-only code, and evaluate on the Pi/Hailo."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from playground.autoresearch.perception_score import _read_jsonl

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / ".autoresearch" / "datasets"
SAFE_HOST = re.compile(r"^[A-Za-z0-9._-]+$")
SAFE_REMOTE_ROOT = re.compile(r"^/[A-Za-z0-9._/-]+$")
SAFE_ARTIFACT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}\.hef$")


def _validate_host(value: str) -> str:
    if not SAFE_HOST.fullmatch(value):
        raise argparse.ArgumentTypeError("host must be a simple SSH alias or hostname")
    return value


def _validate_remote_root(value: str) -> str:
    if not SAFE_REMOTE_ROOT.fullmatch(value) or ".." in Path(value).parts:
        raise argparse.ArgumentTypeError("remote root must be a simple absolute path without '..'")
    return value.rstrip("/")


def _hash_file(path: Path, digest: Any) -> None:
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)


def stage_dataset(ground_truth_path: Path) -> tuple[Path, str]:
    ground_truth_path = ground_truth_path.expanduser().resolve()
    records = _read_jsonl(ground_truth_path)
    digest = hashlib.sha256()
    digest.update(ground_truth_path.read_bytes())
    sources: list[Path] = []
    for row in records:
        source = Path(str(row.get("image_path", ""))).expanduser().resolve()
        if not source.is_file():
            raise ValueError(f"missing held-out image: {source}")
        _hash_file(source, digest)
        sources.append(source)
    dataset_id = digest.hexdigest()[:16]
    bundle = STAGING / dataset_id
    images_dir = bundle / "images"
    manifest_path = bundle / "ground_truth.jsonl"
    if manifest_path.is_file():
        return bundle, dataset_id

    images_dir.mkdir(parents=True, exist_ok=True)
    rewritten: list[dict[str, Any]] = []
    for index, (row, source) in enumerate(zip(records, sources, strict=True)):
        suffix = source.suffix.lower() if source.suffix else ".img"
        name = f"{index:06d}{suffix}"
        shutil.copy2(source, images_dir / name)
        rewritten.append({**row, "image_path": f"__REMOTE_DATASET__/images/{name}"})
    manifest_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rewritten),
        encoding="utf-8",
    )
    return bundle, dataset_id


def deploy_command(host: str, remote_root: str) -> list[str]:
    sources = [
        "./playground/__init__.py",
        "./playground/hailo_probe.py",
        "./playground/autonomy/",
        "./playground/vision/",
        "./playground/autoresearch/",
        "./playground/experiments/",
    ]
    return [
        "rsync",
        "-azR",
        "--exclude",
        "__pycache__",
        "--exclude",
        "models",
        *sources,
        f"{host}:{remote_root}/",
    ]


def ensure_remote_dirs_command(
    host: str, remote_root: str, remote_dataset_parent: str
) -> list[str]:
    remote = (
        f"test -d {shlex.quote(remote_root)}; "
        f"mkdir -p {shlex.quote(remote_root + '/playground/vision/models')} "
        f"{shlex.quote(remote_dataset_parent)}"
    )
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=15",
        host,
        remote,
    ]
def dataset_sync_command(bundle: Path, host: str, remote_dataset_parent: str) -> list[str]:
    return [
        "rsync",
        "-az",
        "--delete",
        f"{bundle}/",
        f"{host}:{remote_dataset_parent}/{bundle.name}/",
    ]


def load_candidate_artifact(candidate_path: Path) -> dict[str, str]:
    tree = ast.parse(candidate_path.read_text(encoding="utf-8"), filename=str(candidate_path))
    metadata: dict[str, Any] | None = None
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == "METADATA" for target in targets):
                value = node.value
                if value is not None:
                    parsed = ast.literal_eval(value)
                    if isinstance(parsed, dict):
                        metadata = parsed
    if metadata is None or not isinstance(metadata.get("artifact"), dict):
        raise ValueError("candidate METADATA must contain a literal artifact table")
    raw = metadata["artifact"]
    filename = str(raw.get("filename", ""))
    if not SAFE_ARTIFACT.fullmatch(filename):
        raise ValueError("candidate artifact filename must be a plain .hef filename")
    artifact = {"filename": filename}
    for key in ("sha256", "source_url"):
        if raw.get(key):
            artifact[key] = str(raw[key])
    if "sha256" in artifact and not re.fullmatch(r"[0-9a-fA-F]{64}", artifact["sha256"]):
        raise ValueError("candidate artifact sha256 must be 64 hexadecimal characters")
    if "source_url" in artifact and not artifact["source_url"].startswith("https://"):
        raise ValueError("candidate artifact source_url must use HTTPS")
    return artifact


def prepare_local_artifact(artifact: dict[str, str]) -> Path | None:
    path = ROOT / ".autoresearch" / "artifacts" / artifact["filename"]
    if not path.is_file() and artifact.get("source_url"):
        command = [
            str(ROOT / ".venv" / "bin" / "python"),
            str(ROOT / "scripts" / "fetch_research_artifact.py"),
            "--url",
            artifact["source_url"],
            "--name",
            artifact["filename"],
        ]
        if artifact.get("sha256"):
            command.extend(("--sha256", artifact["sha256"]))
        subprocess.run(command, cwd=ROOT, check=True)
    if not path.is_file():
        return None
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if artifact.get("sha256") and digest.lower() != artifact["sha256"].lower():
        raise ValueError(f"local artifact SHA256 mismatch for {path}")
    return path


def artifact_sync_command(
    artifact_path: Path, host: str, remote_root: str, filename: str
) -> list[str]:
    return [
        "rsync",
        "-az",
        str(artifact_path),
        f"{host}:{remote_root}/playground/vision/models/{filename}",
    ]


def remote_eval_command(
    *,
    remote_root: str,
    remote_dataset_parent: str,
    dataset_id: str,
    target_labels: list[str],
    latency_budget_ms: float,
    min_target_recall: float,
    artifact: dict[str, str],
) -> str:
    dataset_dir = f"{remote_dataset_parent}/{dataset_id}"
    manifest = f"{dataset_dir}/ground_truth.jsonl"
    labels = " ".join(f"--target-label {shlex.quote(label)}" for label in target_labels)
    remote_artifact = f"{remote_root}/playground/vision/models/{artifact['filename']}"
    verify_artifact = f"test -f {shlex.quote(remote_artifact)}; "
    if artifact.get("sha256"):
        verify_artifact += (
            f"test \"$(sha256sum {shlex.quote(remote_artifact)} | cut -d' ' -f1)\" = "
            f"{shlex.quote(artifact['sha256'].lower())}; "
        )
    # Replace the staging marker after upload; the candidate sandbox still never receives this manifest.
    return (
        "set -eu; "
        f"test -d {shlex.quote(remote_root)}; "
        f"test -x {shlex.quote(remote_root + '/.venv/bin/python')}; "
        "test -e /dev/h1x-0; "
        + verify_artifact
        + f"sed -i 's#__REMOTE_DATASET__#{dataset_dir}#g' {shlex.quote(manifest)}; "
        f"cd {shlex.quote(remote_root)}; "
        f".venv/bin/python -m playground.autoresearch.perception_evaluate "
        f"--ground-truth {shlex.quote(manifest)} {labels} "
        f"--latency-budget-ms {latency_budget_ms:.6f} "
        f"--min-target-recall {min_target_recall:.6f} --no-sandbox --json"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--host", type=_validate_host, default="rpicarbox.local")
    parser.add_argument("--remote-root", type=_validate_remote_root, default="/tmp/tiny_pi_car")
    parser.add_argument(
        "--remote-dataset-parent",
        type=_validate_remote_root,
        default="/tmp/tiny_pi_car_autoresearch_datasets",
    )
    parser.add_argument("--target-label", action="append", required=True)
    parser.add_argument("--latency-budget-ms", type=float, default=100.0)
    parser.add_argument("--min-target-recall", type=float, default=0.5)
    parser.add_argument("--timeout-s", type=int, default=900)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.latency_budget_ms <= 0:
        parser.error("--latency-budget-ms must be positive")
    if not 0.0 <= args.min_target_recall <= 1.0:
        parser.error("--min-target-recall must be in [0, 1]")

    bundle, dataset_id = stage_dataset(args.ground_truth)
    artifact = load_candidate_artifact(
        ROOT / "playground" / "experiments" / "perception" / "candidate.py"
    )
    local_artifact = prepare_local_artifact(artifact)
    remote_manifest = bundle / "ground_truth.jsonl"
    # Ensure a prior live run's marker replacement never contaminates the host cache.
    if "__REMOTE_DATASET__" not in remote_manifest.read_text(encoding="utf-8"):
        raise RuntimeError("host staging manifest lost its remote dataset marker")
    deploy = deploy_command(args.host, args.remote_root)
    ensure_dirs = ensure_remote_dirs_command(
        args.host, args.remote_root, args.remote_dataset_parent
    )
    sync = dataset_sync_command(bundle, args.host, args.remote_dataset_parent)
    remote = remote_eval_command(
        remote_root=args.remote_root,
        remote_dataset_parent=args.remote_dataset_parent,
        dataset_id=dataset_id,
        target_labels=args.target_label,
        latency_budget_ms=args.latency_budget_ms,
        min_target_recall=args.min_target_recall,
        artifact=artifact,
    )
    ssh = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=15",
        args.host,
        remote,
    ]
    if args.dry_run:
        print(
            json.dumps(
                {
                    "dataset_id": dataset_id,
                    "deploy": shlex.join(deploy),
                    "ensure_remote_dirs": shlex.join(ensure_dirs),
                    "dataset_sync": shlex.join(sync),
                    "remote_eval": shlex.join(ssh),
                    "artifact": artifact,
                    "artifact_sync": (
                        shlex.join(
                            artifact_sync_command(
                                local_artifact, args.host, args.remote_root, artifact["filename"]
                            )
                        )
                        if local_artifact
                        else "use existing remote artifact"
                    ),
                },
                indent=2,
            )
        )
        return 0

    subprocess.run(ensure_dirs, cwd=ROOT, timeout=args.timeout_s, check=True)
    subprocess.run(deploy, cwd=ROOT, timeout=args.timeout_s, check=True)
    if local_artifact:
        subprocess.run(
            artifact_sync_command(local_artifact, args.host, args.remote_root, artifact["filename"]),
            cwd=ROOT,
            timeout=args.timeout_s,
            check=True,
        )
    subprocess.run(sync, cwd=ROOT, timeout=args.timeout_s, check=True)
    completed = subprocess.run(
        ssh,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=args.timeout_s,
        check=False,
    )
    print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
