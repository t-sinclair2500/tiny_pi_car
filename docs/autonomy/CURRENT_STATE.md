# CURRENT_STATE — single source of truth

**Probed / updated:** 2026-07-16 · **Ops:** [SESSIONS.md](SESSIONS.md) · **Pi live:** [PI_BRINGUP.md](PI_BRINGUP.md) · **Ticks:** [BUILD_NEXT.md](BUILD_NEXT.md)

This file overrides stale “runtime not installed” / “sonar is future” / “first frame is fine” wording elsewhere. Research under `docs/research/` is background.

**Last session note:** Fresh **Trixie** on `rpicarbox` (`tyler@rpicarbox.local`).
**MasterPi chassis board is not on the Pi** (no USB cam, UART motors, sonar).
Hailo-10H PCIe is present; `/dev/h1x-0` pending `hailo-h10-all`. Host-side
vision suite + freer autoresearch ready. See [PI_BRINGUP.md](PI_BRINGUP.md).

---

## Hardware that works today

| Piece | Reality |
|---|---|
| OS | Debian 13 **Trixie** (fresh SD). Host docs may still mention Bookworm Path B. |
| Hailo-10H | PCIe `1e60:45c4` @ `0001:01:00.0` — **present** |
| Driver / node | Bring-up in progress: expect `hailo1x_pci` + **`/dev/h1x-0`** after `hailo-h10-all` |
| HailoRT | Pending bring-up (`hailo-h10-all` on Trixie) |
| Python | Host `.venv` ok; Pi `.venv` missing as of probe |
| HEF | Slots empty until zoo HEFs dropped under `playground/vision/models/` |
| Camera / UART / motors | **Offline** — MasterPi board not attached to this Pi |
| Stock daemon | N/A until chassis returns |
| Sonar | On the MasterPi board — unavailable until chassis is attached |

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

Agents may iterate under `playground/` + `autoresearch/car/` without waiting for
formal Session A–C. For live hardware, prefer:

1. Camera + Hailo detect log (bottle/cup) — Session A facts still useful
2. Short motion trials with stop-on-exit — Session B without wheels-raised ceremony
3. Tracker + supervised approach when detect is reliable

Tick boxes in [BUILD_NEXT.md](BUILD_NEXT.md) when a fact is proven on hardware.

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
