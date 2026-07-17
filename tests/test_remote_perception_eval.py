from __future__ import annotations

import json

import cv2
import numpy as np

import scripts.remote_perception_eval as remote_eval


def test_stage_dataset_rewrites_images_to_remote_marker(monkeypatch, tmp_path):
    image = tmp_path / "source.png"
    assert cv2.imwrite(str(image), np.full((8, 10, 3), 50, dtype=np.uint8))
    truth = tmp_path / "truth.jsonl"
    truth.write_text(
        json.dumps(
            {
                "frame_id": "one",
                "image_path": str(image),
                "objects": [{"label": "cup", "bbox_px": [1, 1, 6, 7]}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(remote_eval, "STAGING", tmp_path / "staging")
    bundle, dataset_id = remote_eval.stage_dataset(truth)
    record = json.loads((bundle / "ground_truth.jsonl").read_text(encoding="utf-8"))
    assert len(dataset_id) == 16
    assert record["image_path"].startswith("__REMOTE_DATASET__/images/")
    assert (bundle / "images" / "000000.png").is_file()


def test_remote_eval_is_static_hailo_only_and_does_not_expose_uart():
    command = remote_eval.remote_eval_command(
        remote_root="/tmp/tiny_pi_car",
        remote_dataset_parent="/tmp/tiny_pi_car_autoresearch_datasets",
        dataset_id="0123456789abcdef",
        target_labels=["cup", "bottle"],
        latency_budget_ms=100.0,
        min_target_recall=0.5,
        artifact={"filename": "yolov8n.hef"},
    )
    assert "perception_evaluate" in command
    assert "test -e /dev/h1x-0" in command
    assert "--no-sandbox" in command
    assert "command -v bwrap" not in command
    assert "yolov8n.hef" in command
    assert "--target-label cup" in command
    assert "/dev/ttyAMA0" not in command
    assert "micro_move" not in command
    assert "systemctl stop" not in command


def test_deploy_excludes_models_and_only_syncs_playground_research_code():
    command = remote_eval.deploy_command("rpicarbox-1", "/tmp/tiny_pi_car")
    assert command[0] == "rsync"
    assert "models" in command
    assert "./playground/autoresearch/" in command
    assert "./playground/experiments/" in command
    assert all("MasterPi" not in item for item in command)


def test_remote_directory_setup_creates_only_research_paths():
    command = remote_eval.ensure_remote_dirs_command(
        "rpicarbox-1", "/tmp/tiny_pi_car", "/tmp/tiny_pi_car_autoresearch_datasets"
    )
    joined = " ".join(command)
    assert "playground/vision/models" in joined
    assert "tiny_pi_car_autoresearch_datasets" in joined
    assert "/home/pi/MasterPi" not in joined


def test_candidate_artifact_is_literal_safe_and_names_a_hef(tmp_path):
    candidate = tmp_path / "candidate.py"
    candidate.write_text(
        'METADATA = {"artifact": {"filename": "yolov11n.hef", '
        '"sha256": "' + "a" * 64 + '", "source_url": "https://example.test/y.hef"}}\n',
        encoding="utf-8",
    )
    artifact = remote_eval.load_candidate_artifact(candidate)
    assert artifact["filename"] == "yolov11n.hef"
    assert artifact["sha256"] == "a" * 64


def test_candidate_artifact_rejects_nonliteral_code(tmp_path):
    import pytest

    candidate = tmp_path / "candidate.py"
    candidate.write_text(
        'METADATA = {"artifact": load_untrusted_metadata()}\n', encoding="utf-8"
    )
    with pytest.raises((ValueError, TypeError)):
        remote_eval.load_candidate_artifact(candidate)
