# Hardware stack and interface ownership

**SSOT:** [CURRENT_STATE.md](CURRENT_STATE.md) · **Probed 2026-07-15:** Hailo `/dev/h1x-0` ready; sonar is real I2C hardware (not hypothetical).

## Roles

| Component | Role in autonomy | Repo path / interface |
|---|---|---|
| Raspberry Pi 5 | Orchestrator, FSM, logging, pre/post vision | `playground/autonomy/*` |
| Hailo PCIe | Detector (COCO yolov8n today; later seg/pose) | `1e60:45c4`; `/dev/h1x-0`; probe: `playground/hailo_probe.py` |
| USB camera | Bearing / free-space / verify cues | `/dev/video0`; broker: `playground/autonomy/camera_broker.py` (lock `/tmp/playground_camera_broker.lock`); stock `MasterPi.Camera` uses `VideoCapture(-1)` |
| Ultrasonic | Forward collision gate (**real HW**) | `common.sonar.Sonar`, I2C-1 `0x77`, mm; `sensors.SonarGate`; `watch_sonar` / `sonar_sample` |
| Mecanum | Low-speed translate/yaw | `common.mecanum.MecanumChassis.set_velocity(v, dir, yaw)` |
| 5-DOF arm + gripper | Reach / grasp / carry | `kinematics.arm_move_ik.ArmIK`; gripper PWM servo **1** via `Board.pwm_servo_set_position` |
| Expansion board | Motors, PWM, battery | `common.ros_robot_controller_sdk.Board`, `/dev/ttyAMA0` |

## Call signatures (copy into new APIs)

| API | Signature / units | Autonomy rule |
|---|---|---|
| Chassis | `set_velocity(velocity, direction_deg, angular_rate)` | Cap velocity ≤40 (start 25); dir 90 fwd / 270 rev; always end `0,0,0` |
| Arm IK | `setPitchRangeMoving((x,y,z)_cm, alpha, a1, a2, movetime_ms)` | Abort if returns `False`; wait movetime+settle |
| Gripper | `pwm_servo_set_position(duration_s, [[1, pulse_us]])` | Open ~2000, close ~1200 (provisional); one close per attempt |
| Sonar | `getDistance() → mm` | **5000** = over-range; init/error paths can look like **99999** — never treat as clear; reject ≥4999 in `SonarGate` |
| Battery | `get_battery() → mV` | Gate roam/grasp on low voltage (set cutoff after measuring pack under load); `playground/hello_board.py` |
| Camera broker | exclusive lock + `grab_frame` / shared latest | One owner; stop `MasterPi.py` first |

Stock demos (`MasterPi/mecanum_control/car_*.py`) use velocity **50** and always stop in `finally`-equivalent paths — treat as API examples, **not** autonomy speed targets. Stock avoidance (`functions/avoidance.py`) filters 5 sonar samples and rotates a fixed **0.5 s** at yaw **−0.5**; replace with leased FSM for autonomy.

## Exclusive resources

| Resource | Contenders | Rule |
|---|---|---|
| `/dev/ttyAMA0` | `MasterPi.py`, `rpc_server.py`, `micro_move`, `blanket_fetch`, `RobotIO` | **One** board client. Autonomy runner is sole owner while live |
| Camera `/dev/video0` | stock Camera thread, `fswebcam`, OpenCV capture, `CameraBroker` | One capturer; distribute frames in-process or via agreed latest-frame path |
| I2C sonar `0x77` | stock games + playground | One sampler thread/owner; publish timestamped mm to FSMs |
| Hailo device | `HailoHEFDetector` / future multi-process | Single inferencing owner; node is `/dev/h1x-0` on this stack |

## Ownership architecture (target)

```text
operator enable
    → runner (max_seconds / max_steps)
        → RoamFSM / GraspFSM  (pure suggestions)
        → SafetyGate          (lease + sonar + speed cap)
        → RobotIO             (sole UART; sonar reads via sensors / board path — sonar HW already present)
        → CameraBroker        (sole camera)
```

