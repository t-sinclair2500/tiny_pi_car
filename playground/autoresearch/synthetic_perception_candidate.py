"""Deterministic green-box detector used only to smoke-test the locked vision arena."""

from __future__ import annotations

import numpy as np

from playground.vision.detector import Detection

METADATA = {"name": "synthetic-green-box-smoke", "hardware": "cpu", "test_only": True}


class GreenBoxDetector:
    def detect(self, frame: np.ndarray) -> list[Detection]:
        import cv2

        mask = (
            (frame[:, :, 1] >= 200)
            & (frame[:, :, 0] <= 80)
            & (frame[:, :, 2] <= 80)
        ).astype(np.uint8)
        points = cv2.findNonZero(mask)
        if points is None:
            return []
        x, y, width, height = cv2.boundingRect(points)
        return [Detection("cup", 1.0, (x, y, x + width, y + height))]


def create_detector() -> GreenBoxDetector:
    return GreenBoxDetector()
