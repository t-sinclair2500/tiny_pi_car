# BUILD_NEXT — executable queue

**Updated:** 2026-07-15 · **Horizon:** next hours → ~1 week  
**SSOT:** [CURRENT_STATE.md](CURRENT_STATE.md)  
**How to run sessions:** [SESSIONS.md](SESSIONS.md) ← **start here for human ops**  
**Ladder:** [architecture-and-roadmap.md](architecture-and-roadmap.md)  
**Deep-dives:** [hardware](hardware-and-interfaces.md) · [perception](perception.md) · [nav](navigation.md) · [grasp](grasping.md)

Work **top to bottom**. Session packaging in SESSIONS.md maps onto these ticks — do not invent a third sequence in chat.

Mark ticks: `[ ]` → `[x]` when done. Record blockers in CURRENT_STATE.

---

## Session map (summary)

| Session | Name | Ticks | Motors? |
|---|---|---|---|
| **A** | Perception that doesn’t lie | H5, #6a–#6b (+ camera AE rules) | No |
| **B** | Safety green light | #3 live, #4, #5 | Wheels raised only |
| **C** | Supervised approach | #7a–#7b, #9, #10 | Wheels down, human stop |
| After C | Grasp prep | #8, #11–#14 | Supervised |

Full SOP + checklists: [SESSIONS.md](SESSIONS.md).

---

## Now / blocked

| ID | Status | Item |
|---|---|---|
| B0 | **DONE** | Hailo-10H Path B: HailoRT **5.3**, `hailo1x_pci`, `/dev/h1x-0`, probe `ready: True`, COCO `yolov8n.hef`. [docs/hailo.md](../hailo.md) |
| B1 | **ACTIVE** | Camera exclusivity: `sudo systemctl stop masterpi` before vision |
| B2 | **ACTIVE** | UART exclusivity: same before `RobotIO(live=True)` / `micro_move` |

**Forbidden:** `apt install hailo-all` · concurrent MasterPi + playground · committing HEFs/captures · house roam · unbounded loops · pretending we have a grasp/`can` HEF · driving on a single untracked frame.

---

## Hailo track

| ID | Status | Tick |
|---|---|---|
| H1 | [x] | Install H10 stack (Path B) |
| H2 | [x] | `hailo_probe` → `ready: True` |
| H3 | [x] | hailo10h `yolov8n.hef` in gitignored `models/` |
| H4 | [x] | `HailoHEFDetector` / `build_detector()` wired |
| H5 | [ ] | **Session A live** — inference + end-to-end latency p50/p90 from ≥10 valid Pi frames (no motors) |

Camera AE: UVC needs ~15–25 warmup frames; cold frames are nearly black. Use `playground.vision.camera.grab_frame` (warms). See [perception.md](perception.md#camera-pitfalls).

Partial evidence (not a tick): 2026-07-15 remote smoke logged 10/10 valid frames and 2 `person`
boxes; inference p50/p90 16.543/17.852 ms, end-to-end 4076.755/4088.034 ms. Log:
`/tmp/tiny_pi_car/session-a-codex-smoke.jsonl` on `rpicarbox-1`. Repeat with a deliberately staged,
measured COCO target before closing H5/#6b.

---

## Session A ticks (perception, no motors)

| ID | Status | Depends | Done when | Kill |
|---|---|---|---|---|
| #6a | [x] code | H4 | Bounded `playground/vision/log_detections.py`; exact JSONL/CSV schema + pure tests | Never treat `--allow-unavailable` as live evidence |
| #6b | [ ] live | #6a, AE grab | Detect **COCO** bottle/cup/person in ≥10 valid Pi samples; retain log path | Wrong HEF arch → redownload hailo10h; soda can alone is not a valid M1 target |

---

## Session B ticks (safety)

| ID | Status | Depends | Done when | Kill |
|---|---|---|---|---|
| #1 | [x] / policy | — | Process policy known (`systemctl stop masterpi`) | — |
| #2 | [x] | — | `pytest tests/test_safety_lease.py` green | — |
| #3 | [ ] live | I2C | 20 samples at 200/500/1000 mm + open air; raw log, error/dropout, hard-stop/warn worksheet **written down** | Invalid-as-clear, ≥10% target dropout, or unreliable stop band → fix before Session C |
| #4 | [ ] | wheels raised | Creep + interrupt / lease expiry → chassis zero ×5 | Stop fails → **halt all floor work** |
| #5 | [ ] | UART free | Pose stub: home / cam-up / look-down documented | IK `False` → do not grasp |

Simulate sonar already exists; **live** `#3` is the remaining work.

---

## Session C ticks (supervised approach)

| ID | Status | Depends | Done when | Kill |
|---|---|---|---|---|
| #7a | [x] code | #6a | Pure IoU/centroid tracker; default 3 consecutive hits; miss revokes confirm; unit tests | Raw/unconfirmed outputs remain log-only |
| #7b | [ ] integration | #6b, #7a | Observation/runner consumes confirmed tracks only; camera freshness + sonar + lease still gate motion | Jitter/loss → raise confirm count; never bypass tracker |
| #9 | [ ] | #4, SonarGate | ≤30 s roam runner always exits **stopped** | Near-hit → raise thresholds, lower speed |
| #10 | [ ] | #4, #9, #7b | Taped approach to COCO target; stops classified | Collision / missed sonar → Session B |

---

## After Session C (M3 prep — do not reorder ahead of A–C)

| ID | Status | Depends | Done when | Kill |
|---|---|---|---|---|
| #8 | [ ] | #6b + tape | Floor-plane range error magnitude recorded | Absurd error → fix mount/intrinsics before grasp |
| #11 | [ ] | #5 | Pose table v0 (stow/carry, cam-up, ready, pre-grasp) | — |
| #12 | [ ] | UART | Gripper open/close ×10 supervised; PWM endpoints recorded | Servo glitch → inspect |
| #13 | [ ] | #8, #11 | Cam–arm cal: predicted vs contact @ ≥2 points | Error > grasp tol → no closed-loop reach |
| #14 | [ ] | #7a | Grasp FSM dry-run on logs | — |

**M3 8/10 pickup is not required to finish Day-2 prep.** Custom/seg HEF later.

---

## Explicitly later (do not start)

- Custom / seg / grasp HEF compile (until COCO approach is reliable)
- M4 room-scale / mapping / return-home
- MasterPi.py as autonomy orchestrator / stock “game” adapter
- Concurrent MJPEG + Hailo without broker
- Blind mapping from open-loop odometry alone
- OS migrate to Trixie (optional; Bookworm Path B is fine)

---

## Verify cheat sheet

```sh
sudo systemctl stop masterpi
source .venv/bin/activate
.venv/bin/python -m playground.hailo_probe      # ready: True
.venv/bin/python -m playground.vision_smoke     # AE-warmup grab + detect
.venv/bin/python -m playground.autonomy_smoke
.venv/bin/python -m playground.watch_sonar
.venv/bin/python -m playground.sonar_sample --live
.venv/bin/python -m playground.micro_move stop
pytest tests/test_safety_lease.py tests/test_roam_fsm.py
pytest tests/test_detection_log.py tests/test_tracking.py
```

---

## Ownership

| Surface | Owner |
|---|---|
| SESSIONS + BUILD_NEXT + architecture | Sequencing / ops |
| `playground/vision/*`, HEF, camera AE | Perception |
| Speeds, sonar thresholds, roam | Navigation |
| Poses, grasp verify | Grasping |
| UART, battery, bring-up | Hardware |

Order conflicts for the next week → **SESSIONS / BUILD_NEXT win**. Kill criteria in architecture win over optimism.
