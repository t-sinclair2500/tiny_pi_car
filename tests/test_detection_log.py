from __future__ import annotations

import csv
import json

import numpy as np

from playground.vision.detector import Detection
from playground.vision.log_detections import SCHEMA_VERSION, log_detections


class FakeDetector:
    def detect(self, frame: np.ndarray) -> list[Detection]:
        assert frame.shape == (12, 16, 3)
        return [Detection("bottle", 0.91, (1.0, 2.0, 8.0, 10.0))]


class EmptyDetector:
    def detect(self, frame: np.ndarray) -> list[Detection]:
        return []


def test_jsonl_records_one_frame_object_per_sample(tmp_path) -> None:
    output = tmp_path / "detections.jsonl"
    frame = np.full((12, 16, 3), 64, dtype=np.uint8)

    summary = log_detections(
        detector=FakeDetector(),
        frame_supplier=frame.copy,
        output_path=output,
        frame_count=3,
        source="still:test.jpg",
    )
    records = [json.loads(line) for line in output.read_text().splitlines()]

    assert summary.frame_count == summary.valid_frame_count == 3
    assert summary.detection_count == 3
    assert len(records) == 3
    assert records[0]["schema_version"] == SCHEMA_VERSION
    assert records[0]["brightness_mean"] == 64.0
    assert records[0]["detections"] == [
        {"bbox_px": [1.0, 2.0, 8.0, 10.0], "label": "bottle", "score": 0.91}
    ]


def test_csv_preserves_frames_with_no_detections(tmp_path) -> None:
    output = tmp_path / "detections.csv"
    frame = np.ones((12, 16, 3), dtype=np.uint8)

    summary = log_detections(
        detector=EmptyDetector(),
        frame_supplier=frame.copy,
        output_path=output,
        frame_count=2,
        source="still:test.jpg",
        output_format="csv",
    )
    with output.open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert summary.detection_count == 0
    assert len(rows) == 2
    assert rows[0]["detection_count"] == "0"
    assert rows[0]["label"] == ""
