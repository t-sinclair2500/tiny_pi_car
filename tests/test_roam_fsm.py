"""RoamFSM pure unit tests — no motors."""

from __future__ import annotations

from time import monotonic

from playground.autonomy.roam_fsm import (
    RoamFSM,
    pick_primary_detection,
    suggested_yaw_from_detections,
)
from playground.autonomy.types import Observation


def test_suggested_yaw_turns_toward_off_center_target():
    yaw = suggested_yaw_from_detections(
        ({"label": "cup", "score": 0.9, "bbox": (0.7, 0.2, 0.9, 0.6)},)
    )
    assert yaw < 0.0  # target right => turn right (negative yaw)


def test_suggested_yaw_deadband():
    yaw = suggested_yaw_from_detections(
        ({"label": "cup", "score": 0.9, "bbox": (0.46, 0.2, 0.54, 0.6)},)
    )
    assert yaw == 0.0


def test_pick_primary_prefers_person_over_higher_score_cup():
    dets = (
        {"label": "cup", "score": 0.95, "bbox": (0.1, 0.2, 0.3, 0.6)},
        {"label": "person", "score": 0.70, "bbox": (0.5, 0.2, 0.7, 0.6)},
    )
    primary = pick_primary_detection(dets)
    assert primary is not None
    assert primary["label"] == "person"


def test_pick_primary_highest_score_when_no_person():
    dets = (
        {"label": "cup", "score": 0.60, "bbox": (0.1, 0.2, 0.3, 0.6)},
        {"label": "bottle", "score": 0.90, "bbox": (0.5, 0.2, 0.7, 0.6)},
    )
    primary = pick_primary_detection(dets)
    assert primary is not None
    assert primary["label"] == "bottle"


def test_roam_align_command_on_detection():
    fsm = RoamFSM(max_steps=4)
    obs = Observation(
        t_mono=monotonic(),
        detections=({"label": "cup", "score": 0.9, "bbox": (0.1, 0.2, 0.3, 0.6)},),
        camera_ok=True,
        hailo_ready=True,
    )
    cmd = fsm.step(obs)
    assert cmd.chassis_mm_s == 0.0
    assert cmd.yaw > 0.0  # target left => positive yaw
    assert "align" in cmd.reason or "hold" in cmd.reason
