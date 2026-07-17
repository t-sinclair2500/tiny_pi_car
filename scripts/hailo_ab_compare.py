#!/usr/bin/env python3
"""Compare two Hailo-10H HEFs on the same image set (simple A/B score).

Example:
  .venv/bin/python scripts/hailo_ab_compare.py \\
    --hef-a playground/vision/models/yolov8n.hef \\
    --hef-b .autoresearch/artifacts/yolov8s.hef \\
    --images captures/ab_frames
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _list_images(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    return sorted(p for p in path.rglob("*") if p.suffix.lower() in exts)


def _score_hef(hef: Path, images: list[Path], conf: float) -> dict:
    import cv2

    from playground.vision.detector import HailoHEFDetector

    started = time.perf_counter()
    detector = HailoHEFDetector(hef, score_thresh=conf)
    total = 0
    frames = 0
    latencies: list[float] = []
    try:
        for image in images:
            frame = cv2.imread(str(image))
            if frame is None:
                continue
            t0 = time.perf_counter()
            dets = detector.detect(frame)
            latencies.append(time.perf_counter() - t0)
            total += len(dets)
            frames += 1
    finally:
        detector.close()
    elapsed = time.perf_counter() - started
    return {
        "hef": str(hef),
        "frames": frames,
        "detections": total,
        "mean_dets_per_frame": (total / frames) if frames else 0.0,
        "mean_latency_s": (sum(latencies) / len(latencies)) if latencies else None,
        "elapsed_s": elapsed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hef-a", type=Path, required=True)
    parser.add_argument("--hef-b", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--conf", type=float, default=0.35)
    args = parser.parse_args()
    from playground.vision.models import resolve_hef

    hef_a = resolve_hef(str(args.hef_a)) or args.hef_a
    hef_b = resolve_hef(str(args.hef_b)) or args.hef_b
    images = _list_images(args.images)
    if not images:
        print(json.dumps({"error": "no images", "images": str(args.images)}))
        return 2
    if not Path(hef_a).is_file() or not Path(hef_b).is_file():
        print(json.dumps({"error": "missing hef", "a": str(hef_a), "b": str(hef_b)}))
        return 2
    a = _score_hef(Path(hef_a), images, args.conf)
    b = _score_hef(Path(hef_b), images, args.conf)
    winner = "a" if a["mean_dets_per_frame"] >= b["mean_dets_per_frame"] else "b"
    # Prefer lower latency on ties in detection count.
    if a["mean_dets_per_frame"] == b["mean_dets_per_frame"]:
        la, lb = a["mean_latency_s"] or 1e9, b["mean_latency_s"] or 1e9
        winner = "a" if la <= lb else "b"
    print(json.dumps({"a": a, "b": b, "winner": winner, "frames": len(images)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
