"""Short gripper-only open/close — no chassis, no arm joints.

Clears space around the claw, then:

    source .venv/bin/activate
    python -m playground.gripper_wiggle
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTERPI = ROOT / "MasterPi"
for rel in ("masterpi_sdk/common_sdk",):
    p = MASTERPI / rel
    if p.is_dir():
        sys.path.insert(0, str(p))

# Stock pulse values from color_sorting / hardware_test
OPEN_PULSE = 2000
CLOSE_PULSE = 1500
NEUTRAL_PULSE = 1500
MOVE_S = 0.5


def main() -> int:
    from common.ros_robot_controller_sdk import Board

    board = Board()
    board.enable_reception()
    time.sleep(0.3)

    mv = board.get_battery()
    if mv is None:
        print("battery: unavailable (check UART / power) — aborting motion")
        return 1
    print(f"battery_mV={mv} battery_V={mv / 1000.0:.2f}")

    try:
        print(f"open -> {OPEN_PULSE}")
        board.pwm_servo_set_position(MOVE_S, [[1, OPEN_PULSE]])
        time.sleep(MOVE_S + 0.2)

        print(f"close -> {CLOSE_PULSE}")
        board.pwm_servo_set_position(MOVE_S, [[1, CLOSE_PULSE]])
        time.sleep(MOVE_S + 0.2)

        print(f"open -> {OPEN_PULSE}")
        board.pwm_servo_set_position(MOVE_S, [[1, OPEN_PULSE]])
        time.sleep(MOVE_S + 0.2)
    finally:
        print(f"neutral -> {NEUTRAL_PULSE}")
        board.pwm_servo_set_position(MOVE_S, [[1, NEUTRAL_PULSE]])
        time.sleep(MOVE_S + 0.1)

    print("gripper_wiggle done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
