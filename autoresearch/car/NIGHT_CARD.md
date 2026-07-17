# Night card — Qwen OpenCode (no chassis motion)

**Audience:** `autoresearch-director` (27B) → `autoresearch-worker` (35B), helper 2B, reviewer 9B.  
**Host SSH:** `rpicarbox.local` (alias `rpicarbox-1`). Repo on Pi: `~/Desktop/tiny_pi_car`.  
**Human away:** progress is fine; **do not move the wheels / mecanum / chassis.**

## Hard fence (tonight)

| Allowed | Forbidden |
|---|---|
| Camera capture, AE warmup tuning, look at images | Any mecanum / `physical_trial` wheel actions (`forward`/`reverse`/`yaw_*` chassis) |
| Hailo detect, HEF A/B, score_thresh, letterbox, logging | Unbounded loops; inventing hardware results |
| Tracker / Observation plumbing (no motors) | Driving on detections |
| Arm/gripper **only if** UART exists **and** move is timed + stopped — prefer **skip arm** tonight unless needed for cam pose | Leaving motors running |
| Edit `playground/vision/**`, `playground/experiments/perception/**`, `autoresearch/car/**`, latency helpers | Secrets, non-`hailo10h` HEFs |

Always: stop `masterpi.service` before owning `/dev/video0`. Stop any arm trial in `finally`.

## Live facts (2026-07-16 preflight)

- OS: Trixie; `hailo-h10-all` present; probe **`ready: True`**
- Device node: **`/dev/hailo0`** (module `hailo1x_pci`)
- `/dev/video0` present; camera snap OK (`/tmp/tiny_pi_car/preflight.jpg`)
- On-Pi HEFs already: `yolov8m_h10.hef`, `yolov11m_h10.hef` — **A/B these first**
- UART may be missing — **no chassis/arm** until `ttyAMA0` exists; perception-only is enough
- Prefer measuring on Pi via SSH; pull JPEGs/JSONL back and **read the images**

## How to measure (no motion)

```bash
# status
.venv/bin/python scripts/pi_agent_gate.py status

# snap + inspect
.venv/bin/python scripts/pi_agent_gate.py camera-snap --stop-masterpi
# scp rpicarbox.local:/tmp/tiny_pi_car/snap-*.jpg captures/ && Read the jpg

# capture-only latency (no Hailo; hypotheses 1–2)
ssh rpicarbox.local 'cd ~/Desktop/tiny_pi_car && sudo -n systemctl stop masterpi; \
  .venv/bin/python -m playground.vision.capture_bench --samples 5'

# latency / detections (finite)
ssh rpicarbox.local 'cd ~/Desktop/tiny_pi_car && sudo -n systemctl stop masterpi; \
  .venv/bin/python -m playground.vision.log_detections --frames 30 --output /tmp/det.jsonl'

# suite / A/B when second HEF exists
.venv/bin/python scripts/vision_suite_status.py --host rpicarbox.local
ssh rpicarbox.local 'cd ~/Desktop/tiny_pi_car && .venv/bin/python scripts/hailo_ab_compare.py --hef-a playground/vision/models/yolov8m_h10.hef --hef-b playground/vision/models/yolov11m_h10.hef --images captures/ab_frames'
```

## Measured baseline (no motion, 10 frames)

### Before H1 fix (reopen-per-frame, warmup=25)
| Metric | Value | Implication |
|---|---|---|
| inference p50/p90 | **~28 / 55 ms** | Hailo is already fast |
| end-to-end latency p50 | **~3490 ms** | Capture/warmup path dominated — reopen + AE per frame |

### After H1 fix (persistent camera, warmup=5) ✅
| Metric | Value | Implication |
|---|---|---|
| capture p50 | **~103 ms** | Single USB frame read, no open/close overhead |
| inference p50/p90 | **~27 / 28 ms** | Hailo-10H steady (both v8m and v11m) |
| end-to-end latency p50 | **~130 ms** | **27x improvement** over old pipeline |
| detections | "person" FP at thresh≤0.35, none at 0.45+ | Ambient scene has no COCO objects; need staged targets |

### Council metric (fixed scalar — maximize)

| Field | Role |
|---|---|
| **`score`** | `100 * (500 - latency_p50_ms) / (500 - 50)` clipped to \[0, 100\] |
| **`hard_gates_passed`** | All frames valid; inference_p50 ≤ 150 ms; latency_p50 ≤ 2000 ms |
| detections | Logged but **not scored** (no FP farming on empty scenes) |

Host command: `.venv/bin/python scripts/night_perception_eval.py --json`  
(~130 ms e2e ≈ score **~84**). Log under `.autoresearch/runs/`.

## Hypothesis queue (pick ONE per trial; cycle families on plateau)

1. **AE warmup vs capture latency** — Default 25 warmup frames dominate wall time. Sweep `warmup_frames` ∈ {5,10,15,20,25} after a settled stream; keep quality (mean brightness > 20) while cutting capture_ms.
2. **Persistent camera vs open/close per frame** — `log_detections` may reopen V4L2 each sample. Hold one `VideoCapture`, grab N frames; compare p50 capture_ms.
3. **Shared latest-frame broker** — Writer process/thread drops frames to `/tmp/robot_cam_latest.jpg`; detector never blocks on AE. Measure end-to-end age_s + detect FPS.
4. **Letterbox / preprocess on Pi vs Hailo path** — Profile CPU time in `_letterbox` + RGB convert vs `infer`. Try smaller path (reuse buffer, cv2.INTER_LINEAR vs AREA) without changing HEF input size unless measured.
5. **score_thresh sweep** — {0.25,0.35,0.45,0.55,0.65} on the same 30-frame log; maximize useful cup/bottle recall with precision not collapsing.
6. **HEF A/B (on disk)** — `yolov8m_h10.hef` vs `yolov11m_h10.hef` on identical frames: dets/frame, inference_ms, qualitative boxes. Point `prefer_hef` / candidate METADATA at the winner.
7. **VDevice / scheduling** — Confirm single owner of Hailo; avoid multi-process fights. Measure if keeping HEF loaded across frames beats reload.
8. **Resolution / ROI** — Full frame vs center crop before letterbox: latency vs recall for tabletop objects.
9. **Pi vs Hailo split** — Keep NMS-in-HEF; move only cheap CPU work (grab, letterbox, JSON log) to Pi. Do **not** run a second full detector on CPU. Document where time goes (pie chart in run log).
10. **Tracker confirm streak** — Wire `DetectionTracker` (≥3 hits) into Observation without motors; measure ID stability on a static cup. No chassis follow.
11. **Async pipeline** — Overlap next `grab` with current `infer` (double buffer). Target higher effective FPS without raising inference_ms.
12. **Postprocess parse cost** — Profile `_parse_nms` on Pi; vectorize / early-exit low counts if it shows in traces.

## Director standing order

1. Prefer hypotheses **1 → 5 → 6 → 9 → 11** first (latency + usefulness).
2. One change per trial; keep/discard with numbers.
3. After 3 discards in a family, switch family.
4. You may edit this file and `program.md` if the fence stays: **no wheel motion**.
5. Reviewer blocks only: fake metrics, wheel motion, unbounded loops, non-hailo10h HEFs.

## Start (human / host)

```bash
lms server status   # ensure 27B/35B/9B/2B available
opencode serve --port 4096
# then talk to autoresearch-director with: read autoresearch/car/NIGHT_CARD.md and run perception-only trials
```
