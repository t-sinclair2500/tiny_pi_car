"""Editable baseline policy for the offline autonomy arena.

Deterministic, no I/O. Autoresearch workers improve this toward better approach
behavior under the fixed evaluator.
"""

from __future__ import annotations

from typing import Any


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class Policy:
    """Approach: scan, yaw-align, creep to handoff distance, then stop."""

    HANDOFF_MM = 315.0

    def __init__(self) -> None:
        self.scan_steps = 0
        self.last_yaw = 0.0

    def reset(self) -> None:
        self.scan_steps = 0
        self.last_yaw = 0.0

    def step(self, observation: dict[str, Any]) -> dict[str, Any]:
        camera_ok = bool(observation.get("camera_ok", False))
        hailo_ready = bool(observation.get("hailo_ready", False))
        sonar_mm = observation.get("sonar_mm")
        sonar_age_s = float(observation.get("sonar_age_s", 99.0))
        confirmed = bool(observation.get("target_confirmed", False))
        error = observation.get("target_x_error")

        if not camera_ok or not hailo_ready:
            return {"speed_mm_s": 0.0, "yaw": 0.0, "reason": "perception_unavailable"}
        if sonar_mm is None or sonar_age_s > 0.35:
            return {"speed_mm_s": 0.0, "yaw": 0.0, "reason": "sonar_stale"}

        sonar_mm = float(sonar_mm)
        if sonar_mm <= 200.0:
            return {"speed_mm_s": 0.0, "yaw": 0.0, "reason": "sonar_stop"}

        if not confirmed or error is None:
            self.scan_steps += 1
            yaw = 0.12 if self.scan_steps <= 10 else 0.0
            self.last_yaw = yaw
            return {"speed_mm_s": 0.0, "yaw": yaw, "reason": "bounded_scan"}

        self.scan_steps = 0
        error = float(error)
        yaw = _clip(-0.65 * error, -0.4, 0.4)

        # Evaluator success: distance <= handoff, |error| <= 0.10, speed == 0.
        if sonar_mm <= self.HANDOFF_MM and abs(error) <= 0.10:
            self.last_yaw = 0.0
            return {"speed_mm_s": 0.0, "yaw": 0.0, "reason": "handoff_ready"}

        speed = 0.0
        if abs(error) <= 0.32:
            if sonar_mm > self.HANDOFF_MM + 120.0:
                speed = _clip((sonar_mm - self.HANDOFF_MM) * 0.22, 30.0, 85.0)
            elif sonar_mm > self.HANDOFF_MM:
                # Finish the last meters; min speed must close the gap before timeout.
                speed = _clip((sonar_mm - self.HANDOFF_MM) * 0.4, 18.0, 32.0)
            # If past handoff but not yet aligned, hold and yaw only.
        self.last_yaw = yaw
        return {"speed_mm_s": speed, "yaw": yaw, "reason": "track_target"}
