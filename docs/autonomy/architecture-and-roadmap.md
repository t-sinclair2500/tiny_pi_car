# Software architecture, safety, and roadmap

**Last updated:** 2026-07-15 · **Owner of this file:** architecture / promotion / sequencing  
**SSOT:** [CURRENT_STATE.md](CURRENT_STATE.md)  
**Sibling owners (do not thrash):** [hardware-and-interfaces.md](hardware-and-interfaces.md) · [perception.md](perception.md) · [navigation.md](navigation.md) · [grasping.md](grasping.md)  
**Executable queue:** [BUILD_NEXT.md](BUILD_NEXT.md) · **Ops sessions:** [SESSIONS.md](SESSIONS.md) · Hailo bring-up: [docs/hailo.md](../hailo.md) · [scripts/setup_hailo_10h.md](../../scripts/setup_hailo_10h.md)

---

## Non-negotiables

| Rule | Meaning |
|---|---|
| Playground first | All new autonomy lives in `playground/` until a milestone passes its kill criteria. |
| One UART owner | Never run `MasterPi.py` / RPC + `RobotIO` / `micro_move` together. |
| One camera owner | Never dual-open `/dev/video0`. Broker or stock — not both. |
| Bounded motion only | Every chassis/arm command has a lease, timeout, and `finally: stop_all()`. |
| No HEFs / dumps in git | Weights under `playground/vision/models/` (gitignored); captures untracked. |
| Hailo-10H ≠ Hailo-8 | PCI `1e60:45c4` = **Hailo-10H**. Never `apt install hailo-all` (4.20 / H8). Current: Bookworm + HailoRT **5.3** (`/dev/h1x-0`). Trixie optional later. |

---

## Architecture (as built)

```text
camera_broker ──► detect/vision ──► Observation ──► roam_fsm / grasp_fsm
                       ▲                                │
                       │                                ▼
                    hailo_probe                   safety_gate (veto)
                                                    │
                                                    ▼
                                              RobotIO (sole UART)
                                                    │
                                      Board / Mecanum / ArmIK / Sonar
```

| Module | Role | Live motors? |
|---|---|---|
| `playground/autonomy/types.py` | Observation, MotionLease, FaultReason, RobotCommand | no |
| `camera_broker.py` | Exclusive cam + pid lock under `/tmp` | no |
| `detect.py` + `playground/vision/` | Detector facade → Hailo when ready | no |
| `sensors.py` | Sonar freshness / SonarGate | read-only when live |
| `safety_gate.py` | Pure veto of leases/commands | no |
| `roam_fsm.py` / `grasp_fsm.py` | Explicit FSMs | no (emit intents) |
| `robot_io.py` | **Only** live UART/board owner | yes iff `live=True` |
| `playground/autonomy_smoke.py` | Dry-run FSM + lease (default `live=False`) | no |
| `playground/hailo_probe.py` | PCIe / modules / apt / bindings report | no |

**Not built yet (still required):** `tracking.py`, `geometry.py`, `replay.py`, event log, supervisor heartbeat, MasterPi “game” adapter.

---

## playground/ vs MasterPi/

| Concern | Now | Later (promotion) |
|---|---|---|
| Camera / MJPEG / RPC | Stock `MasterPi/MasterPi.py` | Keep stock until broker API can feed MJPEG; then adapt `Camera.Camera` producer |
| Autonomy FSM / safety | `playground/autonomy/` only | New stock “game” adapter **after** supervised M2/M3 pass |
| Chassis / arm / gripper | `RobotIO` + existing `micro_move.py` | Replace one-off scripts; do **not** make `MasterPi.py` the first orchestrator |
| Perception HEF | `playground/vision/` | Stay in playground; MasterPi only consumes observations if ever wired |
| Sonar | `sensors.SonarGate` wrapping stock `Sonar` | Same; stock avoidance demos are reference only |

**Process policy:** stop MasterPi → run playground session → stop motors → restart MasterPi if needed. No concurrent ownership.

---

## Hailo-10H constraints (hard)

| Fact | Action |
|---|---|
| Device = Hailo-10H (`1e60:45c4`) | HEFs must be **hailo10h**-compiled; H8 HEFs will not run |
| Bookworm has no `hailo-h10-all` | **Path B DONE:** HailoRT 5.3 / `hailo1x_pci` / `/dev/h1x-0`. Path A (Trixie) optional, not required now |
| `hailo-all` 4.20 is wrong | Do not install; conflicts with H10 stack |
| Device node | **`/dev/h1x-0`** (HailoRT 5.x), not `/dev/hailo0` |
| Probe | `python3 -m playground.hailo_probe` → **`ready: True`** on this machine |
| HEF today | COCO **`yolov8n.hef` only** — no grasp/seg HEF yet |

Detail: [perception.md](perception.md), [docs/hailo.md](../hailo.md), [CURRENT_STATE.md](CURRENT_STATE.md).

---

## Safety contract (gates every live milestone)

