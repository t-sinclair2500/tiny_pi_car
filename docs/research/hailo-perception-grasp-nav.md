# Hailo-10H perception for indoor roam + reliable pickup

> **STATUS (2026-07-15):** Runtime + COCO **`yolov8n.hef`** are live (`/dev/h1x-0`, HailoRT 5.3). This note remains a **dream-big model roster** — no grasp/seg/depth HEF on disk yet. Device node is **`h1x`**, not `hailo0`. Do not `apt install hailo-all`. **Sonar is already on this robot** (I2C-1 `@0x77`) — fuse with vision. Ops SSOT: [CURRENT_STATE.md](../autonomy/CURRENT_STATE.md) · [hailo.md](../hailo.md).

**Status:** research note (dream-big, grounded in Hailo zoo / GenAI docs as of mid-2026)  
**Platform:** Raspberry Pi 5 + Hailo-10H (PCIe; see `docs/hailo.md`) + USB camera + **on-board ultrasonic** + MasterPi mecanum + 5-DOF arm  
**Goal:** a phased perception roster that can (1) roam a house without hitting people/pets/furniture and (2) find, approach, and pick up known household objects with measurable reliability.

Related in-repo docs: `docs/hailo.md`, `docs/autonomy/perception.md`, `docs/autonomy/grasping.md`, `docs/autonomy/navigation.md`. Sibling research topics (conceptual; files may not exist yet): **official zoo HEF bring-up**, **custom HEF compile / fine-tune pipeline**.

---

## 1. Problem framing

Indoor house roaming + pickup is not one model. It is a **scheduler over several tasks** with different latency and risk budgets:

| Task | Cadence | Failure mode if wrong |
|------|---------|------------------------|
| Find-and-approach (object detect + track) | 10–30 Hz | Miss target / chase clutter |
| Free-space / obstacle cue | 5–15 Hz | Collision, stuck |
| Person/pet safety | ≥10 Hz, hard stop | Injury / scare |
| Grasp affordance (where to grip) | 2–10 Hz near object | Empty grasp, tip, crush |
| Optional high-level VLM | Event / sparse | Latency; must not block motors |

**Non-negotiables for this robot:** low chassis/arm speeds, explicit stop, short timeouts, ultrasonic as a hard near-field veto, camera broker owns the device (see autonomy docs). Perception proposes; motion and `ArmIK` remain authorities.

**Hardware reality check (this repo):** PCIe shows Hailo-10H (`1e60:45c4`). Runtime is **up** (`/dev/h1x-0`, HailoRT 5.3) — re-measure HEF timing on-device; do not trust vendor Gen3 x4 benches. FPS numbers below are **vendor zoo bench figures**, not Pi5 x1 measurements—treat them as upper bounds.

---

## 2. What Hailo-10H actually supports

Verified from Hailo product pages, Model Zoo (`hailo-ai/hailo_model_zoo` **master** = Hailo-10/15), and GenAI zoo (`hailo-ai/hailo_model_zoo_genai`):

- **Classical vision HEFs** for Hailo-10H: object detection, instance segmentation, pose, semantic segmentation, depth estimation, oriented detection, person/face nets, zero-shot variants (e.g. FastSAM, YOLO-World), CLIP-class encoders, etc.
- **GenAI on Hailo-10H:** dedicated DDR + INT4-friendly stack; official small LLMs and VLMs via Hailo Model Zoo GenAI / Hailo-Ollama (not invented): e.g. `Qwen2-VL-2B-Instruct`, `Qwen3-VL-2B-Instruct`, `Llama3.2-1B-Instruct`, `Qwen2.5-1.5B-Instruct`, `Qwen3-1.7B-Instruct`, Whisper-{Tiny,Base,Small}. These are **seconds-scale** interactive models (TTFT ~0.3–1.5 s, ~5–10 tok/s on published tables)—useful for sparse reasoning, **not** closed-loop control.
- **Compile path:** zoo HEFs for `hailo10h`, or custom ONNX → Dataflow Compiler → `.hef` (x86 Ubuntu compile machine typical). Sibling topic: custom HEF / fine-tune.

Do **not** use Hailo-8-only HEFs or the `hailo8` driver branch on this board.

---

## 3. Task-by-task model choices

### 3.1 Object detection — find-and-approach

**Role:** class + box → tracker → chassis approach vector. Prefer small/fast COCO detectors first; fine-tune later on household objects (cups, toys, remotes).

