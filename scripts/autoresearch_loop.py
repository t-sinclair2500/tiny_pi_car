#!/usr/bin/env python3
"""Bounded OpenCode autoresearch loop with mechanical keep/discard decisions."""

from __future__ import annotations

import argparse
import csv
import fnmatch
import hashlib
import json
import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAMPAIGN = ROOT / "autoresearch" / "car" / "campaigns" / "policy.toml"


@dataclass(frozen=True)
class Campaign:
    name: str
    objective: str
    program: Path
    editable_paths: tuple[str, ...]
    eval_command: tuple[str, ...]
    metric_key: str
    hard_gate_key: str
    maximize: bool
    min_delta: float
    eval_timeout_s: int


def load_campaign(path: Path) -> Campaign:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))["campaign"]
    program = (ROOT / str(raw["program"])).resolve()
    campaign = Campaign(
        name=str(raw["name"]),
        objective=str(raw["objective"]),
        program=program,
        editable_paths=tuple(str(item) for item in raw["editable_paths"]),
        eval_command=tuple(str(item) for item in raw["eval_command"]),
        metric_key=str(raw.get("metric_key", "score")),
        hard_gate_key=str(raw.get("hard_gate_key", "hard_gates_passed")),
        maximize=bool(raw.get("maximize", True)),
        min_delta=float(raw.get("min_delta", 1e-6)),
        eval_timeout_s=int(raw.get("eval_timeout_s", 120)),
    )
    if not campaign.program.is_file():
        raise ValueError(f"campaign program does not exist: {campaign.program}")
    if not campaign.editable_paths or not campaign.eval_command:
        raise ValueError("campaign needs editable_paths and eval_command")
    return campaign


def _last_json_object(output: str) -> dict[str, Any]:
    for line in reversed(output.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("evaluator did not emit a JSON object")


def materialize_command(command: tuple[str, ...], *, root: Path) -> tuple[str, ...]:
    resolved: list[str] = []
    for token in command:
        if token == "{python}":
            resolved.append(sys.executable)
        elif token == "{root}":
            resolved.append(str(root))
        elif token.startswith("{env:") and token.endswith("}"):
            name = token[5:-1]
            value = os.environ.get(name)
            if not value:
                raise ValueError(f"campaign requires environment variable {name}")
            resolved.append(value)
        else:
            resolved.append(token)
    return tuple(resolved)


def evaluate(campaign: Campaign, *, root: Path = ROOT) -> tuple[float, bool, dict[str, Any], str]:
    completed = subprocess.run(
        materialize_command(campaign.eval_command, root=root),
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=campaign.eval_timeout_s,
        check=False,
    )
    payload = _last_json_object(completed.stdout)
    metric = float(payload[campaign.metric_key])
    hard_gate = bool(payload[campaign.hard_gate_key])
    return metric, hard_gate, payload, completed.stdout


def extract_opencode_text(output: str) -> str:
    chunks: list[str] = []
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "text":
            text = event.get("part", {}).get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "\n".join(chunks).strip()


def invoke_opencode(
    *,
    agent: str,
    model: str,
    prompt: str,
    title: str,
    timeout_s: int,
    attach: str | None,
) -> tuple[int, str, str]:
    command = [
        "opencode",
        "run",
        "--agent",
        agent,
        "--model",
        model,
        "--format",
        "json",
        "--title",
        title,
    ]
    if attach:
        command.extend(("--attach", attach, "--dir", str(ROOT)))
    command.append(prompt)
    env = dict(os.environ)
    env["OPENCODE_DISABLE_AUTOUPDATE"] = "true"
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_s,
            check=False,
        )
        output = completed.stdout
        return completed.returncode, extract_opencode_text(output), output
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        return 124, extract_opencode_text(output), output + "\nTIMEOUT\n"


def _git_lines(*args: str) -> list[str]:
    output = subprocess.check_output(("git", *args), cwd=ROOT, text=True)
    return [line for line in output.splitlines() if line]


def changed_paths() -> set[str]:
    tracked = set(_git_lines("diff", "--name-only"))
    untracked = set(_git_lines("ls-files", "--others", "--exclude-standard"))
    return tracked | untracked


def path_allowed(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _snapshots(paths: tuple[str, ...]) -> dict[str, bytes | None]:
    snapshots: dict[str, bytes | None] = {}
    for pattern in paths:
        if any(char in pattern for char in "*?["):
            for match in ROOT.glob(pattern):
                if match.is_file():
                    snapshots[str(match.relative_to(ROOT))] = match.read_bytes()
        else:
            item = ROOT / pattern
            snapshots[pattern] = item.read_bytes() if item.is_file() else None
    return snapshots


def restore(snapshots: dict[str, bytes | None], patterns: tuple[str, ...]) -> None:
    current = {path for path in changed_paths() if path_allowed(path, patterns)}
    for path in current | set(snapshots):
        target = ROOT / path
        content = snapshots.get(path)
        if content is None:
            if target.is_file():
                target.unlink()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)


