"""Vision-guided trial policy unit tests — no motors."""

from __future__ import annotations

from playground.autoresearch.vision_guided_trial import decide_action_and_yaw


def test_off_center_bbox_yaws_toward_target():
    dets = ({"label": "person", "score": 0.9, "bbox": (0.7, 0.2, 0.9, 0.6)},)
    action, yaw, rate, reason, primary = decide_action_and_yaw(
        dets,
        default_action="yaw_left",
        default_yaw=0.3,
        max_yaw=0.15,
        deadband=0.05,
        sonar_mm=400.0,
        forward_clearance_mm=220.0,
    )
    assert primary is not None
    assert action == "yaw_left"  # target right => negative yaw_rate
    assert reason == "bbox_center_align"
    assert rate < 0


def test_centered_with_clear_sonar_forwards():
    dets = ({"label": "person", "score": 0.9, "bbox": (0.46, 0.2, 0.54, 0.6)},)
    action, yaw, rate, reason, _primary = decide_action_and_yaw(
        dets,
        default_action="yaw_left",
        default_yaw=0.3,
        max_yaw=0.15,
        deadband=0.05,
        sonar_mm=400.0,
        forward_clearance_mm=220.0,
    )
    assert action == "forward"
    assert reason == "centered_sonar_clear"
    assert yaw == 0.0


def test_centered_blocked_sonar_falls_back():
    dets = ({"label": "person", "score": 0.9, "bbox": (0.46, 0.2, 0.54, 0.6)},)
    action, yaw, _rate, reason, _primary = decide_action_and_yaw(
        dets,
        default_action="yaw_left",
        default_yaw=0.3,
        max_yaw=0.15,
        deadband=0.05,
        sonar_mm=200.0,
        forward_clearance_mm=220.0,
    )
    assert action == "yaw_left"
    assert reason == "centered_sonar_blocked"
    assert yaw == 0.3
