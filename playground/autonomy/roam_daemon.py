"""On-Pi continuous roam daemon: sonar interrupt + warm Hailo + ~10 Hz FSM.

Requires ``--allow-wheels`` for any chassis motion (same fence as motion trials).
Always ``stop_all`` in ``finally``. L3 sticky track / L4 grasp are hooks only.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import threading
import time
from pathlib import Path
from time import monotonic
from typing import Any

import cv2

from playground.autonomy.floor_clutter import floor_clutter_risk
from playground.autonomy.grasp_fsm import GraspFSM
from playground.autonomy.robot_io import RobotIO
from playground.autonomy.roam_fsm import RoamFSM, RoamState
from playground.autonomy.safety_gate import SafetyGate, StopLease
from playground.autonomy.types import Observation, RobotCommand
from playground.vision.detector import UnavailableHailoDetector, build_detector

ALLOW_WHEELS_ENV = "TINY_PI_ALLOW_WHEELS"
STREAM_CARD = "autoresearch/car/STREAM_CARD.md"
DEFAULT_LOG = Path("/tmp/tiny_pi_car/roam_daemon.jsonl")
DEFAULT_PID = Path("/tmp/tiny_pi_car/roam_daemon.pid")
CONTROL_HZ = 10.0
SONAR_HZ = 25.0
VISION_HZ = 5.0
SONAR_HARD_STOP_MM = 180.0
FORWARD_CLEARANCE_MM = 220.0
MAX_SPEED_CAP_MM_S = 30.0
LEASE_TTL_S = 0.35


def wheels_allowed(*, cli_flag: bool) -> bool:
    return cli_flag or os.environ.get(ALLOW_WHEELS_ENV) == "1"


class SharedSense:
    """Latest sonar / vision sample shared across threads."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.sonar_mm: float | None = None
        self.hard_stop = False
        self.detections: tuple[dict[str, Any], ...] = ()
        self.camera_ok = False
        self.hailo_ready = False
        self.floor_clutter_risk = False
        self.look_down_sticky = False
        self.clutter_metrics: dict[str, float] = {}
        self.last_frame = None
        self.fault: str | None = None


def _det_dicts(dets: list[Any]) -> tuple[dict[str, Any], ...]:
    out: list[dict[str, Any]] = []
    for d in dets:
        if hasattr(d, "to_dict"):
            out.append(d.to_dict())
        elif hasattr(d, "label"):
            out.append(
                {
                    "label": d.label,
                    "score": float(d.score),
                    "bbox": tuple(d.bbox),
                }
            )
        elif isinstance(d, dict):
            out.append(d)
    return tuple(out)


def _write_jsonl(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, separators=(",", ":")) + "\n")