def _digest(paths: set[str]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.encode())
        target = ROOT / path
        if target.is_file():
            digest.update(target.read_bytes())
    return digest.hexdigest()[:12]


def better(candidate: float, baseline: float, campaign: Campaign) -> bool:
    if campaign.maximize:
        return candidate >= baseline + campaign.min_delta
    return candidate <= baseline - campaign.min_delta


def _append_result(path: Path, row: dict[str, Any]) -> None:
    fieldnames = [
        "trial",
        "timestamp",
        "status",
        "baseline",
        "metric",
        "hard_gate",
        "candidate",
        "hypothesis",
        "review",
    ]
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        if not exists:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in fieldnames})


def _tail_results(path: Path, count: int = 12) -> str:
    if not path.exists():
        return "No previous trials."
    return "\n".join(path.read_text(encoding="utf-8").splitlines()[-count:])


def _commit(campaign: Campaign, trial: int, metric: float) -> None:
    branch = subprocess.check_output(
        ("git", "branch", "--show-current"), cwd=ROOT, text=True
    ).strip()
    if not branch.startswith("autoresearch/"):
        raise RuntimeError("--commit requires an autoresearch/* branch")
    paths = sorted(path for path in changed_paths() if path_allowed(path, campaign.editable_paths))
    if not paths:
        return
    subprocess.run(("git", "add", "--", *paths), cwd=ROOT, check=True)
    subprocess.run(
        (
            "git",
            "commit",
            "-m",
            f"autoresearch({campaign.name}): trial {trial} score {metric:.6f}",
        ),
        cwd=ROOT,
        check=True,
    )


