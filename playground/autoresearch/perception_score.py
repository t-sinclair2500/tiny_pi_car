"""Score detector prediction JSONL against a frozen object-detection manifest.

This module only scores precomputed results. Model execution can happen on the
host, Pi/Hailo, or another machine as long as it emits the documented schema.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PerceptionScore:
    score: float
    hard_gates_passed: bool
    frames: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    target_recall: float
    latency_p90_ms: float
    missing_prediction_frames: int


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict) or not isinstance(value.get("frame_id"), str):
            raise ValueError(f"{path}:{line_number}: expected object with string frame_id")
        records.append(value)
    if not records:
        raise ValueError(f"empty manifest: {path}")
    return records


def _bbox(item: dict[str, Any]) -> tuple[float, float, float, float]:
    raw = item.get("bbox_px")
    if not isinstance(raw, list) or len(raw) != 4:
        raise ValueError("every object/detection needs bbox_px=[x1,y1,x2,y2]")
    x1, y1, x2, y2 = (float(value) for value in raw)
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def _iou(left: dict[str, Any], right: dict[str, Any]) -> float:
    ax1, ay1, ax2, ay2 = _bbox(left)
    bx1, by1, bx2, by2 = _bbox(right)
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    return intersection / union if union > 0.0 else 0.0


def score_records(
    ground_truth: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    *,
    target_labels: frozenset[str],
    iou_threshold: float = 0.5,
    latency_budget_ms: float = 100.0,
    min_target_recall: float = 0.5,
) -> PerceptionScore:
    predicted_by_id = {str(row["frame_id"]): row for row in predictions}
    if len(predicted_by_id) != len(predictions):
        raise ValueError("prediction frame_id values must be unique")

    tp = fp = fn = target_tp = target_fn = missing = 0
    latencies: list[float] = []
    for truth_frame in ground_truth:
        frame_id = str(truth_frame["frame_id"])
        truth = truth_frame.get("objects", [])
        if not isinstance(truth, list):
            raise ValueError(f"ground truth {frame_id}: objects must be a list")
        prediction_frame = predicted_by_id.get(frame_id)
        if prediction_frame is None:
            detections: list[dict[str, Any]] = []
            missing += 1
        else:
            raw_detections = prediction_frame.get("detections", [])
            if not isinstance(raw_detections, list):
                raise ValueError(f"prediction {frame_id}: detections must be a list")
            detections = raw_detections
            latency = float(prediction_frame.get("latency_ms", 0.0))
            if latency < 0.0:
                raise ValueError(f"prediction {frame_id}: latency_ms cannot be negative")
            latencies.append(latency)

        candidates: list[tuple[float, int, int]] = []
        for truth_index, truth_item in enumerate(truth):
            truth_label = str(truth_item.get("label", ""))
            for detection_index, detection in enumerate(detections):
                if str(detection.get("label", "")) != truth_label:
                    continue
                overlap = _iou(truth_item, detection)
                if overlap >= iou_threshold:
                    candidates.append((overlap, truth_index, detection_index))

        matched_truth: set[int] = set()
        matched_detections: set[int] = set()
        for _overlap, truth_index, detection_index in sorted(candidates, reverse=True):
            if truth_index in matched_truth or detection_index in matched_detections:
                continue
            matched_truth.add(truth_index)
            matched_detections.add(detection_index)

        tp += len(matched_truth)
        fp += len(detections) - len(matched_detections)
        fn += len(truth) - len(matched_truth)
        for truth_index, truth_item in enumerate(truth):
            if str(truth_item.get("label", "")) in target_labels:
                if truth_index in matched_truth:
                    target_tp += 1
                else:
                    target_fn += 1

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    target_recall = target_tp / (target_tp + target_fn) if target_tp + target_fn else recall
    latency_p90 = _percentile(latencies, 0.9)
    latency_score = max(0.0, 1.0 - latency_p90 / max(latency_budget_ms, 1.0))
    score = 100.0 * (0.45 * target_recall + 0.25 * recall + 0.20 * precision + 0.10 * latency_score)
    hard_gate = (
        missing == 0
        and target_recall >= min_target_recall
        and latency_p90 <= latency_budget_ms * 2.0
    )
    return PerceptionScore(
        score=round(score, 6),
        hard_gates_passed=hard_gate,
        frames=len(ground_truth),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        precision=round(precision, 6),
        recall=round(recall, 6),
        target_recall=round(target_recall, 6),
        latency_p90_ms=round(latency_p90, 6),
        missing_prediction_frames=missing,
    )


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return float("inf")
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * fraction)))
    return float(ordered[index])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--target-label", action="append", default=[])
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--latency-budget-ms", type=float, default=100.0)
    parser.add_argument("--min-target-recall", type=float, default=0.5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not 0.0 < args.iou <= 1.0:
        parser.error("--iou must be in (0, 1]")
    if args.latency_budget_ms <= 0.0:
        parser.error("--latency-budget-ms must be positive")
    if not 0.0 <= args.min_target_recall <= 1.0:
        parser.error("--min-target-recall must be in [0, 1]")

    result = score_records(
        _read_jsonl(args.ground_truth),
        _read_jsonl(args.predictions),
        target_labels=frozenset(args.target_label),
        iou_threshold=args.iou,
        latency_budget_ms=args.latency_budget_ms,
        min_target_recall=args.min_target_recall,
    )
    payload = asdict(result)
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0 if result.hard_gates_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
