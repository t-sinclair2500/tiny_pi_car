"""Score a detector candidate (optional bubblewrap sandbox), then score it."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .perception_score import _read_jsonl, score_records

WORKSPACE = Path(__file__).resolve().parents[2]


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def build_sandbox_command(
    *,
    workspace: Path,
    python_prefix: Path,
    images: list[tuple[Path, str]],
    image_manifest: Path,
    output_dir: Path,
    candidate_module: str,
) -> list[str]:
    command = [
        "bwrap",
        "--die-with-parent",
        "--new-session",
        "--unshare-net",
        "--ro-bind",
        "/usr",
        "/usr",
        "--ro-bind",
        "/lib",
        "/lib",
    ]
    if Path("/lib64").exists():
        command.extend(("--ro-bind", "/lib64", "/lib64"))
    if Path("/etc/ld.so.cache").exists():
        command.extend(("--dir", "/etc", "--ro-bind", "/etc/ld.so.cache", "/etc/ld.so.cache"))
    command.extend(
        (
            "--ro-bind",
            str(python_prefix),
            "/venv",
            "--ro-bind",
            str(workspace),
            "/workspace",
            "--dir",
            "/input",
            "--ro-bind",
            str(image_manifest),
            "/input/images.jsonl",
            "--bind",
            str(output_dir),
            "/out",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
            "--dir",
            "/data",
            "--chdir",
            "/workspace",
            "--setenv",
            "PYTHONPATH",
            "/workspace",
            "--setenv",
            "HOME",
            "/tmp",
        )
    )
    if Path("/sys").is_dir():
        command.extend(("--ro-bind", "/sys", "/sys"))
    for device in (Path("/dev/h1x-0"), Path("/dev/hailo0")):
        if device.exists():
            command.extend(("--dev-bind", str(device), str(device)))
    for source, sandbox_path in images:
        command.extend(("--ro-bind", str(source), sandbox_path))
    command.extend(
        (
            "/venv/bin/python",
            "-m",
            "playground.autoresearch.perception_candidate_run",
            "--images",
            "/input/images.jsonl",
            "--predictions",
            "/out/predictions.jsonl",
            "--metadata",
            "/out/metadata.json",
            "--candidate-module",
            candidate_module,
        )
    )
    return command


def _image_only_manifest(
    ground_truth: list[dict[str, Any]], manifest_path: Path
) -> list[tuple[Path, str]]:
    bindings: list[tuple[Path, str]] = []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, row in enumerate(ground_truth):
        source = Path(str(row.get("image_path", ""))).expanduser().resolve()
        if not source.is_file():
            raise ValueError(f"missing held-out image: {source}")
        frame_id = str(row["frame_id"])
        if frame_id in seen:
            raise ValueError(f"duplicate ground-truth frame_id: {frame_id}")
        seen.add(frame_id)
        suffix = source.suffix.lower() if source.suffix else ".img"
        sandbox_path = f"/data/{index:06d}{suffix}"
        bindings.append((source, sandbox_path))
        rows.append({"frame_id": frame_id, "image_path": sandbox_path})
    manifest_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return bindings


def _run_unsandboxed(
    *,
    ground_truth: list[dict[str, Any]],
    candidate_module: str,
    output_dir: Path,
) -> tuple[Path, Path, str]:
    images_manifest = output_dir / "images.jsonl"
    prediction_path = output_dir / "predictions.jsonl"
    metadata_path = output_dir / "metadata.json"
    rows = [
        {
            "frame_id": str(row["frame_id"]),
            "image_path": str(Path(str(row["image_path"])).expanduser().resolve()),
        }
        for row in ground_truth
    ]
    images_manifest.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    command = [
        sys.executable,
        "-m",
        "playground.autoresearch.perception_candidate_run",
        "--images",
        str(images_manifest),
        "--predictions",
        str(prediction_path),
        "--candidate-module",
        candidate_module,
        "--metadata",
        str(metadata_path),
    ]
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(WORKSPACE),
        timeout=max(60, len(rows) * 30),
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"candidate failed with exit {completed.returncode}:\n" + completed.stdout[-4000:]
        )
    return prediction_path, metadata_path, completed.stdout


def evaluate_candidate(
    *,
    ground_truth_path: Path,
    target_labels: frozenset[str],
    iou_threshold: float,
    latency_budget_ms: float,
    min_target_recall: float,
    candidate_module: str,
    keep_predictions: Path | None,
    sandbox: bool | None = None,
) -> tuple[dict[str, Any], str]:
    """Score a candidate. Uses bwrap when available unless ``sandbox=False``."""
    ground_truth_path = ground_truth_path.expanduser().resolve()
    ground_truth = _read_jsonl(ground_truth_path)
    use_sandbox = sandbox if sandbox is not None else shutil.which("bwrap") is not None

    with tempfile.TemporaryDirectory(prefix="tiny-pi-perception-") as temporary:
        temp = Path(temporary)
        output_dir = temp / "output"
        output_dir.mkdir()

        if use_sandbox:
            if shutil.which("bwrap") is None:
                raise RuntimeError("sandbox requested but bubblewrap (bwrap) is not installed")
            input_dir = temp / "input"
            input_dir.mkdir()
            manifest = input_dir / "images.jsonl"
            images = _image_only_manifest(ground_truth, manifest)
            command = build_sandbox_command(
                workspace=WORKSPACE,
                python_prefix=Path(sys.prefix).resolve(),
                images=images,
                image_manifest=manifest,
                output_dir=output_dir,
                candidate_module=candidate_module,
            )
            completed = subprocess.run(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=max(60, len(images) * 30),
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    f"sandboxed candidate failed with exit {completed.returncode}:\n"
                    + completed.stdout[-4000:]
                )
            prediction_path = output_dir / "predictions.jsonl"
            metadata_path = output_dir / "metadata.json"
            candidate_output = completed.stdout
            sandboxed = True
        else:
            prediction_path, metadata_path, candidate_output = _run_unsandboxed(
                ground_truth=ground_truth,
                candidate_module=candidate_module,
                output_dir=output_dir,
            )
            sandboxed = False

        predictions = _read_jsonl(prediction_path)
        result = score_records(
            ground_truth,
            predictions,
            target_labels=target_labels,
            iou_threshold=iou_threshold,
            latency_budget_ms=latency_budget_ms,
            min_target_recall=min_target_recall,
        )
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if keep_predictions:
            keep_predictions.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(prediction_path, keep_predictions)
        payload = {**asdict(result), "sandboxed": sandboxed, "candidate": metadata}
        return payload, candidate_output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--target-label", action="append", required=True)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--latency-budget-ms", type=float, default=150.0)
    parser.add_argument("--min-target-recall", type=float, default=0.3)
    parser.add_argument(
        "--candidate-module",
        default="playground.experiments.perception.candidate",
    )
    parser.add_argument("--keep-predictions", type=Path)
    parser.add_argument("--sandbox", action="store_true", help="force bubblewrap sandbox")
    parser.add_argument("--no-sandbox", action="store_true", help="run without bwrap")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.sandbox and args.no_sandbox:
        parser.error("use only one of --sandbox / --no-sandbox")
    sandbox: bool | None = True if args.sandbox else False if args.no_sandbox else None
    try:
        payload, candidate_output = evaluate_candidate(
            ground_truth_path=args.ground_truth,
            target_labels=frozenset(args.target_label),
            iou_threshold=args.iou,
            latency_budget_ms=args.latency_budget_ms,
            min_target_recall=args.min_target_recall,
            candidate_module=args.candidate_module,
            keep_predictions=args.keep_predictions,
            sandbox=sandbox,
        )
        if not args.json and candidate_output:
            print(candidate_output, end="" if candidate_output.endswith("\n") else "\n")
    except Exception as exc:  # noqa: BLE001 - evaluator must emit a parseable failed gate
        payload = {
            "score": -1_000_000.0,
            "hard_gates_passed": False,
            "sandboxed": True,
            "error": str(exc),
        }
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload.get("hard_gates_passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
