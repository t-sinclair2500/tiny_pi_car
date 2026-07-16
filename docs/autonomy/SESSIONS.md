# Operational sessions — how we execute the plan

**Updated:** 2026-07-15  
**Facts:** [CURRENT_STATE.md](CURRENT_STATE.md)  
**Tick queue:** [BUILD_NEXT.md](BUILD_NEXT.md)  
**Milestones:** [architecture-and-roadmap.md](architecture-and-roadmap.md)

This is the **human runbook**. Do not invent parallel plans in chat — update this file and `BUILD_NEXT.md` when sequencing changes.

---

## Doc hierarchy (what wins)

| Priority | Doc | Role |
|---|---|---|
| 1 | [CURRENT_STATE.md](CURRENT_STATE.md) | What is true on this robot *today* |
| 2 | This file (`SESSIONS.md`) | How we work session-by-session |
| 3 | [BUILD_NEXT.md](BUILD_NEXT.md) | Ordered ticks + kill criteria |
| 4 | architecture / perception / navigation / grasping / hardware | Deep-dives |
| 5 | `docs/research/*` | Background; banners may be outdated vs CURRENT_STATE |

When chat and docs disagree → **update docs**, don’t keep tribal knowledge in chat.

---

## Every session — SOP (non-negotiable)

Print this checklist and tick it before any live work.

### Pre-flight
- [ ] `cd ~/Desktop/tiny_pi_car && source .venv/bin/activate`
- [ ] `sudo systemctl stop masterpi` (or confirm `inactive`)
- [ ] `pgrep -af MasterPi` → empty
- [ ] `systemctl is-active masterpi` → `inactive`
- [ ] Clear floor; human at power cutoff
- [ ] For **any new motion**: wheels **raised** until stop path proven this session
- [ ] `.venv/bin/python -m playground.hailo_probe` → `ready: True` (if using vision)
- [ ] Note battery / power source (wall PSU preferred for Hailo + motion)

### During
- [ ] One owner of `/dev/video0`, one of `/dev/ttyAMA0`, one of `/dev/h1x-0`
- [ ] Speeds ≤ ~25 unless measured otherwise
- [ ] Every motion path ends in `micro_move stop` / `RobotIO.stop_all()`
- [ ] No unbounded `while True` without timeout + stop

### Post-flight
- [ ] Chassis stopped; arm in known pose or home
- [ ] Kill playground watchers you started (`watch_camera`, `watch_sonar`) if done
- [ ] Update checkboxes in [BUILD_NEXT.md](BUILD_NEXT.md)
- [ ] One-line note in CURRENT_STATE “Last session” if hardware behavior changed
- [ ] Optional: `sudo systemctl start masterpi` if you need stock daemon again

### Forbidden
- `apt install hailo-all`
- Concurrent MasterPi + playground camera/UART
- Committing HEFs, captures, `.venv`, secrets
- House roam / closed-loop grasp before M2 approach is green
- Driving on a **single** untracked detection frame

---

## Milestone map (M0 → M4)

| Milestone | Meaning | Exit criteria (ruthless) |
|---|---|---|
| **M0** | Safe I/O | MasterPi exclusivity; wheels-raised stop; lease expiry stops motion; live sonar readable |
| **M1** | Perception usable | AE-warmup grab; COCO detect logged; latency noted; **tracker** (≥3 hits) before any vision-driven motor |
| **M2** | Supervised approach | Taped floor; human stop; COCO target approach; sonar hard-stop works; ≤30 s runner always exits stopped |
| **M3** | Supervised grasp | Pose table; grip cycles; cam–arm cal; grasp FSM; pickup metrics (target later: 8/10) |
| **M4** | Room-scale | Only after M2+M3 hold; mapping / return-home — **not started** |

Detail + kill criteria: [architecture-and-roadmap.md](architecture-and-roadmap.md).

---

## Next 3 sessions (execute in order)

These map 1:1 onto BUILD_NEXT ticks. Do not skip Session A to “just drive.”

### Session A — Perception that doesn’t lie (no motors)

**Goal:** Prove the camera + Hailo path under real lighting with a **COCO-visible** object.  
**Maps to:** H5, #6a–#6b (and AE camera lessons below).  
**Duration:** ~45–90 min.

| Step | Action | Done when |
|---|---|---|
| A0 | Pre-flight SOP | MasterPi stopped |
| A1 | Place a **bottle or cup** (not a soda can — COCO has no `can`) in view | Object visible to human |
| A2 | Arm pose: cam-up or slight look-down via `micro_move` / IK | Frame shows object |
| A3 | Warm grab + detect | `vision_smoke` or scripted detect; mean brightness ≫ 20 |
| A4 | Log ≥10 frames | `python -m playground.vision.log_detections --frames 10`; JSONL/CSV contract below |
| A5 | Record p50/p90 latency | Command summary records inference and capture-to-result p50/p90 |
| A6 | Update BUILD_NEXT | H5 + #6b marked done or blocked with reason |

