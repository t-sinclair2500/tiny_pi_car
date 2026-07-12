# Getting started

## Environment

```bash
cd ~/Desktop/tiny_pi_car
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

System packages on Raspberry Pi OS may already provide OpenCV / PyQt. The venv is still useful for pinned playground deps.

## First experiments

1. Confirm UART / board talk (see `docs/hardware.md`).
2. Run a stock board demo from `MasterPi/board_demo/` with the robot elevated or wheels clear.
3. Open the Arm desktop app only when you intend to move servos.
4. Put new scripts in `playground/` instead of editing stock files until you understand the call path.

## Stock vs playground

| Stock (`MasterPi/`) | Playground (`playground/`) |
|---------------------|----------------------------|
| Vendor demos & SDK | Our thin wrappers and tests |
| Change carefully | Default place for new work |
| Learn-first | Replace-as-you-go |
