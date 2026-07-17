from pathlib import Path

from playground.autoresearch.physical_trial import TrialConfig, run_trial
from playground.autonomy.types import RobotCommand


class FakeRobot:
    def __init__(self, *, live: bool, sonar: list[float | None]) -> None:
        assert live is True
        self.sonar = iter(sonar)
        self.applied: list[RobotCommand] = []
        self.stops = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read_sonar_mm(self) -> float | None:
        return next(self.sonar)

    def apply(self, cmd: RobotCommand) -> None:
        self.applied.append(cmd)

    def stop_all(self) -> None:
        self.stops += 1


def test_forward_trial_runs_and_always_stops(tmp_path: Path):
    robot = FakeRobot(live=True, sonar=[900.0, 800.0, 700.0])
    result = run_trial(
        TrialConfig("forward", duration_s=0.11, speed_mm_s=20.0, stage="free"),
        arm_file=tmp_path / "missing-arm.json",
        log_dir=tmp_path / "logs",
        robot_factory=lambda **_kwargs: robot,
        service_active=lambda: False,
        sleep=lambda _seconds: None,
    )
    assert len(robot.applied) == 3
    assert robot.stops == 1
    assert result.executed_steps == 3
    assert result.final_stop_sent is True
    assert result.stop_reason == "duration_complete"


def test_forward_clearance_veto_sends_stop(tmp_path: Path):
    robot = FakeRobot(live=True, sonar=[150.0])
    result = run_trial(
        TrialConfig("forward", duration_s=0.05, stage="free"),
        arm_file=tmp_path / "missing-arm.json",
        log_dir=tmp_path / "logs",
        robot_factory=lambda **_kwargs: robot,
        service_active=lambda: False,
        sleep=lambda _seconds: None,
    )
    assert robot.applied == []
    assert robot.stops == 1
    assert result.stop_reason == "forward_clearance_veto"
    assert result.final_stop_sent is True


def test_trial_refuses_when_masterpi_owns_uart(tmp_path: Path):
    robot = FakeRobot(live=True, sonar=[900.0])
    try:
        run_trial(
            TrialConfig("forward", duration_s=0.05),
            arm_file=tmp_path / "x.json",
            log_dir=tmp_path / "logs",
            robot_factory=lambda **_kwargs: robot,
            service_active=lambda: True,
            sleep=lambda _seconds: None,
        )
        raised = False
    except RuntimeError as exc:
        raised = True
        assert "masterpi" in str(exc)
    assert raised
