# Getting started

## Environment

```bash
cd ~/Desktop/tiny_pi_car
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

System packages on Raspberry Pi OS may already provide OpenCV / PyQt. The venv is still useful for pinned playground deps (including `hailo_platform` after HailoRT 5.3 install).

OS today: Debian 12 **Bookworm**. Hailo-10H uses Path B debs — see [hailo.md](hailo.md). Do **not** `apt install hailo-all`.

## First experiments

1. Confirm UART / board talk (see [hardware.md](hardware.md)).
2. Confirm Hailo: `python3 -m playground.hailo_probe` → `ready: True` (node `/dev/h1x-0`).
3. Run a stock board demo from `MasterPi/board_demo/` with the robot elevated or wheels clear — stop `masterpi.service` first if it holds UART.
4. Open the Arm desktop app only when you intend to move servos.
5. Put new scripts in `playground/` instead of editing stock files until you understand the call path.

Living snapshot: [autonomy/CURRENT_STATE.md](autonomy/CURRENT_STATE.md) · short pointers: [STATUS.md](STATUS.md).

## Stock vs playground

| Stock (`MasterPi/`) | Playground (`playground/`) |
|---------------------|----------------------------|
| Vendor demos & SDK | Our thin wrappers and tests |
| Change carefully | Default place for new work |
| Learn-first | Replace-as-you-go |
