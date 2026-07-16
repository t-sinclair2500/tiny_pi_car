# tiny_pi_car

Hands-on playground for a Raspberry Pi 5 + HiWonder MasterPi (mecanum chassis, 5-DOF arm, camera) + **Hailo-10H**.

This folder is meant to be opened **on the Pi** (Remote SSH / local editor). Start from the stock HiWonder `MasterPi/` tree, learn how it works, then replace and upgrade pieces gradually in `playground/`.

## Layout

| Path | Role |
|------|------|
| `MasterPi/` | Stock HiWonder code (demos, Arm UI, SDK, action groups) |
| `playground/` | Our thin experiments and replacements |
| `docs/` | How-to notes for this robot |
| `scripts/` | Small helpers (smoke checks, Hailo setup) |

## Quick start

```bash
cd ~/Desktop/tiny_pi_car
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
```

Smoke-check imports:

```bash
python scripts/smoke_imports.py
```

Hailo probe (expect `ready: True` after Path B install):

```bash
.venv/bin/python -m playground.hailo_probe
```

## Autonomy docs (start here)

| Doc | Role |
|------|------|
| [docs/autonomy/SESSIONS.md](docs/autonomy/SESSIONS.md) | **Ops runbook** — SOP + Sessions A→B→C |
| [docs/autonomy/CURRENT_STATE.md](docs/autonomy/CURRENT_STATE.md) | What’s true on this Pi today |
| [docs/autonomy/BUILD_NEXT.md](docs/autonomy/BUILD_NEXT.md) | Checkbox tick queue |
| [docs/STATUS.md](docs/STATUS.md) | Short index |

## Hardware notes

- Expansion board UART on Pi 5 usually needs `dtoverlay=uart0-pi5` in `/boot/firmware/config.txt`.
- Stock SDK expects `/dev/ttyAMA0`.
- Ultrasonic sonar is real (I2C `@0x77`); Hailo device node is `/dev/h1x-0`.
- Prefer low speeds, explicit stops, and no unbounded motion loops while experimenting.
- Stop `masterpi.service` before playground camera/UART sessions.

Also: [docs/getting-started.md](docs/getting-started.md), [docs/hardware.md](docs/hardware.md), [docs/hailo.md](docs/hailo.md).
