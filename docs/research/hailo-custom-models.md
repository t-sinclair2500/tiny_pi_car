# Hailo custom / third-party models — how-to roadmap

> **STATUS (2026-07-15):** Zoo COCO **`yolov8n.hef`** already runs here. This DFC essay is for **future** custom/seg HEFs — not a blocker for COCO approach. Runtime is `/dev/h1x-0` (HailoRT 5.3). Do not install Bookworm `hailo-all`. Ops: [hailo.md](../hailo.md) · [CURRENT_STATE.md](../autonomy/CURRENT_STATE.md).

**Status:** research note (2026-07-14). Mix of verified public docs and community paths.  
**Audience:** getting *our own* or non-zoo models onto the MasterPi’s Hailo when stock Model Zoo HEFs are not enough.  
**Related:** [docs/hailo.md](../hailo.md) (bring-up), [docs/autonomy/perception.md](../autonomy/perception.md), `playground/vision/models.py`.

---

## Verdict for this repo

1. **Train / export elsewhere** (x86 Linux or cloud). **Do not expect DFC to run on the Pi.**
2. **Compile for the exact SKU.** This machine’s PCIe ID is `1e60:45c4` → treated as **Hailo-10H** in [docs/hailo.md](../hailo.md). HEFs for `hailo8` / `hailo8l` are **not** interchangeable with `hailo10h`.
3. **Deploy only `.hef` (+ labels metadata)** under `playground/vision/models/` (gitignored via `*.hef` and `playground/vision/models/`). Keep ONNX/weights/datasets off-repo.
4. Prefer **YOLOv8n / YOLO11n detection** for custom classes (socks, cups, toys) first; treat seg/pose as a later grasping upgrade.

---

## Fact vs promising-but-unverified

| Claim | Confidence | Notes |
| --- | --- | --- |
| Pipeline is ONNX/TF → HAR → optimize/quantize → HEF | **Fact** | Official DFC / Ultralytics / RidgeRun writeups |
| DFC needs **x86_64 Linux** (Ubuntu 20.04/22.04 or WSL2); not Pi/ARM | **Fact** | Hailo community + Ultralytics |
| `--hw-arch` must match chip (`hailo8` ≠ `hailo8l` ≠ `hailo10h`) | **Fact** | Community gists + Ultralytics SDK version split |
| Hailo-8/8L → DFC **v3.x**; Hailo-10/15 → DFC **v5.x** | **Fact** (Ultralytics docs) | Confirm against current Developer Zone for 10H |
| Calibration: unlabeled images; ~64 works; **1024** unlocks higher opt levels | **Fact** (community + DFC guides) | Diversity > volume of consecutive frames |
| Ultralytics has **no** `export(format="hailo")` yet; ONNX then DFC | **Fact** (Ultralytics 2025–26 docs) | |
| Custom YOLOv8/11 detection → HEF via `hailomz compile` | **Fact** (many Pi 5 + 8L writeups) | |
| Custom YOLO **seg / pose** → HEF for grasping | **Promising** | Zoo has pose/seg; custom heads need extra validation |
| DeGirum Cloud Compiler → HEF without local DFC | **Promising** | Early access; docs list **Hailo-8/8L**, not 10H yet |
| This Pi’s 10H will run a given community HEF | **Partially verified** | Runtime up (`ready: True`); still validate each HEF on `/dev/h1x-0`; compile target must be `hailo10h` |

---

## 1. End-to-end DFC workflow

```text
Train (PyTorch / TF)
    → export ONNX (or TF / TFLite)
    → parse          →  .har   (Hailo Archive: graph + weights)
    → optimize       →  .har   (INT8 calib + optional .alls script)
    → compile        →  .hef   (Hailo Executable Format)
    → copy to Pi     →  HailoRT / GStreamer / py bindings
```

| Stage | What happens | Typical tools |
| --- | --- | --- |
| **Parse** | Map ONNX/TF ops to Hailo IR; pick start/end nodes | `hailo parser` / `ClientRunner.translate_onnx_model` / `hailomz parse` |
| **Optimize** | Collect activation stats; quantize; optional AdaRound / finetune | `hailo optimize` + **calibration images** + model script (`.alls`) |
| **Compile** | Map layers to HW, schedule, emit HEF for `--hw-arch` | `hailo compiler` / `runner.compile()` / `hailomz compile` |
| **Profile** (optional) | Estimate FPS / utilization from HAR | `hailo profiler` |

