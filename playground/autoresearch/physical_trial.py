"""Run a physical movement trial on the Pi. Soft defaults; always stops at the end.

Chassis/wheel actions (``forward``, ``reverse``, ``yaw_left``, ``yaw_right``) are disabled
by default for perception-only night runs — see ``autoresearch/car/NIGHT_CARD.md``.
Pass ``--allow-wheels`` or set ``TINY_PI_ALLOW_WHEELS=1`` to override.
Arm motion is handled separately via ``playground.autoresearch.motion_arm``.
"""

from __future__ import annotations

import argparse
import os
import json
import math
import signal
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Protocol

from playground.autonomy.robot_io import RobotIO
from playground.autonomy.safety_gate import SafetyGate, StopLease
from playground.autonomy.types import Observation, RobotCommand

from .motion_arm import DEFAULT_ARM_FILE, read_arm_lease

ACTIONS = ("forward", "reverse", "yaw_left", "yaw_right")
CHASSIS_ACTIONS = frozenset(ACTIONS)
ALLOW_WHEELS_ENV = "TINY_PI_ALLOW_WHEELS"
NIGHT_CARD = "autoresearch/car/NIGHT_CARD.md"


def wheels_allowed(*, cli_flag: bool) -> bool:
    return cli_flag or os.environ.get(ALLOW_WHEELS_ENV) == "1"


def chassis_motion_blocked_message() -> str:
    return (
        f"chassis motion blocked for perception-only runs (see {NIGHT_CARD}): "
        f"pass --allow-wheels or set {ALLOW_WHEELS_ENV}=1"
    )
# Soft defaults — agents may raise these via CLI for longer experiments.
DEFAULT_MAX_DURATION_S = 8.0
DEFAULT_MAX_SPEED_MM_S = 120.0
DEFAULT_MAX_YAW = 1.0
CONTROL_PERIOD_S = 0.05
SONAR_HARD_STOP_MM = 180.0
FORWARD_CLEARANCE_MM = 220.0
SONAR_MAX_VALID_MM = 4999.0
DEFAULT_LOG_DIR = Path("/tmp/tiny_pi_car/motion-trials")


class RobotLike(Protocol):
    def __enter__(self) -> RobotLike: ...
    def __exit__(self, *exc: object) -> None: ...
    def read_sonar_mm(self) -> float | None: ...
    def apply(self, cmd: RobotCommand) -> None: ...
    def stop_all(self) -> None: ...


@dataclass(frozen=True)
class TrialConfig:
    action: str
    duration_s: float = 0.8
    speed_mm_s: float = 40.0
    yaw: float = 0.35
    stage: str = "free"
    respect_sonar: bool = True

    def validate(self) -> None:
        if self.action not in ACTIONS:
            raise ValueError(f"action must be one of {ACTIONS}")
        if not 0.01 <= self.duration_s <= DEFAULT_MAX_DURATION_S:
            raise ValueError(f"duration must be between 0.01 and {DEFAULT_MAX_DURATION_S:.1f}s")
        if not 0.0 <= self.speed_mm_s <= DEFAULT_MAX_SPEED_MM_S:
            raise ValueError(f"speed must be between 0 and {DEFAULT_MAX_SPEED_MM_S:.1f} mm/s")
        if not 0.0 <= self.yaw <= DEFAULT_MAX_YAW:
            raise ValueError(f"yaw must be between 0 and {DEFAULT_MAX_YAW:.2f}")


@dataclass(frozen=True)
class TrialResult:
    action: str
    requested_duration_s: float
    executed_steps: int
    stop_reason: str
    minimum_sonar_mm: float | None
    final_stop_sent: bool
    log_path: str


def masterpi_service_active() -> bool:
    result = subprocess.run(
        ["systemctl", "is-active", "masterpi"],
        capture_output=True,
        text=True,
        check=False,
        timeout=3,
    )
    return result.stdout.strip() == "active"


def _desired_command(config: TrialConfig) -> RobotCommand:
    if config.action == "forward":
        return RobotCommand(config.speed_mm_s, 90.0, 0.0, reason="physical_trial")
    if config.action == "reverse":
        return RobotCommand(config.speed_mm_s, 270.0, 0.0, reason="physical_trial")
    yaw = -config.yaw if config.action == "yaw_left" else config.yaw
    return RobotCommand(0.0, 90.0, yaw, reason="physical_trial")


