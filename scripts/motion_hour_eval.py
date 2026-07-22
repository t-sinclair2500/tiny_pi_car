#!/usr/bin/env python3
"""Fixed scalar eval for the motion-hour campaign (wheels ALLOWED, short trials only).

Runs ONE short, sonar-gated chassis trial on the Pi (default: forward,
the Phase-A translate action) via SSH, straight to
``playground.autoresearch.physical_trial`` — every trial ends with an explicit
motor stop. This script requires ``--allow-wheels`` itself (mirrors
``scripts/pi_agent_gate.py`` / ``physical_trial.py``); see
``autoresearch/car/MOTION_HOUR_CARD.md``.

Metric (maximize) rewards a clean, responsive, fully-stopped trial — NOT more
distance, more speed, or longer motion. With ``--with-vision`` (motion-hour
default), a short post-stop camera+Hailo step multiplies the score so the loop
can optimize vision-nav, not only SSH ceremony:

    completion_ratio      = executed_steps / expected_steps            (0..1)
    dispatch_overhead_ms  = wall_clock_round_trip_ms - requested_duration_ms
    overhead_factor       = clamp((budget_ms - dispatch_overhead_ms)
                                   / (budget_ms - floor_ms), 0, 1)
    vision_factor         = 1.0 if vision ok / unused, else 0.5
    score = 100 * completion_ratio * overhead_factor * vision_factor

Hard gates (ALL required; vision failure does not waive them): trial reported
``final_stop_sent`` true, ``executed_steps >= 1``, and ``stop_reason`` was not
``aborted_before_final_stop``.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHASSIS_ACTIONS = ("forward", "reverse", "yaw_left", "yaw_right")
NIGHT_CARD = "autoresearch/car/NIGHT_CARD.md"
MOTION_HOUR_CARD = "autoresearch/car/MOTION_HOUR_CARD.md"
UNSAFE_STOP_REASONS = frozenset({"aborted_before_final_stop"})
CONTROL_PERIOD_S = 0.05  # must match playground/autoresearch/physical_trial.py
SSH_CONTROL_DIR = Path("/tmp/tiny_pi_car-ssh")


def ssh_argv(host: str, *, timeout_s: int, command: str) -> list[str]:
    SSH_CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    control_path = SSH_CONTROL_DIR / "control-%r@%h:%p"
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={min(15, timeout_s)}",
        "-o",
        "ControlMaster=auto",
        "-o",
        f"ControlPath={control_path}",
        "-o",
        "ControlPersist=120",
        host,
        command,
    ]


def prewarm_ssh(host: str, *, timeout_s: int) -> None:
    subprocess.run(
        ssh_argv(host, timeout_s=timeout_s, command="true"),
        capture_output=True,
        timeout=timeout_s,
        check=False,
    )


def _stop_masterpi_if_active() -> str:
    return (
        "if systemctl is-active --quiet masterpi 2>/dev/null; then "
        "sudo -n systemctl stop masterpi >/dev/null 2>&1 || true; fi; "
    )


def build_remote_command(
    *,
    remote_root: str,
    action: str,
    duration_s: float,
    speed_mm_s: float,
    yaw: float,
    no_sonar: bool,
) -> str:
    root = shlex.quote(remote_root)
    sonar = "--no-sonar " if no_sonar else ""
    watchdog_s = max(10, int(duration_s) + 8)
    return (
        "set -eu; "
        f"cd {root}; "
        f"{_stop_masterpi_if_active()}"
        f"timeout --signal=TERM --kill-after=2s {watchdog_s}s "
        ".venv/bin/python -m playground.autoresearch.physical_trial "
        f"{shlex.quote(action)} --duration-s {duration_s:.3f} "
        f"--speed-mm-s {speed_mm_s:.3f} --yaw {yaw:.3f} "
        f"{sonar}--allow-wheels"
    )


def build_vision_guided_command(
    *,
    remote_root: str,
    action: str,
    duration_s: float,
    speed_mm_s: float,
    yaw: float,
    no_sonar: bool,
    warmup_frames: int,
    sequential_init: bool,
    deadband: float,
) -> str:
    root = shlex.quote(remote_root)
    sonar = "--no-sonar " if no_sonar else ""
    seq = " --sequential-init" if sequential_init else ""
    # Pre vision only (post skipped when pre scores); watchdog still generous.
    watchdog_s = max(35, int(duration_s) + 30)
    return (
        "set -eu; "
        f"cd {root}; "
        f"{_stop_masterpi_if_active()}"
        f"timeout --signal=TERM --kill-after=2s {watchdog_s}s "
        ".venv/bin/python -m playground.autoresearch.vision_guided_trial "
        f"--duration-s {duration_s:.3f} --speed-mm-s {speed_mm_s:.3f} "
        f"--default-action {shlex.quote(action)} --default-yaw {yaw:.3f} "
        f"--deadband {deadband:.4f} "
        f"--warmup-frames {warmup_frames}{seq} "
        f"{sonar}--allow-wheels"
    )


def build_vision_suffix(
    *, stamp: int, warmup_frames: int = 3, sequential_init: bool = False
) -> tuple[str, str, str]:
    snap = f"/tmp/tiny_pi_car/motion-hour-vision-{stamp}.jpg"
    dets = f"/tmp/tiny_pi_car/motion-hour-vision-{stamp}.jsonl"
    seq = " --sequential-init" if sequential_init else ""
    command = (
        "mkdir -p /tmp/tiny_pi_car; "
        f".venv/bin/python -m playground.vision.snap_and_detect "
        f"--snap-output {shlex.quote(snap)} "
        f"--dets-output {shlex.quote(dets)} "
        f"--warmup-frames {warmup_frames}{seq} --allow-zero-detections"
    )
    return command, snap, dets


def _parse_vision_decision(text: str) -> dict | None:
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("vision_decision"):
            return value
    return None


def _parse_vision_from_text(text: str) -> dict:
    ok = "vision_snap:" in text and "vision_dets:" in text
    snap = dets = None
    for line in text.splitlines():
        if line.startswith("vision_snap:"):
            snap = line.split(":", 1)[1]
        elif line.startswith("vision_dets:"):
            dets = line.split(":", 1)[1]
    return {
        "vision_ok": ok,
        "vision_snap": snap if ok else None,
        "vision_dets": dets if ok else None,
        "vision_tail": text[-1500:],
    }


def run_pi_trial(
    *,
    host: str,
    remote_root: str,
    action: str,
    duration_s: float,
    speed_mm_s: float,
    yaw: float,
    no_sonar: bool,
    timeout_s: int,
    with_vision: bool = False,
    vision_guided: bool = False,
    warmup_frames: int = 3,
    sequential_init: bool = False,
    deadband: float = 0.05,
) -> tuple[str, float, dict | None, dict | None]:
    stamp = int(time.time())
    vision: dict | None = None
    decision: dict | None = None
    if vision_guided:
        if not with_vision:
            raise ValueError("--vision-guided requires --with-vision")
        command = build_vision_guided_command(
            remote_root=remote_root,
            action=action,
            duration_s=duration_s,
            speed_mm_s=speed_mm_s,
            yaw=yaw,
            no_sonar=no_sonar,
            warmup_frames=warmup_frames,
            sequential_init=sequential_init,
            deadband=deadband,
        )
    else:
        trial_command = build_remote_command(
            remote_root=remote_root,
            action=action,
            duration_s=duration_s,
            speed_mm_s=speed_mm_s,
            yaw=yaw,
            no_sonar=no_sonar,
        )
        if with_vision:
            vision_command, _, _ = build_vision_suffix(
                stamp=stamp,
                warmup_frames=warmup_frames,
                sequential_init=sequential_init,
            )
            command = f"{trial_command}; {vision_command}"
        else:
            command = trial_command
    argv = ssh_argv(host, timeout_s=timeout_s, command=command)
    started = time.monotonic()
    trial_round_trip_s: float | None = None
    proc = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    output_lines: list[str] = []
    try:
        assert proc.stdout is not None
        for raw in proc.stdout:
            output_lines.append(raw)
            line = raw.strip()
            if trial_round_trip_s is not None or not line.startswith("{"):
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and "final_stop_sent" in value:
                trial_round_trip_s = time.monotonic() - started
    finally:
        try:
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
            raise
    text = "".join(output_lines)
    round_trip_s = trial_round_trip_s if trial_round_trip_s is not None else time.monotonic() - started
    if with_vision:
        vision = _parse_vision_from_text(text)
        vision["vision_returncode"] = proc.returncode
        if proc.returncode != 0 and not vision["vision_ok"]:
            vision["vision_ok"] = False
    if vision_guided:
        decision = _parse_vision_decision(text)
    if proc.returncode != 0 and '"final_stop_sent"' not in text:
        raise RuntimeError(f"remote trial failed (exit {proc.returncode}):\n{text[-3000:]}")
    return text, round_trip_s, vision, decision


def parse_trial_result(text: str) -> dict:
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "final_stop_sent" in value:
            return value
    raise ValueError(f"no TrialResult JSON found in output:\n{text[-2000:]}")


def hard_gates(result: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not result.get("final_stop_sent"):
        reasons.append("final_stop_sent is false (motors may not have stopped)")
    executed_steps = int(result.get("executed_steps", 0))
    if executed_steps < 1:
        reasons.append("executed_steps < 1 (trial never actually moved)")
    stop_reason = str(result.get("stop_reason", ""))
    if stop_reason in UNSAFE_STOP_REASONS:
        reasons.append(f"unsafe stop_reason: {stop_reason}")
    return (not reasons), reasons


def evaluate_payload(
    result: dict,
    *,
    round_trip_s: float,
    budget_ms: float,
    floor_ms: float,
    vision: dict | None = None,
    decision: dict | None = None,
) -> dict:
    if budget_ms <= floor_ms:
        raise ValueError("budget_ms must be greater than floor_ms")
    ok, reasons = hard_gates(result)
    requested_duration_s = float(result.get("requested_duration_s", 0.0))
    expected_steps = max(1, round(requested_duration_s / CONTROL_PERIOD_S))
    executed_steps = int(result.get("executed_steps", 0))
    completion_ratio = max(0.0, min(1.0, executed_steps / expected_steps))

    dispatch_overhead_ms = max(0.0, round_trip_s * 1000.0 - requested_duration_s * 1000.0)
    if dispatch_overhead_ms <= floor_ms:
        overhead_factor = 1.0
    elif dispatch_overhead_ms >= budget_ms:
        overhead_factor = 0.0
    else:
        overhead_factor = (budget_ms - dispatch_overhead_ms) / (budget_ms - floor_ms)

    if vision is None:
        vision_factor = 1.0
        vision_ok = None
    else:
        vision_ok = bool(vision.get("vision_ok"))
        vision_factor = 1.0 if vision_ok else 0.5

    score = round(100.0 * completion_ratio * overhead_factor * vision_factor, 6)
    if not ok:
        score = min(score, 0.0) - 10.0 * len(reasons)
    payload = {
        "score": round(score, 6),
        "hard_gates_passed": ok,
        "gate_failures": reasons,
        "action": result.get("action"),
        "stop_reason": result.get("stop_reason"),
        "final_stop_sent": result.get("final_stop_sent"),
        "executed_steps": executed_steps,
        "expected_steps": expected_steps,
        "completion_ratio": round(completion_ratio, 6),
        "minimum_sonar_mm": result.get("minimum_sonar_mm"),
        "round_trip_s": round(round_trip_s, 6),
        "dispatch_overhead_ms": round(dispatch_overhead_ms, 3),
        "budget_ms": budget_ms,
        "floor_ms": floor_ms,
        "vision_factor": vision_factor,
        "vision_ok": vision_ok,
        "metric": "completion_x_overhead_x_vision",
        "note": (
            "maximize score; reward fully-stopped trial + optional post-stop "
            "vision step; never more speed/duration/distance"
        ),
    }
    if vision is not None:
        payload["vision_snap"] = vision.get("vision_snap")
        payload["vision_dets"] = vision.get("vision_dets")
    if decision is not None:
        payload["vision_guided"] = True
        payload["chosen_action"] = decision.get("chosen_action")
        payload["chosen_yaw"] = decision.get("chosen_yaw")
        payload["n_detections"] = decision.get("n_detections")
        payload["decision_reason"] = decision.get("decision_reason")
        payload["chosen_label"] = decision.get("chosen_label")
        payload["chosen_score"] = decision.get("chosen_score")
        payload["detection_labels"] = decision.get("detection_labels")
        payload["pre_sonar_mm"] = decision.get("pre_sonar_mm")
        payload["deadband"] = decision.get("deadband")
        payload["pre_snap"] = decision.get("pre_snap")
        payload["pre_dets"] = decision.get("pre_dets")
        payload["skip_post_vision"] = decision.get("skip_post_vision")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="rpicarbox.local")
    parser.add_argument("--remote-root", default="/home/tyler/Desktop/tiny_pi_car")
    parser.add_argument(
        "--action",
        choices=CHASSIS_ACTIONS,
        default="forward",
        help="chassis action (Phase A translate default: forward)",
    )
    parser.add_argument("--duration-s", type=float, default=0.6)
    parser.add_argument("--speed-mm-s", type=float, default=40.0)
    parser.add_argument("--yaw", type=float, default=0.3)
    parser.add_argument("--no-sonar", action="store_true")
    parser.add_argument("--budget-ms", type=float, default=4000.0)
    parser.add_argument("--floor-ms", type=float, default=500.0)
    parser.add_argument("--timeout-s", type=int, default=60)
    parser.add_argument(
        "--allow-wheels",
        action="store_true",
        help=(
            "required to actually run the trial; without it this eval refuses "
            f"to move the chassis (see {NIGHT_CARD} / {MOTION_HOUR_CARD})"
        ),
    )
    parser.add_argument(
        "--with-vision",
        action="store_true",
        help=(
            "after a stopped trial, run camera_snap + 1-frame Hailo log_detections; "
            "multiplies score by vision_factor (1.0 ok / 0.5 fail). Does not weaken "
            "motion hard gates."
        ),
    )
    parser.add_argument(
        "--warmup-frames",
        type=int,
        default=3,
        help="AE warmup frames for post-trial snap_and_detect (default: 3)",
    )
    parser.add_argument(
        "--vision-guided",
        action="store_true",
        help=(
            "pre-trial snap+Hailo: bbox center picks yaw_left/yaw_right, then "
            "post-stop vision for scoring (requires --with-vision)"
        ),
    )
    parser.add_argument(
        "--deadband",
        type=float,
        default=0.05,
        help="bbox center deadband for --vision-guided (default: 0.05)",
    )
    parser.add_argument(
        "--sequential-init",
        action="store_true",
        help="serial camera warmup then Hailo init (default: parallel overlap)",
    )
    parser.add_argument(
        "--result-file",
        type=Path,
        help="offline: parse a saved physical_trial JSON line instead of SSH",
    )
    parser.add_argument("--json", action="store_true", help="emit one JSON object")
    args = parser.parse_args()

    if not args.allow_wheels and not args.result_file:
        parser.error(
            "chassis motion blocked: pass --allow-wheels to permit wheel/mecanum "
            f"actions this hour (see {MOTION_HOUR_CARD})"
        )
    if args.vision_guided and not args.with_vision:
        parser.error("--vision-guided requires --with-vision")
    if not 0.01 <= args.duration_s <= 8.0:
        parser.error("--duration-s must be between 0.01 and 8.0 (short trials only)")
    if not 0.0 <= args.speed_mm_s <= 120.0:
        parser.error("--speed-mm-s must be between 0 and 120")
    if not 0.0 <= args.yaw <= 1.0:
        parser.error("--yaw must be between 0 and 1.0")

    if args.result_file:
        result = parse_trial_result(args.result_file.read_text(encoding="utf-8"))
        round_trip_s = float(result.get("requested_duration_s", args.duration_s))
        vision = {"vision_ok": True, "vision_snap": None, "vision_dets": None} if args.with_vision else None
    else:
        prewarm_ssh(args.host, timeout_s=min(args.timeout_s, 15))
        text, round_trip_s, vision, decision = run_pi_trial(
            host=args.host,
            remote_root=args.remote_root,
            action=args.action,
            duration_s=args.duration_s,
            speed_mm_s=args.speed_mm_s,
            yaw=args.yaw,
            no_sonar=args.no_sonar,
            timeout_s=args.timeout_s,
            with_vision=args.with_vision,
            vision_guided=args.vision_guided,
            warmup_frames=args.warmup_frames,
            sequential_init=args.sequential_init,
            deadband=args.deadband,
        )
        result = parse_trial_result(text)

    payload = evaluate_payload(
        result,
        round_trip_s=round_trip_s,
        budget_ms=args.budget_ms,
        floor_ms=args.floor_ms,
        vision=vision,
        decision=decision,
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
