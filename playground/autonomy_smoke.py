"""Dry-run autonomy loop: perception + FSM + safety lease. No motors. No Hailo required."""

from __future__ import annotations

import argparse
import json
from time import monotonic

from playground.autonomy.camera_broker import CameraBroker
from playground.autonomy.detect import make_detector, observe
from playground.autonomy.grasp_fsm import GraspFSM
from playground.autonomy.robot_io import RobotIO
from playground.autonomy.roam_fsm import RoamFSM
from playground.autonomy.safety_gate import SafetyGate, StopLease
from playground.autonomy.sensors import SonarGate
from playground.hailo_probe import probe


def run(*, steps: int = 3, use_camera: bool = True, fake_det: bool = False) -> dict[str, object]:
    hailo = probe()
    lease = StopLease(ttl_s=0.5, max_speed_mm_s=25.0)
    gate = SafetyGate(stop_lease=lease, max_cmd_speed_mm_s=25.0)
    sonar_gate = SonarGate()
    roam = RoamFSM(max_steps=steps)
    grasp = GraspFSM(max_steps=steps)
    detector = make_detector()
    log: list[dict[str, object]] = []

    # Simulated sonar clear path for dry-run (no I2C)
    sonar_gate.update(800.0)

    frame = None
    cam_note = "skipped"
    if use_camera:
        try:
            with CameraBroker(prefer_shared_latest=True) as cam:
                packet = cam.latest()
                if packet is not None:
                    frame = packet.frame
                    cam_note = packet.source
                else:
                    cam_note = "no_frame"
        except RuntimeError as exc:
            cam_note = f"broker_busy:{exc}"
    if fake_det and frame is None:
        # Minimal placeholder so observe() marks camera_ok without opening VideoCapture.
        import numpy as np

        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        cam_note = "fake_frame"

    with RobotIO(live=False) as robot:
        for i in range(steps):
            lease.renew(owner="autonomy_smoke")
            obs = observe(frame, detector=detector, sonar_mm=sonar_gate.last.distance_mm if sonar_gate.last else None)
            if fake_det:
                from dataclasses import replace

                obs = replace(
                    obs,
                    detections=(
                        {"label": "fake_cup", "score": 0.9, "bbox": (0.7, 0.3, 0.9, 0.7)},
                    ),
                    camera_ok=True,
                )
            cmd = roam.step(obs)
            allowed = gate.allow(cmd, obs)
            if allowed is None:
                robot.apply(gate.stop_command(reason=gate.last_fault.value))
                log.append(
                    {
                        "i": i,
                        "state": roam.state.name,
                        "veto": gate.last_fault.value,
                        "cmd": cmd.reason,
                    }
                )
            else:
                robot.apply(allowed)
                log.append(
                    {
                        "i": i,
                        "state": roam.state.name,
                        "applied": allowed.reason,
                        "detections": len(obs.detections),
                    }
                )
            _ = grasp.step(obs)
        robot.stop_all()
        # Prove lease expiry veto
        lease.expire()
        blocked = gate.allow(roam.step(observe(frame, detector=detector, sonar_mm=800.0)), None)
        log.append({"lease_expiry_veto": blocked is None, "fault": gate.last_fault.value})

    return {
        "t_mono": monotonic(),
        "hailo_ready": hailo.get("ready"),
        "hailo_model": hailo.get("model"),
        "camera": cam_note,
        "detector": getattr(detector, "reason", type(detector).__name__),
        "commands_recorded": len(robot.commands_sent),
        "last_stop": robot.commands_sent[-1].reason if robot.commands_sent else None,
        "steps": log,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=3)
    parser.add_argument("--no-camera", action="store_true")
    parser.add_argument(
        "--fake-det",
        action="store_true",
        help="inject a fake off-center detection to exercise roam align yaw (no motors)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run(
        steps=max(1, args.steps),
        use_camera=not args.no_camera,
        fake_det=args.fake_det,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Hailo ready: {result['hailo_ready']} ({result['hailo_model']})")
        print(f"Camera: {result['camera']}")
        print(f"Detector: {result['detector']}")
        print(f"Commands recorded (dry-run): {result['commands_recorded']}; last={result['last_stop']}")
        for row in result["steps"]:
            print(f"  {row}")
        print("OK — autonomy_smoke completed without motors / Hailo requirement.")


if __name__ == "__main__":
    main()
