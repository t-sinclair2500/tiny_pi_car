# Indoor navigation and roaming

> **Sonar:** HiWonder ultrasonic is **already on the robot** (I2C-1 `@0x77`). Do not plan “add sonar later” — hard-stop/warn gates exist; next work is to **fuse sonar with vision** (and retune thresholds), not to invent a new ranging BOM item.

## Status vs code (2026-07-15)

| Piece | Path | Reality |
|---|---|---|
| Lease + sonar veto | `playground/autonomy/safety_gate.py` | Pure functions + tests; defaults: lease TTL **0.35 s**, hard-stop **250 mm**, max **40 mm/s** |
| Sonar hardware | `common.sonar.Sonar` I2C `@0x77` | **Real** — `watch_sonar`, `sonar_sample`, `RobotIO.read_sonar_mm` |
| Sonar freshness | `playground/autonomy/sensors.py` `SonarGate` | Rejects age >0.35 s and values ≥4999 mm |
| Chassis owner | `playground/autonomy/robot_io.py` | Dry-run default; live needs `live=True`; `stop_all()` → `set_velocity(0,0,0)` |
| Vision cue | Hailo COCO `yolov8n` | Align yaw from bbox center possible; **no** translation until M2; no grasp HEF |
| Roam FSM | `playground/autonomy/roam_fsm.py` | Partial: capped align yaw; no real explore yet |
| Manual primitives | `playground/micro_move.py` | Proven: `forward/reverse` @25, yaw ±0.28 for ~0.12 s, always `finally: stop` |
| Stock reference | `MasterPi/functions/avoidance.py` | 5-sample mean±std filter; Threshold **30 cm**; fixed-time rotate — **not** a lease controller |

SSOT: [CURRENT_STATE.md](CURRENT_STATE.md). Do **not** reimplement safety/RobotIO from scratch. Extend stubs; stock avoidance is behaviour reference only.

## Interface notes (chassis)

`MecanumChassis.set_velocity(velocity, direction, angular_rate)`:

| Arg | Units / range (stock demos) | Autonomy convention |
|---|---|---|
| `velocity` | stock demos 0–100; playground uses **22–28** for crawl | Cap ≤ **40**; start at **25** |
| `direction` | 0–360°, polar | **90** = forward, **270** = reverse, **0/180** = lateral |
| `angular_rate` | roughly −2…2 | Start ±**0.28** for ~0.12 s yaw ticks; never leave spinning without timeout |

Open-loop only — no wheel odometry in the current board API. Every motion is a **timed lease**: renew ≤250–350 ms or stop. `RobotIO.apply()` must go through `SafetyGate.allow()` before UART write.

Exclusive resources: stop `MasterPi.py` / `rpc_server.py` before any live `RobotIO`. One process owns `/dev/ttyAMA0`.

## Two-layer progression

### Layer 1: reactive free-space (do this first)

Inputs at 5–10 Hz:

- filtered forward sonar (mm) + monotonic timestamp;
- camera OK / free-space cue / detector list from perception;
- battery mV (`Board.get_battery()`);
- operator enable + dead-man lease.

Policy table:

| Condition | Action |
|---|---|
| lease expired, sonar stale/invalid (≥4999 or age >0.35 s), camera stale, battery low, no heartbeat | `stop_all()` immediately; arm to cam-up/carry if feasible |
| sonar ≤ hard-stop (start **250 mm**, retune after N1) | zero velocity; mark heading blocked |
| hard-stop < sonar ≤ warn (**450 mm**) | stop; bounded yaw scan; pick clearest heading |
| clear, no target | forward one lease @ ≤25 mm/s, dir 90 |
| target stable, beyond handoff | approach with bearing correction + sonar gate |
| target in handoff range | stop chassis; emit `GRASP_HANDOFF` |

Do not trust stock `Threshold=30` cm until measured on this mount (blind zone + braking distance).

### Layer 2: mapped house (gate behind Layer-1 metrics)

Only after Layer-1 pass criteria below:

1. Confirm whether board exposes wheel ticks; if not, use VO / tags / external lidar — do not fake a map from open-loop duty.
2. Local occupancy from camera free-space; **sonar already available** as the **forward hard constraint** — fuse with vision soft cues (do not wait for lidar to ship a near-field stop).
3. Room anchors (AprilTags) before multi-room routes.
4. Layer-1 gate remains final authority on every command.
5. Docking marker required before unattended runs.

## Roam state machine

```text
IDLE -> SELF_CHECK -> SCAN -> EXPLORE -> TARGET_TRACK
  ^       | failed       |                 |
  |       v              v                 v
  +---- FAULT <------ AVOID <---------- GRASP_HANDOFF
```

| State | Allowed motion | Timeout / cap | Exit |
|---|---|---|---|
| `SELF_CHECK` | none | 5 s | fail → `FAULT` if UART/camera/sonar/battery fail |
| `SCAN` | yaw ticks only, chassis otherwise stopped | ≤8 ticks or 10 s | clearest heading or abort |
| `EXPLORE` | leased forward ≤25 mm/s | `--max-seconds 30`, `--max-distance-m 1` | obstacle → `AVOID`; target → `TARGET_TRACK` |
| `AVOID` | stop first, then one scan cycle | 5 s | resume `EXPLORE` or `FAULT` |
| `TARGET_TRACK` | leased approach | lose target 1 s → `SCAN` | handoff range → stop + `GRASP_HANDOFF` |
| `FAULT` | `stop_all()` only | sticky until operator reset | — |