| Candidate (Hailo-10H zoo) | Why | Caveat |
|---------------------------|-----|--------|
| **`yolov8n`** | Starred apps path; ~375 FPS zoo BS=1; mature NMS-in-HEF examples | COCO classes only until custom |
| **`yolov11n`** | Newer family, ~302 FPS zoo; similar footprint | Slightly less example glue than v8 in older tutorials |
| **`yolo26n`** | NMS-free family in recent zoo | Different postprocess path—validate runtime before betting MVP |
| **`yolov5s` / `yolov8s`** | Better mAP when nano misses small objects | Burns budget if also running seg + depth |
| **`yolo_world_v2s`** (zero-shot) | Open-vocab “find the red mug” without full retrain | Heavier; better as Phase 2+ experiment |
| **`yolov5s_personface`** (Hailo in-house) | Strong person/face prior for safety lane | Two-class; complementary to general detector |

**MVP pick:** `yolov8n` (or `yolov11n` if apps/examples on your HailoRT version prefer it). Track with a light BYTE/SORT-style filter; never drive motors from a single frame.

### 3.2 Instance segmentation / grasp affordance

**Role:** mask → contact patch / grasp axis in image → project with camera extrinsics + floor/arm calibration → gripper open width and approach pose. Boxes alone are weak for clutter and thin handles.

| Candidate | Why | Caveat |
|-----------|-----|--------|
| **`yolov8n_seg`** | Fast instance masks (~311 FPS zoo); same family as detector | Mask quality on tiny objects needs eval |
| **`yolov8s_seg`** | Better mask mAP (~36+ HW) when n_seg fails grasp | ~138 FPS zoo—still fine if scheduled |
| **`yolov5n_seg` / `yolov5s_seg`** | Well-supported in Hailo-apps seg demos | Older arch |
| **`yolo26n_seg` / `yolo26s_seg`** | Newer seg family | Postprocess maturity |
| **`fast_sam_s`** | Zero-shot masks (prompted regions) | Not class-aware; good for “segment whatever is in the ROI” |
| Dedicated grasp nets (e.g. GG-CNN / Contact-GraspNet style) | True affordance | **Not** first-class in public Hailo-10H tables—custom HEF research if classical masks plateau |

**Practical affordance without a grasp CNN:** from the instance mask, estimate centroid, major axis (PCA on mask pixels), and a contact strip on the upper/near edge for top-down or side grasp; reject if mask area unstable across N frames or if ultrasonic says “too close / unexpected.”

**MVP pick:** `yolov8n_seg` in a **near-field grasp mode** only (switch HEF or multi-net schedule when distance < threshold), not full-rate while roaming.

### 3.3 Pose / keypoints

**Role on this platform:**

- **Person:** `yolov8s_pose` / `yolov8m_pose` / `centerpose_regnetx_800mf` — posture / proximity for soft stops (kneeling child, pet height is *not* covered by human pose).
- **Object 6D pose:** useful for known rigid objects, but 5-DOF + stock `ArmIK` usually wants **reachable XYZ + simple orientation**, not full SE(3). Prefer mask + known object height priors before investing in custom 6D HEFs.

**MVP:** skip object keypoints. Optionally run **`yolov8s_pose`** only in “human nearby” safety mode, or rely on person boxes from detection/`yolov5s_personface`.

### 3.4 Scene understanding / obstacles / free space

Fuse **vision soft cues** with **ultrasonic hard veto**:

| Cue | Model / sensor | Notes |
|-----|----------------|-------|
| Monocular depth | **`scdepthv3`** (starred), **`fast_depth`** (tiny/fast) | Zoo has Hailo-10H depth HEFs. Relative/metric quirks—calibrate against ultrasonic at 20–80 cm |
| Zero-shot depth | **`depthanything_vits` / `depthanything_v2_vits`** (zoo changelog / other-tasks) | Stronger geometry; heavier—Phase 2+ |
| Semantic free-space | **`segformer_b0_bn`**, **`stdc1`**, FCN variants (Cityscapes-trained) | Domain gap: outdoor street labels ≠ living room. Fine-tune or treat as weak prior |
| Stereo | **`stereonet`** (listed for 10H/15H in zoo releases) | Needs dual cameras—MasterPi is typically mono |
| Near obstacle | **Ultrasonic** | Always-on stop / slow; do not wait for DNN |

