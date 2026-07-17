# Vision model suite

Intentional slots for Hailo-10H perception A/B and later custom HEFs.

## Layout

| Path | Role |
|---|---|
| [`MANIFEST.json`](./MANIFEST.json) | Slot list (zoo + custom/HF recipe stubs) |
| `playground/vision/models/*.hef` | Deployed HEFs (gitignored) |
| `.autoresearch/artifacts/*.hef` | Lab downloads / A/B candidates |
| [`models.py`](../models.py) | Runtime registry used by detectors |

## Host commands

```bash
# What is on disk vs what the suite wants
.venv/bin/python scripts/vision_suite_status.py

# Download one artifact when you have an HTTPS URL + optional sha256
.venv/bin/python scripts/fetch_research_artifact.py \
  --url 'https://…/yolov8n.hef' --name yolov8n.hef --sha256 …

# Fill a suite slot from artifacts/ (or any path)
.venv/bin/python scripts/vision_suite_install.py --slot yolov8n --from .autoresearch/artifacts/yolov8n.hef

# A/B two HEFs on a folder of frames
.venv/bin/python scripts/hailo_ab_compare.py --hef-a yolov8n --hef-b yolov8s --images captures/ab_frames
```

## Hugging Face / custom classes

Train on x86 (Ultralytics + your labeled cups/bottles), export ONNX, compile with
DFC/`hailomz` for **`hailo10h`**, then install into the `grasp-candidates` slot.
See [`docs/research/hailo-custom-models.md`](../../../docs/research/hailo-custom-models.md).

Do not expect transformers to run on the Hailo — only compiled `.hef` files.