Align enum names with `RoamFSM` when promoting stubs (`SCAN`/`APPROACH`/`HOLD`/`FAULT` today).

## Sequenced experiments

| ID | Experiment | Setup | Procedure | Pass metric | Fail / stop rule |
|---|---|---|---|---|---|
| **N0** | Pure lease replay | no motors | unit test: renew → expire → `allow()` returns `None` | 100% veto on expiry | any motion after expiry |
| **N1** | Sonar stationarity | robot still, clear arm | 20 samples each at 0.2 / 0.5 / 1.0 m + open air; log median/IQR/dropout to `/tmp` | dropout <10%; open-air never treated as clear if ≥4999 | treat 5000/99999 as clear |
| **N2** | Hard-stop brake | wheels **raised**, then taped 1 m corridor | drive @25 toward soft obstacle; measure stop distance after veto | stop within 150 mm of hard-stop trigger; `finally` always zeros | overshoot into contact or motors left running |
| **N3** | Dead-man kill | wheels raised | start 0.25 s crawl; SIGINT / kill process mid-lease | `stop_all` in `finally`; wheels quiet <100 ms after exit | residual velocity |
| **N4** | Yaw scan bound | clear floor, operator present | 8× yaw_left/right @0.12 s / 0.28; stop between | heading change useful; total time <5 s; stop after each tick | continuous spin or >10 s |
| **N5** | Supervised roam | taped corridor ≤1 m | `roam` with `--max-seconds 30 --max-distance-m 1`, speed 25 | completes without fault; ≥1 successful stop-on-obstacle | any unbounded loop; leave UART contested |
| **N6** | Target handoff | one visible soft object | approach until handoff range; chassis stop | stop before arm motion; handoff event logged | chassis moving during grasp |

Order: N0 → N1 → N3 → N2 → N4 → N5 → N6. No free-room roam until N5 pass ×3.

### N1 threshold selection (record values, do not guess)

Use the four 20-sample sets in the [Session B worksheet](SESSIONS.md#session-b-sonar-threshold-worksheet-3).
Calculate positive range error as `reading_mm - tape_mm`; its p90 protects against the sonar
reporting an obstacle farther away than reality. Start with static clearance 150 mm, extra margin
50 mm, and the existing floor of 250 mm:

```text
provisional_hard_stop_mm = max(250,
                               minimum_reliable_mm + 50,
                               150 + positive_range_error_p90_mm + 50)
provisional_warn_mm = provisional_hard_stop_mm + 200
```

Round up to 25 mm. After N2, fold measured p90 braking overshoot into the final hard-stop formula
in the worksheet; thresholds may rise, not fall, on early evidence. Invalid/stale/over-range
values always veto forward motion. Store raw samples under `/tmp`, then write the selected numeric
hard-stop/warn values and log path into BUILD_NEXT #3 and the session note.

## Safety envelope (non-negotiable)

- Speed: ≤40 mm/s autonomy cap; default crawl **25**.
- Explicit stop: every path ends in `set_velocity(0,0,0)`; prefer dir `0,0,0` for full stop (stock) after directed crawl.
- Timeouts: lease TTL ≤0.35 s; approach timeout (blanket reference **8 s**); roam hard caps on seconds + distance + FSM steps.
- No `while True` without max_steps / wall-clock / operator stop.
- Never run concurrent with `MasterPi.py`.

## Decision criteria

| Decision | Choose A if… | Choose B if… |
|---|---|---|
| Hard-stop distance | N1 median at contact − braking margin ≥200 mm → keep **250** | carpet / slow brake → raise to **300–350** |
| Warn zone | need scan space before stop | if warn≈hard-stop, skip warn and always stop-then-scan |
| Explore vs always-scan | N5 shows stable forward corridors | cluttered room → SCAN-heavy policy only |
| Add odometry / map | Layer-1 passes and you need multi-room | single-room fetch — stay Layer-1 |
| Stock avoidance reuse | learning filter maths | production controller — keep lease FSM |

## Success metrics (Layer-1 done)

- 3/3 supervised 30 s corridor runs stop cleanly on soft obstacle.
- Zero orphaned motor motion after process exit (N3).
- Sonar freshness violations always veto motion in replay + live.
- Handoff: chassis velocity 0 for ≥0.5 s before grasp FSM owns UART arm path.

## Build next

1. Wire `RoamFSM.step` → `SafetyGate.allow` → `RobotIO.apply` in one supervised runner; dry-run first.
2. Pure tests: lease expiry, sonar stale, hard-stop, step-cap → HOLD/FAULT *(lease + roam align mostly done)*.
3. Live sonar N1 + log replay before wheels-down.
4. Promote N5 runner: `--max-seconds 30 --max-distance-m 1 --speed 25 --live` (live opt-in); approach **COCO-visible** targets only.
5. Emit `GRASP_HANDOFF` observation event; do not call arm from roam path.
