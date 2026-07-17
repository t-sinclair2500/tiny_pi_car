#!/usr/bin/env python3
"""Fixed scalar eval for perception-latency night campaign (no chassis motion).

Metric (maximize):
  score = 100 * clamp((budget_ms - latency_p50_ms) / (budget_ms - floor_ms), 0, 1)

Default budget 500 ms, floor 50 ms → ~130 ms e2e scores ~84; regressions toward
3.5 s score ~0. Detection count is NOT in the score (ambient scenes would game
false positives). Hard gates require a healthy camera+Hailo pipeline instead.

Runs a bounded ``log_detections`` on the Pi over SSH and parses the summary.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMARY_RE = re.compile(r"^(?P<key>[a-z0-9_]+):\s*(?P<value>.+)$", re.MULTILINE)


def score_latency(
    *,
    latency_p50_ms: float,
    budget_ms: float = 500.0,
    floor_ms: float = 50.0,
) -> float:
    if budget_ms <= floor_ms:
        raise ValueError("budget_ms must be greater than floor_ms")
    if latency_p50_ms <= floor_ms:
        return 100.0
    if latency_p50_ms >= budget_ms:
        return 0.0
    return round(100.0 * (budget_ms - latency_p50_ms) / (budget_ms - floor_ms), 6)


def parse_summary(text: str) -> dict[str, float | int | str]:
    raw: dict[str, str] = {}
    for match in SUMMARY_RE.finditer(text):
        raw[match.group("key")] = match.group("value").strip()
    required = (
        "frame_count",
        "valid_frame_count",
        "detection_count",
        "inference_p50_ms",
        "latency_p50_ms",
    )
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"missing summary keys: {missing}; output was:\n{text[-2000:]}")
    return {
        "frame_count": int(float(raw["frame_count"])),
        "valid_frame_count": int(float(raw["valid_frame_count"])),
        "detection_count": int(float(raw["detection_count"])),
        "inference_p50_ms": float(raw["inference_p50_ms"]),
        "inference_p90_ms": float(raw.get("inference_p90_ms", raw["inference_p50_ms"])),
        "latency_p50_ms": float(raw["latency_p50_ms"]),
        "latency_p90_ms": float(raw.get("latency_p90_ms", raw["latency_p50_ms"])),
        "output_path": raw.get("output_path", ""),
    }


def hard_gates(
    summary: dict[str, float | int | str],
    *,
    max_inference_ms: float,
    max_latency_ms: float,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    frames = int(summary["frame_count"])
    valid = int(summary["valid_frame_count"])
    if valid != frames:
        reasons.append(f"valid_frames {valid}/{frames}")
    if float(summary["inference_p50_ms"]) > max_inference_ms:
        reasons.append(f"inference_p50 {summary['inference_p50_ms']} > {max_inference_ms}")
    if float(summary["latency_p50_ms"]) > max_latency_ms:
        reasons.append(f"latency_p50 {summary['latency_p50_ms']} > {max_latency_ms}")
    return (not reasons), reasons


def build_remote_command(*, remote_root: str, frames: int) -> str:
    root = shlex.quote(remote_root)
    out = "/tmp/tiny_pi_car/night-eval.jsonl"
    return (
        "set -eu; "
        f"cd {root}; "
        "sudo -n systemctl stop masterpi >/dev/null 2>&1 || true; "
        f".venv/bin/python -m playground.vision.log_detections "
        f"--frames {frames} --warmup-frames 5 --allow-zero-detections "
        f"--output {shlex.quote(out)}"
    )


def run_pi_eval(
    *,
    host: str,
    remote_root: str,
    frames: int,
    timeout_s: int,
) -> str:
    command = build_remote_command(remote_root=remote_root, frames=frames)
    completed = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={min(15, timeout_s)}",
            host,
            command,
        ],
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    text = (completed.stdout or "") + "\n" + (completed.stderr or "")
    if completed.returncode != 0 and "latency_p50_ms:" not in text:
        raise RuntimeError(
            f"remote eval failed (exit {completed.returncode}):\n{text[-3000:]}"
        )
    return text


def evaluate_payload(
    summary: dict[str, float | int | str],
    *,
    budget_ms: float,
    floor_ms: float,
    max_inference_ms: float,
    max_latency_ms: float,
) -> dict:
    ok, reasons = hard_gates(
        summary,
        max_inference_ms=max_inference_ms,
        max_latency_ms=max_latency_ms,
    )
    score = score_latency(
        latency_p50_ms=float(summary["latency_p50_ms"]),
        budget_ms=budget_ms,
        floor_ms=floor_ms,
    )
    if not ok:
        score = min(score, 0.0) - 10.0 * len(reasons)
    return {
        "score": round(score, 6),
        "hard_gates_passed": ok,
        "gate_failures": reasons,
        "latency_p50_ms": summary["latency_p50_ms"],
        "latency_p90_ms": summary["latency_p90_ms"],
        "inference_p50_ms": summary["inference_p50_ms"],
        "detection_count": summary["detection_count"],
        "frame_count": summary["frame_count"],
        "valid_frame_count": summary["valid_frame_count"],
        "budget_ms": budget_ms,
        "floor_ms": floor_ms,
        "metric": "latency_p50_to_score",
        "note": "maximize score; lower e2e latency_p50 raises score; dets not scored",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="rpicarbox.local")
    parser.add_argument("--remote-root", default="/home/tyler/Desktop/tiny_pi_car")
    parser.add_argument("--frames", type=int, default=15)
    parser.add_argument("--budget-ms", type=float, default=500.0)
    parser.add_argument("--floor-ms", type=float, default=50.0)
    parser.add_argument("--max-inference-ms", type=float, default=150.0)
    parser.add_argument("--max-latency-ms", type=float, default=2000.0)
    parser.add_argument("--timeout-s", type=int, default=180)
    parser.add_argument(
        "--summary-file",
        type=Path,
        help="offline: parse a saved log_detections summary text instead of SSH",
    )
    parser.add_argument("--json", action="store_true", help="emit one JSON object")
    args = parser.parse_args()

    if args.summary_file:
        text = args.summary_file.read_text(encoding="utf-8")
    else:
        text = run_pi_eval(
            host=args.host,
            remote_root=args.remote_root,
            frames=args.frames,
            timeout_s=args.timeout_s,
        )
    summary = parse_summary(text)
    payload = evaluate_payload(
        summary,
        budget_ms=args.budget_ms,
        floor_ms=args.floor_ms,
        max_inference_ms=args.max_inference_ms,
        max_latency_ms=args.max_latency_ms,
    )
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0 if payload["hard_gates_passed"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — campaign runner needs a JSON failure shape
        print(
            json.dumps(
                {"score": -100.0, "hard_gates_passed": False, "error": str(exc)},
                sort_keys=True,
            )
        )
        raise SystemExit(2) from None
