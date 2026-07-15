"""Aggressively sample USB camera → /tmp/robot_cam_latest.jpg + rotating buffer."""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

LATEST = Path("/tmp/robot_cam_latest.jpg")
BUF = Path("/tmp/robot_cam_buf")
INTERVAL = 0.35


def main() -> None:
    BUF.mkdir(parents=True, exist_ok=True)
    i = 0
    while True:
        tmp = Path("/tmp/robot_cam_tmp.jpg")
        subprocess.run(
            [
                "fswebcam",
                "-d",
                "/dev/video0",
                "-r",
                "640x480",
                "--no-banner",
                "-q",
                str(tmp),
            ],
            check=False,
            capture_output=True,
        )
        if tmp.is_file() and tmp.stat().st_size > 1000:
            shutil.copy(tmp, LATEST)
            shutil.copy(tmp, BUF / f"{i:04d}.jpg")
            i = (i + 1) % 40
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