**Known camera pitfalls (must handle):**
- UVC **auto-exposure** needs ~15–25 frames after open; first frames are nearly black.
- `grab_frame()` warms frames; do not trust a single cold OpenCV read.
- Strong red/orange WB cast may remain; detection can still work if exposure is OK.
- Stock COCO will **not** label most soda cans; use bottle/cup/person for M1–M2.

### Session A detection-log contract

Script: `playground/vision/log_detections.py`. Default output is
`/tmp/tiny_pi_car/detections-<UTC>.jsonl`; use `--format csv` for CSV or `--output PATH`
for an explicit destination. The loop is always bounded by `--frames` (default 10).

JSONL is one object per attempted frame, including frames with no detections:

```json
{"schema_version":"tiny_pi_car.detect_log.v1","run_id":"UUID","frame_index":0,"captured_at_utc":"2026-07-15T12:34:56.789+00:00","t_mono_s":123.456,"source":"camera:/dev/video0","frame_ok":true,"image_width_px":640,"image_height_px":480,"brightness_mean":72.1,"capture_ms":810.2,"inference_ms":31.4,"latency_ms":841.6,"detector_status":"ready","detection_count":1,"detections":[{"label":"bottle","score":0.91,"bbox_px":[101.0,52.0,244.0,420.0]}]}
```

CSV is one row per detection. A frame with zero detections still emits one row with blank
detection fields, so frame count and misses remain auditable. Exact header:

```text
schema_version,run_id,frame_index,captured_at_utc,t_mono_s,source,frame_ok,image_width_px,image_height_px,brightness_mean,capture_ms,inference_ms,latency_ms,detector_status,detection_count,detection_index,label,score,bbox_x1_px,bbox_y1_px,bbox_x2_px,bbox_y2_px
```

`latency_ms = capture_ms + inference_ms`. Because the current camera path reopens and performs
the 25-frame AE warmup for each sample, report **both** inference p50/p90 and end-to-end latency
p50/p90. `--image PATH` repeats a still image for bounded Mac/offline input. On a Mac without
Hailo, `--allow-unavailable` may validate the source/schema but prints a warning and **does not**
satisfy Session A. With Hailo available, zero detections or a missing frame exits non-zero and
retains the diagnostic log.

### Definition of Done — Session A

- [ ] Pre-flight evidence says MasterPi inactive; no actuator command ran.
- [ ] One command produced ≥10 `frame_ok=true` records with `detector_status=ready`.
- [ ] The intended COCO bottle/cup/person appears with a plausible pixel bbox in the log.
- [ ] Inference p50/p90 and end-to-end p50/p90 are copied into the session note.
- [ ] Log path, lighting/target/range, misses, and failures are recorded; H5 and #6b are updated.

**Exit Session A:** every Definition-of-Done box above is checked. No chassis translation.

---

### Session B — Safety green light

**Goal:** Prove stop + sonar before any vision-driven drive.  
**Maps to:** #3 live, #4, #5.  
**Duration:** ~45–90 min.  
**Depends on:** Session A optional for vision; **required** before Session C motors on floor.

| Step | Action | Done when |
|---|---|---|
| B0 | Pre-flight; wheels **raised** | — |
| B1 | Live sonar | `watch_sonar` or `sonar_sample --live`; reject 5000/99999 as “clear” |
| B2 | Tune hard-stop mm | Document threshold in navigation notes / BUILD_NEXT |
| B3 | Creep + interrupt | Start short forward; Ctrl-C / lease expire → full stop |
| B4 | Repeat stop ×5 | No coast; always zero velocity |
| B5 | Named poses only | cam-up / look-down / home documented (pose table stub) |
| B6 | Update BUILD_NEXT | #3–#5 checkboxes |

**Kill:** stop fails with wheels raised → **no wheels-down work** until fixed.

### Session B sonar threshold worksheet (#3)

Keep the robot stationary and sample at ≥5 Hz. At each setup collect **20 readings** with the
obstacle measured from the sonar face. Values `>=4999`, including `5000` and `99999`, are invalid
and must produce STOP/UNKNOWN, never “clear.” Save raw readings under `/tmp`.

| Setup | True mm | Median mm | P10 / P90 mm | Invalid / 20 | Notes |
|---|---:|---:|---:|---:|---|
| Soft flat target | 200 | ___ | ___ / ___ | ___ | |
| Soft flat target | 500 | ___ | ___ / ___ | ___ | |
| Soft flat target | 1000 | ___ | ___ / ___ | ___ | |
| Open air | n/a | ___ | ___ / ___ | ___ | Must not become a clear reading |

Record the calibration inputs and selected thresholds:

```text
minimum_reliable_mm: ___
positive_range_error_p90_mm (reading minus tape): ___
desired_static_clearance_mm: 150
extra_margin_mm: 50
provisional_hard_stop_mm: max(250, minimum_reliable_mm + 50,
                              150 + positive_range_error_p90_mm + 50) = ___
provisional_warn_mm: hard_stop_mm + 200 = ___
N2_braking_overshoot_p90_mm (fill after brake test): ___
final_hard_stop_mm: max(provisional_hard_stop_mm,
                        desired_static_clearance_mm + N2_braking_overshoot_p90_mm
                        + positive_range_error_p90_mm + extra_margin_mm) = ___
final_warn_mm: final_hard_stop_mm + 200 = ___
```

