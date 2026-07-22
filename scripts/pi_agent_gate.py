#!/usr/bin/env python3
"""Convenience SSH helpers for Pi research. Agents may also use raw SSH."""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")
CHASSIS_ACTIONS = frozenset({"forward", "reverse", "yaw_left", "yaw_right"})
NIGHT_CARD = "autoresearch/car/NIGHT_CARD.md"


def motion_trial_requires_allow_wheels(args: argparse.Namespace) -> str | None:
    """Return an error message when motion-trial would move the chassis without consent."""
    if args.operation != "motion-trial":
        return None
    if args.action not in CHASSIS_ACTIONS:
        return None
    if getattr(args, "allow_wheels", False):
        return None
    return (
        f"chassis motion blocked for perception-only runs (see {NIGHT_CARD}): "
        "pass --allow-wheels to permit wheel/mecanum actions"
    )


def _validate_host(value: str) -> str:
    if not SAFE_NAME.fullmatch(value):
        raise argparse.ArgumentTypeError("host must be an SSH alias or simple hostname")
    return value


def _ssh(host: str, command: str, *, timeout_s: int, dry_run: bool) -> int:
    argv = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={min(timeout_s, 15)}",
        host,
        command,
    ]
    if dry_run:
        print(shlex.join(argv))
        return 0
    return subprocess.run(argv, timeout=timeout_s, check=False).returncode


def _remote_root(value: str) -> str:
    if not value.startswith("/") or any(char in value for char in "\n\r\0"):
        raise argparse.ArgumentTypeError("remote root must be an absolute path")
    return value


