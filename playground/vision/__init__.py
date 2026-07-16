"""Portable camera and object-detection primitives for robot experiments."""

from .detector import Detection, Detector, UnavailableHailoDetector, build_detector

__all__ = ["Detection", "Detector", "UnavailableHailoDetector", "build_detector"]