Round thresholds **up** to the next 25 mm and never lower the existing 250 mm hard-stop from
stationary evidence alone. If target-distance dropout is ≥10%, open air becomes a finite clear
value, or the minimum reliable range overlaps the selected stop band, #3 is blocked.

### Definition of Done — Session B

- [ ] The four 20-sample sonar rows and every threshold blank above are filled from live evidence.
- [ ] Invalid/stale sonar readings veto motion; #3 records the raw log path and final thresholds.
- [ ] Wheels-raised creep ends at zero on Ctrl-C/lease expiry 5/5 times (#4).
- [ ] Home/cam-up/look-down poses are recorded and failed IK is handled (#5).
- [ ] Every test ends stopped; no wheels-down work occurred after any stop failure.

**Exit Session B:** every Definition-of-Done box above is checked.

---

### Session C — First supervised approach (M2 edge)

**Goal:** Human-supervised creep toward a COCO target with sonar veto.  
**Maps to:** #7a–#7b, #9, #10 (tracker + capped runner + taped approach).  
**Duration:** ~1–2 h.  
**Depends on:** Session A (detect) + Session B (stop/sonar).

| Step | Action | Done when |
|---|---|---|
| C0 | Pre-flight; tape a lane; human at stop | — |
| C1 | Tracker integration | Feed detections through `DetectionTracker`; require ≥3 consecutive hits before yaw/forward |
| C2 | Align yaw only first | Bbox center → capped `yaw_left`/`yaw_right` |
| C3 | Tiny forward steps | Sonar hard-stop + time cap (≤30 s total) |
| C4 | Classify every stop | `target_lost` / `sonar` / `timeout` / `human` logged |
| C5 | Update BUILD_NEXT | #7b, #9, #10 |

**Success:** approached a bottle/cup without collision; always exited stopped.  
**Not success:** pickup, house roam, custom can class.

**Kill:** any near-hit / missed sonar stop → back to Session B.

### Tracker contract used by Session C (#7)

- `playground/autonomy/tracking.py` accepts `{label, score, bbox}` detections in one consistent
  coordinate system and associates only the same class.
- Greedy matching uses IoU ≥0.30 first; centroid distance ≤1.0 mean box diagonal is the fallback.
- Default confirmation is 3 **consecutive** observed frames. Any missed frame immediately revokes
  confirmation and the hit count restarts at one on reacquisition.
- A track may retain its ID for at most two missed frames, but missed tracks are never returned by
  `current_tracks()` and never qualify for motion.
- Motion code may consume only `current_tracks(confirmed_only=True)` plus its independent camera
  freshness, sonar, lease, and timeout gates. Raw detections and unconfirmed tracks are log-only.

### Definition of Done — Session C

- [ ] #7b proves logged/live input cannot produce motion on hits 1–2 or after a missed frame.
- [ ] Runner is capped at ≤30 s and every exit calls stop; stop reasons use the named classes.
- [ ] First wheels-down run is taped, low-speed, and human-supervised after Sessions A and B pass.
- [ ] Target approach succeeds without entering the sonar hard-stop band; near-hits send work back to B.
- [ ] Log contains track ID/hits, sonar, commands, timestamps, and final stop reason; #9–#10 updated.

**Exit Session C:** every Definition-of-Done box above is checked; pickup is not part of this session.

---

## After Session C (do not reorder)

1. Pose table v0 + gripper open/close ×10 supervised (`#11–#12`)
2. Floor-plane / cam–arm cal (`#8`, `#13`)
3. Grasp FSM dry-run then supervised grasp (`#14` → M3)
4. Custom HEF (can/sock/…) **only after** COCO approach is boringly reliable

---

## Session log template (copy into notes or PR)

```text
Date:
Session: A / B / C / other
Operator:
MasterPi stopped: Y/N
Wheels: raised / down
Hailo ready: Y/N
What ran:
Results (detects / sonar mm / stops):
Failures / surprises:
BUILD_NEXT ticks updated:
Follow-up:
```

---

## Quick command card

```sh
sudo systemctl stop masterpi
source .venv/bin/activate
.venv/bin/python -m playground.hailo_probe
.venv/bin/python -m playground.vision_smoke
.venv/bin/python -m playground.vision.log_detections --frames 10
.venv/bin/python -m playground.watch_sonar          # Ctrl-C when done
.venv/bin/python -m playground.sonar_sample --live
.venv/bin/python -m playground.micro_move stop
.venv/bin/python -m playground.autonomy_smoke
pytest tests/test_safety_lease.py tests/test_roam_fsm.py
pytest tests/test_detection_log.py tests/test_tracking.py
# restore stock daemon when finished with playground:
# sudo systemctl start masterpi
```
