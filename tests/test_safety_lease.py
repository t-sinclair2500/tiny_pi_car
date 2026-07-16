"""Pure lease / safety-gate tests — no motors, no I2C, no camera."""

from __future__ import annotations

from time import sleep

from playground.autonomy.safety_gate import SafetyGate, StopLease
from playground.autonomy.types import FaultReason, Observation, RobotCommand


def test_lease_renew_then_expire_blocks_motion():
    lease = StopLease(ttl_s=0.25, max_speed_mm_s=40.0)
    gate = SafetyGate(stop_lease=lease, max_cmd_speed_mm_s=40.0)
    cmd = RobotCommand(chassis_mm_s=20.0, direction_deg=90.0, reason="test_fwd")

    lease.renew(owner="test")
    assert lease.alive()
    allowed = gate.allow(cmd, None)
    assert allowed is not None
    assert allowed.chassis_mm_s == 20.0
    assert gate.last_fault == FaultReason.NONE

    lease.expire()
    assert not lease.alive()
    blocked = gate.allow(cmd, None)
    assert blocked is None
    assert gate.last_fault == FaultReason.LEASE_EXPIRED
    stop = gate.stop_command(reason=gate.last_fault.value)
    assert stop.chassis_mm_s == 0.0
    assert stop.yaw == 0.0
    assert stop.reason == FaultReason.LEASE_EXPIRED.value


def test_lease_ttl_expires_without_explicit_expire():
    lease = StopLease(ttl_s=0.05, max_speed_mm_s=25.0)
    gate = SafetyGate(stop_lease=lease)
    lease.renew(owner="ttl")
    assert gate.allow(RobotCommand(chassis_mm_s=10.0, reason="go"), None) is not None
    sleep(0.08)
    assert gate.allow(RobotCommand(chassis_mm_s=10.0, reason="go"), None) is None
    assert gate.last_fault == FaultReason.LEASE_EXPIRED


def test_sonar_hard_stop_vetoes_motion():
    lease = StopLease(ttl_s=1.0)
    lease.renew()
    gate = SafetyGate(stop_lease=lease, sonar_hard_stop_mm=250.0)
    obs = Observation(t_mono=__import__("time").monotonic(), sonar_mm=100.0, camera_ok=True)
    blocked = gate.allow(RobotCommand(chassis_mm_s=15.0, reason="fwd"), obs)
    assert blocked is None
    assert gate.last_fault == FaultReason.SONAR_HARD_STOP


def test_sonar_stale_vetoes_motion():
    lease = StopLease(ttl_s=1.0)
    lease.renew()
    gate = SafetyGate(stop_lease=lease, sonar_stale_s=0.05)
    obs = Observation(t_mono=__import__("time").monotonic() - 1.0, sonar_mm=800.0, camera_ok=True)
    blocked = gate.allow(RobotCommand(chassis_mm_s=15.0, reason="fwd"), obs)
    assert blocked is None
    assert gate.last_fault == FaultReason.SONAR_STALE
