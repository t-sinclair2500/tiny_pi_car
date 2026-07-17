# Hailo vision bring-up

## Hardware

- PCIe `1e60:45c4` at `0001:01:00.0` — **Hailo-10H** (AI HAT+ 2 class), Gen3 x1
- Device node on **Trixie + hailo-h10-all 5.1.1**: **`/dev/hailo0`** (Bookworm HailoRT 5.3 used `/dev/h1x-0`)
- USB camera: `32e6:9005` → `/dev/video0` (MasterPi)

## Runtime status (Trixie + `hailo-h10-all` 5.1.1) — current

Installed on `rpicarbox` via official Pi apt (2026-07-16):

| Piece | Status |
|-------|--------|
| `hailo-h10-all` | **5.1.1** |
| `hailo1x_pci` | loaded |
| `/dev/hailo0` | present |
| `hailortcli fw-control identify` | **HAILO10H**, FW 5.1.1 |
| Python `hailo_platform` 5.1.1 | system package `python3-h10-hailort` (use venv `--system-site-packages`) |
| HEFs | `/usr/share/hailo-models/*_h10.hef` (symlinked under `playground/vision/models/`) |
| PCIe | Gen3 x1 (`8GT/s`); `pcie_aspm=off` in cmdline |

```sh
cd ~/Desktop/tiny_pi_car
source .venv/bin/activate
python -m playground.hailo_probe   # expect ready: True
```

## Do / don't

| Action | Verdict |
|--------|---------|
| `apt install hailo-h10-all` on **Trixie** | **YES** — official path |
| `apt install hailo-all` | **NO** — conflicts; Hailo-8 metapackage |
| Bookworm + HailoRT 5.3 debs | legacy path only (see `scripts/setup_hailo_10h.md`) |

## Code

- `playground/hailo_probe.py` — PCIe / device node / bindings / ready
- `playground/vision/detector.py` — `HailoHEFDetector`
- HEFs under `playground/vision/models/` (gitignored) or `/usr/share/hailo-models/`

No actuator commands in the vision path.

## References

- [`docs/autonomy/CURRENT_STATE.md`](autonomy/CURRENT_STATE.md) — living SSOT
- [`scripts/setup_hailo_10h.md`](../scripts/setup_hailo_10h.md)
- [`docs/research/hailo-official-ecosystem.md`](research/hailo-official-ecosystem.md)
- Pi AI software: https://www.raspberrypi.com/documentation/computers/ai.html
