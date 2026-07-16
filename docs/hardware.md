# Hardware

## Platform

- Raspberry Pi 5, Debian 12 **Bookworm**
- HiWonder MasterPi: mecanum base, 5-DOF arm, USB camera
- Expansion board over serial (UART `/dev/ttyAMA0`)
- Forward ultrasonic on I2C-1 `@0x77` (`common.sonar.Sonar`) — **real hardware**, used by `SonarGate` / `watch_sonar` / `sonar_sample`

## Accelerator and camera (2026-07-15)

| Item | Status |
|---|---|
| Hailo PCIe | `1e60:45c4` at `0001:01:00.0` → **Hailo-10H** (AI HAT+ 2 class), Gen3 x1 |
| Runtime | HailoRT **5.3** installed (Path B debs). Driver `hailo1x_pci`; node **`/dev/h1x-0`** |
| Probe | `python3 -m playground.hailo_probe` → `ready: True` |
| HEF | Local gitignored `playground/vision/models/yolov8n.hef` (hailo10h, COCO) |
| Camera | USB `32e6:9005` → `/dev/video0` |

Do **not** `apt install hailo-all` (Bookworm 4.20 / Hailo-8). Detail: [hailo.md](hailo.md), [scripts/setup_hailo_10h.md](../scripts/setup_hailo_10h.md). Living snapshot: [autonomy/CURRENT_STATE.md](autonomy/CURRENT_STATE.md).

- Do not run `MasterPi/Camera.py` (OpenCV `-1`) and playground camera capture together. One broker owns the device.
- `masterpi.service` is often **enabled but inactive** during playground sessions — keep it stopped while claiming UART or `/dev/video0`.

## UART (Pi 5)

Stock HiWonder code expects **`/dev/ttyAMA0`**.

On Pi 5, enable the GPIO UART overlay in `/boot/firmware/config.txt`:

```text
dtoverlay=uart0-pi5
```

Avoid binding a login console to that same UART (`console=serial0,...` in cmdline) while using the robot board.

Reboot after changing boot config.

## Safety defaults

- Keep speeds low while bringing up code.
- Always send an explicit stop / neutral pose before exiting scripts.
- Watch battery voltage; HiWonder demos often warn when voltage is low.
- Clear space around wheels and arm before enabling actuators.