def _save_snap(path: Path, frame: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if frame is not None:
        cv2.imwrite(str(path), frame)


def run_look_down_gate(
    robot: RobotIO,
    *,
    device: str,
    snap_dir: Path | None,
    sense: SharedSense,
) -> bool:
    """Look-down then look-ahead; set floor_clutter_risk. Returns risk bool."""
    robot.set_arm_pose("look_down")
    time.sleep(0.15)
    cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    down = None
    try:
        for _ in range(8):
            ok, frame = cap.read()
            if ok and frame is not None:
                down = frame
    finally:
        cap.release()

    risk, metrics = floor_clutter_risk(down) if down is not None else (True, {"reason": 1.0})
    if snap_dir is not None and down is not None:
        _save_snap(snap_dir / "look_down.jpg", down)

    robot.set_arm_pose("look_ahead")
    time.sleep(0.15)
    cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    ahead = None
    try:
        for _ in range(8):
            ok, frame = cap.read()
            if ok and frame is not None:
                ahead = frame
    finally:
        cap.release()
    if snap_dir is not None and ahead is not None:
        _save_snap(snap_dir / "look_ahead.jpg", ahead)

    with sense.lock:
        sense.floor_clutter_risk = bool(risk)
        sense.look_down_sticky = bool(risk)
        sense.clutter_metrics = metrics
        if ahead is not None:
            sense.last_frame = ahead
            sense.camera_ok = True
    return bool(risk)


def _sonar_loop(robot: RobotIO, sense: SharedSense, stop: threading.Event) -> None:
    period = 1.0 / SONAR_HZ
    while not stop.is_set():
        t0 = monotonic()
        mm = robot.read_sonar_mm()
        hard = False
        if mm is not None and mm < 4999.0 and mm <= SONAR_HARD_STOP_MM:
            hard = True
            try:
                robot.stop_all()
            except Exception:
                pass
        with sense.lock:
            sense.sonar_mm = mm
            if hard:
                sense.hard_stop = True
                sense.fault = "sonar_hard_stop"
        elapsed = monotonic() - t0
        stop.wait(max(0.0, period - elapsed))


def _vision_loop(
    sense: SharedSense,
    stop: threading.Event,
    *,
    device: str,
    detector: Any,
) -> None:
    period = 1.0 / VISION_HZ
    unavailable = isinstance(detector, UnavailableHailoDetector)
    cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    try:
        while not stop.is_set():
            t0 = monotonic()
            ok, frame = cap.read()
            dets: tuple[dict[str, Any], ...] = ()
            cam_ok = bool(ok and frame is not None)
            if cam_ok and not unavailable:
                try:
                    raw = detector.detect(frame)
                    dets = _det_dicts(list(raw))
                except Exception as exc:
                    with sense.lock:
                        sense.fault = f"vision_error:{exc}"
            # Continuous soft gate from look-ahead bottom band (cheap).
            clutter = False
            metrics: dict[str, float] = {}
            if cam_ok:
                clutter, metrics = floor_clutter_risk(frame)
            with sense.lock:
                sense.camera_ok = cam_ok
                sense.hailo_ready = not unavailable
                sense.detections = dets
                if cam_ok:
                    sense.last_frame = frame
                if sense.look_down_sticky:
                    sense.floor_clutter_risk = True
                else:
                    sense.floor_clutter_risk = bool(clutter)
                    if clutter:
                        sense.clutter_metrics = metrics
            elapsed = monotonic() - t0
            stop.wait(max(0.0, period - elapsed))
    finally:
        cap.release()


def run_daemon(
    *,
    duration_s: float,
    max_speed_mm_s: float,
    allow_wheels: bool,
    look_down_first: bool,
    explore_crawl: bool,
    log_jsonl: Path,
    device: str,
    snap_dir: Path | None,
    enable_grasp_hook: bool,
) -> int:
    if not wheels_allowed(cli_flag=allow_wheels):
        print(
            f"chassis motion blocked (see {STREAM_CARD}): "
            f"pass --allow-wheels or set {ALLOW_WHEELS_ENV}=1",
            flush=True,
        )
        return 2

    speed = min(float(max_speed_mm_s), MAX_SPEED_CAP_MM_S)
    stop = threading.Event()
    sense = SharedSense()
    lease = StopLease(ttl_s=LEASE_TTL_S, max_speed_mm_s=speed)
    gate = SafetyGate(
        stop_lease=lease,
        sonar_hard_stop_mm=SONAR_HARD_STOP_MM,
        max_cmd_speed_mm_s=speed,
    )
    max_steps = max(1, int(duration_s * CONTROL_HZ) + 5)
    roam = RoamFSM(
        max_steps=max_steps,
        approach_speed_mm_s=speed,
        forward_clearance_mm=FORWARD_CLEARANCE_MM,
        allow_crawl_without_target=explore_crawl,
    )
    # L4 hook only — never issued live in MVP.
    grasp = GraspFSM(max_steps=1) if enable_grasp_hook else None

    DEFAULT_PID.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_PID.write_text(f"{os.getpid()}\n", encoding="utf-8")
    if log_jsonl.exists():
        log_jsonl.unlink()

    def _on_signal(_signum: int, _frame: Any) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    detector = build_detector()
    exit_code = 0
    robot: RobotIO | None = None
    sonar_th: threading.Thread | None = None
    vision_th: threading.Thread | None = None

    try:
        robot = RobotIO(live=True)
        robot.open()
        robot.stop_all()

        if look_down_first:
            risk = run_look_down_gate(robot, device=device, snap_dir=snap_dir, sense=sense)
            _write_jsonl(
                log_jsonl,
                {
                    "t": 0.0,
                    "event": "look_down_gate",
                    "floor_clutter_risk": risk,
                    "metrics": sense.clutter_metrics,
                    "snap_dir": str(snap_dir) if snap_dir else None,
                },
            )

        sonar_th = threading.Thread(
            target=_sonar_loop, args=(robot, sense, stop), name="sonar", daemon=True
        )
        vision_th = threading.Thread(
            target=_vision_loop,
            args=(sense, stop),
            kwargs={"device": device, "detector": detector},
            name="vision",
            daemon=True,
        )
        sonar_th.start()
        vision_th.start()

        t0 = monotonic()
        period = 1.0 / CONTROL_HZ
        # L3 sticky-track hook: future holder for locked target id (unused MVP).
        _sticky_track_id: str | None = None
        del _sticky_track_id

        while not stop.is_set() and (monotonic() - t0) < duration_s:
            cycle_t0 = monotonic()
            lease.renew(owner="roam_daemon")
            with sense.lock:
                sonar_mm = sense.sonar_mm
                hard = sense.hard_stop
                dets = sense.detections
                cam_ok = sense.camera_ok
                hailo_ok = sense.hailo_ready
                clutter = sense.floor_clutter_risk
                fault = sense.fault
                metrics = dict(sense.clutter_metrics)

            obs = Observation(
                t_mono=monotonic(),
                detections=dets,
                sonar_mm=sonar_mm,
                camera_ok=cam_ok,
                hailo_ready=hailo_ok,
                floor_clutter_risk=clutter,
            )

            if hard:
                cmd = RobotCommand(reason="sonar_hard_stop")
                allowed = gate.stop_command(reason="sonar_hard_stop")
                robot.apply(allowed)
                fault = "sonar_hard_stop"
            else:
                cmd = roam.step(obs)
                # Refuse crawl / yaw into soft clutter (addresses laundry jam).
                if clutter and (abs(cmd.chassis_mm_s) > 0 or abs(cmd.yaw) > 0):
                    cmd = RobotCommand(
                        reason="floor_clutter_refuse",
                        meta={"floor_clutter": True, **metrics},
                    )
                    roam.state = RoamState.HOLD
                allowed = gate.allow(cmd, obs)
                if allowed is None:
                    allowed = gate.stop_command(reason=gate.last_fault.value)
                    fault = gate.last_fault.value
                # MVP: never apply arm grip while driving (L4 stub).
                if allowed.arm_pose and allowed.arm_pose not in (
                    "neutral",
                    "look_ahead",
                    "look_down",
                ):
                    allowed = RobotCommand(reason="arm_cmd_refused_mvp")
                robot.apply(allowed)
                if grasp is not None and roam.state == RoamState.HOLD:
                    _ = grasp.step(obs)  # L4 hook: suggest only, not applied

            applied = allowed
            _write_jsonl(
                log_jsonl,
                {
                    "t": round(monotonic() - t0, 3),
                    "state": roam.state.name,
                    "sonar_mm": sonar_mm,
                    "n_det": len(dets),
                    "cmd": {
                        "chassis_mm_s": applied.chassis_mm_s,
                        "direction_deg": applied.direction_deg,
                        "yaw": applied.yaw,
                        "reason": applied.reason,
                    },
                    "fault": fault,
                    "floor_clutter_risk": clutter,
                    "lease_alive": lease.alive(),
                },
            )
            elapsed = monotonic() - cycle_t0
            time.sleep(max(0.0, period - elapsed))

        _write_jsonl(
            log_jsonl,
            {"t": round(monotonic() - t0, 3), "event": "duration_complete", "state": roam.state.name},
        )
    except Exception as exc:
        exit_code = 1
        _write_jsonl(log_jsonl, {"t": 0.0, "event": "fault", "fault": str(exc)})
    finally:
        stop.set()
        if robot is not None:
            try:
                robot.stop_all()
            except Exception:
                pass
            try:
                robot.close()
            except Exception:
                pass
        if sonar_th is not None:
            sonar_th.join(timeout=1.0)
        if vision_th is not None:
            vision_th.join(timeout=1.0)
        try:
            if DEFAULT_PID.exists() and DEFAULT_PID.read_text().strip() == str(os.getpid()):
                DEFAULT_PID.unlink(missing_ok=True)
        except OSError:
            pass
        _write_jsonl(log_jsonl, {"t": -1, "event": "stopped"})
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-s", type=float, default=30.0)
    parser.add_argument("--max-speed-mm-s", type=float, default=25.0)
    parser.add_argument(
        "--allow-wheels",
        action="store_true",
        help=f"permit chassis motion (required; see {STREAM_CARD})",
    )
    parser.add_argument(
        "--look-down-first",
        action="store_true",
        help="look_down clutter gate before crawl; save paired snaps if --snap-dir set",
    )
    parser.add_argument(
        "--explore-crawl",
        action="store_true",
        help="slow forward when no target if sonar+floor clear",
    )
    parser.add_argument("--log-jsonl", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--device", default="/dev/video0")
    parser.add_argument(
        "--snap-dir",
        type=Path,
        default=None,
        help="directory for look_down / look_ahead JPEGs (default under .autoresearch if look-down)",
    )
    parser.add_argument(
        "--enable-grasp-hook",
        action="store_true",
        help="run GraspFSM.step on HOLD (suggestions only; not applied)",
    )
    args = parser.parse_args()
    if not 1.0 <= args.duration_s <= 300.0:
        parser.error("--duration-s must be between 1 and 300")
    if not 1.0 <= args.max_speed_mm_s <= MAX_SPEED_CAP_MM_S:
        parser.error(f"--max-speed-mm-s must be between 1 and {MAX_SPEED_CAP_MM_S}")
    snap_dir = args.snap_dir
    if args.look_down_first and snap_dir is None:
        snap_dir = Path(".autoresearch/runs/stream-l2")
    return run_daemon(
        duration_s=args.duration_s,
        max_speed_mm_s=args.max_speed_mm_s,
        allow_wheels=args.allow_wheels,
        look_down_first=args.look_down_first,
        explore_crawl=args.explore_crawl,
        log_jsonl=args.log_jsonl,
        device=args.device,
        snap_dir=snap_dir,
        enable_grasp_hook=args.enable_grasp_hook,
    )


if __name__ == "__main__":
    raise SystemExit(main())
