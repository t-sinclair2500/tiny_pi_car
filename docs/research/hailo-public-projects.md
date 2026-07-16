# Hailo on Raspberry Pi — public projects survey

> **STATUS (2026-07-15):** Our stack is Hailo-10H + HailoRT 5.3 on Bookworm (`/dev/h1x-0`). Public repos often say `sudo apt install hailo-all` — that is the **Hailo-8** path; do not copy it. Steal pipeline patterns only. Ops: [hailo.md](../hailo.md).

Research note for **tiny_pi_car** (Pi 5 + Hailo-10H PCIe + HiWonder MasterPi mecanum/arm).  
Snapshot: **2026-07-14**. Stars from GitHub API at survey time.

**Local context:** see [`docs/hailo.md`](../hailo.md) (Hailo-10H bring-up) and [`docs/autonomy/perception.md`](../autonomy/perception.md) (intended pipeline). Most public examples target **Hailo-8 / 8L**; treat HEFs and driver branches as **architecture-specific**.

---

## Top projects (ranked by relevance to tiny_pi_car)

| Rank | Project | Stars | Why it matters here |
|-----:|---------|------:|---------------------|
| 1 | [hailo-ai/hailo-rpi5-examples](https://github.com/hailo-ai/hailo-rpi5-examples) | **933** | Canonical Pi5 + AI Kit/HAT pipelines: detection, pose, segmentation, **person tracking** callbacks, GStreamer + Python. Best starting reference for async camera→Hailo. |
| 2 | [codefortheplanet/…-ROS2-Robot-Car](https://github.com/codefortheplanet/Raspberry-Pi-5-AI-HAT-plus-for-Computer-Vision-Autonomous-Driving-Tasks-on-ROS2-Robot-Car) | **0** | **HiWonder robot car + AI HAT+ + ROS2**: patches stock YOLOv5 ROS2 node to run `.hef` on Hailo (~3s CPU → ~100ms). Closest public HiWonder+Hailo path. |
| 3 | [kyrikakis/hailo_tappas_ros2](https://github.com/kyrikakis/hailo_tappas_ros2) | **34** | Mature community **ROS2 Jazzy + TAPPAS** Docker on Pi5; multi-model nodes (YOLO + face), topic publish, low host CPU. Pattern for later Nav2 wiring. |
| 4 | [DurraniHakim27/…ThermoVision…](https://github.com/DurraniHakim27/Autonomous-Navigation-IoT-Robot-with-Vision-Thermal-Sensing-and-Control) | **0** | **Pi5 + Hailo-8 + mecanum**: YOLO + SCDepthV3 on Pi, serial cmds to ESP32 for omnidirectional drive. Architecture twin for “perception on Pi, low-level motion elsewhere”. |
| 5 | [Stonej29/pi-comp-vision](https://github.com/Stonej29/pi-comp-vision) | **2** | Person detect + **smooth pan/zoom follow** on Pi5/Hailo-8L (~30 FPS YOLOv8s), MJPEG stream, hysteresis. Copy for person-follow control filtering. |
| 6 | [hailo-ai/Hailo-Application-Code-Examples](https://github.com/hailo-ai/Hailo-Application-Code-Examples) | **211** | Python object detection with optional **`--track` / BYTETracker**; C++ **SCDepthv3** / StereoNet depth samples. Portable beyond GStreamer. |
| 7 | [koh43/pi_hailo_ros2](https://github.com/koh43/pi_hailo_ros2) | **8** | Pi5 + AI HAT (8L) ROS2 Jazzy + venv + TAPPAS notes. Documents the painful host install path. |
| 8 | [TrescherDe/ros2-hailort](https://github.com/TrescherDe/ros2-hailort) | **8** | Thin HailoRT↔ROS2 integration; often cited by Hailo staff when asked for official ROS (there is none). |
| 9 | [slgrobotics/ros2_inference_stereo](https://github.com/slgrobotics/ros2_inference_stereo) | **1** | Pi5 ROS2: stereo→PointCloud2 + detection → Nav2/BT. Depth fusion pattern even if stereo HW differs. |
| 10 | [CursedPrograms/KIDA-Robot-v01](https://github.com/CursedPrograms/KIDA-Robot-v01) | **0** | Full Pi5 tank + Hailo + dual cam + sonar (HC-SR04) + local LLM. Useful BOM/power ideas; code maturity unclear. |

**Supporting infra (not robots, but required stack):**

| Repo | Stars | Role |
|------|------:|------|
| [hailo-ai/hailort](https://github.com/hailo-ai/hailort) | 204 | Runtime |
| [hailo-ai/hailort-drivers](https://github.com/hailo-ai/hailort-drivers) | 91 | PCIe driver (`master` for 10H; do not use `hailo8` branch on this machine) |
| [hailo-ai/hailo-apps-infra](https://github.com/hailo-ai/hailo-apps-infra) / [hailo-apps](https://github.com/hailo-ai/hailo-apps) | ~194–454 | Pipeline building blocks behind rpi5-examples |
| [raspberrypi/rpicam-apps](https://github.com/raspberrypi/rpicam-apps) | 565 | Official CSI camera + Hailo post-process demos |

---

## What people actually build

### Autonomy / robots

- **Perception offload, CPU for Nav2/control.** Duggan “Butterbot Tank” blog ([The $75 HAT That Outruns a $500 Jetson](https://www.dugganusa.com/post/the-75-hat-that-outruns-a-500-jetson)): Pi5 + Hailo-8 for YOLO/pose/seg; Nav2/SLAM on CPU; motors on **HiWonder STM32** over UART. Reports ~309 FPS YOLOv8s headroom math for multi-model at 30 FPS camera.
- **HiWonder ROS2 car + Hailo:** [codefortheplanet](https://github.com/codefortheplanet/Raspberry-Pi-5-AI-HAT-plus-for-Computer-Vision-Autonomous-Driving-Tasks-on-ROS2-Robot-Car) swaps CPU YOLO for AI HAT+ HEF in stock HiWonder launch files (traffic-sign / ADAS sandbox).
- **Mecanum + Hailo:** ThermoVision repo — YOLO alignment + monocular depth → ESP32 mecanum controller over USB serial/MQTT.
- **Person tracking camera (not chassis):** Stonej29 — bbox union → smooth crop/zoom (same control idea as person-follow steering with deadzone + EMA).
- **Home / survey robots:** KIDA (tank + Hailo + sonar + voice); wildlife capture [Gordon999/Pi_Hailo_Wildlife](https://github.com/Gordon999/Pi_Hailo_Wildlife) (2★) — event-triggered record, not navigation.
- **Grasp / pick:** No mature public MasterPi/Hailo grasp stack found. Closest patterns are pose/segmentation models in rpi5-examples + floor-plane geometry (as in our perception doc), not end-to-end pick demos.

### Official / community CV pipelines

- Detection / pose / instance seg GStreamer apps in **hailo-rpi5-examples** (person filter + track ID in callbacks).
- Python HailoRT + **ByteTrack**: Application-Code-Examples `object_detection.py --track`; also [cj-mills YOLOX+Hailo+ByteTrack script](https://github.com/cj-mills/pytorch-yolox-object-detection-tutorial-code/blob/main/scripts/yolox-hailo-bytetrack-rpi.py) (parent repo 21★).
- **Depth:** SCDepthv3 monocular (relative, ~30 FPS cited on Pi5+H8); StereoNet for metric stereo (H8 HEFs more common than H8L). Hailo community: [depth discussion](https://community.hailo.ai/t/highly-accurate-model-for-estimating-depth-and-distance-in-space/13589).
- **Nav2:** No first-party Hailo Nav2 package. Patterns: publish detections + PointCloud2; use VoxelLayer ([Nav2 AI depth tutorial](https://docs.nav2.org/tutorials/docs/depth_ai_integration.html) — TensorRT-oriented but architecture transfers). Hailo staff point to community ROS2 repos rather than an official package ([forum](https://community.hailo.ai/t/is-there-an-official-ros2-package-for-running-yolo-on-raspberry-pi-5-with-ai-hat/12539)).

---

## Blogs / videos that document real builds

| Resource | Type | Takeaway |
|----------|------|----------|
| [Raspberry Pi AI software docs](https://www.raspberrypi.com/documentation/computers/ai.html) | Official | AI Kit / HAT+ / HAT+ 2 (10H); `hailo-all`; PCIe Gen3 |
| [RPi news: AI Kit setup](https://www.raspberrypi.com/news/how-to-set-up-the-raspberry-pi-ai-kit-with-raspberry-pi-5/) | Official | Install verify with `hailortcli fw-control identify` |
| [DataRoot Labs AI Kit pipelines](https://datarootlabs.com/blog/hailo-ai-kit-raspberry-pi-5-setup-and-computer-vision-pipelines) | Blog | Clone rpi5-examples; custom HEF needs custom postprocess |
| [Luiz d’Oleron — custom YOLO→HEF](https://pub.towardsai.net/custom-dataset-with-hailo-ai-hat-yolo-raspberry-pi-5-and-docker-0d88ef5eb70f) | Blog | Train → ONNX → DFC → deploy via `detection.py` |
| [Duggan Butterbot Tank](https://www.dugganusa.com/post/the-75-hat-that-outruns-a-500-jetson) | Blog | Multi-model NPU util; power brownout when compiling+inferring; HiWonder MCU for motors |
| [3we Hailo integration](https://docs.3we.org/hailo_integration/) | Docs | ROS-style perception node params / FPS tables |
| [Hailo Community hub](https://community.hailo.ai/t/getting-started-with-rpi5-hailo8l/740) | Forum | Canonical onboarding thread |
| [AI Hat+ unbox + YOLOv6](https://www.youtube.com/watch?v=GEtjKo96Kp4) | YouTube | Hardware + `hailo-all` + CSI demo |
| [Edge CV Pi5 AI Kit](https://www.youtube.com/watch?v=xiHv7xd1drY) | YouTube | Full install → ~30 FPS detection |
| [NxHailo / Nerves](https://www.youtube.com/watch?v=7DW508YiKCk) | YouTube | Non-Python edge pipeline on Pi5+HAT |
| [Unlocking Hailo tips](https://www.youtube.com/watch?v=n6ePp5-ceLg) | YouTube | Quantization / model selection reality |

---

## Patterns worth copying

### 1. Async inference + camera broker (highest priority)

```text
camera owns device → latest-frame buffer (drop stale)
        → preprocess (letterbox matching HEF)
        → Hailo async infer (bounded in-flight = 1..2)
        → postprocess + tracker
        → observations (timestamped) → control / Nav2
```

- Never queue unbounded frames (matches our perception doc).
- Prefer **one** process owning `/dev/video*` / CSI (MasterPi MJPEG/daemon conflicts are common).
- GStreamer (rpi5-examples) or Python HailoRT callback + dedicated capture thread both work; keep display optional/off for stability.

### 2. Tracker (ByteTrack) before control

- Filter class=`person` (or target object), keep **stable track_id**.
- Control on track center error with **deadzone + EMA/hysteresis** (Stonej29 zoom delay; follow robots do the same for steer).
- Official `--track` path or hailoapps tracker metadata — don’t reinvent association.

### 3. Depth + RGB (optional second stage)

- MVP: floor-plane raycast from bbox (no depth model).
- Next: **SCDepthv3** (or stereo) for approach distance / obstacle blob; fuse with YOLO for “target range”.
- Metric depth for grasp: stereo / RGB-D preferred over monocular relative depth (Hailo community consensus).

### 4. Sonar / ultrasonic fusion

- MasterPi **already has** HiWonder ultrasonic on I2C (`0x77`) plus stock obstacle mode in firmware.
- Pattern from tank builds: **near-field stop = sonar**, mid-field = vision costmap; vision alone is brittle indoors.
- Keep ultrasonic on the expansion-board I2C path; do not block Hailo loop waiting on I2C. Fuse — do not treat sonar as a future add-on.

### 5. Split brains (especially with HiWonder)

- **NPU:** detect / pose / seg  
- **Pi CPU:** tracking, geometry, light planning  
- **Expansion MCU / serial SDK:** mecanum + arm (low speed, explicit stop)  
- Avoid running heavy compiles or parallel ROS builds while loading HEFs (Butterbot brownout lesson).

### 6. ROS2 later, not first

- Prove playground Python loop first (aligns with AGENTS.md).
- When promoting: Dockerized TAPPAS+ROS2 ([kyrikakis](https://github.com/kyrikakis/hailo_tappas_ros2)) or thin HailoRT node publishing `vision_msgs` / custom observations; Nav2 consumes PointCloud2 + detections.

---

## What worked vs common pain points

| Area | What works | Pain / failure modes |
|------|------------|----------------------|
| **Drivers / packages** | For **Hailo-8** examples: `hailo-all`. For **this robot (10H):** matched HailoRT **5.x** / `hailo1x_pci` or Trixie `hailo-h10-all` — see [setup](../../scripts/setup_hailo_10h.md); verify with `hailortcli` / `hailo_probe` | Version skew OS↔DKMS↔HailoRT; blind Bookworm `hailo-all` 4.20 is wrong for 10H ([our bring-up](../hailo.md)) |
| **PCIe** | Gen3 for bandwidth; AI HAT EEPROM often auto-sets Gen3 | M.2 HAT needs manual Gen3; loose FPC → flaky device |
| **Kernel 6.12+** | Inference still runs | `hailo_pci` `find_vma` without `mmap_read_lock` → WARN flood / slow configure / RPC timeouts; workaround `loglevel=3` ([community](https://community.hailo.ai/t/hailo-pci-4-20-0-dkms-driver-triggers-120-find-vma-kernel-warns-during-model-configure-on-rpi-5-kernel-6-12-x/19079)) |
| **Camera conflicts** | Single owner; CSI via rpicam or exclusive V4L2 | USB V4L2 + Hailo VDMA + display DMA → `COMMUNICATION_CLOSED` / transfer fail after minutes on AI HAT+ 2 ([thread](https://community.hailo.ai/t/hailo-10h-communication-closed-after-5000-frames-of-continuous-inference-ai-hat-2-pi-5/19012)); MasterPi daemon already holds camera |
| **Thermal** | Active cooler on Pi5; HAT heatsink | Sustained multi-model + SoC heat; throttle / instability |
| **Power** | Official 27W PSU or solid 5V robot supply; HAT GPIO 5V/GND for power delivery | Brownouts under compile+infer+motors; AI HAT expects GPIO header power/EEPROM ([GPIO guide](https://community.hailo.ai/t/using-the-raspberry-pi-gpios-with-the-hailo-ai-hat/11237)) |
| **HAT vs MasterPi GPIO** | Keep expansion-board I2C/UART path; sonar already on MasterPi (`0x77`) | AI HAT covers 40-pin; I2C0 EEPROM pins sensitive — do not treat sonar as a future BOM item; fuse existing ultrasonic with vision |
| **Models** | Zoo HEFs + NMS-in-HEF for drop-in detection | Custom models need DFC on x86; postprocess must match; **8 vs 8L vs 10H HEFs not interchangeable** |
| **ROS2** | Community Docker images isolate deps | Official ROS package absent; venv + colcon + system Hailo libs are fragile |

---

## HiWonder / MasterPi / mecanum + Hailo

| Finding | Detail |
|---------|--------|
| **No MasterPi-official Hailo product** | Stock MasterPi is OpenCV-on-CPU + expansion board; docs do not ship Hailo. |
| **Closest matches** | (1) [codefortheplanet](https://github.com/codefortheplanet/Raspberry-Pi-5-AI-HAT-plus-for-Computer-Vision-Autonomous-Driving-Tasks-on-ROS2-Robot-Car) HiWonder ROS2 car + AI HAT+; (2) Butterbot Tank on HiWonder controller + Hailo-8; (3) ThermoVision mecanum + Hailo (non-HiWonder chassis). |
| **MasterPi-specific Hailo grasp/follow repos** | **None found** in this survey. Expect to invent the glue in `playground/`. |
| **Mechanical note** | AI HAT+ / +2 sits on Pi5 PCIe + GPIO; MasterPi camera is arm-mounted USB/CSI-class — exclusive camera ownership and cable clearance matter more than software novelty. |

---

## Actionable architecture ideas for tiny_pi_car

Prioritized for this repo (Hailo-10H + MasterPi):

1. **Finish runtime bring-up** per [`docs/hailo.md`](../hailo.md); verify with probe before any motion.
2. **Camera broker first** — stop MasterPi daemon / other grabbers; one latest-frame API (already sketched in perception doc).
3. **Clone patterns from hailo-rpi5-examples**, not forks: YOLOv8-class HEF compiled for **10H**, person/object filter, ByteTrack, async drop-stale.
4. **Person-follow MVP:** track_id → lateral error → low-speed mecanum `vx,vy,ω` with deadzone + timeout stop (Stonej29 filtering + stock chassis SDK).
5. **Obstacle MVP:** reuse MasterPi ultrasonic for hard stop; vision bbox/floor as soft cost — don’t wait for full Nav2.
6. **Depth later:** try SCDepth-class HEF if available for 10H; else stereo/RGB-D or keep floor-plane.
7. **ROS2 / Nav2:** only after playground loop is stable; prefer kyrikakis-style isolation or thin publishers.
8. **Power/thermal budget:** no background compiles during demos; active cooling; never leave motors in unbounded loops.
9. **Watch AI HAT+ 2 DMA issues** if using USB camera + live display; prefer headless inference or CSI when possible.

---

## Quick link index

- Examples: https://github.com/hailo-ai/hailo-rpi5-examples  
- Apps infra: https://github.com/hailo-ai/hailo-apps-infra  
- Code examples (ByteTrack, depth): https://github.com/hailo-ai/Hailo-Application-Code-Examples  
- ROS2 TAPPAS: https://github.com/kyrikakis/hailo_tappas_ros2  
- HiWonder + Hailo ROS2 car: https://github.com/codefortheplanet/Raspberry-Pi-5-AI-HAT-plus-for-Computer-Vision-Autonomous-Driving-Tasks-on-ROS2-Robot-Car  
- Mecanum + YOLO + depth: https://github.com/DurraniHakim27/Autonomous-Navigation-IoT-Robot-with-Vision-Thermal-Sensing-and-Control  
- Person track camera: https://github.com/Stonej29/pi-comp-vision  
- Community: https://community.hailo.ai/  
- RPi AI docs: https://www.raspberrypi.com/documentation/computers/ai.html  

*Stars and repos change; re-check before depending on a dormant project.*
