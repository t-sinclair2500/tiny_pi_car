"""Model intent registry; HEF artifacts are deliberately local-only."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from playground.vision.coco_labels import COCO80

MODEL_DIR = Path(__file__).parent / "models"


@dataclass(frozen=True)
class ModelSpec:
    name: str
    purpose: str
    hef_path: Path
    labels: tuple[str, ...]
    hw_arch: str = "hailo10h"


MODELS = (
    ModelSpec(
        "yolov8n",
        "COCO detect for find-and-approach + person safety (Hailo-10H zoo HEF).",
        MODEL_DIR / "yolov8n.hef",
        COCO80,
    ),
    ModelSpec(
        "yolo-object-detection",
        "Alias path for older docs; prefers yolov8n.hef if present.",
        MODEL_DIR / "yolo_object_detection.hef",
        COCO80,
    ),
    ModelSpec(
        "grasp-candidate-detector",
        "Fine-tuned target classes for reliable tabletop pickup.",
        MODEL_DIR / "grasp_candidates.hef",
        (),
    ),
)


def list_local_hefs() -> list[Path]:
    if not MODEL_DIR.is_dir():
        return []
    return sorted(MODEL_DIR.glob("*.hef"))


def prefer_hef() -> Path | None:
    for name in ("yolov8n.hef", "yolo_object_detection.hef"):
        path = MODEL_DIR / name
        if path.is_file():
            return path
    hefs = list_local_hefs()
    return hefs[0] if hefs else None
