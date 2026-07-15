"""Creep forward ~6 inches (open-loop timed), then stop.

No wheel encoders — distance is approximate. Clear space in front.

    source .venv/bin/activate
    python -m playground.forward_6in
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

# Stock demos use velocity ~50 for 1s; dialed down for a short creep.
# Direction 90 = forward in MecanumChassis polar coords.
VELOCITY = 30
DIRECTION_FORWARD = 90
DURATION_S = 0.65  # tune after first run (~6 in at this duty is a guess)


def main() -> int:
    import common.mecanum as mecanum

    chassis = mecanum.MecanumChassis()
    print(f"forward velocity={VELOCITY} dir={DIRECTION_FORWARD} for {DURATION_S}s")
    try:
        chassis.set_velocity(VELOCITY, DIRECTION_FORWARD, 0)
        time.sleep(DURATION_S)
    finally:
        chassis.set_velocity(0, 0, 0)
        time.sleep(0.05)
        print("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