def run_trial(
    config: TrialConfig,
    *,
    arm_file: Path = DEFAULT_ARM_FILE,
    log_dir: Path = DEFAULT_LOG_DIR,
    robot_factory: Callable[..., RobotLike] = RobotIO,
    service_active: Callable[[], bool] = masterpi_service_active,
    sleep: Callable[[float], None] = time.sleep,
    require_arm: bool = False,
) -> TrialResult:
    """Run one timed trial. Always ends with ``stop_all``."""
    config.validate()
    read_arm_lease(arm_file, required_stage=None if config.stage == "free" else config.stage, required=require_arm)
    if service_active():
        raise RuntimeError("masterpi.service owns the UART; stop it first")

    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    log_path = log_dir / f"{stamp}-{time.time_ns() % 1_000_000_000:09d}.jsonl"
    command = _desired_command(config)
    stop_lease = StopLease(ttl_s=0.5, max_speed_mm_s=DEFAULT_MAX_SPEED_MM_S)
    safety = SafetyGate(
        stop_lease,
        sonar_hard_stop_mm=SONAR_HARD_STOP_MM if config.respect_sonar else 1.0,
        sonar_stale_s=0.5,
        max_cmd_speed_mm_s=DEFAULT_MAX_SPEED_MM_S,
    )
    steps = math.ceil(config.duration_s / CONTROL_PERIOD_S)
    executed = 0
    sonar_samples: list[float] = []
    stop_reason = "duration_complete"
    final_stop_sent = False

    def record(event: dict[str, object]) -> None:
        with log_path.open("a") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")

    record({"event": "start", "config": asdict(config), "epoch_s": time.time()})
    try:
        with robot_factory(live=True) as robot:
            try:
                for index in range(steps):
                    sonar = robot.read_sonar_mm()
                    if sonar is not None:
                        sonar_samples.append(sonar)
                    if config.respect_sonar and config.action == "forward":
                        if sonar is not None and sonar < SONAR_MAX_VALID_MM and sonar <= FORWARD_CLEARANCE_MM:
                            stop_reason = "forward_clearance_veto"
                            break
                    stop_lease.renew(owner="opencode-trial")
                    observation = (
                        Observation(t_mono=time.monotonic(), sonar_mm=sonar)
                        if config.respect_sonar and config.action == "forward"
                        else None
                    )
                    allowed = safety.allow(command, observation) if config.respect_sonar else command
                    if allowed is None:
                        stop_reason = f"safety_veto:{safety.last_fault.value}"
                        break
                    robot.apply(allowed)
                    executed += 1
                    record(
                        {
                            "event": "motion_slice",
                            "index": index,
                            "sonar_mm": sonar,
                            "command": asdict(allowed),
                        }
                    )
                    sleep(min(CONTROL_PERIOD_S, config.duration_s - index * CONTROL_PERIOD_S))
            finally:
                robot.stop_all()
                final_stop_sent = True
                record({"event": "final_stop", "reason": stop_reason})
    finally:
        if not final_stop_sent:
            record({"event": "aborted_before_final_stop", "reason": stop_reason})

    return TrialResult(
        action=config.action,
        requested_duration_s=config.duration_s,
        executed_steps=executed,
        stop_reason=stop_reason,
        minimum_sonar_mm=min(sonar_samples) if sonar_samples else None,
        final_stop_sent=final_stop_sent,
        log_path=str(log_path),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=ACTIONS)
    parser.add_argument("--duration-s", type=float, default=0.8)
    parser.add_argument("--speed-mm-s", type=float, default=40.0)
    parser.add_argument("--yaw", type=float, default=0.35)
    parser.add_argument("--stage", default="free")
    parser.add_argument("--no-sonar", action="store_true")
    parser.add_argument("--require-arm", action="store_true")
    parser.add_argument(
        "--allow-wheels",
        action="store_true",
        help=(
            "permit chassis motion (forward/reverse/yaw); "
            f"default off — see {NIGHT_CARD} or set {ALLOW_WHEELS_ENV}=1"
        ),
    )
    args = parser.parse_args()
    if args.action in CHASSIS_ACTIONS and not wheels_allowed(cli_flag=args.allow_wheels):
        parser.error(chassis_motion_blocked_message())

    def interrupted(signum: int, _frame: object) -> None:
        raise RuntimeError(f"motion trial interrupted by signal {signum}")

    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    config = TrialConfig(
        action=args.action,
        duration_s=args.duration_s,
        speed_mm_s=args.speed_mm_s,
        yaw=args.yaw,
        stage=args.stage,
        respect_sonar=not args.no_sonar,
    )
    try:
        result = run_trial(config, require_arm=args.require_arm)
    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(asdict(result), sort_keys=True))
    return 0 if result.executed_steps else 3


if __name__ == "__main__":
    raise SystemExit(main())
