"""Immutable autonomy types (no hardware I/O)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import monotonic
from typing import Any


class FaultReason(str, Enum):
    NONE = "none"
    LEASE_EXPIRED = "lease_expired"
    SONAR_HARD_STOP = "sonar_hard_stop"
    SONAR_STALE = "sonar_stale"
    CAMERA_STALE = "camera_stale"
    HAILO_UNAVAILABLE = "hailo_unavailable"
    BATTERY_LOW = "battery_low"
    SUPERVISOR_STOP = "supervisor_stop"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Observation:
    """One perception + sensor sample. Timestamps use monotonic seconds."""

    t_mono: float
    detections: tuple[dict[str, Any], ...] = ()
    sonar_mm: float | None = None
    camera_ok: bool = False
    hailo_ready: bool = False
    floor_clutter_risk: bool = False
    notes: str = ""


@dataclass(frozen=True)
class MotionLease:
    """Dead-man ticket: motion is illegal after expires_at_mono."""

    owner: str
    issued_at_mono: float
    expires_at_mono: float
    max_speed_mm_s: float = 40.0

    @classmethod
    def issue(cls, owner: str, ttl_s: float = 0.35, max_speed_mm_s: float = 40.0) -> MotionLease:
        now = monotonic()
        return cls(owner=owner, issued_at_mono=now, expires_at_mono=now + ttl_s, max_speed_mm_s=max_speed_mm_s)

    def alive(self, now: float | None = None) -> bool:
        return (now if now is not None else monotonic()) < self.expires_at_mono


@dataclass(frozen=True)
class RobotCommand:
    """Desired chassis/arm action before safety veto."""

    chassis_mm_s: float = 0.0
    direction_deg: float = 90.0
    yaw: float = 0.0
    arm_pose: str | None = None
    reason: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
