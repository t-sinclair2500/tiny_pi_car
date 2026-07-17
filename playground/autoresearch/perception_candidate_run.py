"""Locked image-only runner for an editable perception candidate."""

from __future__ import annotations

import argparse
import importlib
import json
import time
from pathlib import Path
from typing import Any


def _load_records(path: Path) -> list[dict[str, Any]]:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not records:
        raise ValueError("image manifest is empty")
    for row in records:
        if not isinstance(row.get("frame_id"), str) or not isinstance(row.get("image_path"), str):
            raise ValueError("each image row needs string frame_id and image_path")
    return records


def _detection_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        label = item.get("label")
        score = item.get("score", 0.0)
        bbox = item.get("bbox_px", item.get("bbox"))
    else:
        label = getattr(item, "label", None)
        score = getattr(item, "score", 0.0)
        bbox = getattr(item, "bbox", None)
    if not isinstance(label, str) or bbox is None or len(bbox) != 4:
        raise ValueError("candidate detections need label, score, and four-value bbox")
    return {
        "label": label,
        "score": round(float(score), 6),
        "bbox_px": [round(float(value), 3) for value in bbox],
    }


def run_candidate(
    *,
    detector: Any,
    records: list[dict[str, Any]],
    output_path: Path,
) -> int:
    import cv2

    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8") as output:
        for row in records:
            frame = cv2.imread(str(row["image_path"]))
            if frame is None or frame.size == 0:
                raise ValueError(f"could not read held-out image: {row['image_path']}")
            started = time.perf_counter()
            detections = [_detection_dict(item) for item in detector.detect(frame)]
            latency_ms = (time.perf_counter() - started) * 1000.0
            output.write(
                json.dumps(
                    {
                        "frame_id": row["frame_id"],
                        "latency_ms": round(latency_ms, 6),
                        "detections": detections,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument(
        "--candidate-module",
        default="playground.experiments.perception.candidate",
    )
    parser.add_argument("--metadata", type=Path)
    args = parser.parse_args()

    module = importlib.import_module(args.candidate_module)
    factory = getattr(module, "create_detector", None)
    if not callable(factory):
        raise RuntimeError(f"{args.candidate_module} must define create_detector()")
    detector = factory()
    try:
        count = run_candidate(
            detector=detector,
            records=_load_records(args.images),
            output_path=args.predictions,
        )
    finally:
        close = getattr(detector, "close", None)
        if callable(close):
            close()

    if args.metadata:
        metadata = getattr(module, "METADATA", {})
        args.metadata.write_text(
            json.dumps({"candidate_module": args.candidate_module, "metadata": metadata}, sort_keys=True),
            encoding="utf-8",
        )
    print(json.dumps({"frames": count, "predictions": str(args.predictions)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
