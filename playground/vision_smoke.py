"""Check Hailo runtime; optionally grab one camera frame and run detection."""

from __future__ import annotations

from playground.hailo_probe import probe
from playground.vision.camera import grab_frame
from playground.vision.detector import build_detector


def main() -> None:
    status = probe()
    print(f"Hailo model: {status['model']}; runtime ready: {status['ready']}")
    if status.get("warning"):
        print(f"Warning: {status['warning']}")

    frame = grab_frame()
    if frame is None:
        print("Camera: unavailable or busy (no retry loop was started).")
    else:
        print(f"Camera: frame acquired, shape={frame.shape}")

    detector = build_detector()
    reason = getattr(detector, "reason", None)
    print(f"Detector: {type(detector).__name__}" + (f" ({reason})" if reason else ""))

    if frame is not None and reason is None:
        dets = detector.detect(frame)
        print(f"Detections ({len(dets)}):")
        for det in dets[:20]:
            print(f"  {det.label:16s} {det.score:.3f} {det.bbox}")

    if hasattr(detector, "close"):
        detector.close()


if __name__ == "__main__":
    main()
