# Experiment learnings (2026-07)

Committed digest of live Pi sessions. Raw tick JSON / snaps live under
`.autoresearch/runs/` (gitignored). Prefer this file when docs conflict with
older CURRENT_STATE snapshots.

**Pi path:** `tyler@rpicarbox` → `/home/tyler/Desktop/tiny_pi_car` only  
**Host path:** `/home/tyler/Documents/GitHub/tiny_pi_car`

---

## Orchestration

| Approach | Outcome |
|----------|---------|
| OpenCode + local Qwen council | Poor fit for timed motion. Empty LMS `tool_calls: []` needed `scripts/lms_openai_proxy.py`; `opencode run` stalled at init; councils hit false `scope_violation` / `agent_error`. |
| Cursor Composer + direct SSH eval | Produced almost all real progress (`motion_hour_eval`, `pi_agent_gate`, physical trials). |
| Stream roam track | **No OpenCode / LMS proxy.** On-Pi daemon; host syncs, starts/stops, scores. See [`STREAM_CARD.md`](../../autoresearch/car/STREAM_CARD.md). |

**Ops facts:** Stock `masterpi.service` is not the research path. Kinematics may still expect `/home/pi/MasterPi/...` (symlink to Desktop tree). Prefer `/dev/hailo0` over stale `/dev/h1x-0` checks when probing.

---

## Night perception (2026-07-17) — wheels OFF

Source: `.autoresearch/runs/NIGHT_SESSION_2026-07-17.md`

| Trial | Result | Keep? |
|-------|--------|-------|
| Persistent camera + warmup=5 | ~27× e2e speedup (~3490 ms → ~130 ms p50) | **Yes** — default in `log_detections` |
| `score_thresh` sweep | 0.25 → bottom-corner person FPs; **0.45** correct for ambient | **Yes** — CLI `--score-thresh` |
| yolov8m vs yolov11m | ~identical latency/recall without staged objects | Keep yolov8n/8m; `--hef-path` for A/B |

---

## motion15-direct (Composer, yaw + vision-guided)

Source: `.autoresearch/runs/motion15-direct/SUMMARY.md`  
Metric: `100 × completion × overhead × vision` via `scripts/motion_hour_eval.py`.

| Mode | Best score | Overhead |
|------|-----------:|---------:|
| Dispatch + post vision | **86.46** | ~974 ms |
| Vision-guided (pre bbox yaw) | **64.85** | ~1730 ms |

### Shipped code

- `playground/vision/snap_and_detect.py` — one camera open; optional warm detector reuse
- `playground/autoresearch/vision_guided_trial.py` — pre snap → yaw decision → short trial; skip post when pre scored
- `scripts/motion_hour_eval.py` — `--with-vision` / `--vision-guided`
- `roam_fsm.suggested_yaw_from_detections` — bbox center → tiny yaw

### Learnings

1. Pre-trial vision is enough for the metric; post-stop snap was mostly redundant (~90–130 ms).
2. **Hailo VDevice init dominates** vision-guided overhead; reuse across pre/post cut ~400+ ms.
3. Parallel V4L2 warmup ∥ Hailo load helps the dispatch path.
4. BBox-center yaw works when a COCO target is in FOV; deadband ~0.08 skips tiny errors.
5. Metric penalizes pre-trial latency, not nav quality — hard gates (final stop) always held.

---

## auto20 Phase A — translate (ticks 0–6)

Source: `.autoresearch/runs/auto20/` (`CHARTER.md`, `phaseA-notes.md`)

- Short sonar-gated **forward** ≤30 mm/s, ≤0.4 s; scores **~84–86**.
- Sonar during session: **791 → 391 mm** creep; veto at **220 mm** never hit (min observed 391 mm).
- Person dets + deadband → often `no_align_needed` → forward.
- Every trial: `final_stop_sent: true`.

### Phase B abort — laundry jam (critical)

Phase B (vision-guided spins) jammed the robot into a **soft clothes pile**.

| Failure mode | Detail |
|--------------|--------|
| Sonar blind zone | Ultrasonic sits ~**3″** off the deck → misses low fabric/toys |
| Cam-up FOV | Room-level; floor clutter only at bumper edge |
| Yaw-in-place near laundry | Spins into soft obstacles sonar does not veto |

**Recovery:** e-stop; manual reverse **3.5 s @ 80 mm/s** cleared jam. Standing snap: `.autoresearch/runs/auto20/snap-as-standing.jpg`. Live sonar after: ~341 mm.

**Standing order after this:** refuse crawl / yaw into unknown soft clutter; use **look-down + lower-FOV clutter heuristic** before sustained forward. Do not treat sonar-alone as floor-safe.

---

## Stream roam leapfrog (prep, host-side)

Goal: replace one-shot SSH trials as the **control path** with an on-Pi continuous loop; keep SSH evals as regression.

| Layer | Status |
|-------|--------|
| Docs + campaign | `STREAM_CARD` / `START_STREAM` / `campaigns/stream-roam.toml` |
| L1 daemon | `playground/autonomy/roam_daemon.py` (~10 Hz FSM, sonar interrupt, warm Hailo, lease, JSONL) |
| L2 floor gate | `look_down` / `look_ahead` poses; `floor_clutter.py`; refuse crawl on risk |
| Gate wrappers | `pi_agent_gate` `roam-start` / `roam-stop` / `roam-status` |
| Eval | `scripts/stream_roam_eval.py` |
| L3 sticky / L4 grasp | Hooks / stubs only |
| **Pi smoke** | **Blocked** — Pi powered off at write-up; clear-floor 30 s + soft-pile refuse still required |

Runbook: [`START_STREAM.md`](../../autoresearch/car/START_STREAM.md).

---

## Sense–act pattern (what to steal)

Hobby stacks run **fixed-rate cmd** + **latest-frame** vision + **fast sensor veto**, not SSH one-shots:

- Camera thread → latest frame (drop stale)
- Sonar/ToF → hard stop at higher Hz
- Policy/FSM → cmd every ~20–100 ms
- Heavy Hailo ~5–15 Hz; chassis loop faster

References used for design: omnibotAi-style bbox cycles, Hailo RPi5 streaming examples, Donkey/OpenCV RC fixed-rate loops.

---

## Next (when Pi is on)

1. Rsync host → Desktop repo.
2. Clear-floor 30 s `roam-start` + e-stop verify.
3. Soft-pile in front → look-down refuse; save `.autoresearch/runs/stream-l2/` snaps.
4. Confirm `motion_hour_eval` short forward still passes (regression).
5. Timed Composer research on daemon params (no OpenCode).
