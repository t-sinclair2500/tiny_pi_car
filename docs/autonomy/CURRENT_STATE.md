# CURRENT_STATE — single source of truth

**Probed / updated:** 2026-07-15 · **Ops runbook:** [SESSIONS.md](SESSIONS.md) · **Ticks:** [BUILD_NEXT.md](BUILD_NEXT.md) · **Index:** [docs/STATUS.md](../STATUS.md)

This file overrides stale “runtime not installed” / “sonar is future” / “first frame is fine” wording elsewhere. Research under `docs/research/` is background.

**Last session note:** Camera UVC auto-exposure requires ~15–25 warmup frames (cold frames nearly black). `grab_frame()` warms. COCO `yolov8n` does not detect soda cans; use bottle/cup for M1–M2. MasterPi stopped via `systemctl` during playground vision. A 2026-07-15 remote logger smoke produced 10/10 valid frames, 2 `person` boxes, inference p50/p90 **16.543/17.852 ms**, and capture-to-result p50/p90 **4076.755/4088.034 ms** at `/tmp/tiny_pi_car/session-a-codex-smoke.jsonl`; Session A remains open because no target/range was deliberately staged.

---

## Hardware that works today

| Piece | Reality |
|---|---|
| OS | Debian 12 **Bookworm** — staying here (no Trixie required) |
| Hailo-10H | PCIe `1e60:45c4` @ `0001:01:00.0`, Gen3 x1 |
| Driver / node | `hailo1x_pci`; **`/dev/h1x-0`** (not `/dev/hailo0`) |
| HailoRT | **5.3** debs + FW 5.3.0; `hailortcli` → **HAILO10H** |
| Python | `hailo_platform` 5.3 in `.venv`; probe **`ready: True`** |
| HEF | `playground/vision/models/yolov8n.hef` (COCO80, gitignored) |
| Camera | USB `32e6:9005` → `/dev/video0`; AE warmup required |
| Stock daemon | `masterpi.service` — **stop** for playground cam/UART |
| Sonar | **Real** I2C-1 `@0x77` (`SonarGate`, `watch_sonar`, `sonar_sample`) |
| Motion | Mecanum + ArmIK + gripper via UART `/dev/ttyAMA0` |

**Install:** Path B — `./scripts/setup_hailo_10h.sh --install bookworm-hailort-5.3`. **Never** `apt install hailo-all`.

---

## Software that works today

| Capability | Status |
|---|---|
| Hailo probe + HEF load + COCO detect | Works (after AE warmup) |
| `HailoHEFDetector` / `build_detector()` | Wired; unavailable fallback if missing |
| Bounded detection logger | JSONL/CSV + capture/inference latency; live Session A evidence pending |
| `DetectionTracker` | Pure IoU/centroid association; 3 consecutive hits; unit-tested, not runner-wired |
| `vision_smoke` / `autonomy_smoke` | Dry-run / no motors by default |
| Safety lease + SonarGate | Logic + unit tests |
| RoamFSM | Align-yaw intents only; **no** translation until M2 |
| GraspFSM | Stub; **no** live grasp |
| `RobotIO` | Dry-run default; live opt-in |
| `micro_move` | Bounded live commands |
| Camera grab | V4L2 + **warmup**; shared `/tmp/robot_cam_latest.jpg` if fresh |

---

## Stubbed / missing

- No grasp / seg / custom-class HEF (no `can` class)
- No `geometry.py`, `poses.py`, `replay.py`
- Tracker is not yet wired into `Observation` / a supervised approach runner
- No proven wheels-down supervised approach runner yet
- No cam–arm calibration numbers
- Battery cutoff not in `SafetyGate` yet

---

## What’s next (operational)

Follow **[SESSIONS.md](SESSIONS.md)** in order:

1. **Session A** — COCO detect log + latency (H5, #6b; logger #6a built)
2. **Session B** — live sonar + wheels-raised stop (#3–#5)
3. **Session C** — tracker integration + supervised taped approach (#7b, #9, #10; pure tracker #7a built)
4. Then grasp prep (#8, #11–#14) → M3

Tick boxes in [BUILD_NEXT.md](BUILD_NEXT.md) as you go.

---

## Quick verify

```sh
sudo systemctl stop masterpi
source .venv/bin/activate
.venv/bin/python -m playground.hailo_probe   # ready: True
.venv/bin/python -m playground.vision_smoke
.venv/bin/python -m playground.autonomy_smoke
.venv/bin/python -m playground.watch_sonar
```
