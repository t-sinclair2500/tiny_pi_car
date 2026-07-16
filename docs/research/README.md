# Research index — Hailo + MasterPi autonomy

Timeboxed notes for house-roaming + reliable pickup on this Pi 5 + **Hailo-10H** (`1e60:45c4`) + HiWonder MasterPi.

Status legend: **verified** = matches this robot today · **outdated** = local facts drifted (keep for history) · **still useful** = guidance remains good with caveats.

## Bring-up (start here)

| Doc | Status | Notes |
| --- | --- | --- |
| [docs/hailo.md](../hailo.md) | **verified** | Local PCIe/runtime status and probe commands (HailoRT 5.3 on Bookworm) |
| [scripts/setup_hailo_10h.md](../../scripts/setup_hailo_10h.md) | **verified** | Correct Hailo-10H install path (Bookworm HailoRT 5.3 debs or Trixie `hailo-h10-all`) |
| [docs/hardware.md](../hardware.md) | **verified** | Board inventory + Hailo/sonar status (2026-07-15) |

## Hailo research

| Doc | Status | One-line |
| --- | --- | --- |
| [hailo-official-ecosystem.md](hailo-official-ecosystem.md) | **still useful** | Official Pi/Hailo packages, Trixie vs Bookworm, HEF/GenAI landscape — do **not** treat Bookworm `hailo-all` snippets as our path |
| [hailo-pi5-gotchas.md](hailo-pi5-gotchas.md) | **outdated** (baseline) / **still useful** (footguns) | PCIe/driver/package traps still apply; 2026-07-14 “no driver / no `/dev/hailo*`” baseline is stale |
| [hailo-custom-models.md](hailo-custom-models.md) | **still useful** | ONNX → DFC → `hailo10h` HEF workflow; checklist item for runtime is done (`/dev/h1x-0`) |
| [hailo-perception-grasp-nav.md](hailo-perception-grasp-nav.md) | **still useful** | Perception roster for roam + pickup; ultrasonic hard-veto framing is correct |
| [hailo-public-projects.md](hailo-public-projects.md) | **still useful** | Public Pi5/Hailo robot patterns; many examples are Hailo-8 — do not copy `hailo-all` for this HAT |

## Autonomy plan

| Doc | Status | Notes |
| --- | --- | --- |
| [docs/autonomy/README.md](../autonomy/README.md) | **verified** | Plan set overview + ground truth |
| [CURRENT_STATE.md](../autonomy/CURRENT_STATE.md) | **verified** | Living SSOT — what works / stubbed / next |
| [architecture-and-roadmap.md](../autonomy/architecture-and-roadmap.md) | **verified** | Modules, safety, milestones — Hailo B0 done |
| [hardware-and-interfaces.md](../autonomy/hardware-and-interfaces.md) | **verified** | UART/camera/sonar ownership; sonar already on I2C-1 `@0x77` |
| [perception.md](../autonomy/perception.md) | **verified** | Detector up (COCO yolov8n); tracker/geometry still open |
| [navigation.md](../autonomy/navigation.md) | **verified** | Reactive roam → mapping; fuse sonar with vision (sonar already present) |
| [grasping.md](../autonomy/grasping.md) | **verified** | Pickup FSM stub; no grasp HEF yet |
| [BUILD_NEXT.md](../autonomy/BUILD_NEXT.md) | **verified** | Prioritized next builder tick; **B0 Hailo runtime DONE** |

## Hard rules (from research)

- **Do not** `apt install hailo-all` on Bookworm for this HAT — that is the Hailo-8 **4.20** path and is wrong for Hailo-10H.
- Prefer **matched HailoRT 5.x / `hailo1x_pci`** on Bookworm (current) or later **Trixie + `hailo-h10-all`**.
- HEFs must target **`hailo10h`**; keep artifacts under gitignored `playground/vision/models/`.
- **Sonar is already on the robot** (HiWonder ultrasonic, I2C-1 `@0x77`) — fuse with vision; do not plan “add sonar later.”
- Verify with: `python3 -m playground.hailo_probe`
