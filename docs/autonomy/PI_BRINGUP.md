# Pi bring-up — live facts (fresh Trixie)

**Probed:** 2026-07-16 from host via SSH. Another agent owns driver/repo setup;
this file is shared truth so we do not thrash each other.

## Reachability

| Item | Value |
|---|---|
| SSH | `tyler@rpicarbox.local` |
| Aliases | `rpicarbox-1`, `rpicarbox` → same host (host `~/.ssh/config`) |
| Hostname | `rpicarbox` |
| OS | **Debian 13 Trixie** (Raspberry Pi OS 64-bit) — not Bookworm |
| Kernel | `6.18.34+rpt-rpi-2712` aarch64 |
| Repo on Pi | `~/Desktop/tiny_pi_car` (present; may lag host uncommitted work) |
| `.venv` on Pi | **missing** as of probe |
| Camera `/dev/video0` | **N/A** — MasterPi board (USB cam, UART, motors) is **not attached** right now. Only Pi ISP/HEVC nodes may show. |

## Scope right now

| Available | Not available (board off) |
|---|---|
| SSH + Trixie OS | USB camera (`/dev/video0`) |
| Hailo-10H PCIe (driver bring-up) | UART / mecanum / arm / gripper |
| Repo sync, venv, HEF smoke once RT is up | Live sonar, motion trials |

Useful work while chassis is off: HailoRT + HEF load/`hailo_probe`, offline
image A/B on copied frames, vision suite downloads, Python venv. Skip anything
that needs `/dev/video0` or `/dev/ttyAMA0`.

## Hailo (as of probe)

| Item | Value |
|---|---|
| PCIe | **present** — `0001:01:00.0` Hailo-10H (`1e60:45c4`) |
| `/dev/h1x-0` | **missing** — driver/runtime not installed yet |
| apt packages | none matching `hailo*` |

### Correct install path on this SD image

This Pi is already **Trixie** → use official Path A:

```sh
sudo apt update
sudo apt install dkms
sudo apt install hailo-h10-all   # NOT hailo-all (that is Hailo-8)
sudo reboot
hailortcli fw-control identify   # expect HAILO10H
ls /dev/h1x-0
```

Do **not** `apt install hailo-all`. Detail: [`scripts/setup_hailo_10h.md`](../../scripts/setup_hailo_10h.md).

## Host-side helpers (after driver + venv exist)

```sh
# from laptop
.venv/bin/python scripts/pi_agent_gate.py --host rpicarbox.local status
.venv/bin/python scripts/pi_agent_gate.py --host rpicarbox.local hailo-probe
.venv/bin/python scripts/list_hefs.py
.venv/bin/python scripts/vision_suite_status.py
```

## Vision suite (next after HailoRT)

See [`playground/vision/suite/`](../../playground/vision/suite/). Plan:

1. Get `/dev/h1x-0` + Python bindings in a venv.
2. Drop COCO `yolov8n.hef` (hailo10h) under `playground/vision/models/`.
3. A/B zoo n/s/11n via `scripts/hailo_ab_compare.py`.
4. Later: HF/Ultralytics finetune → ONNX → DFC on x86 → custom HEF.

## Coordination

- Leave Hailo package install / reboot to the bring-up agent.
- Prefer editing host repo; sync to Pi when asked (`rsync` / git pull).
- Scripts default host is now `rpicarbox.local`.
