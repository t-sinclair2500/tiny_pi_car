"""Single-shot USB camera capture with AE warmup and bounded fallbacks."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import cv2
import numpy as np

LATEST_FRAME = Path("/tmp/robot_cam_latest.jpg")


def _warmup_and_read(device: str, frames: int = 25) -> np.ndarray | None:
    """Open V4L2, discard frames so UVC auto-exposure can settle, then read."""
    capture = cv2.VideoCapture(device, cv2.CAP_V4L2)
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    try:
        if not capture.isOpened():
            return None
        last = None
        for _ in range(max(1, frames)):
            ok, frame = capture.read()
            if ok and frame is not None:
                last = frame
        return last
    finally:
        capture.release()


def grab_frame(
    device: str = "/dev/video0",
    timeout_seconds: float = 2.0,
    *,
    warmup_frames: int = 25,
) -> np.ndarray | None:
    """Return one BGR frame. Prefers a fresh shared jpg, else warmed V4L2, else fswebcam."""
    if LATEST_FRAME.is_file():
        age = time.time() - LATEST_FRAME.stat().st_mtime
        if age < 3.0:
            frame = cv2.imread(str(LATEST_FRAME))
            if frame is not None and float(frame.mean()) > 20.0:
                return frame

    frame = _warmup_and_read(device, frames=warmup_frames)
    if frame is not None and float(frame.mean()) > 8.0:
        return frame

    target = Path("/tmp/hailo_vision_frame.jpg")
    try:
        result = subprocess.run(
            ["fswebcam", "-d", device, "-r", "640x480", "--no-banner", "-q", str(target)],
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode == 0 and target.is_file():
        return cv2.imread(str(target))
    return None
