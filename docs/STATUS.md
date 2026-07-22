# Status (short)

Living pointers — deep plans under `docs/autonomy/` and `docs/research/`.

| Topic | Truth | Doc |
|---|---|---|
| **How to work** | Sessions A→B→C + SOP | [autonomy/SESSIONS.md](autonomy/SESSIONS.md) |
| **What’s true now** | SSOT | [autonomy/CURRENT_STATE.md](autonomy/CURRENT_STATE.md) |
| **Experiment results** | Night / motion15 / auto20 / stream prep | [autonomy/EXPERIMENT_LEARNINGS.md](autonomy/EXPERIMENT_LEARNINGS.md) |
| **What to do next** | Checkbox ticks | [autonomy/BUILD_NEXT.md](autonomy/BUILD_NEXT.md) |
| Hailo-10H | Up — HailoRT 5.3; prefer `/dev/hailo0` on live box | [hailo.md](hailo.md) |
| Detector | COCO `yolov8n` only; AE warmup required; no `can` class | [autonomy/perception.md](autonomy/perception.md) |
| Sonar | Real I2C `@0x77` — ~3″ blind to floor clutter | [autonomy/navigation.md](autonomy/navigation.md) |
| Motion | UART exclusive; stream roam daemon on Desktop repo | [hardware.md](hardware.md) |
| Research | Indexed background | [research/README.md](research/README.md) |

Do **not** `apt install hailo-all`. Prefer CURRENT_STATE when docs conflict.
