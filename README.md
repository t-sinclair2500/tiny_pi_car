# tiny_pi_car

Hands-on playground for a Raspberry Pi 5 + HiWonder MasterPi (mecanum chassis, 5-DOF arm, camera).

This folder is meant to be opened **on the Pi** (Remote SSH / local editor). Start from the stock HiWonder `MasterPi/` tree, learn how it works, then replace and upgrade pieces gradually in `playground/`.

## Layout

| Path | Role |
|------|------|
| `MasterPi/` | Stock HiWonder code (demos, Arm UI, SDK, action groups) |
| `playground/` | Our thin experiments and replacements |
| `docs/` | How-to notes for this robot |
| `scripts/` | Small helpers (smoke checks, setup) |

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

## Hardware notes

- Expansion board UART on Pi 5 usually needs `dtoverlay=uart0-pi5` in `/boot/firmware/config.txt`.
- Stock SDK expects `/dev/ttyAMA0`.
- Prefer low speeds, explicit stops, and no unbounded motion loops while experimenting.

See `docs/getting-started.md` and `docs/hardware.md`.
