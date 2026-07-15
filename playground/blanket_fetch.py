"""Blanket fetch: left nudge → sonar approach → grip → reverse ~4ft.

Snapshots to /tmp/blanket_*.jpg (playground/captures is cursorignored).

    source .venv/bin/activate
    python -m playground.blanket_fetch
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTERPI = ROOT / "MasterPi"
for rel in (
    "",
    "masterpi_sdk/common_sdk",
    "masterpi_sdk/kinematics_sdk",
):
    p = MASTERPI / rel if rel else MASTERPI
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Open-loop tunables (carpet / first try)
TURN_YAW = -0.28  # CCW = left
TURN_S = 0.18  # ~10° from prior 180°≈1.6s @0.3
DRIVE_V = 28
APPROACH_STOP_MM = 180
APPROACH_TIMEOUT_S = 8.0
REVERSE_S = 5.2  # ~4 ft vs 6in/0.65s scale
GRIP_OPEN = 2000
GRIP_CLOSE = 1200
SNAP_DIR = Path("/tmp")


def snap(tag: str) -> Path:
    out = SNAP_DIR / f"blanket_{tag}.jpg"
    subprocess.run(
        [
            "fswebcam",
            "-d",
            "/dev/video0",
            "-r",
            "640x480",
            "--no-banner",
            "-q",
            str(out),
        ],
        check=False,
        capture_output=True,
    )
    print(f"snap {out}")
    return out


def stop_chassis(chassis) -> None:
    chassis.set_velocity(0, 0, 0)
    time.sleep(0.05)


def main() -> int:
    import common.mecanum as mecanum
    from common.sonar import Sonar
    from kinematics.arm_move_ik import ArmIK

    board = mecanum.board
    board.enable_reception()
    time.sleep(0.25)

    chassis = mecanum.MecanumChassis()
    sonar = Sonar()
    sonar.setRGBMode(0)
    ak = ArmIK()
    ak.board = board

    print(f"battery_mV={board.get_battery()} sonar_mm={sonar.getDistance()}")
    snap("00_start")

    try:
        print("open gripper")
        board.pwm_servo_set_position(0.6, [[1, GRIP_OPEN]])
        time.sleep(0.7)

        print(f"turn left yaw={TURN_YAW} for {TURN_S}s")
        chassis.set_velocity(0, 90, TURN_YAW)
        time.sleep(TURN_S)
        stop_chassis(chassis)
        time.sleep(0.3)
        snap("01_after_turn")
        print(f"sonar_mm={sonar.getDistance()}")

        print("arm ready then reach")
        ak.setPitchRangeMoving((0, 6, 18), 0, -90, 90, 1200)
        time.sleep(1.3)
        result = ak.setPitchRangeMoving((0, 14, 5), -90, -90, 0, 1500)
        print(f"reach result={result}")
        time.sleep(1.6)
        board.pwm_servo_set_position(0.5, [[1, GRIP_OPEN]])
        time.sleep(0.5)
        snap("02_reach")

        print(f"approach until sonar<{APPROACH_STOP_MM}mm")
        t0 = time.time()
        chassis.set_velocity(DRIVE_V, 90, 0)
        while time.time() - t0 < APPROACH_TIMEOUT_S:
            d = sonar.getDistance()
            if d < APPROACH_STOP_MM:
                print(f"stop approach sonar_mm={d}")
                break
            time.sleep(0.08)
        else:
            print(f"approach timeout sonar_mm={sonar.getDistance()}")
        stop_chassis(chassis)
        time.sleep(0.25)
        snap("03_close")

        print("nudge + close grip")
        chassis.set_velocity(22, 90, 0)
        time.sleep(0.35)
        stop_chassis(chassis)
        board.pwm_servo_set_position(0.7, [[1, GRIP_CLOSE]])
        time.sleep(0.9)
        snap("04_gripped")

        print("lift while holding")
        ak.setPitchRangeMoving((0, 8, 14), -30, -90, 90, 1500)
        time.sleep(1.6)
        snap("05_lifted")

        print(f"reverse {REVERSE_S}s")
        chassis.set_velocity(DRIVE_V, 270, 0)
        time.sleep(REVERSE_S)
        stop_chassis(chassis)
        snap("06_done")
        print(f"final sonar_mm={sonar.getDistance()}")
        print("done (gripper still closed)")
        return 0
    except Exception as exc:
        print(f"ERROR {exc!r}")
        return 1
    finally:
        stop_chassis(chassis)


if __name__ == "__main__":
    raise SystemExit(main())
