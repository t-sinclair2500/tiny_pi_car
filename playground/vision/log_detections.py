"""Bounded COCO detection logger for Session A (no actuator imports)."""

from __future__ import annotations

import argparse
import csv
import json
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional, TextIO

import numpy as np

from playground.vision.detector import Detection, Detector, UnavailableHailoDetector, build_detector

SCHEMA_VERSION = "tiny_pi_car.detect_log.v1"
CSV_FIELDS = (
    "schema_version",
    "run_id",
    "frame_index",
    "captured_at_utc",
    "t_mono_s",
    "source",
    "frame_ok",
    "image_width_px",
    "image_height_px",
    "brightness_mean",
    "capture_ms",
    "inference_ms",
    "latency_ms",
    "detector_status",
    "detection_count",
    "detection_index",
    "label",
    "score",
    "bbox_x1_px",
    "bbox_y1_px",
    "bbox_x2_px",
    "bbox_y2_px",
)


@dataclass(frozen=True)
class LogSummary:
    output_path: Path
    frame_count: int
    valid_frame_count: int
    detection_count: int
    inference_p50_ms: float
    inference_p90_ms: float
    latency_p50_ms: float
    latency_p90_ms: float


FrameSupplier = Callable[[], Optional[np.ndarray]]


def log_detections(
    *,
    detector: Detector,
    frame_supplier: FrameSupplier,
    output_path: Path,
    frame_count: int = 10,
    source: str,
    output_format: str = "jsonl",
    interval_s: float = 0.0,
    detector_status: str = "ready",
) -> LogSummary:
    """Capture and log a finite number of frames, returning latency percentiles."""
    if frame_count < 1:
        raise ValueError("frame_count must be at least 1")
    if interval_s < 0.0:
        raise ValueError("interval_s must be non-negative")
    if output_format not in {"jsonl", "csv"}:
        raise ValueError("output_format must be 'jsonl' or 'csv'")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())
    records: list[dict[str, object]] = []
    inference_samples: list[float] = []
    latency_samples: list[float] = []

    for frame_index in range(frame_count):
        capture_started = time.monotonic()
        frame = frame_supplier()
        captured_at_mono = time.monotonic()
        capture_ms = (captured_at_mono - capture_started) * 1000.0
        captured_at_utc = datetime.now(timezone.utc).isoformat(timespec="milliseconds")

        detections: list[Detection] = []
        inference_ms = 0.0
        if frame is not None and frame.size > 0:
            inference_started = time.monotonic()
            detections = list(detector.detect(frame))
            inference_ms = (time.monotonic() - inference_started) * 1000.0
            inference_samples.append(inference_ms)

        latency_ms = capture_ms + inference_ms
        latency_samples.append(latency_ms)
        height = int(frame.shape[0]) if frame is not None and frame.size > 0 else None
        width = int(frame.shape[1]) if frame is not None and frame.size > 0 else None
        brightness = float(frame.mean()) if frame is not None and frame.size > 0 else None
        records.append(
            {
                "schema_version": SCHEMA_VERSION,
                "run_id": run_id,
                "frame_index": frame_index,
                "captured_at_utc": captured_at_utc,
                "t_mono_s": round(captured_at_mono, 6),
                "source": source,
                "frame_ok": frame is not None and frame.size > 0,
                "image_width_px": width,
                "image_height_px": height,
                "brightness_mean": _rounded(brightness),
                "capture_ms": _rounded(capture_ms),
                "inference_ms": _rounded(inference_ms),
                "latency_ms": _rounded(latency_ms),
                "detector_status": detector_status,
                "detection_count": len(detections),
                "detections": [_detection_record(item) for item in detections],
            }
        )
        if interval_s and frame_index + 1 < frame_count:
            time.sleep(interval_s)

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        if output_format == "jsonl":
            _write_jsonl(handle, records)
        else:
            _write_csv(handle, records)

    return LogSummary(
        output_path=output_path,
        frame_count=frame_count,
        valid_frame_count=sum(bool(record["frame_ok"]) for record in records),
        detection_count=sum(int(record["detection_count"]) for record in records),
        inference_p50_ms=_percentile(inference_samples, 50),
        inference_p90_ms=_percentile(inference_samples, 90),
        latency_p50_ms=_percentile(latency_samples, 50),
        latency_p90_ms=_percentile(latency_samples, 90),
    )


