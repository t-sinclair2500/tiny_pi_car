"""Supervised autonomy stubs: perception → FSM → safety gate → RobotIO."""

from .types import FaultReason, MotionLease, Observation, RobotCommand
from .safety_gate import SafetyGate, StopLease

__all__ = [
    "FaultReason",
    "MotionLease",
    "Observation",
    "RobotCommand",
    "SafetyGate",
    "StopLease",
]
