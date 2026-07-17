"""Editable detector candidate for held-out host/Pi/Hailo evaluation.

Autoresearch workers may replace this adapter or point it at a different model.
The locked runner only relies on ``create_detector()`` and optional ``METADATA``.
"""

from __future__ import annotations

from playground.vision.detector import Detector, HailoHEFDetector
from playground.vision.models import MODEL_DIR, prefer_hef

METADATA = {
    "name": "stock-hailo-yolov8m",
    "family": "yolov8m",
    "runtime": "HailoRT 5.3",
    "hardware": "hailo10h",
    "source": "repo baseline",
    "artifact": {"filename": "yolov8m_h10.hef"},
}


def create_detector() -> Detector:
    """Return the current candidate; unavailable hardware fails the locked run."""
    hef = prefer_hef()
    if hef is None:
        hef = MODEL_DIR / str(METADATA["artifact"]["filename"])
    return HailoHEFDetector(hef, score_thresh=0.45)
