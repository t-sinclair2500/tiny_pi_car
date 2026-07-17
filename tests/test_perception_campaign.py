from __future__ import annotations

import json

import cv2
import numpy as np

from playground.autoresearch.perception_candidate_run import run_candidate
from playground.autoresearch.perception_evaluate import build_sandbox_command, evaluate_candidate
from playground.vision.detector import Detection


class FakeDetector:
    def detect(self, frame: np.ndarray) -> list[Detection]:
        assert frame.shape == (12, 16, 3)
        return [Detection("cup", 0.9, (1.0, 2.0, 8.0, 10.0))]


def test_candidate_runner_emits_model_independent_prediction_schema(tmp_path):
    image_path = tmp_path / "frame.png"
    assert cv2.imwrite(str(image_path), np.full((12, 16, 3), 80, dtype=np.uint8))
    output = tmp_path / "predictions.jsonl"
    count = run_candidate(
        detector=FakeDetector(),
        records=[{"frame_id": "frame-1", "image_path": str(image_path)}],
        output_path=output,
    )
    record = json.loads(output.read_text(encoding="utf-8"))
    assert count == 1
    assert record["frame_id"] == "frame-1"
    assert record["latency_ms"] >= 0.0
    assert record["detections"] == [
        {"bbox_px": [1.0, 2.0, 8.0, 10.0], "label": "cup", "score": 0.9}
    ]


def test_sandbox_command_has_no_network_or_ground_truth_binding(tmp_path):
    workspace = tmp_path / "workspace"
    prefix = tmp_path / "venv"
    manifest = tmp_path / "input" / "images.jsonl"
    output = tmp_path / "output"
    image = tmp_path / "heldout.png"
    for directory in (workspace, prefix, manifest.parent, output):
        directory.mkdir(parents=True, exist_ok=True)
    image.write_bytes(b"image")
    manifest.write_text("{}\n", encoding="utf-8")
    command = build_sandbox_command(
        workspace=workspace,
        python_prefix=prefix,
        images=[(image, "/data/000000.png")],
        image_manifest=manifest,
        output_dir=output,
        candidate_module="playground.experiments.perception.candidate",
    )
    joined = " ".join(command)
    assert "--unshare-net" in command
    assert "/dev/ttyAMA0" not in joined
    assert "ground-truth" not in joined
    assert str(image) in command
    assert "/out/predictions.jsonl" in command


def test_evaluator_scores_synthetic_candidate(tmp_path):
    image_path = tmp_path / "heldout.png"
    frame = np.zeros((100, 120, 3), dtype=np.uint8)
    frame[20:70, 30:80, 1] = 255
    assert cv2.imwrite(str(image_path), frame)
    truth_path = tmp_path / "private-ground-truth.jsonl"
    truth_path.write_text(
        json.dumps(
            {
                "frame_id": "green-cup",
                "image_path": str(image_path),
                "objects": [{"label": "cup", "bbox_px": [30, 20, 80, 70]}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    payload, _output = evaluate_candidate(
        ground_truth_path=truth_path,
        target_labels=frozenset({"cup"}),
        iou_threshold=0.5,
        latency_budget_ms=100.0,
        min_target_recall=1.0,
        candidate_module="playground.autoresearch.synthetic_perception_candidate",
        keep_predictions=None,
        sandbox=False,
    )
    assert payload["sandboxed"] is False
    assert payload["hard_gates_passed"] is True
    assert payload["target_recall"] == 1.0
    assert payload["candidate"]["metadata"]["test_only"] is True
