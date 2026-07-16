"""Pure safety policy: motion leases and command vetoes."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from .types import FaultReason, MotionLease, Observation, RobotCommand


@dataclass
class StopLease:
    """Renewable dead-man lease. Expired lease => stop_all only."""

    ttl_s: float = 0.35
    max_speed_mm_s: float = 40.0
    _lease: MotionLease | None = None
    last_fault: FaultReason = FaultReason.NONE

    def renew(self, owner: str = "autonomy") -> MotionLease:
        self._lease = MotionLease.issue(owner, ttl_s=self.ttl_s, max_speed_mm_s=self.max_speed_mm_s)
        self.last_fault = FaultReason.NONE
        return self._lease

    def expire(self) -> None:
        if self._lease is None:
            return
        self._lease = MotionLease(
            owner=self._lease.owner,
            issued_at_mono=self._lease.issued_at_mono,
            expires_at_mono=0.0,
            max_speed_mm_s=self._lease.max_speed_mm_s,
        )
        self.last_fault = FaultReason.LEASE_EXPIRED

    @property
    def lease(self) -> MotionLease | None:
        return self._lease

    def alive(self, now: float | None = None) -> bool:
        return self._lease is not None and self._lease.alive(now)


class SafetyGate:
    """Veto chassis commands that violate lease / sensor policy."""

    def __init__(
        self,
        stop_lease: StopLease | None = None,
        sonar_hard_stop_mm: float = 250.0,
        sonar_stale_s: float = 0.35,
        max_cmd_speed_mm_s: float = 40.0,
    ) -> None:
        self.stop_lease = stop_lease or StopLease()
        self.sonar_hard_stop_mm = sonar_hard_stop_mm
        self.sonar_stale_s = sonar_stale_s
        self.max_cmd_speed_mm_s = max_cmd_speed_mm_s
        self.last_fault = FaultReason.NONE

    def allow(self, cmd: RobotCommand, obs: Observation | None = None) -> RobotCommand | None:
        now = monotonic()
        if not self.stop_lease.alive(now):
            self.last_fault = FaultReason.LEASE_EXPIRED
            return None

        speed = abs(cmd.chassis_mm_s)
        cap = min(self.max_cmd_speed_mm_s, self.stop_lease.lease.max_speed_mm_s if self.stop_lease.lease else 0.0)
        if speed > cap:
            cmd = RobotCommand(
                chassis_mm_s=cap if cmd.chassis_mm_s >= 0 else -cap,
                direction_deg=cmd.direction_deg,
                yaw=cmd.yaw,
                arm_pose=cmd.arm_pose,
                reason=cmd.reason + "|speed_capped",
                meta=dict(cmd.meta),
            )

        if obs is not None:
            age = now - obs.t_mono
            if obs.sonar_mm is None or age > self.sonar_stale_s:
                if speed > 0 or abs(cmd.yaw) > 0:
                    self.last_fault = FaultReason.SONAR_STALE
                    return None
            elif obs.sonar_mm <= self.sonar_hard_stop_mm and (speed > 0 or abs(cmd.yaw) > 0):
                self.last_fault = FaultReason.SONAR_HARD_STOP
                return None

        self.last_fault = FaultReason.NONE
        return cmd

    def stop_command(self, reason: str = "safety_stop") -> RobotCommand:
        return RobotCommand(chassis_mm_s=0.0, direction_deg=90.0, yaw=0.0, reason=reason)
