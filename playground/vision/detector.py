"""Hailo-10H detector with safe fallback when runtime/HEF is missing."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from playground.hailo_probe import probe
from playground.vision.coco_labels import COCO80
from playground.vision.models import MODEL_DIR, prefer_hef


@dataclass(frozen=True)
class Detection:
    label: str
    score: float
    bbox: tuple[float, float, float, float]  # x1,y1,x2,y2 in original frame pixels

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class Detector(Protocol):
    def detect(self, frame: np.ndarray) -> list[Detection]: ...


class UnavailableHailoDetector:
    """Explicit no-op detector; it never fabricates autonomous pickup targets."""

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def detect(self, frame: np.ndarray) -> list[Detection]:
        del frame
        return []


def _letterbox(frame: np.ndarray, size: int = 640) -> tuple[np.ndarray, float, int, int]:
    """Resize keeping aspect ratio; pad to square. Returns image, scale, pad_x, pad_y."""
    h, w = frame.shape[:2]
    scale = size / max(h, w)
    nh, nw = int(round(h * scale)), int(round(w * scale))
    import cv2

    resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    pad_y = (size - nh) // 2
    pad_x = (size - nw) // 2
    canvas[pad_y : pad_y + nh, pad_x : pad_x + nw] = resized
    return canvas, scale, pad_x, pad_y


def _parse_nms(
    raw: np.ndarray,
    *,
    orig_h: int,
    orig_w: int,
    scale: float,
    pad_x: int,
    pad_y: int,
    score_thresh: float,
    labels: tuple[str, ...],
    letterbox_size: int = 640,
) -> list[Detection]:
    """Parse Hailo HAILO_NMS_BY_CLASS tensor → Detection list in original pixels.

    Layout for yolov8n hailo10h: flat float32 of size num_classes * (1 + 5 * max_boxes)
    → reshape (C, 1+5*max_boxes). Slot 0 is count; then count boxes of
    (xmin, ymin, xmax, ymax, score) normalized to the letterboxed square.
    """
    arr = np.asarray(raw, dtype=np.float32).reshape(-1)
    detections: list[Detection] = []

    # Prefer BY_CLASS packed form used by HailoRT 5.x YOLO HEFs (80 * 501 for max=100).
    if arr.size % 80 == 0 and arr.size // 80 >= 6:
        per = arr.size // 80
        table = arr.reshape(80, per)
        for class_id in range(80):
            row = table[class_id]
            count = int(round(float(row[0])))
            if count <= 0:
                continue
            count = min(count, (per - 1) // 5)
            label = labels[class_id] if class_id < len(labels) else str(class_id)
            dets = row[1 : 1 + count * 5].reshape(count, 5)
            for det in dets:
                score = float(det[4])
                if score < score_thresh:
                    continue
                detections.append(
                    Detection(
                        label,
                        score,
                        _unmap_box(
                            det[:4],
                            orig_h,
                            orig_w,
                            scale,
                            pad_x,
                            pad_y,
                            letterbox_size=letterbox_size,
                        ),
                    )
                )
    detections.sort(key=lambda d: d.score, reverse=True)
    return detections


def _unmap_box(
    box: np.ndarray,
    orig_h: int,
    orig_w: int,
    scale: float,
    pad_x: int,
    pad_y: int,
    *,
    letterbox_size: int = 640,
) -> tuple[float, float, float, float]:
    """Map normalized xmin,ymin,xmax,ymax on letterbox → original x1,y1,x2,y2 pixels."""
    xmin, ymin, xmax, ymax = (float(v) for v in box[:4])
    if max(abs(xmin), abs(ymin), abs(xmax), abs(ymax)) <= 1.5:
        size = float(letterbox_size)
        xmin, xmax = xmin * size, xmax * size
        ymin, ymax = ymin * size, ymax * size
    x1 = (xmin - pad_x) / scale
    x2 = (xmax - pad_x) / scale
    y1 = (ymin - pad_y) / scale
    y2 = (ymax - pad_y) / scale
    lo_x, hi_x = sorted((x1, x2))
    lo_y, hi_y = sorted((y1, y2))
    return (
        float(np.clip(lo_x, 0, orig_w - 1)),
        float(np.clip(lo_y, 0, orig_h - 1)),
        float(np.clip(hi_x, 0, orig_w - 1)),
        float(np.clip(hi_y, 0, orig_h - 1)),
    )


class HailoHEFDetector:
    """Sync HailoRT infer for hailo10h YOLO HEFs with on-device NMS."""

    def __init__(
        self,
        hef_path: Path | None = None,
        *,
        score_thresh: float = 0.45,
        labels: tuple[str, ...] = COCO80,
    ) -> None:
        status = probe()
        if not status.get("ready"):
            raise RuntimeError("Hailo runtime not ready; use UnavailableHailoDetector")
        self.hef_path = Path(hef_path) if hef_path else prefer_hef()
        if self.hef_path is None or not self.hef_path.is_file():
            raise RuntimeError(f"No HEF under {MODEL_DIR}")
        self.score_thresh = score_thresh
        self.labels = labels
        self._vdevice = None
        self._configured = None
        self._config_ctx = None
        self._infer_model = None
        self._output_name = ""
        self._input_hw: tuple[int, int] = (640, 640)
        self._open()

    def _open(self) -> None:
        from hailo_platform import FormatType, HailoSchedulingAlgorithm, VDevice

        params = VDevice.create_params()
        params.scheduling_algorithm = HailoSchedulingAlgorithm.ROUND_ROBIN
        self._vdevice = VDevice(params)
        self._infer_model = self._vdevice.create_infer_model(str(self.hef_path))
        self._infer_model.set_batch_size(1)
        self._infer_model.input().set_format_type(FormatType.UINT8)
        for out in self._infer_model.outputs:
            self._infer_model.output(out.name).set_format_type(FormatType.FLOAT32)
            self._output_name = out.name
        shape = self._infer_model.input().shape
        self._input_hw = (int(shape[0]), int(shape[1]))
        self._config_ctx = self._infer_model.configure()
        self._configured = self._config_ctx.__enter__()

    def close(self) -> None:
        if self._config_ctx is not None:
            try:
                self._config_ctx.__exit__(None, None, None)
            except Exception:
                pass
            self._config_ctx = None
            self._configured = None
        if self._vdevice is not None:
            try:
                self._vdevice.release()
            except Exception:
                pass
            self._vdevice = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def detect(self, frame: np.ndarray) -> list[Detection]:
        if frame is None or frame.size == 0 or self._configured is None or self._infer_model is None:
            return []
        if frame.ndim == 2:
            frame = np.stack([frame] * 3, axis=-1)
        if frame.shape[2] == 4:
            frame = frame[:, :, :3]
        # OpenCV frames are BGR; Hailo zoo HEFs typically expect RGB
        import cv2

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        orig_h, orig_w = rgb.shape[:2]
        size = self._input_hw[0]
        letterboxed, scale, pad_x, pad_y = _letterbox(rgb, size=size)

        output_buffers = {
            self._output_name: np.empty(
                self._infer_model.output(self._output_name).shape,
                dtype=np.float32,
            )
        }
        binding = self._configured.create_bindings(output_buffers=output_buffers)
        binding.input().set_buffer(letterboxed)
        self._configured.wait_for_async_ready(timeout_ms=10000)
        job = self._configured.run_async([binding])
        job.wait(10000)
        raw = output_buffers[self._output_name]
        return _parse_nms(
            raw,
            orig_h=orig_h,
            orig_w=orig_w,
            scale=scale,
            pad_x=pad_x,
            pad_y=pad_y,
            score_thresh=self.score_thresh,
            labels=self.labels,
            letterbox_size=size,
        )


def build_detector(
    *,
    force_unavailable: bool = False,
    hef_path: Path | None = None,
    score_thresh: float | None = None,
) -> Detector:
    """Select Hailo detector when probe says ready and a HEF exists; else safe empty."""
    if force_unavailable:
        return UnavailableHailoDetector("forced unavailable")
    status = probe()
    if not status.get("ready"):
        return UnavailableHailoDetector(
            "Hailo-10H runtime not ready (need /dev/h1x-* + hailo_platform). "
            "See scripts/setup_hailo_10h.md"
        )
    hef = Path(hef_path) if hef_path else prefer_hef()
    if hef is None or not hef.is_file():
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        return UnavailableHailoDetector(
            f"Hailo ready but no HEF under {MODEL_DIR} (place hailo10h .hef files there)."
        )
    try:
        kwargs = {}
        if score_thresh is not None:
            kwargs["score_thresh"] = score_thresh
        return HailoHEFDetector(hef, **kwargs)
    except Exception as exc:  # noqa: BLE001 — degrade gracefully for smoke
        return UnavailableHailoDetector(f"Hailo detector init failed: {exc}")
