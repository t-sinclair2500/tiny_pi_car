# Status (short)

Living pointers — deep plans under `docs/autonomy/` and `docs/research/`.

| Topic | Truth | Doc |
|---|---|---|
| **How to work** | Sessions A→B→C + SOP | [autonomy/SESSIONS.md](autonomy/SESSIONS.md) |
| **What’s true now** | SSOT | [autonomy/CURRENT_STATE.md](autonomy/CURRENT_STATE.md) |
| **What to do next** | Checkbox ticks | [autonomy/BUILD_NEXT.md](autonomy/BUILD_NEXT.md) |
| Hailo-10H | Up — HailoRT 5.3, `/dev/h1x-0`, probe ready | [hailo.md](hailo.md) |
| Detector | COCO `yolov8n` only; AE warmup required; no `can` class | [autonomy/perception.md](autonomy/perception.md) |
| Sonar | Real I2C `@0x77` — fuse with vision | [autonomy/navigation.md](autonomy/navigation.md) |
| Motion | UART exclusive; stop MasterPi for playground | [hardware.md](hardware.md) |
| Research | Indexed background | [research/README.md](research/README.md) |

Do **not** `apt install hailo-all`. Prefer CURRENT_STATE when docs conflict.
