"""Read battery voltage via stock Board SDK — no motion.

Run on the Pi with the expansion board powered:

    source .venv/bin/activate
    python -m playground.hello_board
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


def main() -> int:
    from common.ros_robot_controller_sdk import Board

    board = Board()
    board.enable_reception()
    time.sleep(0.3)
    mv = board.get_battery()
    if mv is None:
        print("battery: unavailable (check UART / power)")
        return 1
    print(f"battery_mV={mv} battery_V={mv / 1000.0:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
