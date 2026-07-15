"""Single micro chassis/arm/gripper command. UART exclusive while running.

Examples:
  python -m playground.micro_move cam_up
  python -m playground.micro_move stop
  python -m playground.micro_move forward 0.4 25
  python -m playground.micro_move reverse 0.4 25
  python -m playground.micro_move yaw_left 0.12 0.28
  python -m playground.micro_move yaw_right 0.12 0.28
  python -m playground.micro_move grip_open
  python -m playground.micro_move grip_close
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTERPI = ROOT / "MasterPi"
for rel in ("", "masterpi_sdk/common_sdk", "masterpi_sdk/kinematics_sdk"):
    p = MASTERPI / rel if rel else MASTERPI
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        print(__doc__)
        return 2
    cmd = argv[0]
    import common.mecanum as mecanum
    from kinematics.arm_move_ik import ArmIK

    board = mecanum.board
    board.enable_reception()
    time.sleep(0.15)
    chassis = mecanum.MecanumChassis()
    ak = ArmIK()
    ak.board = board

    def stop() -> None:
        chassis.set_velocity(0, 0, 0)
        time.sleep(0.05)

    try:
        if cmd == "stop":
            stop()
        elif cmd == "cam_up":
            ak.setPitchRangeMoving((0, 6, 18), 0, -90, 90, 1200)
            time.sleep(1.3)
        elif cmd == "forward":
            dur = float(argv[1]) if len(argv) > 1 else 0.35
            vel = int(argv[2]) if len(argv) > 2 else 25
            chassis.set_velocity(vel, 90, 0)
            time.sleep(dur)
            stop()
        elif cmd == "reverse":
            dur = float(argv[1]) if len(argv) > 1 else 0.35
            vel = int(argv[2]) if len(argv) > 2 else 25
            chassis.set_velocity(vel, 270, 0)
            time.sleep(dur)
            stop()
        elif cmd == "yaw_left":
            dur = float(argv[1]) if len(argv) > 1 else 0.12
            yaw = float(argv[2]) if len(argv) > 2 else 0.28
            chassis.set_velocity(0, 90, -abs(yaw))
            time.sleep(dur)
            stop()
        elif cmd == "yaw_right":
            dur = float(argv[1]) if len(argv) > 1 else 0.12
            yaw = float(argv[2]) if len(argv) > 2 else 0.28
            chassis.set_velocity(0, 90, abs(yaw))
            time.sleep(dur)
            stop()
        elif cmd == "grip_open":
            board.pwm_servo_set_position(0.5, [[1, 2000]])
            time.sleep(0.55)
        elif cmd == "grip_close":
            board.pwm_servo_set_position(0.6, [[1, 1200]])
            time.sleep(0.7)
        elif cmd == "reach":
            ak.setPitchRangeMoving((0, 14, 5), -90, -90, 0, 1200)
            time.sleep(1.3)
        else:
            print(f"unknown cmd {cmd}")
            return 2
        print(f"ok {cmd}")
        return 0
    finally:
        stop()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
