"""One camera open: save a JPEG and log a single Hailo detection frame."""

from __future__ import annotations

import argparse
import concurrent.futures
from pathlib import Path

import cv2

from playground.vision.detector import Detector, UnavailableHailoDetector, build_detector
from playground.vision.log_detections import _camera_supplier, log_detections


def _grab_warmed_frame(device: str, warmup_frames: int) -> tuple[object | None, object | None]:
    """Open camera, AE-warmup, return (frame, supplier) — caller must close supplier."""
    supplier = _camera_supplier(device, warmup_frames=warmup_frames)
    frame = supplier()
    return frame, supplier


def _parallel_capture_and_detector(
    device: str, warmup_frames: int, *, sequential: bool = False
) -> tuple[object | None, object | None, Detector]:
    """Overlap V4L2 warmup/read with Hailo VDevice+HEF init unless sequential."""
    if sequential:
        frame, supplier = _grab_warmed_frame(device, warmup_frames)
        return frame, supplier, build_detector()

    supplier_holder: list[object] = []

    def capture() -> object | None:
        frame, supplier = _grab_warmed_frame(device, warmup_frames)
        supplier_holder.append(supplier)
        return frame

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        frame_future = pool.submit(capture)
        detector_future = pool.submit(build_detector)
        frame = frame_future.result()
        detector = detector_future.result()
    supplier = supplier_holder[0] if supplier_holder else None
    return frame, supplier, detector


def snap_and_detect_once(
    snap_output: Path,
    dets_output: Path,
    *,
    device: str = "/dev/video0",
    warmup_frames: int = 5,
    sequential_init: bool = False,
    allow_zero_detections: bool = False,
    detector: Detector | None = None,
) -> tuple[int, Detector | None, bool]:
    """Capture one frame, run Hailo once, write JPEG + JSONL.

    When ``detector`` is None, builds (and owns) a new detector. When reusing a
    prior detector, skips VDevice/HEF init — the main win for vision-guided trials.
    Returns ``(exit_code, detector, owns_detector)``.
    """
    if warmup_frames < 1:
        raise ValueError("warmup_frames must be at least 1")

    snap_output.parent.mkdir(parents=True, exist_ok=True)
    dets_output.parent.mkdir(parents=True, exist_ok=True)

    owns_detector = detector is None
    if owns_detector:
        frame, supplier, detector = _parallel_capture_and_detector(
            device, warmup_frames, sequential=sequential_init
        )
    else:
        frame, supplier = _grab_warmed_frame(device, warmup_frames)
        assert detector is not None

    try:
        if frame is None or frame.size == 0:
            print("camera_snap:failed", flush=True)
            return 3, detector, owns_detector
        if not cv2.imwrite(str(snap_output), frame):
            print("camera_snap:write_failed", flush=True)
            return 3, detector, owns_detector

        unavailable = isinstance(detector, UnavailableHailoDetector)
        if unavailable:
            print(f"WARNING: detector unavailable: {getattr(detector, 'reason', '')}", flush=True)

        captured = frame.copy()

        def still_supplier():
            return captured

        summary = log_detections(
            detector=detector,
            frame_supplier=still_supplier,
            output_path=dets_output,
            frame_count=1,
            source=f"camera:{device}",
            detector_status="unavailable" if unavailable else "ready",
        )

        if summary.valid_frame_count != 1:
            return 3, detector, owns_detector
        if summary.detection_count == 0 and not unavailable and not allow_zero_detections:
            return 3, detector, owns_detector
    finally:
        if supplier is not None:
            supplier.close()

    print(f"vision_snap:{snap_output}", flush=True)
    print(f"vision_dets:{dets_output}", flush=True)
    return 0, detector, owns_detector


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snap-output", type=Path, required=True)
    parser.add_argument("--dets-output", type=Path, required=True)
    parser.add_argument("--device", default="/dev/video0")
    parser.add_argument("--warmup-frames", type=int, default=5)
    parser.add_argument(
        "--allow-zero-detections",
        action="store_true",
        help="do not fail when zero boxes are logged",
    )
    parser.add_argument(
        "--sequential-init",
        action="store_true",
        help="warm camera then init Hailo serially (A/B vs parallel overlap)",
    )
    args = parser.parse_args()

    rc, detector, owns = snap_and_detect_once(
        args.snap_output,
        args.dets_output,
        device=args.device,
        warmup_frames=args.warmup_frames,
        sequential_init=args.sequential_init,
        allow_zero_detections=args.allow_zero_detections,
    )
    if owns and detector is not None:
        det_close = getattr(detector, "close", None)
        if callable(det_close):
            det_close()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
