"""Grab one camera frame to a JPEG path (host or Pi)."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from playground.vision.camera import grab_frame


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/tmp/tiny_pi_car/snap.jpg"))
    parser.add_argument("--device", default="/dev/video0")
    parser.add_argument("--warmup-frames", type=int, default=25)
    args = parser.parse_args()
    frame = grab_frame(args.device, warmup_frames=max(1, args.warmup_frames))
    if frame is None:
        print("camera_snap:failed", flush=True)
        return 3
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.output), frame):
        print("camera_snap:write_failed", flush=True)
        return 3
    print(f"result:{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