def build_remote_command(args: argparse.Namespace) -> str:
    root = shlex.quote(args.remote_root)
    python = f"{root}/.venv/bin/python"
    if args.operation == "status":
        return (
            "set -eu; "
            "hostname; uname -m; "
            ". /etc/os-release; echo os:$VERSION_CODENAME; "
            "systemctl is-active masterpi || true; "
            "test -e /dev/h1x-0 && echo hailo_device:present || echo hailo_device:missing; "
            "lsmod | grep -E '^hailo' || echo hailo_module:missing; "
            "if test -e /dev/video0; then echo camera:video0; "
            "elif ls /dev/video* >/dev/null 2>&1; then echo camera:other_nodes; ls /dev/video* 2>/dev/null | head -5; "
            "else echo camera:missing; fi; "
            "test -d " + root + " && echo research_root:present || echo research_root:missing; "
            "test -d /home/tyler/Desktop/tiny_pi_car && echo desktop_repo:present || true"
        )
    if args.operation == "stop-masterpi":
        return "set -u; sudo -n systemctl stop masterpi || systemctl --user stop masterpi || true; systemctl is-active masterpi || true"
    if args.operation == "hailo-probe":
        return f"set -eu; cd {root}; {python} -m playground.hailo_probe"
    if args.operation == "motion-status":
        return f"set -eu; cd {root}; {python} -m playground.autoresearch.motion_arm status"
    if args.operation == "arm":
        return (
            f"set -eu; cd {root}; {python} -m playground.autoresearch.motion_arm arm "
            f"--stage {shlex.quote(args.stage)} --ttl-s {args.ttl_s}"
        )
    if args.operation == "camera-snap":
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        output = f"/tmp/tiny_pi_car/snap-{stamp}.jpg"
        stop = (
            "sudo -n systemctl stop masterpi >/dev/null 2>&1 || true; "
            if args.stop_masterpi
            else ""
        )
        return (
            "set -eu; "
            f"{stop}"
            f"cd {root}; mkdir -p /tmp/tiny_pi_car; "
            f"{python} -m playground.camera_snap --output {shlex.quote(output)}"
        )
    if args.operation == "perception":
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        output = f"/tmp/tiny_pi_car/autoresearch-perception-{stamp}.jsonl"
        stop = (
            "sudo -n systemctl stop masterpi >/dev/null 2>&1 || true; "
            if args.stop_masterpi
            else ""
        )
        return (
            "set -eu; "
            f"{stop}"
            f"cd {root}; mkdir -p /tmp/tiny_pi_car; "
            f"{python} -m playground.vision.log_detections "
            f"--frames {args.frames} --interval-s {args.interval_s:.3f} "
            f"--output {shlex.quote(output)}; echo result:{shlex.quote(output)}"
        )
    if args.operation == "motion-trial":
        stop = (
            "sudo -n systemctl stop masterpi >/dev/null 2>&1 || true; "
            if args.stop_masterpi
            else (
                "test \"$(systemctl is-active masterpi || true)\" != active || "
                "{ echo 'masterpi.service owns the UART; stop it first' >&2; exit 3; }; "
            )
        )
        sonar = "--no-sonar " if args.no_sonar else ""
        allow_wheels = "--allow-wheels " if args.allow_wheels else ""
        return (
            "set -eu; "
            f"{stop}"
            f"cd {root}; "
            f"cleanup() {{ {python} -m playground.micro_move stop >/dev/null 2>&1 || true; }}; "
            "trap cleanup EXIT HUP INT TERM; "
            f"timeout --signal=TERM --kill-after=2s {max(10, int(args.duration_s) + 8)}s {python} "
            "-m playground.autoresearch.physical_trial "
            f"{shlex.quote(args.action)} --duration-s {args.duration_s:.3f} "
            f"--speed-mm-s {args.speed_mm_s:.3f} --yaw {args.yaw:.3f} "
            f"--stage {shlex.quote(args.stage)} {sonar}{allow_wheels}"
        )
    if args.operation == "emergency-stop":
        return (
            f"set -u; sudo -n systemctl stop masterpi || true; cd {root}; "
            f"{python} -m playground.micro_move stop"
        )
    if args.operation == "roam-start":
        if not args.allow_wheels:
            raise ValueError("roam-start requires --allow-wheels (see autoresearch/car/STREAM_CARD.md)")
        look = "--look-down-first " if args.look_down_first else ""
        explore = "--explore-crawl " if args.explore_crawl else ""
        snap = (
            f"--snap-dir {shlex.quote(args.snap_dir)} "
            if args.snap_dir
            else ""
        )
        log = shlex.quote(args.log_jsonl)
        # Background daemon; host watches JSONL / roam-status.
        return (
            "set -eu; "
            f"cd {root}; mkdir -p /tmp/tiny_pi_car; "
            "if test -f /tmp/tiny_pi_car/roam_daemon.pid; then "
            "  old=$(cat /tmp/tiny_pi_car/roam_daemon.pid || true); "
            "  if test -n \"$old\" && kill -0 \"$old\" 2>/dev/null; then "
            "    echo 'roam_daemon already running pid:'$old >&2; exit 4; "
            "  fi; "
            "fi; "
            f"nohup {python} -m playground.autonomy.roam_daemon "
            f"--duration-s {args.duration_s:.3f} "
            f"--max-speed-mm-s {args.max_speed_mm_s:.3f} "
            f"--allow-wheels {look}{explore}{snap}"
            f"--log-jsonl {log} "
            ">/tmp/tiny_pi_car/roam_daemon.out 2>&1 & "
            "echo $! >/tmp/tiny_pi_car/roam_daemon.pid; "
            "echo started_pid:$(cat /tmp/tiny_pi_car/roam_daemon.pid); "
            f"echo log:{log}"
        )
    if args.operation == "roam-stop":
        return (
            "set -u; "
            f"cd {root}; "
            "if test -f /tmp/tiny_pi_car/roam_daemon.pid; then "
            "  pid=$(cat /tmp/tiny_pi_car/roam_daemon.pid || true); "
            "  if test -n \"$pid\"; then kill -TERM \"$pid\" 2>/dev/null || true; "
            "  sleep 0.5; kill -KILL \"$pid\" 2>/dev/null || true; fi; "
            "  rm -f /tmp/tiny_pi_car/roam_daemon.pid; "
            "fi; "
            f"{python} -m playground.micro_move stop >/dev/null 2>&1 || true; "
            "echo roam:stopped"
        )
    if args.operation == "roam-status":
        return (
            "set -u; "
            "if test -f /tmp/tiny_pi_car/roam_daemon.pid; then "
            "  pid=$(cat /tmp/tiny_pi_car/roam_daemon.pid); "
            "  if kill -0 \"$pid\" 2>/dev/null; then echo roam:running pid:$pid; "
            "  else echo roam:stale_pid:$pid; fi; "
            "else echo roam:not_running; fi; "
            "test -f /tmp/tiny_pi_car/roam_daemon.jsonl && "
            "  echo jsonl_lines:$(wc -l </tmp/tiny_pi_car/roam_daemon.jsonl) || "
            "  echo jsonl:missing; "
            "tail -n 3 /tmp/tiny_pi_car/roam_daemon.jsonl 2>/dev/null || true"
        )
    if args.operation == "shell":
        if not args.remote_cmd:
            raise ValueError("shell requires --remote-cmd")
        return args.remote_cmd
    raise ValueError(f"unknown operation: {args.operation}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=(
            "status",
            "stop-masterpi",
            "hailo-probe",
            "perception",
            "camera-snap",
            "motion-status",
            "arm",
            "motion-trial",
            "emergency-stop",
            "roam-start",
            "roam-stop",
            "roam-status",
            "shell",
        ),
    )
    parser.add_argument("--host", type=_validate_host, default="rpicarbox")
    parser.add_argument(
        "--remote-root",
        type=_remote_root,
        default="/home/tyler/Desktop/tiny_pi_car",
    )
    parser.add_argument("--frames", type=int, default=20)
    parser.add_argument("--interval-s", type=float, default=0.1)
    parser.add_argument("--action", choices=("forward", "reverse", "yaw_left", "yaw_right"), default="forward")
    parser.add_argument("--duration-s", type=float, default=0.8)
    parser.add_argument("--speed-mm-s", type=float, default=40.0)
    parser.add_argument("--max-speed-mm-s", type=float, default=25.0)
    parser.add_argument("--yaw", type=float, default=0.35)
    parser.add_argument("--stage", default="free")
    parser.add_argument("--ttl-s", type=int, default=3600)
    parser.add_argument("--timeout-s", type=int, default=300)
    parser.add_argument("--stop-masterpi", action="store_true")
    parser.add_argument("--no-sonar", action="store_true")
    parser.add_argument(
        "--allow-wheels",
        action="store_true",
        help=(
            "permit chassis motion for motion-trial / roam-start; "
            f"default off — see {NIGHT_CARD}"
        ),
    )
    parser.add_argument(
        "--look-down-first",
        action="store_true",
        help="roam-start: run look_down floor clutter gate before crawl",
    )
    parser.add_argument(
        "--explore-crawl",
        action="store_true",
        help="roam-start: slow forward when no target if clear",
    )
    parser.add_argument(
        "--snap-dir",
        default="",
        help="roam-start: remote dir for look_down/look_ahead snaps",
    )
    parser.add_argument(
        "--log-jsonl",
        default="/tmp/tiny_pi_car/roam_daemon.jsonl",
        help="roam-start: remote JSONL path",
    )
    parser.add_argument("--remote-cmd", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    blocked = motion_trial_requires_allow_wheels(args)
    if blocked:
        parser.error(blocked)
    if args.operation == "roam-start" and not args.allow_wheels:
        parser.error(
            "roam-start requires --allow-wheels (see autoresearch/car/STREAM_CARD.md)"
        )
    if not 1 <= args.frames <= 600:
        parser.error("--frames must be between 1 and 600")
    if not 0.0 <= args.interval_s <= 30.0:
        parser.error("--interval-s must be between 0 and 30")
    if args.operation in ("roam-start",):
        if not 1.0 <= args.duration_s <= 300.0:
            parser.error("--duration-s must be between 1 and 300 for roam-start")
        if not 1.0 <= args.max_speed_mm_s <= 30.0:
            parser.error("--max-speed-mm-s must be between 1 and 30 for roam-start")
    else:
        if not 0.01 <= args.duration_s <= 60.0:
            parser.error("--duration-s must be between 0.01 and 60")
    if not 0.0 <= args.speed_mm_s <= 250.0:
        parser.error("--speed-mm-s must be between 0 and 250")
    if not 0.0 <= args.yaw <= 2.0:
        parser.error("--yaw must be between 0 and 2")
    return _ssh(
        args.host,
        build_remote_command(args),
        timeout_s=args.timeout_s,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
