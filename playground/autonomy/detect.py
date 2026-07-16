"""Perception adapter: playground.vision → Observation detections."""

from __future__ import annotations

from time import monotonic
from typing import Any

import numpy as np

from playground.hailo_probe import probe
from playground.vision.detector import Detection, Detector, UnavailableHailoDetector, build_detector

from .types import Observation


def make_detector() -> Detector:
    """Prefer live Hailo when ready; otherwise explicit empty fallback."""
    return build_detector()


def detections_to_dicts(detections: list[Detection]) -> tuple[dict[str, Any], ...]:
    return tuple(d.to_dict() for d in detections)


def observe(
    frame: np.ndarray | None,
    *,
    detector: Detector | None = None,
    sonar_mm: float | None = None,
) -> Observation:
    status = probe()
    hailo_ready = bool(status.get("ready"))
    det = detector or make_detector()
    detections: list[Detection] = []
    notes = ""
    if frame is None:
        notes = "no_frame"
    else:
        detections = list(det.detect(frame))
        if isinstance(det, UnavailableHailoDetector):
            notes = det.reason
    return Observation(
        t_mono=monotonic(),
        detections=detections_to_dicts(detections),
        sonar_mm=sonar_mm,
        camera_ok=frame is not None,
        hailo_ready=hailo_ready,
        notes=notes,
    )
