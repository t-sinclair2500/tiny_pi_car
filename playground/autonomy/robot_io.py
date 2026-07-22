"""Single UART/board owner. Default dry-run; live needs explicit enable."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from .types import RobotCommand

ROOT = Path(__file__).resolve().parents[2]
MASTERPI = ROOT / "MasterPi"


def _ensure_masterpi_path() -> None:
    for rel in ("", "masterpi_sdk/common_sdk", "masterpi_sdk/kinematics_sdk"):
        p = MASTERPI / rel if rel else MASTERPI
        if p.is_dir() and str(p) not in sys.path:
            sys.path.insert(0, str(p))


class RobotIO:
    """Wraps Board / Mecanum / ArmIK. Live mode is opt-in and always stops on exit."""

    def __init__(self, *, live: bool = False) -> None:
        self.live = live
        self._chassis = None
        self._board = None
        self._ak = None
        self._opened = False
        self.commands_sent: list[RobotCommand] = []

    def open(self) -> None:
        if not self.live:
            self._opened = True
            return
        _ensure_masterpi_path()
        import common.mecanum as mecanum
        from kinematics.arm_move_ik import ArmIK

        self._board = mecanum.board
        self._board.enable_reception()
        time.sleep(0.15)
        self._chassis = mecanum.MecanumChassis()
        self._ak = ArmIK()
        self._ak.board = self._board
        self._opened = True

    def close(self) -> None:
        try:
            self.stop_all()
        finally:
            self._opened = False

    def __enter__(self) -> RobotIO:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def apply(self, cmd: RobotCommand) -> None:
        if not self._opened:
            raise RuntimeError("RobotIO not open")
        self.commands_sent.append(cmd)
        if not self.live:
            return
        assert self._chassis is not None
        self._chassis.set_velocity(float(cmd.chassis_mm_s), float(cmd.direction_deg), float(cmd.yaw))
        if cmd.arm_pose and self._ak is not None:
            self.set_arm_pose(cmd.arm_pose)

    def set_arm_pose(self, pose: str, *, settle_s: float | None = None) -> None:
        """Bounded ArmIK poses. ``neutral`` / ``look_ahead`` = cam-up; ``look_down`` = floor FOV."""
        if not self._opened or not self.live or self._ak is None:
            return
        if pose in ("neutral", "look_ahead"):
            # cam-up / carry-ish
            self._ak.setPitchRangeMoving((0, 6, 18), 0, -90, 90, 1200)
            time.sleep(settle_s if settle_s is not None else 1.3)
        elif pose == "look_down":
            # Pitch camera toward near floor (soft-clutter check). Timed + bounded.
            self._ak.setPitchRangeMoving((0, 10, 10), -25, -90, 90, 1200)
            time.sleep(settle_s if settle_s is not None else 1.3)
        else:
            raise ValueError(f"unknown arm_pose: {pose!r}")

    def stop_all(self) -> None:
        stop = RobotCommand(chassis_mm_s=0.0, direction_deg=90.0, yaw=0.0, reason="stop_all")
        self.commands_sent.append(stop)
        if self.live and self._chassis is not None:
            self._chassis.set_velocity(0, 0, 0)
            time.sleep(0.05)

    def read_sonar_mm(self) -> float | None:
        if not self.live:
            return None
        _ensure_masterpi_path()
        try:
            from common.sonar import Sonar

            return float(Sonar().getDistance())
        except Exception:
            return None