`RobotIO` defaults `live=False` (records commands only). Live opt-in only after N3/G1 style stops work.

## Bring-up checklist (sequenced)

| Step | Action | Pass | Fail |
|---|---|---|---|
| H1 | Confirm `dtoverlay=uart0-pi5`; no serial console on UART0 | `hello_board` prints mV | hang / None battery |
| H2 | Stop stock daemon; `python scripts/smoke_imports.py` | imports OK | fix PYTHONPATH / MasterPi layout |
| H3 | Wheels raised: `python -m playground.micro_move stop` | motors quiet | skip all motion |
| H4 | `v4l2-ctl --list-devices`; one snap via broker or `fswebcam` | frame exists; note res/FPS | dual open with MasterPi |
| H5 | Sonar: 20 samples @ 0.2 / 0.5 / 1.0 m + open; CSV in `/tmp` | stats logged; invalids classified | treating 5000 as clear |
| H6 | Dead-man: kill mid `forward 0.25 25` | `finally` zero velocity | residual motion |
| H7 | Arm: cam_up → reach → cam_up, chassis stopped | IK OK; envelope clear | continue without recovery pose |
| H8 | Grip: 10 open/close, ≥0.5 s gaps | complete; no loop | PWM spam |

## Sequenced hardware experiments (cross-cutting)

| ID | Goal | Links | Metric |
|---|---|---|---|
| **H-N** | Sonar + stop integration | feeds nav **N1–N3** | freshness <250 ms p95 when sampling ≥5 Hz; stop on veto |
| **H-G** | Pose + grip table | feeds grasp **G1–G2** | versioned pulses/poses written down |
| **H-X** | Mutual exclusion | start MasterPi then RobotIO | second opener must fail loud or be procedurally prevented |
| **H-B** | Battery cutoff draft | log mV idle + under crawl | pick cutoff with margin; gate `SafetyGate` / runner |

## Safety envelope (hardware)

- Lowest practical speed; autonomy ≤40, bring-up 25.
- Explicit stop on every exit path (`SIGINT`, exception, lease expiry, step cap).
- Short timeouts; no unbounded motion loops.
- Arm envelope clear; wheels raised for first chassis tests.
- Never debug gripper close in a tight loop.

## Decision criteria

| Topic | Prefer | Avoid until… |
|---|---|---|
| Camera path | `CameraBroker` single process | sharing with MasterPi MJPEG without a real frame bus |
| Motion entry | `RobotIO` + `SafetyGate` | raw `MecanumChassis` in new scripts (except one-off micros) |
| Sonar role | hard forward veto | mapping / wall following from one beam |
| Mapping sensors | AprilTags / depth / lidar later | dead reckoning from mecanum duty alone |
| Stock action groups | FAULT recovery macros | closed-loop visual servoing |

## Hardware acceptance criteria

**Before autonomous roaming**

- [ ] Camera exclusive and stable at needed rate
- [ ] Sonar freshness p95 < **250 ms** while moving policy runs
- [ ] Battery read works; cutoff documented
- [ ] N3 dead-man stop proven wheels-raised then wheels-down corridor
- [ ] UART not shared with MasterPi

**Before autonomous grasping**

- [ ] Cam–arm error measured (G4)
- [ ] 10 safe open/close cycles (G2/H8)
- [ ] Chassis interlock: no drive commands during arm phase
- [ ] Recovery / cam-up pose always reachable

## Build next

1. Live sonar (`watch_sonar` / `sonar_sample --live`) → document hard-stop/warn in nav after H5/N1.
2. Add battery field to `Observation` + veto in `SafetyGate` once cutoff known.
3. Extend `RobotIO` with gripper + named poses; keep dry-run default.
4. Enforce camera lock: refuse live autonomy if broker lock held or MasterPi presumed up.
5. Keep HEFs / captures out of git; log metrics under `/tmp` or gitignored dirs.
