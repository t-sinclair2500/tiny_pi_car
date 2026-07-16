# Hailo vision bring-up

## Hardware

- PCIe `1e60:45c4` at `0001:01:00.0` — **Hailo-10H** (AI HAT+ 2 class), Gen3 x1
- Device node after HailoRT 5.x: **`/dev/h1x-0`** (not `/dev/hailo0`)
- USB camera: `32e6:9005` → `/dev/video0` (MasterPi)

## Runtime status (Bookworm + HailoRT 5.3)

Installed via `./scripts/setup_hailo_10h.sh --install bookworm-hailort-5.3`:

| Piece | Status |
|-------|--------|
| `hailo1x_pci` | loaded |
| `/dev/h1x-0` | present |
| `hailortcli fw-control identify` | **HAILO10H**, FW 5.3.0 |
| Python `hailo_platform` 5.3.0 | in `.venv` (cp311 wheel) |
| HEF | `playground/vision/models/yolov8n.hef` (hailo10h zoo, gitignored) |

```sh
.venv/bin/python -m playground.hailo_probe   # expect ready: True
.venv/bin/python -m playground.vision_smoke
```

## Do / don't

| Action | Verdict |
|--------|---------|
| `apt install hailo-all` (Bookworm 4.20) | **NO** — Hailo-8 stack |
| `apt install hailo-h10-all` on Bookworm | **NO** — package missing |
| Stay Bookworm + HailoRT 5.3 debs (current) | **OK** |
| Later: Trixie + `hailo-h10-all` | Official path if you want Pi-blessed apt |

## Code

- `playground/hailo_probe.py` — PCIe / `h1x*` / bindings / ready
- `playground/vision/detector.py` — `HailoHEFDetector` (YOLOv8n NMS_BY_CLASS)
- HEFs only under `playground/vision/models/` (gitignored)

No actuator commands in the vision path.

## References

- [`docs/autonomy/CURRENT_STATE.md`](autonomy/CURRENT_STATE.md) — living SSOT
- [`scripts/setup_hailo_10h.md`](../scripts/setup_hailo_10h.md)
- [`docs/research/hailo-official-ecosystem.md`](research/hailo-official-ecosystem.md)
- [`docs/autonomy/BUILD_NEXT.md`](autonomy/BUILD_NEXT.md)
