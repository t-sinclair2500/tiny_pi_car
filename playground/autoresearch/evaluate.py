"""Offline deterministic evaluator for editable candidate policies.

Hard gates mirror live SafetyGate-ish limits so reckless candidates cannot
win on progress alone. Caps are soft enough for useful approach policies.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from dataclasses import asdict, dataclass
from typing import Any

from .candidate import Policy

DT_S = 0.25
MAX_STEPS = 80
HANDOFF_MM = 315.0
HARD_STOP_MM = 200.0
MAX_SPEED_MM_S = 120.0
MAX_YAW = 0.8
SEEDS = (7, 19, 31, 43, 71, 101, 131, 173)


@dataclass(frozen=True)
class EvalResult:
    score: float
    hard_gates_passed: bool
    safety_violations: int
    episodes: int
    success_rate: float
    mean_progress: float
    mean_final_alignment: float
    mean_smoothness: float
    policy_errors: int


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _action(raw: Any) -> tuple[float, float]:
    if not isinstance(raw, dict):
        raise TypeError("Policy.step() must return a dictionary")
    return _finite(raw.get("speed_mm_s")), _finite(raw.get("yaw"))


def _run_target_episode(policy: Policy, seed: int) -> dict[str, float | int | bool]:
    rng = random.Random(seed)
    start_distance = rng.uniform(760.0, 1260.0)
    distance = start_distance
    start_error = rng.choice((-1.0, 1.0)) * rng.uniform(0.28, 0.78)
    error = start_error
    visible_streak = 0
    last_yaw = 0.0
    yaw_delta = 0.0
    violations = 0
    policy_errors = 0
    success = False

    dropout_steps = {rng.randrange(12, 28), rng.randrange(35, 52)}
    camera_fail_at = rng.randrange(24, 55) if seed % 4 == 3 else None
    stale_at = rng.randrange(18, 48) if seed % 5 == 1 else None

    for step in range(MAX_STEPS):
        camera_ok = camera_fail_at is None or step < camera_fail_at
        visible = camera_ok and step not in dropout_steps
        visible_streak = visible_streak + 1 if visible else 0
        confirmed = visible_streak >= 3
        sonar_age_s = 0.5 if stale_at is not None and step == stale_at else 0.05
        obs = {
            "step": step,
            "camera_ok": camera_ok,
            "hailo_ready": True,
            "target_confirmed": confirmed,
            "target_x_error": error if visible else None,
            "target_area": min(0.9, 90.0 / max(distance, 1.0)),
            "sonar_mm": distance,
            "sonar_age_s": sonar_age_s,
        }
        try:
            speed, yaw = _action(policy.step(obs))
        except Exception:
            speed, yaw = 0.0, 0.0
            policy_errors += 1

        must_stop_all = (
            not camera_ok or sonar_age_s > 0.35 or distance <= HARD_STOP_MM
        )
        if (
            speed < 0.0
            or speed > MAX_SPEED_MM_S
            or abs(yaw) > MAX_YAW
            or (must_stop_all and (speed > 1e-9 or abs(yaw) > 1e-9))
            or (not confirmed and speed > 1e-9)
        ):
            violations += 1

        speed = max(0.0, min(MAX_SPEED_MM_S, speed))
        yaw = max(-MAX_YAW, min(MAX_YAW, yaw))
        if must_stop_all:
            speed = 0.0
            yaw = 0.0
        elif not confirmed:
            speed = 0.0

        yaw_delta += abs(yaw - last_yaw)
        last_yaw = yaw
        error += yaw * DT_S * 4.6
        error += rng.uniform(-0.004, 0.004)
        error = max(-1.0, min(1.0, error))
        distance = max(0.0, distance - speed * DT_S * 1.35)

        if distance <= HANDOFF_MM and abs(error) <= 0.10 and speed <= 1e-9:
            success = True
            break

        # A permanent camera failure is a safety episode, not an approach failure.
        if camera_fail_at is not None and step >= camera_fail_at + 3:
            break

    required_travel = max(1.0, start_distance - HANDOFF_MM)
    progress = max(0.0, min(1.0, (start_distance - distance) / required_travel))
    alignment = max(0.0, 1.0 - abs(error))
    smoothness = max(0.0, 1.0 - yaw_delta / 4.0)
    return {
        "success": success,
        "progress": progress,
        "alignment": alignment,
        "smoothness": smoothness,
        "violations": violations,
        "policy_errors": policy_errors,
    }


def _run_guard_episode(policy: Policy, seed: int) -> dict[str, float | int | bool]:
    """Probe no-target, stale sonar, Hailo loss, and hard-stop behavior."""
    rng = random.Random(seed + 10_000)
    violations = 0
    policy_errors = 0
    last_yaw = 0.0
    yaw_delta = 0.0
    stopped_after_scan = False

    for step in range(20):
        mode = seed % 4
        camera_ok = mode != 0 or step < 5
        hailo_ready = mode != 1 or step < 5
        sonar_mm = 240.0 if mode == 2 and step >= 5 else rng.uniform(500.0, 900.0)
        sonar_age_s = 0.6 if mode == 3 and step >= 5 else 0.04
        obs = {
            "step": step,
            "camera_ok": camera_ok,
            "hailo_ready": hailo_ready,
            "target_confirmed": False,
            "target_x_error": None,
            "target_area": 0.0,
            "sonar_mm": sonar_mm,
            "sonar_age_s": sonar_age_s,
        }
        try:
            speed, yaw = _action(policy.step(obs))
        except Exception:
            speed, yaw = 0.0, 0.0
            policy_errors += 1
        must_stop = not camera_ok or not hailo_ready or sonar_mm <= HARD_STOP_MM or sonar_age_s > 0.35
        if speed < 0.0 or speed > MAX_SPEED_MM_S or abs(yaw) > MAX_YAW:
            violations += 1
        if speed > 1e-9 or (must_stop and abs(yaw) > 1e-9):
            violations += 1
        if step >= 12 and abs(yaw) <= 1e-9:
            stopped_after_scan = True
        yaw_delta += abs(yaw - last_yaw)
        last_yaw = yaw

    return {
        "success": stopped_after_scan,
        "progress": 1.0 if stopped_after_scan else 0.0,
        "alignment": 1.0,
        "smoothness": max(0.0, 1.0 - yaw_delta / 3.0),
        "violations": violations,
        "policy_errors": policy_errors,
    }


def evaluate() -> EvalResult:
    records: list[dict[str, float | int | bool]] = []
    for seed in SEEDS:
        policy = Policy()
        policy.reset()
        records.append(_run_target_episode(policy, seed))
        policy = Policy()
        policy.reset()
        records.append(_run_guard_episode(policy, seed))

    violations = sum(int(row["violations"]) for row in records)
    policy_errors = sum(int(row["policy_errors"]) for row in records)
    hard_gates_passed = violations == 0 and policy_errors == 0
    success_rate = statistics.fmean(float(bool(row["success"])) for row in records)
    progress = statistics.fmean(float(row["progress"]) for row in records)
    alignment = statistics.fmean(float(row["alignment"]) for row in records)
    smoothness = statistics.fmean(float(row["smoothness"]) for row in records)
    score = 45.0 * success_rate + 30.0 * progress + 15.0 * alignment + 10.0 * smoothness
    if not hard_gates_passed:
        score = min(score, 0.0) - 10.0 * violations - 25.0 * policy_errors
    return EvalResult(
        score=round(score, 6),
        hard_gates_passed=hard_gates_passed,
        safety_violations=violations,
        episodes=len(records),
        success_rate=round(success_rate, 6),
        mean_progress=round(progress, 6),
        mean_final_alignment=round(alignment, 6),
        mean_smoothness=round(smoothness, 6),
        policy_errors=policy_errors,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit one machine-readable JSON object")
    args = parser.parse_args()
    result = asdict(evaluate())
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        for key, value in result.items():
            print(f"{key}: {value}")
    return 0 if result["hard_gates_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
