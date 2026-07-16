"""Exclusive camera ownership helper (single process)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from time import monotonic

import numpy as np

from playground.vision.camera import LATEST_FRAME, grab_frame

_LOCK = Path("/tmp/playground_camera_broker.lock")


@dataclass
class FramePacket:
    t_mono: float
    frame: np.ndarray
    source: str


class CameraBroker:
    """Claim exclusive camera ownership; release on context exit."""

    def __init__(self, device: str = "/dev/video0", prefer_shared_latest: bool = True) -> None:
        self.device = device
        self.prefer_shared_latest = prefer_shared_latest
        self._held = False
        self._last: FramePacket | None = None

    def __enter__(self) -> CameraBroker:
        self.acquire()
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()

    def acquire(self) -> None:
        if _LOCK.exists():
            try:
                other = int(_LOCK.read_text().strip().split()[0])
            except (OSError, ValueError):
                other = -1
            if other > 0 and other != os.getpid() and Path(f"/proc/{other}").exists():
                raise RuntimeError(f"camera broker already held by pid {other}")
        _LOCK.write_text(f"{os.getpid()} {monotonic():.3f}\n")
        self._held = True

    def release(self) -> None:
        if not self._held:
            return
        try:
            if _LOCK.exists() and str(os.getpid()) in _LOCK.read_text():
                _LOCK.unlink(missing_ok=True)
        except OSError:
            pass
        self._held = False

    def latest(self) -> FramePacket | None:
        if not self._held:
            raise RuntimeError("camera broker not acquired")
        if self.prefer_shared_latest and LATEST_FRAME.is_file():
            import cv2

            frame = cv2.imread(str(LATEST_FRAME))
            if frame is not None:
                packet = FramePacket(t_mono=monotonic(), frame=frame, source="shared_latest")
                self._last = packet
                return packet
        frame = grab_frame(device=self.device)
        if frame is None:
            return None
        packet = FramePacket(t_mono=monotonic(), frame=frame, source="grab_frame")
        self._last = packet
        return packet

    @property
    def last(self) -> FramePacket | None:
        return self._last
