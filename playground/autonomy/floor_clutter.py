"""Lower-FOV floor clutter heuristic (soft piles / toys sonar misses)."""

from __future__ import annotations

import cv2
import numpy as np


def floor_clutter_risk(
    frame: np.ndarray,
    *,
    bottom_frac: float = 0.35,
    edge_thresh: float = 18.0,
    bright_frac_thresh: float = 0.12,
) -> tuple[bool, dict[str, float]]:
    """Return (risk, metrics) from bottom band edge energy + contrast.

    Dumb on purpose: tunable thresholds for stream research. High edge density
    or high local contrast in the lower FOV → refuse crawl.
    """
    if frame is None or getattr(frame, "size", 0) == 0:
        return True, {"reason": 1.0, "edge_mean": 0.0, "bright_frac": 0.0}
    h, _w = frame.shape[:2]
    y0 = max(0, int(h * (1.0 - bottom_frac)))
    band = frame[y0:, :]
    gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY) if band.ndim == 3 else band
    edges = cv2.Canny(gray, 40, 120)
    edge_mean = float(np.mean(edges))
    # Fraction of pixels far from band median (texture / clutter).
    med = float(np.median(gray))
    bright_frac = float(np.mean(np.abs(gray.astype(np.float32) - med) > 28.0))
    risk = edge_mean >= edge_thresh or bright_frac >= bright_frac_thresh
    return risk, {
        "edge_mean": edge_mean,
        "bright_frac": bright_frac,
        "edge_thresh": edge_thresh,
        "bright_frac_thresh": bright_frac_thresh,
    }