1. **Lease:** motion dies unless renewed by a healthy loop (dead-man).
2. **`stop_all()`:** zero chassis, cancel queued motion, arm safe if possible — on exit, exception, SIGINT/SIGTERM, stale sensors, heartbeat loss.
3. **Hard veto:** low battery, unknown UART, stale camera/sonar, target under arm workspace, unverified calibration → no autonomous motion.
4. **No unbounded loops:** time, distance, state, or freshness bound on every control cycle.
5. **Log:** request, sent command, sensor ages, battery, transitions, stop reason; frames only around fault/success (untracked).
6. **Physical:** clear area → wheels raised first → human at power/stop → then taped floor.

---

## Milestone ladder (ordered, ruthless)

Dependencies flow **down**. Do not start a row until its “Depends on” column is green.

### M0 — Evidence + safe I/O
**Goal:** Prove exclusive I/O and stop paths without roaming.  
**Depends on:** UART free (MasterPi stopped); wheels raised for live tests.  
**Where:** `playground/` only (`RobotIO`, `micro_move`, `autonomy_smoke`, `hailo_probe`).  
**Deliverables:**
- [x] `playground/autonomy/` skeleton + dry-run smoke
- [x] Lease expiry veto exercised in smoke
- [x] Camera broker second-owner reject
- [x] HailoRT 5.3 / H10 stack → `hailo_probe` `ready: True` + local `yolov8n.hef` (**B0 DONE**)
- [ ] Wheels-raised live `stop_all` / lease-expiry stop (UART free)
- [ ] Battery cutoff measured and recorded
**Kill criteria (abort / redesign):** cannot get exclusive UART or stop within one lease after SIGINT; battery/sonar APIs unusable after 1 session of measurement.

### M1 — Perception MVP (no motors)
**Goal:** Timestamped detections on Pi (Hailo) or recorded frames.  
**Depends on:** M0 dry-run done; on-device Hailo: `ready: True` + `hailo10h` HEF *(both done)*.  
**Where:** `playground/vision/`, `detect.py`; detail → [perception.md](perception.md).  
**Deliverables:** detector behind `build_detector()` *(done)*; latency + confidence logged; tracker; floor-plane range error on known **COCO** object (even coarse).  
**Kill criteria:** cannot sustain usable FPS/recall on target COCO class; switch model class or input size before touching motors. Do not wait on a grasp HEF for M1.

### M2 — Supervised target approach
**Goal:** 30 s capped, sonar-gated approach in taped open area.  
**Depends on:** M0 live stop green; M1 observations fresh enough for bearing; SonarGate thresholds from measured samples.  
**Where:** `roam_fsm` + `RobotIO(live=True)` under human supervision; detail → [navigation.md](navigation.md).  
**Deliverables:** stop on stale data; approach without entering hard-stop distance; no MasterPi during run.  
**Kill criteria:** repeated near-collisions or stop failures in wheels-down tests → freeze speeds, remeasure sonar blind zone, do not add mapping.

### M3 — Reliable pickup
**Goal:** ≥8/10 picks of one approved object in controlled scene.  
**Depends on:** M2 stable approach; camera-to-arm calibration; named safe poses.  
**Where:** `grasp_fsm` + `RobotIO`; detail → [grasping.md](grasping.md). Chassis stopped before PRE_GRASP.  
**Deliverables:** every miss classified from logs; visual verify (close ≠ success).  
**Kill criteria:** <5/10 after calibration pass → fix geometry/catalog before any room-scale work.

### M4 — Room-scale roaming
**Goal:** Supervised multi-room route, recovery/return-home, no collisions.  
**Depends on:** M2 solid; localization/anchors (not open-loop mecanum alone); M3 optional for fetch missions.  
**Where:** still playground runner; MasterPi game adapter only if M2/M3 regression suite is green.  
**Deliverables:** documented recovery rate; layer-1 gate remains final authority.  
**Kill criteria:** slip-dominated pose error → add anchors/lidar before claiming “map.”

---

## Promotion path (MasterPi)

1. Stock daemon stays for camera/RPC/MJPEG while experiments use **separate** sessions (daemon stopped).
2. Replace `fswebcam` one-shots with camera broker; later adapt stock `Camera.Camera` if calibration/perf worth keeping.
3. Replace `micro_move` / ad-hoc scripts with `RobotIO` (keep bounded timing + `finally: stop`).
4. Add a stock “game” adapter that **calls** playground playbooks — only after M2 (and preferably M3) supervised pass.  
   **Do not** make `MasterPi.py` the initial autonomy orchestrator.

---

## Risks (architecture-level)

| Risk | Mitigation | Owner doc |
|---|---|---|
| Wrong apt stack (H8 vs H10) | Follow setup script; probe until ready | hailo / perception |
| Camera / UART contention | Process policy + broker lock + single RobotIO | hardware |
| Sonar false clears | Freshness reject; stop gate not nav truth | navigation |
| Open-loop mecanum slip | Short leases; visual bearing; anchors before M4 | navigation |
| Gripper no force proof | Visual verify + supervised catalog | grasping |

---

## Done vs next (snapshot)

**Done:** Hailo Path B (`ready: True`), COCO `yolov8n` detector, autonomy stubs, safety lease tests, camera lock, roam/grasp FSM shells, RobotIO dry-run, real sonar gate paths.  
**Next:** [BUILD_NEXT.md](BUILD_NEXT.md) — latency log + tracker → wheels-raised stop → live sonar tune → taped M2 on COCO-visible targets. See [CURRENT_STATE.md](CURRENT_STATE.md).
