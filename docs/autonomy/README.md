# MasterPi autonomy plan set

Staged engineering plan for a Raspberry Pi 5 + HiWonder MasterPi (mecanum + 5-DOF arm + camera) that can roam indoors and pick up known household objects. New code lives in `playground/` until each capability is safe, measured, and ready to replace a stock path.

## Ground truth on this Pi (2026-07-15)

| Item | Status |
|---|---|
| Accelerator | **Hailo-10H** PCIe `1e60:45c4` at Gen3 x1 — **B0 DONE**: HailoRT **5.3**, `hailo1x_pci`, `/dev/h1x-0`, `hailo_platform` in `.venv`; probe `ready: True` |
| Install path | Stay on Bookworm + HailoRT 5.3 debs **or** later Trixie + `hailo-h10-all`; **never** Bookworm `hailo-all` 4.20 — [scripts/setup_hailo_10h.md](../../scripts/setup_hailo_10h.md) |
| Camera | USB `32e6:9005` → `/dev/video0`; exclusive broker required (stock `MasterPi.py` contends) |
| UART / sonar | Expansion board `/dev/ttyAMA0`; **sonar already on robot** — HiWonder ultrasonic I2C-1 `@0x77` (mm; reject 5000/99999 as clear); fuse with vision |
| Autonomy skeleton | `playground/autonomy/` + `autonomy_smoke` dry-run exist; real HEF detector path present, camera exclusivity still a live blocker |

Verify: `python3 -m playground.hailo_probe` · `python3 -m playground.vision_smoke` · `python3 -m playground.autonomy_smoke`

## Documents

| Doc | Role |
|---|---|
| [SESSIONS.md](SESSIONS.md) | **Human runbook** — SOP, Sessions A/B/C, milestone map |
| [CURRENT_STATE.md](CURRENT_STATE.md) | **SSOT** — what works / stubbed / next on this Pi |
| [BUILD_NEXT.md](BUILD_NEXT.md) | Checkbox tick queue (maps 1:1 to sessions) |
| [architecture-and-roadmap.md](architecture-and-roadmap.md) | Modules, safety contract, milestones M0–M4 |
| [hardware-and-interfaces.md](hardware-and-interfaces.md) | Ownership, UART/camera/sonar, bring-up |
| [perception.md](perception.md) | Hailo pipeline, camera pitfalls, metrics |
| [navigation.md](navigation.md) | Roam + sonar/vision fusion |
| [grasping.md](grasping.md) | Vision-guided pickup FSM |
| [docs/STATUS.md](../STATUS.md) | Short repo index |
| [docs/hailo.md](../hailo.md) | Hailo bring-up |
| [docs/research/README.md](../research/README.md) | Research index (background) |

**Start here for ops:** [SESSIONS.md](SESSIONS.md) → execute → check off [BUILD_NEXT.md](BUILD_NEXT.md).

## Code map (playground)

| Path | Role |
|---|---|
| `python3 -m playground.autonomy_smoke` | Dry-run FSM + safety lease (**no motors**; Hailo optional; `--fake-det` for align yaw) |
| `python3 -m playground.sonar_sample` | Sonar freshness → `/tmp/tiny_pi_sonar_stats.json` (simulate default; `--live` after MasterPi stop) |
| `python3 -m playground.watch_sonar` | Live I2C sonar → `/tmp/robot_sonar.txt` (no UART) |
| `playground/autonomy/` | `types`, `safety_gate`, `sensors`, `camera_broker`, `detect`, `robot_io`, `roam_fsm`, `grasp_fsm` |
| `playground/vision/` | `camera`, `detector` (`HailoHEFDetector` when ready; `UnavailableHailoDetector` fallback), `models` (HEF registry) |
| `playground/hailo_probe.py` | PCIe / modules / `/dev/h1x-*` / apt / bindings |
| `playground/micro_move.py` | Bounded live chassis/arm/gripper (UART exclusive; explicit stop) |
| `tests/test_safety_lease.py` | Pure lease renew→expire→veto (+ sonar hard-stop/stale) |
| `tests/test_roam_fsm.py` | Pure bbox→align-yaw |

Still missing (see perception + BUILD_NEXT): tracking, geometry, poses, replay; camera/UART exclusivity for live sessions. Lease expiry + roam align tests exist under `tests/`.

## Sequencing (execute in order)

1. **Hailo runtime** → **DONE** ([hailo.md](../hailo.md)).
2. **Session A** — perception log + latency ([SESSIONS.md](SESSIONS.md)).
3. **Session B** — live sonar + wheels-raised stop.
4. **Session C** — tracker + supervised COCO approach.
5. **Grasp prep** → poses, grip cycles, cam–arm cal → M3.
6. **Room-scale (M4)** only after M2+M3 hold.

## Operational rule

Only one process may own UART, camera, and `/dev/h1x-0`. Every motion is short, bounded, supervised, and ends in an explicit stop. Full SOP: [SESSIONS.md](SESSIONS.md).
