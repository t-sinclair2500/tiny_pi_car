"""Poll ultrasonic → /tmp/robot_sonar.txt (I2C only, no UART)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "MasterPi/masterpi_sdk/common_sdk"))

OUT = Path("/tmp/robot_sonar.txt")


def main() -> None:
    from common.sonar import Sonar

    s = Sonar()
    s.setRGBMode(0)
    while True:
        d = s.getDistance()
        OUT.write_text(f"{time.time():.3f} mm={d}\n")
        time.sleep(0.12)


if __name__ == "__main__":
    main()
