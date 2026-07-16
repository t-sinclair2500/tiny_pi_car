# Perception pipeline on Hailo

**Status (2026-07-15):** Hailo-10H runtime **up** — `hailo1x_pci`, `/dev/h1x-0`, HailoRT 5.3, probe `ready: True`. Local HEF: **COCO `yolov8n.hef`** (gitignored). `HailoHEFDetector` and a pure 3-hit tracker are wired; tracker integration / geometry / grasp HEF remain. SSOT: [CURRENT_STATE.md](CURRENT_STATE.md).

**Goal:** timestamped object observations good enough for supervised approach and grasp handoff — never raw single-frame boxes driving motors.

Related: [hardware-and-interfaces.md](hardware-and-interfaces.md) · [navigation.md](navigation.md) · [grasping.md](grasping.md) · [BUILD_NEXT.md](BUILD_NEXT.md) · [docs/hailo.md](../hailo.md) · [docs/research/hailo-perception-grasp-nav.md](../research/hailo-perception-grasp-nav.md) · [scripts/setup_hailo_10h.md](../../scripts/setup_hailo_10h.md)

---

## Ground truth on this robot

| Fact | Implication |
|---|---|
| PCI ID `1e60:45c4` = **Hailo-10H** (AI HAT+ 2 class) | HEFs must be compiled for **`hailo10h`**. Hailo-8 HEFs will not run. |
| Bookworm + HailoRT **5.3** Path B (current) | Do **not** `apt install hailo-all` (Hailo-8 / 4.20). Trixie optional later. Device node is **`/dev/h1x-0`**, not `hailo0`. |
| USB camera `32e6:9005` → `/dev/video0` | Exclusive broker; stock `MasterPi.py` / `Camera.py` fight this device. |
| `playground.vision.detector.build_detector()` | Returns `HailoHEFDetector` when probe ready + HEF present; else `UnavailableHailoDetector` (never invents targets). |
| On-disk HEF | **`yolov8n.hef` only** (COCO80). No seg / custom grasp HEF yet — plan approach around cup/bottle/person/etc. |
| `playground.vision.models.MODELS` | Registry; `grasp-candidate-detector` entry is **intent only** until a HEF exists. |
| `playground.autonomy.detect.observe()` | Wraps vision → `Observation` (detections, sonar, camera_ok, hailo_ready). |
| Zoo FPS numbers are Gen3 x4 class benches | On Pi 5 **x1**, re-measure; drop frames, never grow unbounded queues. |

