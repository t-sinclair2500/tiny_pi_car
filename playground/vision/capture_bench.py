"""Bounded camera capture latency benchmark (no Hailo, no motion)."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass

import cv2
import numpy as np

DEFAULT_WARMUP_SWEEP = (5, 10, 15, 20, 25)


@dataclass(frozen=True)
class CaptureStats:
    mean_ms: float
    p50_ms: float
    sample_count: int
    brightness_mean: float | None

    def as_dict(self) -> dict[str, object]:
        return {
            "mean_ms": self.mean_ms,
            "p50_ms": self.p50_ms,
            "sample_count": self.sample_count,
            "brightness_mean": self.brightness_mean,
        }


def _percentile(values: list[float], percentile: int) -> float:
    return round(float(np.percentile(values, percentile)), 3) if values else 0.0


def _stats(values: list[float], brightness: float | None) -> CaptureStats:
    return CaptureStats(
        mean_ms=round(float(np.mean(values)), 3) if values else 0.0,
        p50_ms=_percentile(values, 50),
        sample_count=len(values),
        brightness_mean=round(brightness, 3) if brightness is not None else None,
    )


def _open_capture(device: str) -> cv2.VideoCapture:
    capture = cv2.VideoCapture(device, cv2.CAP_V4L2)
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return capture


def _timed_reopen_capture(
    device: str,
    warmup_frames: int,
    *,
    timeout_s: float,
) -> tuple[float, float | None] | None:
    """Open, warmup, read last frame, release — mirrors grab_frame wall time."""
    started = time.monotonic()
    capture = _open_capture(device)
    try:
        if not capture.isOpened():
            return None
        last = None
        deadline = started + timeout_s
        for _ in range(max(1, warmup_frames)):
            if time.monotonic() > deadline:
                return None
            ok, frame = capture.read()
            if ok and frame is not None:
                last = frame
        if last is None:
            return None
        elapsed_ms = (time.monotonic() - started) * 1000.0
        return elapsed_ms, float(last.mean())
    finally:
        capture.release()


def _bench_reopen_per_frame(
    device: str,
    warmup_frames: int,
    *,
    samples: int,
    timeout_s: float,
) -> CaptureStats:
    timings: list[float] = []
    brightness: float | None = None
    for _ in range(samples):
        result = _timed_reopen_capture(device, warmup_frames, timeout_s=timeout_s)
        if result is None:
            continue
        elapsed_ms, frame_brightness = result
        timings.append(elapsed_ms)
        brightness = frame_brightness
    return _stats(timings, brightness)


def _bench_persistent_reads(
    device: str,
    warmup_frames: int,
    *,
    samples: int,
    timeout_s: float,
) -> tuple[float, CaptureStats]:
    """Hold one VideoCapture; time individual read() after warmup."""
    capture = _open_capture(device)
    warmup_ms = 0.0
    timings: list[float] = []
    brightness: float | None = None
    try:
        if not capture.isOpened():
            return 0.0, _stats([], None)

        warmup_started = time.monotonic()
        deadline = warmup_started + timeout_s
        last = None
        for _ in range(max(1, warmup_frames)):
            if time.monotonic() > deadline:
                break
            ok, frame = capture.read()
            if ok and frame is not None:
                last = frame
        warmup_ms = round((time.monotonic() - warmup_started) * 1000.0, 3)

        for _ in range(samples):
            read_started = time.monotonic()
            ok, frame = capture.read()
            read_ms = (time.monotonic() - read_started) * 1000.0
            if ok and frame is not None:
                timings.append(read_ms)
                last = frame
                brightness = float(last.mean())
            elif read_ms > timeout_s * 1000.0:
                break
    finally:
        capture.release()

    return warmup_ms, _stats(timings, brightness)


def run_bench(
    *,
    device: str,
    samples: int,
    warmup_sweep: tuple[int, ...],
    timeout_s: float,
) -> dict[str, object]:
    reopen: dict[str, object] = {}
    persistent: dict[str, object] = {}

    for warmup_frames in warmup_sweep:
        key = str(warmup_frames)
        reopen[key] = _bench_reopen_per_frame(
            device,
            warmup_frames,
            samples=samples,
            timeout_s=timeout_s,
        ).as_dict()
        warmup_ms, read_stats = _bench_persistent_reads(
            device,
            warmup_frames,
            samples=samples,
            timeout_s=timeout_s,
        )
        persistent[key] = {
            "warmup_ms": warmup_ms,
            **read_stats.as_dict(),
        }

    return {
        "device": device,
        "samples_per_mode": samples,
        "timeout_s": timeout_s,
        "warmup_frames_sweep": list(warmup_sweep),
        "reopen_per_frame": reopen,
        "persistent_reads": persistent,
    }


def _parse_warmup_sweep(raw: str) -> tuple[int, ...]:
    values = tuple(int(item.strip()) for item in raw.split(",") if item.strip())
    if not values:
        raise ValueError("warmup sweep must include at least one integer")
    if any(value < 1 for value in values):
        raise ValueError("warmup frames must be at least 1")
    return values


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure camera capture latency: reopen-per-frame vs persistent reads."
    )
    parser.add_argument("--device", default="/dev/video0", help="V4L2 device (default: /dev/video0)")
    parser.add_argument(
        "--samples",
        type=int,
        default=5,
        help="samples per mode/warmup setting (default: 5, max: 20)",
    )
    parser.add_argument(
        "--warmup-sweep",
        default=",".join(str(value) for value in DEFAULT_WARMUP_SWEEP),
        help="comma-separated warmup frame counts (default: 5,10,15,20,25)",
    )
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=2.0,
        help="per-capture timeout in seconds (default: 2.0)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.samples < 1 or args.samples > 20:
        raise SystemExit("--samples must be between 1 and 20")
    if args.timeout_s <= 0:
        raise SystemExit("--timeout-s must be positive")

    warmup_sweep = _parse_warmup_sweep(args.warmup_sweep)
    result = run_bench(
        device=args.device,
        samples=args.samples,
        warmup_sweep=warmup_sweep,
        timeout_s=args.timeout_s,
    )
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    if not any(
        stats.get("sample_count", 0) > 0
        for stats in result["reopen_per_frame"].values()  # type: ignore[union-attr]
    ):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
