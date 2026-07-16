"""Sample forward sonar and write freshness stats to /tmp (no images).

Default is --simulate (no I2C). Use --live only when MasterPi daemon is stopped
or you accept shared I2C reads of the ultrasonic at 0x77.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from playground.autonomy.robot_io import RobotIO
from playground.autonomy.sensors import SonarGate

DEFAULT_OUT = Path("/tmp/tiny_pi_sonar_stats.json")


def _simulate_samples(n: int, period_s: float) -> list[float]:
    """Deterministic-ish clear-path sequence for dry-run wiring checks."""
    out: list[float] = []
    for i in range(n):
        # Mild oscillation around 700–900 mm
        out.append(800.0 + 50.0 * ((i % 5) - 2))
        time.sleep(period_s)
    return out


def _live_samples(n: int, period_s: float) -> list[float]:
    distances: list[float] = []
    with RobotIO(live=True) as robot:
        try:
            for _ in range(n):
                mm = robot.read_sonar_mm()
                if mm is None:
                    distances.append(float("nan"))
                else:
                    distances.append(float(mm))
                time.sleep(period_s)
        finally:
            robot.stop_all()
    return distances


def summarize(distances: list[float], *, period_s: float, mode: str, hard_stop_mm: float) -> dict:
    gate = SonarGate(hard_stop_mm=hard_stop_mm)
    ages: list[float] = []
    fresh_flags: list[bool] = []
    clear_flags: list[bool] = []
    t0 = time.monotonic()
    for i, mm in enumerate(distances):
        if mm != mm:  # NaN
            gate.reset()
            fresh_flags.append(False)
            clear_flags.append(False)
            ages.append(float("nan"))
            continue
        sample = gate.update(mm, t_mono=t0 + i * period_s)
        # Recompute age against "now" at end of batch for report; use period as proxy
        ages.append(sample.age_s if i == len(distances) - 1 else 0.0)
        fresh_flags.append(gate.fresh())
        clear_flags.append(gate.clear_to_move())

    valid = [d for d in distances if d == d]
    rejected = [d for d in distances if d == d and d >= 4999.0]
    usable = [d for d in valid if d < 4999.0]
    return {
        "t_wall": time.time(),
        "mode": mode,
        "n_requested": len(distances),
        "n_valid": len(usable),
        "n_dropout_nan": sum(1 for d in distances if d != d),
        "n_rejected_invalid": len(rejected),
        "period_s": period_s,
        "hard_stop_mm": hard_stop_mm,
        "distance_mm": {
            "min": min(usable) if usable else None,
            "max": max(usable) if usable else None,
            "mean": statistics.fmean(usable) if usable else None,
            "median": statistics.median(usable) if usable else None,
            "stdev": statistics.pstdev(usable) if len(usable) > 1 else 0.0,
            "samples": usable[:50],  # cap dump size
        },
        "fresh_ratio": (sum(1 for f in fresh_flags if f) / len(fresh_flags)) if fresh_flags else 0.0,
        "clear_ratio": (sum(1 for c in clear_flags if c) / len(clear_flags)) if clear_flags else 0.0,
        "last_fresh": fresh_flags[-1] if fresh_flags else False,
        "last_clear": clear_flags[-1] if clear_flags else False,
        "last_mm": usable[-1] if usable else None,
        "tune_hint": (
            "Raise SonarGate.hard_stop_mm if false hard-stops; "
            "lower max_age_s if clear_ratio high but SafetyGate still SONAR_STALE."
        ),
    }


def run(*, n: int, period_s: float, live: bool, out: Path, hard_stop_mm: float) -> dict:
    mode = "live" if live else "simulate"
    if live:
        distances = _live_samples(n, period_s)
    else:
        distances = _simulate_samples(n, period_s)
    stats = summarize(distances, period_s=period_s, mode=mode, hard_stop_mm=hard_stop_mm)
    out.write_text(json.dumps(stats, indent=2) + "\n")
    stats["out_path"] = str(out)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=20, help="number of samples")
    parser.add_argument("--period-s", type=float, default=0.05, help="inter-sample delay")
    parser.add_argument("--live", action="store_true", help="read I2C sonar via RobotIO (stops chassis on exit)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--hard-stop-mm", type=float, default=250.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.live:
        print("WARNING: --live opens UART/board; stop MasterPi.py first.", file=sys.stderr)

    result = run(
        n=max(1, args.n),
        period_s=max(0.0, args.period_s),
        live=args.live,
        out=args.out,
        hard_stop_mm=args.hard_stop_mm,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        d = result["distance_mm"]
        print(f"mode={result['mode']} wrote {result['out_path']}")
        print(
            f"valid={result['n_valid']}/{result['n_requested']} "
            f"mean={d['mean']} mm fresh_ratio={result['fresh_ratio']:.2f} "
            f"clear_ratio={result['clear_ratio']:.2f}"
        )
        print(result["tune_hint"])


if __name__ == "__main__":
    main()