**MVP:** ultrasonic + detector “large unknown blob / person” + simple floor-plane geometry from calibrated camera. Add **`scdepthv3`** as Phase 1.5 once the camera broker and Hailo runtime are stable. Do not block navigation on Cityscapes semantics until fine-tuned.

### 3.5 Person / pet safety

| Approach | Model | Notes |
|----------|-------|-------|
| Person + face | **`yolov5s_personface`** | Purpose-built; good safety lane |
| Person (COCO) | Any YOLO `person` class | Pets often mislabeled or missed |
| Human pose | **`yolov8s_pose`** | Extra signal for “human in frame” |
| Pet | Custom fine-tune or open-vocab (`yolo_world_v2s`) + dataset | **Expect MVP miss rate**—mechanical limits: low speed + ultrasonic + “stop if uncertain large motion” |

**Policy sketch:** if person/pet confidence > τ within soft radius → decelerate; within hard radius or ultrasonic hit → **immediate stop**, open gripper if closing, no resume without clear frames.

### 3.6 Optional VLM / LLM on Hailo-10H

Hailo-10H **does** run higher-level models officially (GenAI zoo). Useful roles:

- “What am I looking at?” / “Is this graspable / fragile?”
- Natural-language goal → object name for detector/open-vocab
- Whisper for voice goals (optional)

**Do not** put VLM tokens in the 10–30 Hz control loop. Schedule as **async jobs** when chassis is stopped or crawling.

| Model | Role | Published character |
|-------|------|---------------------|
| **`Qwen2-VL-2B-Instruct`** | Image+text Q&A | ~2B, TTFT ~1 s, ~7 tok/s (GenAI tables) |
| **`Qwen3-VL-2B-Instruct`** | Newer VLM | Similar size; check HailoRT ≥5.3 |
| **`Qwen2.5-1.5B-Instruct` / `Llama3.2-1B-Instruct`** | Text planner / tool calling | No vision unless paired with CLIP/VLM |
| **`Qwen2-1.5B-Instruct-Function-Calling-v1`** | Structured actions | Still sparse, not realtime |

**Phase:** Advanced / optional after classical stack works. Sibling topic: GenAI service packaging vs exclusive VDevice (community reports show multi-service needs a **single device manager + request queue**).

---

## 4. Phased model roster

### Phase 0 — Bring-up (no autonomy)

- HailoRT + `/dev/h1x-0` + one official HEF smoke (`hailortcli` / `playground` probe) — **runtime DONE**; keep re-running after driver/OS changes.
- Camera broker + undistort; ultrasonic read; arm home + stop.

### Phase 1 — MVP (recommended stack)

| Lane | Model | Rate idea |
|------|-------|-----------|
| Detect + approach | **`yolov8n`** | Continuous while roaming |
| Safety | COCO `person` from same net **or** interleaved **`yolov5s_personface`** | Continuous; hard stop policy |
| Grasp near target | **`yolov8n_seg`** | On approach / grasp mode only |
| Range veto | Ultrasonic | Continuous |
| Geometry | Floor-plane + camera–arm calibration | Offline cal, online use |

Defer: depth DNN, pose, VLM, open-vocab, custom classes (unless one object class is fine-tuned early).

### Phase 2 — Indoor roam quality

- Add **`scdepthv3`** (or `fast_depth`) fused with ultrasonic.
- Upgrade detect to **`yolov8s` / `yolov11s`** or custom-class HEF (sibling: custom HEF).
- Optional **`yolov8s_pose`** for human soft stops.
- Tracker + occupancy grid / costmap from depth + ultrasonics.

### Phase 3 — Reliable pickup advanced

- Grasp mode: **`yolov8s_seg`** or **`fast_sam_s`** on ROI; consider custom affordance HEF if metrics stall.
- Known-object priors (height, grip width) in config, not in the neural net.
- Optional sparse **`Qwen2-VL-2B-Instruct`** for failure diagnosis / object ID when detector disagrees.

### Phase 4 — Dream-big (still grounded)

- Open-vocab **`yolo_world_v2s`** + VLM confirmation.
- Fine-tuned indoor semantic free-space (not raw Cityscapes).
- Multi-service Hailo device manager (vision + Whisper + VLM) with strict priority: **safety > detect > depth > genai**.
- Stereo / second camera only if mechanical redesign happens.

---

## 5. Multi-model concurrent inference on Hailo-10H

**Feasible, with caveats:**