**Official / solid references**

- [Ultralytics → Hailo (ONNX then DFC)](https://docs.ultralytics.com/integrations/hailo)
- [RidgeRun: Hailo Dataflow Compiler overview](https://developer.ridgerun.com/wiki/index.php/Hailo/Hailo-8/AI_Software_and_Tools/Hailo_Dataflow_Compiler)
- [RidgeRun: ONNX → Hailo-8L walkthrough](https://www.ridgerun.ai/post/convert-onnx-model-to-hailo8l)
- Hailo Developer Zone (account): DFC wheels + full user guide — https://hailo.ai/developer-zone/
- [hailo-ai/hailo_model_zoo](https://github.com/hailo-ai/hailo_model_zoo) — YAML configs, NMS JSON, `hailomz` CLI

---

## 2. Where compilation happens

| Machine | Role |
| --- | --- |
| **x86_64 Linux workstation / VM / WSL2** | Install DFC (+ optional CUDA GPU for faster optimize). Parse / optimize / compile. |
| **Docker (x86)** | Hailo AI Software Suite image — common when host is not Ubuntu. |
| **Raspberry Pi 5 (ARM)** | **Runtime only:** HailoRT, driver, GStreamer plugins, app code. No DFC. |
| **Cloud** | DeGirum Cloud Compiler (browser) — see §5; verify target arch. |

**Practical rule:** develop and compile on a laptop/desktop; `scp` the `.hef` to the Pi.

---

## 3. Model families that matter for MasterPi

### Detection (MVP for navigation + pickup candidates)

| Family | Path maturity | Notes |
| --- | --- | --- |
| **YOLOv8 / YOLO11** (n/s) | Best documented custom path | Shared detection head; `meta_arch=yolov8` in `.alls` often used for both. Fix `imgsz` (e.g. 640). |
| **YOLOv5** | Mature in Model Zoo | Older; still fine if you already have weights. |
| **MobileNet-SSD** | Zoo / classic | Lighter alternative; different postprocess than YOLO. |

**Custom classes (socks, cups, toys):** fine-tune Ultralytics YOLO on a small labeled set → ONNX → `hailomz compile … --classes N --hw-arch hailo10h` (or DFC Python API). Override COCO-80 NMS JSON / class count.

### Segmentation

Instance / semantic seg exists in the zoo and Ultralytics marks instance seg as a **target** for Hailo. Custom mask heads need compile + host-side mask decode validation. Useful for graspable silhouette; heavier than boxes.

### Keypoint / pose (grasping)

Pose HEFs exist for stock models; custom pose is **promising but unverified** for our arm pipeline. Grasping MVP can stay **bbox + known object size + camera-to-arm calibration** ([grasping.md](../autonomy/grasping.md)); add pose only if box centering is insufficient.

---

## 4. Quantization and calibration

Hailo runs **INT8** graphs. Optimize needs a **calibration set**:

| Requirement | Guidance |
| --- | --- |
| Labels? | **No** — statistics only |
| Count | ~**64** often enough to run; **1024** recommended for higher optimization levels (AdaRound etc.) |
| Content | Same domain as deployment (tabletop / floor under MasterPi camera). Prefer diverse angles/lighting; avoid 1000 consecutive video frames |
| Preprocess | Must match inference: letterbox/resize, RGB order, and whether `.alls` does `normalization([0,0,0],[255,255,255])` vs float `[0,1]` |

If calib is too small or no GPU: DFC may drop `optimization_level` and warn about suboptimal accuracy.

---

## 5. Community tools and converters

| Tool | Use | Link |
| --- | --- | --- |
| **hailo_model_zoo** + `hailomz` | Parse/compile with known YAML (yolov8n, etc.); `--ckpt`, `--calib-path`, `--classes`, `--hw-arch` | https://github.com/hailo-ai/hailo_model_zoo |
| **hailo-rpi5-examples** / **hailo-apps** | On-Pi pipelines (detection.py, GStreamer). Good HEF smoke tests after compile | https://github.com/hailo-ai/hailo-rpi5-examples · https://github.com/hailo-ai/hailo-apps |
| **Ultralytics** | Train + `model.export(format="onnx", imgsz=640, opset=11)` then DFC | https://docs.ultralytics.com/integrations/hailo |
| **DeGirum Cloud Compiler** | Upload `.pt` → HEF in browser; early access | https://docs.degirum.com/ai-hub/workspaces/cloud-compiler — **verify Hailo-10H**; currently marketed for 8/8L |
| **DeGirum PySDK** | Alternate Python runtime wrapping HailoRT | https://docs.degirum.com/ |
| **Third-party guides** | Pi 5 + custom YOLOv8 → HEF (usually **hailo8l**) | e.g. [Cytron ONNX→HEF](https://www.cytron.io/tutorial/raspberry-pi-ai-kit-onnx-to-hef-conversion), [doleron Substack](https://doleron.substack.com/p/deploying-a-custom-yolov8-model-on), [gist mi0iou](https://gist.github.com/mi0iou/87c4b5315e4e0edee0437c7e04290cdb) |

**Caution:** Most Pi AI Kit tutorials assume **Hailo-8L** (`--hw-arch hailo8l`). For this robot, retarget **`hailo10h`** and DFC **v5.x** unless you confirm otherwise.

---

## 6. Fine-tune custom classes → HEF (recommended path)

Concrete roadmap for socks / cups / toys:

1. **Collect** 100–500 labeled images per class (Roboflow / CVAT / Ultralytics). Include clutter and MasterPi camera angles.
2. **Train** on x86: `yolo train model=yolo11n.pt data=custom.yaml imgsz=640`.
3. **Export ONNX** (fixed size):  
   `yolo export model=best.pt format=onnx imgsz=640 opset=11`
4. **Build calib folder** (unlabeled subset of train/val or real tabletop snaps), ideally ≥64, prefer ~1024 for production HEF.
5. **On x86 with matching DFC**, either:
   - **Model Zoo CLI** (detection, zoo-like arch):  
     `hailomz compile yolov8n --ckpt best.onnx --calib-path ./calib --hw-arch hailo10h --classes N`  
     (use the YAML that matches your variant; adjust names for YOLO11 as zoo evolves)
   - **DFC Python API** (Ultralytics guide): parse with correct `end_node_names`, `.alls` with normalization + `nms_postprocess(..., meta_arch=yolov8, engine=cpu)`, optimize, compile.
6. **Ship artifacts:** `grasp_candidates.hef` + `labels.txt` / `metadata.yaml` → Pi `playground/vision/models/`.
7. **Smoke on Pi:** `hailortcli run grasp_candidates.hef` then wire into `playground/vision/` (see `models.py` registry).

Register intent already exists:

- `yolo_object_detection.hef` — generic COCO-ish pickup/obstacle classes  
- `grasp_candidates.hef` — fine-tuned target classes  

---

## 7. Runtime APIs (on the Pi)

| Layer | Role | When to use |
| --- | --- | --- |
| **HailoRT** (`hailortcli`, C++/Python) | Load HEF, infer, VStreams | Lowest-level; smoke tests |
| **python3-hailort** / **hailo_platform** / **pyHailort** | Python bindings to HailoRT | Preferred for `playground/` scripts |
| **GStreamer `hailo*`** (TAPPAS / tappas-core) | Camera → preprocess → infer → overlay | Demos, high-throughput pipelines |
| **hailo-apps / hailo-rpi5-examples** | Batteries-included detection pipelines | Copy patterns; don’t depend on full TAPPAS for MVP |
| **picamera2 Hailo helper** | Pi camera + Hailo shortcut | If using CSI cam; MasterPi often uses USB |
| **DeGirum PySDK** | Higher-level model zoo + postprocess | Optional; adds dependency |

Install path for this image is sketched in [docs/hailo.md](../hailo.md) (`hailo-dkms`, `hailort`, `python3-hailort`). Match **runtime major** to the DFC that produced the HEF.

---

## 8. Practical path for `tiny_pi_car`

```text
[x86 workstation]
  dataset → ultralytics train → best.pt → ONNX
  DFC v5.x / hailomz → grasp_candidates.hef  (--hw-arch hailo10h)
       │
       ▼ scp / USB
[Pi 5 + Hailo-10H]
  playground/vision/models/grasp_candidates.hef   # gitignored
  playground/vision/models.py                     # registry only
  HailoRT infer → detections → autonomy/grasp
```

**Do**

- Keep HEFs and calib dumps local / external storage.
- Version HEFs by name + checksum outside git (or release assets).
- Match preprocess in Python to what the HEF expects (letterbox, RGB, size).
- Stop at detection MVP before pose/seg.

**Don’t**

- Commit `.hef`, `.onnx`, weights, or capture dumps.
- Compile with `hailo8l` “because the tutorial said so” for this 10H board.
- Leave long-running GStreamer demos holding `/dev/video0` while debugging other vision tools.

---

## 9. Failure modes (expect these)

| Failure | Symptom | Mitigation |
| --- | --- | --- |
| **Unsupported ops** | Parse fails or suggests cutting start/end nodes | Export simpler ONNX; cut graph before exotic ops; use zoo-supported backbone/head |
| **Wrong end nodes / NMS JSON** | Compile `StopIteration` / empty NMS / garbage boxes | Regenerate NMS config for **class count**, strides, `imgsz`; don’t reuse COCO-80 JSON for 3-class models |
| **NMS on device vs host** | Latency or API shape surprises | `.alls` `nms_postprocess(..., engine=cpu)` runs NMS on host (common for YOLOv8); raw tensors → DIY NMS on host if disabled |
| **Fixed input size** | Runtime shape errors | Export and compile one `imgsz`; letterbox camera frames to that size |
| **Wrong `--hw-arch`** | HEF won’t load / wrong device arch | Compile for `hailo10h` here; never mix 8 / 8L / 10H HEFs |
| **DFC vs HailoRT version skew** | Load failures after apt upgrade | Pin DFC generation to runtime (3.x↔8/8L, 5.x↔10H per Ultralytics) |
| **Quantization drop** | Misses small/dark objects | Better calib; more diverse lighting; higher opt level; slightly larger model (n→s) |
| **Dynamic shapes** | Not supported | Always static `imgsz` |

---

## 10. Checklist (shortest path)

- [x] Confirm 10H runtime: `/dev/h1x-0`, `hailortcli fw-control identify` ([docs/hailo.md](../hailo.md)).
- [ ] Decide MVP: custom **detect** HEF only.
- [ ] Train YOLO11n/YOLOv8n on custom classes on x86.
- [ ] Export ONNX @ fixed 640; build calib set.
- [ ] Compile with DFC **v5.x** / `hailomz`, `--hw-arch hailo10h`, `--classes N`.
- [ ] Copy HEF + labels → `playground/vision/models/`.
- [ ] `hailortcli run …` then integrate with `playground.vision` / autonomy detect path.
- [ ] Only then evaluate seg/pose for grasp refinement.

---

## Link dump

| Topic | URL |
| --- | --- |
| Ultralytics Hailo guide | https://docs.ultralytics.com/integrations/hailo |
| Hailo Model Zoo | https://github.com/hailo-ai/hailo_model_zoo |
| Hailo apps (ex infra) | https://github.com/hailo-ai/hailo-apps |
| RPi5 examples | https://github.com/hailo-ai/hailo-rpi5-examples |
| Raspberry Pi AI software | https://www.raspberrypi.com/documentation/computers/ai.html |
| RidgeRun DFC overview | https://developer.ridgerun.com/wiki/index.php/Hailo/Hailo-8/AI_Software_and_Tools/Hailo_Dataflow_Compiler |
| RidgeRun model scripts / NMS | https://developer.ridgerun.com/wiki/index.php/Hailo/Hailo-8/AI_Software_and_Tools/Hailo_Model_Scripts |
| DeGirum Cloud Compiler | https://docs.degirum.com/ai-hub/workspaces/cloud-compiler |
| Hailo community (DFC host, calib) | https://community.hailo.ai/ |
| YOLO11n → HEF (example, often hailo8) | https://common.rosecityrobotics.com/YOLO_ObjectDetection/YOLOv11n_to_Hailo8_Guide.html |
