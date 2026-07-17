from argparse import Namespace

from scripts.pi_agent_gate import build_remote_command, motion_trial_requires_allow_wheels


def _args(operation: str, **overrides) -> Namespace:
    base = dict(
        operation=operation,
        remote_root="/tmp/tiny_pi_car",
        frames=20,
        interval_s=0.1,
        action="forward",
        duration_s=0.8,
        speed_mm_s=40.0,
        yaw=0.35,
        stage="free",
        ttl_s=3600,
        stop_masterpi=False,
        no_sonar=False,
        allow_wheels=False,
        remote_cmd="",
    )
    base.update(overrides)
    return Namespace(**base)


def test_status_reports_devices():
    command = build_remote_command(_args("status"))
    assert "systemctl is-active masterpi" in command
    assert "hailo_device" in command
    assert "camera:video0" in command or "camera:other_nodes" in command
    assert "VERSION_CODENAME" in command


def test_perception_runs_log_detections():
    command = build_remote_command(_args("perception"))
    assert "--frames 20" in command
    assert "log_detections" in command


def test_camera_snap_uses_helper():
    command = build_remote_command(_args("camera-snap"))
    assert "playground.camera_snap" in command


def test_emergency_stop_stops_motors():
    command = build_remote_command(_args("emergency-stop"))
    assert "systemctl stop masterpi" in command
    assert "playground.micro_move stop" in command


def test_motion_trial_blocked_without_allow_wheels():
    for action in ("forward", "reverse", "yaw_left", "yaw_right"):
        err = motion_trial_requires_allow_wheels(_args("motion-trial", action=action))
        assert err is not None
        assert "NIGHT_CARD" in err
        assert "--allow-wheels" in err


def test_motion_trial_has_cleanup_trap_when_wheels_allowed():
    command = build_remote_command(_args("motion-trial", allow_wheels=True))
    assert "playground.autoresearch.physical_trial forward" in command
    assert "--allow-wheels" in command
    assert "trap cleanup EXIT" in command
    assert "playground.micro_move stop" in command


def test_motion_trial_remote_command_forwards_allow_wheels():
    without = build_remote_command(_args("motion-trial", allow_wheels=False))
    assert "--allow-wheels" not in without

    with_flag = build_remote_command(_args("motion-trial", allow_wheels=True))
    assert "--allow-wheels" in with_flag


def test_agents_can_arm_via_gate():
    command = build_remote_command(_args("arm"))
    assert "playground.autoresearch.motion_arm arm" in command