def _detection_record(detection: Detection) -> dict[str, object]:
    return {
        "label": detection.label,
        "score": round(float(detection.score), 6),
        "bbox_px": [round(float(value), 3) for value in detection.bbox],
    }


def _write_jsonl(handle: TextIO, records: Iterable[dict[str, object]]) -> None:
    for record in records:
        handle.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")


def _write_csv(handle: TextIO, records: Iterable[dict[str, object]]) -> None:
    writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for record in records:
        base = {key: record[key] for key in CSV_FIELDS if key in record}
        detections = record["detections"]
        assert isinstance(detections, list)
        if not detections:
            writer.writerow(base)
            continue
        for index, detection in enumerate(detections):
            assert isinstance(detection, dict)
            bbox = detection["bbox_px"]
            assert isinstance(bbox, list)
            writer.writerow(
                {
                    **base,
                    "detection_index": index,
                    "label": detection["label"],
                    "score": detection["score"],
                    "bbox_x1_px": bbox[0],
                    "bbox_y1_px": bbox[1],
                    "bbox_x2_px": bbox[2],
                    "bbox_y2_px": bbox[3],
                }
            )


def _rounded(value: float | None) -> float | None:
    return round(value, 3) if value is not None else None


def _percentile(values: list[float], percentile: int) -> float:
    return round(float(np.percentile(values, percentile)), 3) if values else 0.0


def _default_output(output_format: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("/tmp/tiny_pi_car") / f"detections-{stamp}.{output_format}"


def _still_supplier(path: Path) -> FrameSupplier:
    import cv2

    frame = cv2.imread(str(path))
    if frame is None:
        raise ValueError(f"could not read still image: {path}")
    return frame.copy


def _camera_supplier(device: str) -> FrameSupplier:
    from playground.vision.camera import grab_frame

    return lambda: grab_frame(device=device, warmup_frames=25)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Log a bounded set of COCO detections and capture/inference latency."
    )
    parser.add_argument("--image", type=Path, help="repeat a still image instead of using camera")
    parser.add_argument("--device", default="/dev/video0", help="camera device (default: /dev/video0)")
    parser.add_argument("--frames", type=int, default=10, help="finite frame count (default: 10)")
    parser.add_argument("--interval-s", type=float, default=0.0, help="pause between samples")
    parser.add_argument("--format", choices=("jsonl", "csv"), default="jsonl")
    parser.add_argument("--output", type=Path, help="output path; default is under /tmp/tiny_pi_car")
    parser.add_argument(
        "--allow-unavailable",
        action="store_true",
        help="allow an unavailable detector for Mac/schema smoke only; never satisfies Session A",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.frames < 1:
        raise SystemExit("--frames must be at least 1")
    if args.interval_s < 0:
        raise SystemExit("--interval-s must be non-negative")

    detector = build_detector()
    unavailable = isinstance(detector, UnavailableHailoDetector)
    reason = getattr(detector, "reason", "")
    if unavailable and not args.allow_unavailable:
        raise SystemExit(f"Detector unavailable: {reason}")
    if unavailable:
        print(f"WARNING: detector unavailable; schema smoke only: {reason}")

    output_path = args.output or _default_output(args.format)
    source = f"still:{args.image}" if args.image else f"camera:{args.device}"
    supplier = (
        _still_supplier(args.image)
        if args.image
        else _camera_supplier(args.device)
    )
    try:
        summary = log_detections(
            detector=detector,
            frame_supplier=supplier,
            output_path=output_path,
            frame_count=args.frames,
            source=source,
            output_format=args.format,
            interval_s=args.interval_s,
            detector_status="unavailable" if unavailable else "ready",
        )
    finally:
        close = getattr(detector, "close", None)
        if callable(close):
            close()

    for key, value in asdict(summary).items():
        print(f"{key}: {value}")
    if summary.valid_frame_count != summary.frame_count:
        raise SystemExit("One or more frames were unavailable; log retained for diagnosis")
    if summary.detection_count == 0 and not args.allow_unavailable:
        raise SystemExit("No detections logged; use a COCO bottle/cup/person and retry")


if __name__ == "__main__":
    main()
