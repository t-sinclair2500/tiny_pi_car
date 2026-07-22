"""Snap → bbox-center yaw decision → short trial → optional post-stop snap."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from playground.autonomy.robot_io import RobotIO
from playground.autonomy.roam_fsm import pick_primary_detection, suggested_yaw_from_detections
from playground.autoresearch.physical_trial import (
    FORWARD_CLEARANCE_MM,
    NIGHT_CARD,
    TrialConfig,
    run_trial,
    wheels_allowed,
)
from playground.vision.snap_and_detect import snap_and_detect_once

DEFAULT_PRE_SNAP = Path("/tmp/tiny_pi_car/vision-guided-pre.jpg")
DEFAULT_PRE_DETS = Path("/tmp/tiny_pi_car/vision-guided-pre.jsonl")
DEFAULT_POST_SNAP = Path("/tmp/tiny_pi_car/vision-guided-post.jpg")
DEFAULT_POST_DETS = Path("/tmp/tiny_pi_car/vision-guided-post.jsonl")
CHASSIS_ACTIONS = ("forward", "yaw_left", "yaw_right")


def _load_detections(path: Path) -> tuple[dict[str, Any], ...]:
    if not path.is_file():
        return ()
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    if not records:
        return ()
    last = records[-1]
    raw = last.get("detections")
    if not isinstance(raw, list):
        return ()
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        bbox = item.get("bbox_px") or item.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        out.append(
            {
                "label": item.get("label"),
                "score": item.get("score"),
                "bbox": bbox,
            }
        )
    return tuple(out)


def _detection_labels(detections: tuple[dict[str, Any], ...]) -> list[str]:
    return [
        f"{d.get('label', '?')}@{float(d.get('score') or 0.0):.2f}"
        for d in detections
    ]


def _read_sonar_mm() -> float | None:
    with RobotIO(live=True) as robot:
        return robot.read_sonar_mm()


def decide_action_and_yaw(
    detections: tuple[dict[str, Any], ...],
    *,
    default_action: str,
    default_yaw: float,
    max_yaw: float,
    deadband: float,
    sonar_mm: float | None,
    forward_clearance_mm: float,
) -> tuple[str, float, float, str, dict[str, Any] | None]:
    """Vision policy: yaw toward off-center target; short forward only when centered and sonar clear."""
    primary = pick_primary_detection(detections)
    if primary is None:
        return default_action, default_yaw, 0.0, "no_detections", None

    yaw_rate = suggested_yaw_from_detections(
        (primary,), deadband=deadband, max_yaw=max_yaw
    )
    if abs(yaw_rate) < 1e-6:
        if (
            sonar_mm is not None
            and sonar_mm < 4999.0
            and sonar_mm > forward_clearance_mm
        ):
            return "forward", 0.0, 0.0, "centered_sonar_clear", primary
        return default_action, default_yaw, 0.0, "centered_sonar_blocked", primary

    if yaw_rate < 0:
        return "yaw_left", abs(yaw_rate), yaw_rate, "bbox_center_align", primary
    return "yaw_right", abs(yaw_rate), yaw_rate, "bbox_center_align", primary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-s", type=float, default=0.6)
    parser.add_argument("--speed-mm-s", type=float, default=40.0)
    parser.add_argument(
        "--default-action",
        choices=CHASSIS_ACTIONS,
        default="yaw_left",
        help="fallback when centered+blocked or no dets (not used for centered+clear)",
    )
    parser.add_argument("--default-yaw", type=float, default=0.3)
    parser.add_argument("--max-yaw", type=float, default=0.15)
    parser.add_argument(
        "--deadband",
        type=float,
        default=0.05,
        help="bbox center error below this is treated as centered (default 0.05)",
    )
    parser.add_argument(
        "--forward-clearance-mm",
        type=float,
        default=FORWARD_CLEARANCE_MM,
        help="pre-trial sonar must exceed this to allow centered forward",
    )
    parser.add_argument("--warmup-frames", type=int, default=3)
    parser.add_argument(
        "--post-warmup-frames",
        type=int,
        default=1,
        help="AE warmup after motion when reusing warm Hailo (default: 1)",
    )
    parser.add_argument(
        "--force-post-vision",
        action="store_true",
        help="run post-stop snap even when pre-trial vision already scored",
    )
    parser.add_argument("--sequential-init", action="store_true")
    parser.add_argument("--no-sonar", action="store_true")
    parser.add_argument("--allow-wheels", action="store_true")
    parser.add_argument("--pre-snap", type=Path, default=DEFAULT_PRE_SNAP)
    parser.add_argument("--pre-dets", type=Path, default=DEFAULT_PRE_DETS)
    parser.add_argument("--post-snap", type=Path, default=DEFAULT_POST_SNAP)
    parser.add_argument("--post-dets", type=Path, default=DEFAULT_POST_DETS)
    args = parser.parse_args()

    if not wheels_allowed(cli_flag=args.allow_wheels):
        parser.error(
            f"chassis motion blocked (see {NIGHT_CARD}): pass --allow-wheels"
        )

    stamp = int(time.time())
    pre_snap = args.pre_snap.with_name(f"{args.pre_snap.stem}-{stamp}{args.pre_snap.suffix}")
    pre_dets = args.pre_dets.with_name(f"{args.pre_dets.stem}-{stamp}{args.pre_dets.suffix}")
    post_snap = args.post_snap.with_name(f"{args.post_snap.stem}-{stamp}{args.post_snap.suffix}")
    post_dets = args.post_dets.with_name(f"{args.post_dets.stem}-{stamp}{args.post_dets.suffix}")

    detector = None
    owns_detector = False
    result = None
    try:
        sonar_mm = _read_sonar_mm() if not args.no_sonar else None
        pre_rc, detector, owns_detector = snap_and_detect_once(
            pre_snap,
            pre_dets,
            warmup_frames=args.warmup_frames,
            sequential_init=args.sequential_init,
            allow_zero_detections=True,
        )
        detections = _load_detections(pre_dets)
        action, yaw, yaw_rate, reason, primary = decide_action_and_yaw(
            detections,
            default_action=args.default_action,
            default_yaw=args.default_yaw,
            max_yaw=args.max_yaw,
            deadband=args.deadband,
            sonar_mm=sonar_mm,
            forward_clearance_mm=args.forward_clearance_mm,
        )
        skip_post_vision = pre_rc == 0 and not args.force_post_vision
        decision = {
            "vision_decision": True,
            "pre_vision_rc": pre_rc,
            "pre_snap": str(pre_snap),
            "pre_dets": str(pre_dets),
            "n_detections": len(detections),
            "detection_labels": _detection_labels(detections),
            "chosen_label": primary.get("label") if primary else None,
            "chosen_score": primary.get("score") if primary else None,
            "pre_sonar_mm": sonar_mm,
            "deadband": args.deadband,
            "chosen_action": action,
            "chosen_yaw": yaw,
            "suggested_yaw_rate": yaw_rate,
            "decision_reason": reason,
            "hailo_reuse": True,
            "skip_post_vision": skip_post_vision,
        }
        print(json.dumps(decision, sort_keys=True), flush=True)

        config = TrialConfig(
            action=action,
            duration_s=args.duration_s,
            speed_mm_s=args.speed_mm_s,
            yaw=yaw,
            respect_sonar=not args.no_sonar,
        )
        result = run_trial(config)
        print(json.dumps(asdict(result), sort_keys=True), flush=True)

        if skip_post_vision:
            print(
                f"vision_scored_from_pre:{pre_snap}",
                flush=True,
            )
        else:
            post_rc, _, _ = snap_and_detect_once(
                post_snap,
                post_dets,
                warmup_frames=args.post_warmup_frames,
                sequential_init=False,
                allow_zero_detections=True,
                detector=detector,
            )
            if post_rc != 0:
                print(f"post_vision_rc:{post_rc}", flush=True)
    finally:
        if owns_detector and detector is not None:
            det_close = getattr(detector, "close", None)
            if callable(det_close):
                det_close()

    return 0 if result is not None and result.executed_steps else 3


if __name__ == "__main__":
    raise SystemExit(main())
