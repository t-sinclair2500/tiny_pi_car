"""Grasp FSM stub — vision propose, safety + RobotIO execute later."""

from __future__ import annotations

from enum import Enum, auto

from .types import Observation, RobotCommand


class GraspState(Enum):
    IDLE = auto()
    ACQUIRE = auto()
    PRE_GRASP = auto()
    CLOSE = auto()
    LIFT = auto()
    VERIFY = auto()
    FAULT = auto()


class GraspFSM:
    def __init__(self, max_steps: int = 12) -> None:
        self.state = GraspState.IDLE
        self.max_steps = max_steps
        self.steps = 0

    def reset(self) -> None:
        self.state = GraspState.IDLE
        self.steps = 0

    def step(self, obs: Observation) -> RobotCommand:
        self.steps += 1
        if self.steps > self.max_steps:
            self.state = GraspState.FAULT
            return RobotCommand(reason="grasp_step_cap")

        if not obs.detections:
            self.state = GraspState.ACQUIRE
            return RobotCommand(reason="no_target")

        if self.state in (GraspState.IDLE, GraspState.ACQUIRE):
            self.state = GraspState.PRE_GRASP
            return RobotCommand(arm_pose=None, reason="pre_grasp_hold", meta={"n_det": len(obs.detections)})

        self.state = GraspState.VERIFY
        return RobotCommand(reason="grasp_stub_no_motion")
