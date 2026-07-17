"""Model intent registry + Hailo-10H zoo candidates for A/B experiments.

HEF binaries stay local (gitignored). Agents fetch/swap them under
``playground/vision/models/`` or ``.autoresearch/artifacts/``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from playground.vision.coco_labels import COCO80

MODEL_DIR = Path(__file__).parent / "models"
ARTIFACT_DIR = Path(__file__).resolve().parents[2] / ".autoresearch" / "artifacts"


@dataclass(frozen=True)
class ModelSpec:
    name: str
    purpose: str
    hef_path: Path
    labels: tuple[str, ...]
    hw_arch: str = "hailo10h"
    zoo_hint: str = ""


# Local slots agents can fill by downloading Hailo-10H zoo HEFs.
MODELS = (
    ModelSpec(
        "yolov8m",
        "COCO detect medium A/B (on-Pi filename yolov8m_h10.hef).",
        MODEL_DIR / "yolov8m_h10.hef",
        COCO80,
        zoo_hint="Hailo model zoo YOLOv8m hailo10h",
    ),
    ModelSpec(
        "yolov11m",
        "COCO detect YOLO11 medium A/B (on-Pi filename yolov11m_h10.hef).",
        MODEL_DIR / "yolov11m_h10.hef",
        COCO80,
        zoo_hint="Hailo model zoo YOLOv11m hailo10h",
    ),
    ModelSpec(
        "yolov8n",
        "COCO detect baseline (Hailo-10H zoo).",
        MODEL_DIR / "yolov8n.hef",
        COCO80,
        zoo_hint="Hailo model zoo YOLOv8n hailo10h",
    ),
    ModelSpec(
        "yolov8s",
        "Heavier COCO detect A/B candidate.",
        MODEL_DIR / "yolov8s.hef",
        COCO80,
        zoo_hint="Hailo model zoo YOLOv8s hailo10h",
    ),
    ModelSpec(
        "yolov11n",
        "Newer nano detector A/B candidate when available.",
        MODEL_DIR / "yolov11n.hef",
        COCO80,
        zoo_hint="Hailo model zoo YOLOv11n hailo10h",
    ),
    ModelSpec(
        "yolo-object-detection",
        "Alias path for older docs; prefers yolov8n.hef if present.",
        MODEL_DIR / "yolo_object_detection.hef",
        COCO80,
    ),
    ModelSpec(
        "grasp-candidate-detector",
        "Fine-tuned target classes for tabletop pickup.",
        MODEL_DIR / "grasp_candidates.hef",
        (),
    ),
)


def list_local_hefs() -> list[Path]:
    found: list[Path] = []
    for directory in (MODEL_DIR, ARTIFACT_DIR):
        if directory.is_dir():
            found.extend(directory.glob("*.hef"))
    return sorted({path.resolve(): path for path in found}.values(), key=lambda p: p.name)


def prefer_hef() -> Path | None:
    for name in (
        "yolov8m_h10.hef",
        "yolov11m_h10.hef",
        "yolov8n.hef",
        "yolo_object_detection.hef",
        "yolov8s.hef",
        "yolov11n.hef",
    ):
        for directory in (MODEL_DIR, ARTIFACT_DIR):
            path = directory / name
            if path.is_file():
                return path
    hefs = list_local_hefs()
    return hefs[0] if hefs else None


def resolve_hef(name_or_path: str) -> Path | None:
    candidate = Path(name_or_path)
    if candidate.is_file():
        return candidate
    for directory in (MODEL_DIR, ARTIFACT_DIR):
        path = directory / name_or_path
        if path.is_file():
            return path
        if not name_or_path.endswith(".hef"):
            path = directory / f"{name_or_path}.hef"
            if path.is_file():
                return path
    return None