def _write_log(run_dir: Path, name: str, content: str) -> None:
    (run_dir / name).write_text(content, encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    campaign = load_campaign(args.campaign.resolve())
    program = campaign.program.read_text(encoding="utf-8")
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = ROOT / ".autoresearch" / "runs" / f"{campaign.name}-{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    results_path = run_dir / "results.tsv"
    _write_log(run_dir, "campaign.json", json.dumps(campaign.__dict__, default=str, indent=2))

    baseline, hard_gate, payload, raw_eval = evaluate(campaign)
    _write_log(run_dir, "baseline.log", raw_eval)
    print(json.dumps({"run_dir": str(run_dir), "baseline": payload}, sort_keys=True))
    if not hard_gate:
        print(
            "warning: baseline failed hard gate; continuing anyway "
            "(fix candidate or use --baseline-only to inspect)",
            file=sys.stderr,
        )
    if args.baseline_only:
        return 0

    dirty = changed_paths()
    if dirty:
        print(f"Note: dirty tree at start: {sorted(dirty)}", file=sys.stderr)

    best = baseline
    last_hypothesis = "Establish a small, testable improvement from the current baseline."
    consecutive_discards = 0

    for trial in range(1, args.iterations + 1):
        if consecutive_discards >= args.plateau_limit:
            print(f"Plateau stop after {consecutive_discards} consecutive discards.")
            break

        snapshots = _snapshots(campaign.editable_paths)
        history = _tail_results(results_path)

        if args.council and (trial == 1 or (trial - 1) % args.director_every == 0):
            director_prompt = f"""You MANAGE car-autonomy research as the LEAD (35B).
Plan and decide; do NOT do every bash/grep/snap yourself.
MUST call 1–2 subagents (helper=2B quick checks; worker/pi-observer=9B medium work).
Max 1–2 concurrent. 27B is unused — never route to it.
Campaign objective: {campaign.objective}
Preferred edit surfaces: {', '.join(campaign.editable_paths)}
Current best metric: {best:.6f} ({'maximize' if campaign.maximize else 'minimize'})

Propose ONE concrete next experiment. You may revise campaign/program files when useful.
On motion-hour prefer vision-nav (snap/perceive → short safe move → stop → resnap).
Prefer live camera, Hailo model-zoo A/B, and real motion when they help.
End with `HYPOTHESIS:` and a short worker directive for the 9B worker.

Program:
{program}

Recent trials:
{history}
"""
            code, text, raw = invoke_opencode(
                agent="autoresearch-director",
                model=args.director_model,
                prompt=director_prompt,
                title=f"{campaign.name}-director-{trial}",
                timeout_s=args.agent_timeout,
                attach=args.attach,
            )
            _write_log(run_dir, f"trial-{trial:03d}-director.jsonl", raw)
            if code == 0 and text:
                last_hypothesis = text[-4000:]

        worker_prompt = f"""Run one autonomy experiment for campaign `{campaign.name}`.
Objective: {campaign.objective}
Current best metric: {best:.6f} ({'higher is better' if campaign.maximize else 'lower is better'}).
Preferred edit surfaces: {', '.join(campaign.editable_paths)}
You may use camera frames (and look at them), Hailo HEF A/B, SSH/motion, and revise
campaign directives if needed. Always stop motors when a trial ends.
Implement the hypothesis, measure honestly, then stop.

Hypothesis from the research director:
{last_hypothesis}

Standing program:
{program}
"""
        code, worker_text, raw = invoke_opencode(
            agent="autoresearch-worker",
            model=args.worker_model,
            prompt=worker_prompt,
            title=f"{campaign.name}-worker-{trial}",
            timeout_s=args.agent_timeout,
            attach=args.attach,
        )
        _write_log(run_dir, f"trial-{trial:03d}-worker.jsonl", raw)

        after = changed_paths()
        unexpected = sorted(path for path in after if not path_allowed(path, campaign.editable_paths))
        status = "discard"
        review = "not_run"
        metric = best
        gate = False

        try:
            if code != 0:
                status = "agent_error"
            elif unexpected:
                status = "scope_violation"
            elif not after:
                status = "no_change"
            else:
                metric, gate, eval_payload, eval_output = evaluate(campaign)
                _write_log(run_dir, f"trial-{trial:03d}-eval.log", eval_output)
                if gate and better(metric, best, campaign):
                    if args.council:
                        diff = subprocess.check_output(
                            ("git", "diff", "--", *campaign.editable_paths),
                            cwd=ROOT,
                            text=True,
                        )[-12000:]
                        reviewer_prompt = f"""Independently review this measured autonomy experiment.
The fixed evaluator improved from {best:.6f} to {metric:.6f} and hard gates passed.
Look for I/O, network access, nondeterminism, evaluator gaming, hidden unsafe motion,
or needless complexity. Do not edit. End with exactly `VERDICT: PASS` or `VERDICT: FAIL`.

Diff:
{diff}
"""
                        review_code, review_text, review_raw = invoke_opencode(
                            agent="autoresearch-reviewer",
                            model=args.reviewer_model,
                            prompt=reviewer_prompt,
                            title=f"{campaign.name}-review-{trial}",
                            timeout_s=args.agent_timeout,
                            attach=args.attach,
                        )
                        _write_log(run_dir, f"trial-{trial:03d}-review.jsonl", review_raw)
                        review = review_text[-2000:]
                        if review_code != 0 or "VERDICT: PASS" not in review:
                            status = "review_reject"
                        else:
                            status = "keep"
                    else:
                        status = "keep"
                else:
                    status = "hard_gate_fail" if not gate else "no_improvement"
        except (KeyError, ValueError, subprocess.SubprocessError) as exc:
            status = "eval_error"
            review = repr(exc)

        candidate_hash = _digest(after) if after else ""
        _append_result(
            results_path,
            {
                "trial": trial,
                "timestamp": datetime.now(UTC).isoformat(),
                "status": status,
                "baseline": f"{best:.6f}",
                "metric": f"{metric:.6f}",
                "hard_gate": gate,
                "candidate": candidate_hash,
                "hypothesis": last_hypothesis.replace("\t", " ").replace("\n", " ")[-1000:],
                "review": review.replace("\t", " ").replace("\n", " ")[-1000:],
            },
        )

        if status == "keep":
            best = metric
            consecutive_discards = 0
            if args.commit:
                _commit(campaign, trial, metric)
        else:
            restore(snapshots, campaign.editable_paths)
            consecutive_discards += 1

        print(json.dumps({"trial": trial, "status": status, "metric": metric, "best": best}))

    print(json.dumps({"best": best, "results": str(results_path)}, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=DEFAULT_CAMPAIGN)
    parser.add_argument("--iterations", type=int, default=8)
    parser.add_argument("--plateau-limit", type=int, default=5)
    parser.add_argument("--agent-timeout", type=int, default=900)
    # 35B manages; 9B worker/reviewer execute; 2B helper; 27B unused.
    parser.add_argument("--worker-model", default="lm-studio/qwen3.5-9b-mtp")
    parser.add_argument("--director-model", default="lm-studio/qwen3.6-35b-a3b-mtp")
    parser.add_argument("--reviewer-model", default="lm-studio/qwen3.5-9b-mtp")
    parser.add_argument("--helper-model", default="lm-studio/qwen3.5-2b")
    parser.add_argument("--director-every", type=int, default=4)
    parser.add_argument(
        "--council",
        action="store_true",
        help="enable director (35B manager) + occasional 9B review on keeps",
    )
    parser.add_argument("--commit", action="store_true", help="commit keeps on autoresearch/* branch")
    parser.add_argument("--attach", help="reuse an `opencode serve` URL")
    parser.add_argument("--baseline-only", action="store_true")
    return parser


def main() -> int:
    return run(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
