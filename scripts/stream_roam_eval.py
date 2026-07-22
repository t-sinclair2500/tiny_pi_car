#!/usr/bin/env python3
"""Score an on-Pi stream roam run (SSH start → JSONL → course score).

Metric (maximize): progress proxies minus jam/fault/timeout penalties.
Hard gates: daemon produced JSONL events, final stop observed, no hard crash.
See ``autoresearch/car/STREAM_CARD.md``.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SSH_CONTROL_DIR = Path("/tmp/tiny_pi_car-ssh")
STREAM_CARD = "autoresearch/car/STREAM_CARD.md"
REMOTE_LOG = "/tmp/tiny_pi_car/roam_daemon.jsonl"


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


def run_ssh(host: str, command: str, *, timeout_s: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ssh_argv(host, timeout_s=timeout_s, command=command),
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )


def score_events(events: list[dict]) -> dict:
    """Compute course score from roam_daemon JSONL events."""
    cycles = [e for e in events if "state" in e and "cmd" in e]
    n = len(cycles)
    if n == 0:
        return {
            "score": 0.0,
            "hard_gates_passed": False,
            "reason": "no_control_cycles",
            "n_cycles": 0,
        }

    crawl_ticks = 0
    yaw_ticks = 0
    hold_ticks = 0
    clutter_refuses = 0
    faults = 0
    sonar_hard = 0
    max_t = 0.0
    for e in cycles:
        max_t = max(max_t, float(e.get("t") or 0.0))
        cmd = e.get("cmd") or {}
        reason = str(cmd.get("reason") or "")
        chassis = abs(float(cmd.get("chassis_mm_s") or 0.0))
        yaw = abs(float(cmd.get("yaw") or 0.0))
        if chassis > 0:
            crawl_ticks += 1
        elif yaw > 0:
            yaw_ticks += 1
        else:
            hold_ticks += 1
        if "floor_clutter" in reason or e.get("floor_clutter_risk"):
            if chassis == 0 and yaw == 0:
                clutter_refuses += 1
        if e.get("fault"):
            faults += 1
            if e.get("fault") == "sonar_hard_stop":
                sonar_hard += 1

    stopped = any(e.get("event") == "stopped" for e in events)
    completed = any(e.get("event") == "duration_complete" for e in events)
    look_down = next((e for e in events if e.get("event") == "look_down_gate"), None)

    # Progress: fraction of time actually commanding motion (crawl or align).
    motion_frac = (crawl_ticks + 0.5 * yaw_ticks) / max(1, n)
    # Survive: ran a meaningful number of cycles without hard faults dominating.
    fault_frac = faults / max(1, n)
    survive = max(0.0, 1.0 - min(1.0, fault_frac * 2.0))
    # Soft-pile bonus: look-down ran and refused motion when risk flagged.
    clutter_bonus = 0.0
    if look_down is not None:
        clutter_bonus = 5.0
        if look_down.get("floor_clutter_risk") and crawl_ticks == 0:
            clutter_bonus += 15.0  # refused crawl on clutter
        elif not look_down.get("floor_clutter_risk") and crawl_ticks + yaw_ticks > 0:
            clutter_bonus += 5.0  # clear floor, still moved

    timeout_pen = 0.0 if (stopped or completed) else 20.0
    jam_pen = min(40.0, sonar_hard * 10.0 + (faults - sonar_hard) * 2.0)

    raw = 100.0 * motion_frac * survive + clutter_bonus - timeout_pen - jam_pen
    score = max(0.0, min(100.0, raw))
    hard = stopped and n >= 5 and fault_frac < 0.9

    return {
        "score": round(score, 3),
        "hard_gates_passed": hard,
        "n_cycles": n,
        "crawl_ticks": crawl_ticks,
        "yaw_ticks": yaw_ticks,
        "hold_ticks": hold_ticks,
        "faults": faults,
        "sonar_hard_stops": sonar_hard,
        "clutter_refuses": clutter_refuses,
        "duration_s_observed": round(max_t, 3),
        "stopped": stopped,
        "duration_complete": completed,
        "look_down_gate": look_down,
        "motion_frac": round(motion_frac, 4),
        "survive": round(survive, 4),
    }


def fetch_remote_jsonl(host: str, remote_path: str, *, timeout_s: int) -> list[dict]:
    proc = run_ssh(host, f"cat {shlex.quote(remote_path)} 2>/dev/null || true", timeout_s=timeout_s)
    events: list[dict] = []
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="rpicarbox")
    parser.add_argument("--remote-root", default="/home/tyler/Desktop/tiny_pi_car")
    parser.add_argument("--duration-s", type=float, default=30.0)
    parser.add_argument("--max-speed-mm-s", type=float, default=25.0)
    parser.add_argument("--allow-wheels", action="store_true")
    parser.add_argument("--look-down-first", action="store_true")
    parser.add_argument("--explore-crawl", action="store_true")
    parser.add_argument("--snap-dir", default=".autoresearch/runs/stream-l2")
    parser.add_argument("--log-jsonl", default=REMOTE_LOG)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--skip-start", action="store_true", help="score existing remote JSONL only")
    parser.add_argument("--timeout-s", type=int, default=180)
    args = parser.parse_args()

    if not args.allow_wheels and not args.skip_start:
        print(f"pass --allow-wheels (see {STREAM_CARD})", file=sys.stderr)
        return 2

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = ROOT / ".autoresearch" / "runs" / f"stream-run-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    gate = ROOT / "scripts" / "pi_agent_gate.py"
    py = sys.executable

    if not args.skip_start:
        # Ensure prior daemon is stopped.
        subprocess.run(
            [
                py,
                str(gate),
                "--host",
                args.host,
                "--remote-root",
                args.remote_root,
                "roam-stop",
            ],
            check=False,
            timeout=60,
        )
        start_argv = [
            py,
            str(gate),
            "--host",
            args.host,
            "--remote-root",
            args.remote_root,
            "roam-start",
            "--duration-s",
            str(args.duration_s),
            "--max-speed-mm-s",
            str(args.max_speed_mm_s),
            "--allow-wheels",
            "--log-jsonl",
            args.log_jsonl,
            "--timeout-s",
            str(min(60, args.timeout_s)),
        ]
        if args.look_down_first:
            start_argv.append("--look-down-first")
            start_argv.extend(["--snap-dir", args.snap_dir])
        if args.explore_crawl:
            start_argv.append("--explore-crawl")
        start = subprocess.run(start_argv, capture_output=True, text=True, timeout=90, check=False)
        (run_dir / "start.out").write_text(start.stdout + "\n" + start.stderr, encoding="utf-8")
        if start.returncode != 0:
            result = {
                "score": 0.0,
                "hard_gates_passed": False,
                "reason": "roam_start_failed",
                "returncode": start.returncode,
                "stdout": start.stdout[-2000:],
                "stderr": start.stderr[-2000:],
            }
            (run_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            if args.json:
                print(json.dumps(result))
            else:
                print(result)
            return 1

        # Wait for duration + arm settle + buffer, then stop.
        time.sleep(float(args.duration_s) + 8.0)
        subprocess.run(
            [
                py,
                str(gate),
                "--host",
                args.host,
                "--remote-root",
                args.remote_root,
                "roam-stop",
            ],
            check=False,
            timeout=60,
        )
        # Belt-and-suspenders e-stop.
        subprocess.run(
            [
                py,
                str(gate),
                "--host",
                args.host,
                "--remote-root",
                args.remote_root,
                "emergency-stop",
            ],
            check=False,
            timeout=60,
        )

    events = fetch_remote_jsonl(args.host, args.log_jsonl, timeout_s=60)
    (run_dir / "roam_daemon.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + ("\n" if events else ""),
        encoding="utf-8",
    )
    scored = score_events(events)
    scored["run_dir"] = str(run_dir)
    scored["host"] = args.host
    scored["n_events"] = len(events)
    (run_dir / "result.json").write_text(json.dumps(scored, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(scored))
    else:
        print(json.dumps(scored, indent=2))
    return 0 if scored.get("hard_gates_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