Sources: [Pi AI software](https://www.raspberrypi.com/documentation/computers/ai.html) · [Hailo-10H object detection zoo](https://github.com/hailo-ai/hailo_model_zoo/blob/master/docs/public_models/HAILO10H/HAILO10H_object_detection.rst)

---

## Pipeline stages

```text
CameraBroker (exclusive /dev/video0 or shared /tmp/robot_cam_latest.jpg)
    → colour / optional undistort (stock CameraCalibration NPZ later)
    → letterbox/crop to HEF input + record inverse transform
    → Hailo worker (one VDevice owner; drop stale frames)
    → NMS / boxes (+ optional masks in grasp mode)
    → tracker (3–5 frame lock) + geometry (floor plane → chassis XY)
    → Observation{t_mono, detections, camera_ok, hailo_ready, ...}
         ↓
    roam / grasp FSMs  (motors only via SafetyGate + RobotIO)
```

| Stage | Owner (code) | Done? | Next concrete work |
|---|---|---|---|
| Exclusive camera | `playground/autonomy/camera_broker.py`, `playground/vision/camera.py` | Stub yes | Fail hard if MasterPi holds device; log source (`shared_latest` vs `grab_frame`) |
| Hailo probe | `playground/hailo_probe.py` | **Yes** | `ready: True` on this machine |
| Detector / log | `playground/vision/detector.py`, `log_detections.py` | **Code yes** | Run live Session A; retain latency + detection evidence |
| Observation adapter | `playground/autonomy/detect.py` | Yes | Add track_id, age_s, bearing, floor_xy fields |
| Tracker | `playground/autonomy/tracking.py` | Pure stub + tests | Wire confirmed tracks into Observation/runner; raw frames never drive |
| Geometry | *missing* | No | Add `playground/autonomy/geometry.py` (intrinsics + floor plane) |
| Replay | *missing* | No | JSON metadata + optional jpeg paths; evaluate offline before motors |
| Grasp HEF | *missing* | No | Seg/custom HEF only after box approach works |
| Undistort | Stock `MasterPi/Camera.py` NPZ | Not wired | Port remap into broker after intrinsics verified |

**Hard rules:** one process owns **`/dev/h1x-0`** (no multi-process VDevice without MPS). Drop old frames if inference lags. Navigation/grasp use only **fresh tracked** observations (`age < ~0.35 s`, hits ≥ 3).

---

## Camera pitfalls {#camera-pitfalls}

| Issue | Symptom | Fix |
|---|---|---|
| UVC auto-exposure cold start | First frames mean ~3 (black); AE settles after ~15–25 frames | `playground.vision.camera.grab_frame()` warms ~25 frames; do not use a single cold `VideoCapture.read()` |
| Stale shared jpg | `/tmp/robot_cam_latest.jpg` from watcher may be dark/old | `grab_frame` ignores shared file if age >3s or mean brightness ≤20 |
| Red/orange WB cast | Usable for detect but ugly | Optional: `v4l2-ctl` WB temp; not required for M1 if detections work |
| MasterPi holds camera | Open fails / “busy” | `sudo systemctl stop masterpi` |
| COCO has no `can` | Soda can visible to human, 0 boxes | Use **bottle/cup/person** for M1–M2; custom HEF later |
| Score cutoff (~0.45) | Weak boxes dropped | Lower only for debugging; never drive motors on low-score singles |

Session A procedure: [SESSIONS.md](SESSIONS.md#session-a--perception-that-doesnt-lie-no-motors).

---

## Model choices (decision criteria)

Match HEF compile arch + HailoRT major version. Prefer zoo HEFs from the same runtime family as installed packages (Pi apt often **5.1.x**; newer zoo HEFs may need newer HailoRT — if `HAILO_NOT_IMPLEMENTED`, pin HEF to runtime or upgrade runtime as a unit).

| Phase | Model | Why pick it | Reject / defer when |
|---|---|---|---|
| **MVP detect** | **`yolov8n`** or **`yolov11n`** (`hailo10h` HEF) | Small, on-chip NMS examples exist, COCO covers cup/bottle/person | Zoo FPS claims; measure Pi5 latency first |
| **MVP safety** | Same net `person` class | Zero extra HEF | Pets poorly covered — ultrasonic + low speed remain mandatory |
| **Grasp mode** | **`yolov8n_seg`** (swap or time-multiplex) | Mask → grip axis better than boxes in clutter | Only when distance < handoff; not full-rate roam |
| **Phase 1.5 depth** | `scdepthv3` or `fast_depth` | Soft free-space cue | After detect FPS budget measured; fuse with sonar, never replace it |
| **Phase 2+** | `yolov5s_personface`, custom-class YOLO, optional VLM | Safety / open-vocab / diagnosis | VLM **async only**, chassis stopped; never in 10–30 Hz loop |
| **Never for MVP** | Hailo-8 HEFs, Cityscapes semantics alone, GenAI in control loop | Wrong arch / domain gap / latency | — |

**MVP pick (done on disk):** official **`hailo10h` `yolov8n`** HEF → `playground/vision/models/yolov8n.hef` (gitignored, COCO80). Keep `UnavailableHailoDetector` when missing. Next model upgrade is optional (`yolov11n` / seg) — not a blocker for approach of COCO-visible objects.

Manifest (commit this, not the HEF): name, zoo URL, SHA256, input WxH, labels file, HailoRT version, measured `p50/p90` ms on this Pi.

---

## Success metrics

### Offline / on-Pi perception (no motors)

| Metric | Definition | MVP gate |
|---|---|---|
| Detector ready path | `hailo_probe` ready + HEF loads without error | Required |
| End-to-end latency | capture → Observation detections | p50 ≤ 100 ms aspirational; **record actual** on x1 |
| Dropped-frame rate | frames skipped under load | Prefer drop over queue > 1 |
| Time-to-first-lock | first track with ≥3 hits on taped target | ≤ 2 s at 0.5–1.5 m |
| Track stability | fragmentations per 10 s approach clip | ≤ 2 |
| Floor XY error | projected vs tape measure / AprilTag | median ≤ 5 cm, p90 ≤ 10 cm in 30–80 cm band |
| Person recall (safety clips) | must-stop scenes | ≥ 0.9; false stop rate logged |

### Before motors may consume detections

- [x] `python3 -m playground.hailo_probe` → `ready: True`
- [ ] One HEF infer on ≥10 Pi frames; boxes + p50/p90 logged, no actuator imports in that path
- [x] Pure tracker rejects single-frame flashes and revokes confirmation after a miss
- [ ] Observation/runner consumes confirmed fresh tracks only
- [ ] `autonomy_smoke` still passes with `RobotIO(live=False)` when Hailo absent **and** when present

---

## Playground experiment checklist (ordered)

Stop `MasterPi.py` before claiming `/dev/video0`. Wheels raised for any later live I/O. No unbounded loops.

1. ~~**Runtime gate**~~ — **DONE** (Bookworm + HailoRT 5.3). Never Bookworm `hailo-all` 4.20.
2. ~~**HEF drop-in**~~ — **DONE** `yolov8n.hef`; still add a one-line manifest JSON (checksum, runtime version) outside git if useful.
3. ~~**Wire `HailoHEFDetector.detect()`**~~ — **DONE**; keep unavailable fallback.
4. **Latency bench** — run `python -m playground.vision.log_detections --frames 10`; retain the JSONL/CSV path and record inference + end-to-end p50/p90. Schema: [SESSIONS.md](SESSIONS.md#session-a-detection-log-contract).
5. **Observation schema bump** — add `track_id`, `hits`, `bearing_rad`, optional `floor_xy_m` to detection dicts; keep backward-compatible dry-run.
6. **Tracker integration** — pure IoU/centroid tracker exists; add track fields to Observation and emit to motion only with consecutive hits ≥3 plus camera freshness.
7. **Floor geometry** — measure camera height/pitch; implement ray–plane; validate with tape at 40/60/80 cm (table in docs, not images in git).
8. **Replay harness** — JSON list of `{t, detections}` (+ optional frame paths outside repo); score precision/recall offline before approach FSM consumes live boxes.
9. **Grasp-mode seg / custom HEF (later)** — only after box approach works on COCO classes; multiplex near handoff range.

Anti-patterns: dual OpenCV capture; inventing detections when Hailo down; committing HEFs/weights; driving chassis from untracked single frames.

---

## Risks

| Risk | Why it hurts | Mitigation |
|---|---|---|
| Wrong apt stack (`hailo-all` on 10H) | Driver fight (`hailo_pci` vs `hailo1x_pci`); breaks `/dev/h1x-0` | Do not install; see [hailo-pi5-gotchas.md](../research/hailo-pi5-gotchas.md) |
| HEF / HailoRT version skew | Load or `HAILO_NOT_IMPLEMENTED` | Pin HEF to installed runtime; upgrade as one matrix |
| Camera contention with stock daemon | Empty frames, broker false confidence | Process policy; lock file already in `CameraBroker` |
| PCIe x1 + thermal throttle | FPS far below zoo | Measure locally; Active Cooler; drop frames |
| COCO domain gap (socks, toys) | Miss household targets | Custom HEF later ([hailo-custom-models.md](../research/hailo-custom-models.md)); open-vocab only Phase 2+ |
| Geometry without cal | Grasp/approach miss | No closed-loop approach until floor XY error meets gate |
| Multi-process Hailo | `HAILO_OUT_OF_PHYSICAL_DEVICES` | Single Hailo worker in autonomy process |

---

## Build next (this doc → code)

Immediate (finish M1):

1. Run and retain the live Pi latency + detection log (no motors).
2. Wire `DetectionTracker` confirmed outputs + fields into Observation.
3. `geometry.py` + tape validation table.
4. Replay JSON harness before any detector-driven `RobotIO(live=True)`.
5. Seg/custom grasp HEF only after COCO box approach is green.
