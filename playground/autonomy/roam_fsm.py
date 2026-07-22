"""Reactive roam FSM — capped steps; emits chassis cmds for roam_daemon."""

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


PERSON_LABEL = "person"


def pick_primary_detection(
    detections: tuple[dict[str, Any], ...],
) -> dict[str, Any] | None:
    """Prefer person; otherwise highest score."""
    if not detections:
        return None
    persons = [
        d for d in detections if str(d.get("label", "")).lower() == PERSON_LABEL
    ]
    if persons:
        return max(persons, key=lambda d: float(d.get("score") or 0.0))
    return max(detections, key=lambda d: float(d.get("score") or 0.0))


def _bbox_center_x(det: dict[str, Any]) -> float | None:
    """Return bbox horizontal center in [0, 1] if normalized-ish, else None."""
    bbox = det.get("bbox")
    if not bbox or len(bbox) != 4:
        return None
    x1, _y1, x2, _y2 = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    cx = 0.5 * (x1 + x2)
    if max(abs(x1), abs(x2), abs(cx)) > 2.0:
        cx = cx / 640.0
    return max(0.0, min(1.0, cx))


def suggested_yaw_from_detections(
    detections: tuple[dict[str, Any], ...],
    *,
    deadband: float = 0.08,
    max_yaw: float = 0.15,
) -> float:
    """Map primary target center error to a tiny yaw rate."""
    primary = pick_primary_detection(detections)
    if primary is None:
        return 0.0
    cx = _bbox_center_x(primary)
    if cx is None:
        return 0.0
    err = cx - 0.5
    if abs(err) < deadband:
        return 0.0
    return max(-max_yaw, min(max_yaw, -err * 0.5))


class RoamFSM:
    """Suggest low-speed commands from observations. Never drives hardware itself."""

    def __init__(
        self,
        max_steps: int = 300,
        approach_speed_mm_s: float = 25.0,
        *,
        deadband: float = 0.08,
        max_yaw: float = 0.12,
        forward_clearance_mm: float = 220.0,
        allow_crawl_without_target: bool = False,
    ) -> None:
        self.state = RoamState.IDLE
        self.max_steps = max_steps
        self.approach_speed_mm_s = approach_speed_mm_s
        self.deadband = deadband
        self.max_yaw = max_yaw
        self.forward_clearance_mm = forward_clearance_mm
        self.allow_crawl_without_target = allow_crawl_without_target
        self.steps = 0

    def reset(self) -> None:
        self.state = RoamState.IDLE
        self.steps = 0

    def _sonar_clear(self, obs: Observation) -> bool:
        if obs.sonar_mm is None:
            return False
        if obs.sonar_mm >= 4999.0:
            return False
        return obs.sonar_mm > self.forward_clearance_mm

    def step(self, obs: Observation) -> RobotCommand:
        self.steps += 1
        if self.steps > self.max_steps:
            self.state = RoamState.HOLD
            return RobotCommand(reason="roam_step_cap")

        if not obs.camera_ok:
            self.state = RoamState.FAULT
            return RobotCommand(reason="no_camera")

        if obs.floor_clutter_risk:
            self.state = RoamState.HOLD
            return RobotCommand(reason="floor_clutter_hold", meta={"floor_clutter": True})

        if obs.detections:
            yaw = suggested_yaw_from_detections(
                obs.detections, deadband=self.deadband, max_yaw=self.max_yaw
            )
            primary = pick_primary_detection(obs.detections)
            meta: dict[str, Any] = {
                "n_det": len(obs.detections),
                "yaw": yaw,
                "label": (primary or {}).get("label"),
            }
            if abs(yaw) > 1e-6:
                self.state = RoamState.APPROACH
                return RobotCommand(
                    chassis_mm_s=0.0,
                    yaw=yaw,
                    reason="target_align_yaw",
                    meta=meta,
                )
            if self._sonar_clear(obs):
                self.state = RoamState.APPROACH
                return RobotCommand(
                    chassis_mm_s=self.approach_speed_mm_s,
                    direction_deg=90.0,
                    yaw=0.0,
                    reason="target_centered_crawl",
                    meta=meta,
                )
            self.state = RoamState.HOLD
            return RobotCommand(reason="target_centered_sonar_blocked", meta=meta)

        if not obs.hailo_ready:
            self.state = RoamState.SCAN
            return RobotCommand(reason="hailo_unavailable_scan_hold")

        # No detections: optional slow exploratory crawl if floor+sonar clear.
        if (
            self.allow_crawl_without_target
            and self._sonar_clear(obs)
            and not obs.floor_clutter_risk
        ):
            self.state = RoamState.SCAN
            return RobotCommand(
                chassis_mm_s=min(20.0, self.approach_speed_mm_s),
                direction_deg=90.0,
                reason="scan_crawl_clear",
            )

        self.state = RoamState.SCAN
        return RobotCommand(chassis_mm_s=0.0, reason="scan_no_target")
