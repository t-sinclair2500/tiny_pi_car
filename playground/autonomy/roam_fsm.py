"""Reactive roam FSM stub — capped steps, no unbounded loops."""

from __future__ import annotations

from enum import Enum, auto
from typing import Any

from .types import Observation, RobotCommand


class RoamState(Enum):
    IDLE = auto()
    SCAN = auto()
    APPROACH = auto()
    HOLD = auto()
    FAULT = auto()


def _bbox_center_x(det: dict[str, Any]) -> float | None:
    """Return bbox horizontal center in [0, 1] if normalized-ish, else None."""
    bbox = det.get("bbox")
    if not bbox or len(bbox) != 4:
        return None
    x1, _y1, x2, _y2 = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    cx = 0.5 * (x1 + x2)
    # Heuristic: values <= 2.0 treated as normalized; else assume pixels / 640
    if max(abs(x1), abs(x2), abs(cx)) > 2.0:
        cx = cx / 640.0
    return max(0.0, min(1.0, cx))


def suggested_yaw_from_detections(
    detections: tuple[dict[str, Any], ...],
    *,
    deadband: float = 0.08,
    max_yaw: float = 0.15,
) -> float:
    """Map target center error to a tiny yaw rate. No forward motion."""
    if not detections:
        return 0.0
    centers = [c for c in (_bbox_center_x(d) for d in detections) if c is not None]
    if not centers:
        return 0.0
    err = centers[0] - 0.5  # >0 => target right => positive yaw (convention: left+)
    if abs(err) < deadband:
        return 0.0
    # Negate so target-right commands turn right (negative if stack uses left+)
    yaw = max(-max_yaw, min(max_yaw, -err * 0.5))
    return yaw


class RoamFSM:
    """Suggest low-speed commands from observations. Never drives hardware itself."""

    def __init__(self, max_steps: int = 8, approach_speed_mm_s: float = 25.0) -> None:
        self.state = RoamState.IDLE
        self.max_steps = max_steps
        self.approach_speed_mm_s = approach_speed_mm_s
        self.steps = 0

    def reset(self) -> None:
        self.state = RoamState.IDLE
        self.steps = 0

    def step(self, obs: Observation) -> RobotCommand:
        self.steps += 1
        if self.steps > self.max_steps:
            self.state = RoamState.HOLD
            return RobotCommand(reason="roam_step_cap")

        if not obs.camera_ok:
            self.state = RoamState.FAULT
            return RobotCommand(reason="no_camera")

        if obs.detections:
            self.state = RoamState.APPROACH
            yaw = suggested_yaw_from_detections(obs.detections)
            # Chassis translation stays 0 until taped-floor approach (M2) is enabled.
            return RobotCommand(
                chassis_mm_s=0.0,
                yaw=yaw,
                reason="target_seen_align" if abs(yaw) > 0 else "target_seen_hold",
                meta={"n_det": len(obs.detections), "yaw": yaw},
            )

        if not obs.hailo_ready:
            self.state = RoamState.SCAN
            return RobotCommand(reason="hailo_unavailable_scan_hold")

        self.state = RoamState.SCAN
        return RobotCommand(chassis_mm_s=0.0, reason="scan_no_target")