1. **Resource model:** Hailo-10H has substantial on-module memory vs Hailo-8-class parts, so **multiple HEFs can be loaded / cached**, but the **inference context (VDevice) is effectively exclusive** for a running graph. Community Pi AI HAT+ 2 experience: second process → `HAILO_OUT_OF_PHYSICAL_DEVICES` unless one owner serializes work.
2. **HailoRT Model Scheduler / multi-network:** vendor path for switching or multiplexing networks in one process—prefer **one Hailo worker process** that owns the device and runs a priority queue (safety detect every frame; seg every Nth frame near target; depth at 5 Hz; VLM only when idle).
3. **Do not** run GenAI (Qwen-VL / LLM) in parallel with a hard realtime GStreamer pipeline without measuring thermal + queue latency. GenAI jobs should **yield** immediately to safety/detect.
4. **Pi5 PCIe x1** reduces headroom vs zoo Gen3 x4 benches—budget FPS locally; drop frames rather than grow queues (`docs/autonomy/perception.md`).
5. **Practical MVP concurrency:** time-multiplex `yolov8n` @ full rate and swap to `yolov8n_seg` for 200–500 ms bursts when entering grasp range (or keep both loaded and alternate if scheduler allows without reload cost).

---

## 6. Evaluation metrics for “reliable pickup”

Define a fixed object set, lighting set (day / evening / lamp), and floor surfaces. Record video + ultrasonic + command traces.

### Perception (offline replay first)

- **Detection:** per-class Precision / Recall / mAP@0.5; **time-to-first-lock** (s); track fragmentations per approach.
- **Segmentation:** mask IoU vs hand labels on grasp frames; **mask stability** (IoU across 5 frames).
- **Localization:** median / P90 error (cm) of projected object XY vs tape measure / AprilTag at 30–80 cm.
- **Safety:** person/pet recall in “must-stop” clips; false-stop rate on empty rooms (nuisance).

### End-to-end grasp (on hardware, low speed)

| Metric | Definition | MVP target (aspirational) |
|--------|------------|---------------------------|
| **Approach success** | Stops in arm annulus without collision | ≥90% |
| **Grasp success** | Object lifted ≥2 cm and held 2 s | ≥70% Phase1 → ≥90% Phase3 |
| **Empty grasp rate** | Close with no contact | ≤10% |
| **Knock / tip rate** | Object tips or falls | ≤5% |
| **Retry count** | Grasps until success or abort | median ≤2 |
| **Cycle time** | Detect → lift | report P50/P90 |
| **Safety interventions** | Human e-stop or policy stop | count; zero contact with living beings |
| **Abort clarity** | System stops with logged reason | 100% of failures classified |

Ablate: box-only vs mask; with/without ultrasonic veto; with/without depth HEF. Promote models only when metrics move.

---

## 7. Suggested software shape (playground)

```text
camera_broker ──► hailo_worker (priority queue)
                      ├─ detect HEF (always)
                      ├─ personface / pose (safety)
                      ├─ seg HEF (grasp mode)
                      ├─ depth HEF (optional)
                      └─ genai client (async, lowest priority)
                 ──► observations (versioned) ──► nav / grasp FSMs
ultrasonic ─────────────────────────────────────► hard veto
```

Artifacts (`.hef`, weights) stay **out of git**; keep a manifest (name, zoo URL, SHA256, input size, measured Pi FPS). Sibling research: **official zoo HEF catalog + download script**, **custom HEF compile checklist**.

---

## 8. Sources (non-exhaustive)

- Hailo-10H product / GenAI claims: [hailo.ai Hailo-10H](https://hailo.ai/products/ai-accelerators/hailo-10h-ai-accelerator/)
- Vision Model Zoo (Hailo-10H tables): [hailo-ai/hailo_model_zoo](https://github.com/hailo-ai/hailo_model_zoo) — `docs/public_models/HAILO10H/*.rst`
- GenAI models: [hailo-ai/hailo_model_zoo_genai](https://github.com/hailo-ai/hailo_model_zoo_genai) `docs/MODELS.rst`
- Person-face net: zoo `hailo_models/personface_detection`
- Multi-service VDevice constraint (community): Pi forums / multi-service wrappers discussing exclusive inference context on AI HAT+ 2

---

## 9. One-line recommendation

**MVP stack:** `yolov8n` (find + person) + ultrasonic veto + grasp-mode `yolov8n_seg` + calibrated floor/arm geometry; add `scdepthv3` and optional `Qwen2-VL-2B` only after measured pickup metrics justify the complexity.
