# CURRENT_STATE — single source of truth

**Probed / updated:** 2026-07-22 · **Ops:** [SESSIONS.md](SESSIONS.md) · **Pi live:** [PI_BRINGUP.md](PI_BRINGUP.md) · **Ticks:** [BUILD_NEXT.md](BUILD_NEXT.md) · **Experiments:** [EXPERIMENT_LEARNINGS.md](EXPERIMENT_LEARNINGS.md)

This file overrides stale wording elsewhere. Research under `docs/research/` is background.
Live session numbers and failure modes: **[EXPERIMENT_LEARNINGS.md](EXPERIMENT_LEARNINGS.md)**.

**Last session note:** Chassis + cam + Hailo worked on Desktop repo via SSH
(`rpicarbox` → `/home/tyler/Desktop/tiny_pi_car`). Night perception + motion15-direct +
auto20 Phase A completed; Phase B aborted on soft laundry jam (sonar ~3″ blind zone).
Stream roam daemon/docs are on host; **Pi smoke still pending** (Pi was powered off).

---

## Hardware that works today

| Piece | Reality |
|---|---|
| OS | Debian 13 **Trixie** on Pi |
| Hailo-10H | Works with HailoRT; device node often **`/dev/hailo0`** (not only `/dev/h1x-0`) |
| Camera | `/dev/video0` USB; AE warmup required |
| UART / mecanum / arm | Live via `RobotIO(live=True)` / `physical_trial` / `micro_move` when MasterPi board attached |
| Sonar | I2C ultrasonic; ~**3″** height → **misses low floor clutter** |
| Stock daemon | Prefer Desktop playground path; stop stock `masterpi` if it owns UART |
| Research root | **`/home/tyler/Desktop/tiny_pi_car` only** |

**Install:** Prefer documented Hailo bring-up scripts. **Never** `apt install hailo-all`.

---

## Software that works today

| Capability | Status |
|---|---|
| Hailo probe + HEF load + COCO detect | Proven on Pi (after AE warmup) |
| Persistent camera + warmup=5 | Night session: ~130 ms e2e vs ~3.5 s reopen |
| `snap_and_detect` + detector reuse | motion15-direct best path |
| Vision-guided short trial | bbox yaw; scores ~65 vs dispatch ~86 (latency tax) |
| Sonar-gated forward ≤30 mm/s | auto20 Phase A scores ~84–86 |
| Safety lease + SonarGate | Logic + unit tests; clearance ~220 mm |
| RoamFSM | Live yaw / crawl / hold / fault (capped); used by daemon |
| `roam_daemon` + floor clutter gate | Host-complete; Pi smoke pending |
| GraspFSM | Stub; daemon refuses grip while driving (L4 later) |
| `RobotIO` | Dry-run default; live opt-in; `look_down` / `look_ahead` / `neutral` poses |
| `micro_move` | Bounded live commands + e-stop path |

---

## Stubbed / missing / blocked

- Stream roam **Pi smoke** (clear floor + soft-pile refuse)
- L3 sticky track / L4 live grasp
- Soft-obstacle ML (heuristic L2 only)
- Tracker not fully wired into continuous approach
- No cam–arm calibration numbers
- Battery cutoff not in `SafetyGate` yet

---

## What’s next (operational)

1. Power Pi → rsync → stream smoke per [START_STREAM.md](../../autoresearch/car/START_STREAM.md)
2. Composer research on `roam_daemon` / floor thresholds (no OpenCode on this track)
3. Unlock L3 only after L1/L2 green

Tick boxes in [BUILD_NEXT.md](BUILD_NEXT.md) when a fact is proven on hardware.

---

## Quick verify

```sh
# On Pi (Desktop repo)
sudo systemctl stop masterpi 2>/dev/null || true
source .venv/bin/activate
.venv/bin/python -m playground.hailo_probe
.venv/bin/python -m playground.vision_smoke
.venv/bin/python -m playground.autonomy_smoke

# From host
.venv/bin/python scripts/pi_agent_gate.py --host rpicarbox status
.venv/bin/python scripts/pi_agent_gate.py --host rpicarbox emergency-stop
```
