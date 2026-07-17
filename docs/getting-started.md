# Getting started

## Environment

```bash
cd ~/Desktop/tiny_pi_car
# --system-site-packages: pick up apt python3-h10-hailort / numpy / opencv
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e ".[dev,vision]"
```

### System deps (Trixie Pi)

| Layer | Packages / notes |
|-------|------------------|
| Hailo-10H | `sudo apt install dkms hailo-h10-all` then reboot. **Never** `hailo-all`. |
| Python bindings | `python3-h10-hailort` (pulled by metapackage; needs venv with `--system-site-packages`) |
| Playground | `numpy`, `PyYAML`, `pyserial` (+ optional `opencv` via apt or `.[vision]`) |
| UART / robot | `dtoverlay=uart0-pi5` in `/boot/firmware/config.txt`; user in `dialout` |
| PCIe tune | `dtparam=pciex1_gen=3` in config.txt; `pcie_aspm=off` on cmdline |

OS today on the robot: Debian 13 **Trixie** + `hailo-h10-all` **5.1.1**. Detail: [hailo.md](hailo.md).

## First experiments

1. Confirm UART / board talk (see [hardware.md](hardware.md)).
2. Confirm Hailo: `python -m playground.hailo_probe` → `ready: True` (node `/dev/hailo0` on Trixie 5.1.1).
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
