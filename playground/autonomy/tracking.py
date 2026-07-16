"""Small, pure detection tracker with a conservative confirmation gate.

The tracker performs greedy, class-preserving association using IoU first and
centroid distance as a fallback.  It has no hardware imports.  A track is safe
for a future motion consumer only while ``confirmed`` is true, which requires
``min_hits`` consecutive observations (three by default).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Iterable, Mapping

BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class Track:
    track_id: int
    label: str
    score: float
    bbox: BBox
    consecutive_hits: int
    age_frames: int
    missed_frames: int
    confirmed: bool


@dataclass
class _TrackState:
    track_id: int
    label: str
    score: float
    bbox: BBox
    consecutive_hits: int
    first_frame: int
    last_frame: int
    missed_frames: int = 0


def bbox_iou(left: BBox, right: BBox) -> float:
    """Return intersection-over-union for two x1,y1,x2,y2 boxes."""
    ix1 = max(left[0], right[0])
    iy1 = max(left[1], right[1])
    ix2 = min(left[2], right[2])
    iy2 = min(left[3], right[3])
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union > 0.0 else 0.0


def centroid_distance_ratio(left: BBox, right: BBox) -> float:
    """Centroid distance divided by mean box diagonal (coordinate-scale neutral)."""
    left_x = (left[0] + left[2]) / 2.0
    left_y = (left[1] + left[3]) / 2.0
    right_x = (right[0] + right[2]) / 2.0
    right_y = (right[1] + right[3]) / 2.0
    distance = hypot(left_x - right_x, left_y - right_y)
    left_diag = hypot(left[2] - left[0], left[3] - left[1])
    right_diag = hypot(right[2] - right[0], right[3] - right[1])
    scale = (left_diag + right_diag) / 2.0
    return distance / scale if scale > 0.0 else float("inf")


class DetectionTracker:
    """Greedy IoU/centroid tracker with consecutive-hit confirmation."""

    def __init__(
        self,
        *,
        min_hits: int = 3,
        max_missed: int = 2,
        iou_threshold: float = 0.30,
        max_centroid_distance: float = 1.0,
    ) -> None:
        if min_hits < 1:
            raise ValueError("min_hits must be at least 1")
        if max_missed < 0:
            raise ValueError("max_missed must be non-negative")
        if not 0.0 <= iou_threshold <= 1.0:
            raise ValueError("iou_threshold must be in [0, 1]")
        if max_centroid_distance < 0.0:
            raise ValueError("max_centroid_distance must be non-negative")
        self.min_hits = min_hits
        self.max_missed = max_missed
        self.iou_threshold = iou_threshold
        self.max_centroid_distance = max_centroid_distance
        self._frame_index = -1
        self._next_track_id = 1
        self._tracks: dict[int, _TrackState] = {}

    def update(self, detections: Iterable[Mapping[str, object]]) -> tuple[Track, ...]:
        """Advance one frame and return tracks observed in this frame.

        Detections must contain ``label``, ``score``, and an x1,y1,x2,y2
        ``bbox``.  Coordinates may be pixels or normalized values, but all
        detections in a sequence must use the same coordinate system.
        """
        self._frame_index += 1
        parsed = sorted((_parse_detection(item) for item in detections), key=lambda d: -d[1])
        unmatched_track_ids = set(self._tracks)
        observed_track_ids: list[int] = []

        for label, score, bbox in parsed:
            track_id = self._best_match(label, bbox, unmatched_track_ids)
            if track_id is None:
                track_id = self._new_track(label, score, bbox)
            else:
                state = self._tracks[track_id]
                state.score = score
                state.bbox = bbox
                state.consecutive_hits += 1
                state.last_frame = self._frame_index
                state.missed_frames = 0
                unmatched_track_ids.remove(track_id)
            observed_track_ids.append(track_id)

        for track_id in unmatched_track_ids:
            state = self._tracks[track_id]
            state.missed_frames += 1
            state.consecutive_hits = 0

        self._tracks = {
            track_id: state
            for track_id, state in self._tracks.items()
            if state.missed_frames <= self.max_missed
        }
        return tuple(self._snapshot(self._tracks[track_id]) for track_id in observed_track_ids)

    def current_tracks(self, *, confirmed_only: bool = False) -> tuple[Track, ...]:
        """Return tracks observed on the most recent frame, optionally confirmed only."""
        tracks = tuple(
            self._snapshot(state)
            for state in sorted(self._tracks.values(), key=lambda item: item.track_id)
            if state.missed_frames == 0
        )
        if confirmed_only:
            return tuple(track for track in tracks if track.confirmed)
        return tracks

    def reset(self) -> None:
        self._frame_index = -1
        self._next_track_id = 1
        self._tracks.clear()

    def _new_track(self, label: str, score: float, bbox: BBox) -> int:
        track_id = self._next_track_id
        self._next_track_id += 1
        self._tracks[track_id] = _TrackState(
            track_id=track_id,
            label=label,
            score=score,
            bbox=bbox,
            consecutive_hits=1,
            first_frame=self._frame_index,
            last_frame=self._frame_index,
        )
        return track_id

    def _best_match(self, label: str, bbox: BBox, candidates: set[int]) -> int | None:
        best_id: int | None = None
        best_affinity = float("-inf")
        for track_id in candidates:
            state = self._tracks[track_id]
            if state.label != label:
                continue
            iou = bbox_iou(state.bbox, bbox)
            distance = centroid_distance_ratio(state.bbox, bbox)
            if iou < self.iou_threshold and distance > self.max_centroid_distance:
                continue
            # Any qualifying IoU match wins over a centroid-only fallback.
            affinity = 2.0 + iou if iou >= self.iou_threshold else 1.0 - distance
            if affinity > best_affinity:
                best_id = track_id
                best_affinity = affinity
        return best_id

    def _snapshot(self, state: _TrackState) -> Track:
        return Track(
            track_id=state.track_id,
            label=state.label,
            score=state.score,
            bbox=state.bbox,
            consecutive_hits=state.consecutive_hits,
            age_frames=self._frame_index - state.first_frame + 1,
            missed_frames=state.missed_frames,
            confirmed=state.missed_frames == 0 and state.consecutive_hits >= self.min_hits,
        )


def _parse_detection(item: Mapping[str, object]) -> tuple[str, float, BBox]:
    try:
        label = str(item["label"])
        score = float(item["score"])  # type: ignore[arg-type]
        raw_bbox = item["bbox"]
        if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) != 4:
            raise ValueError
        bbox = tuple(float(value) for value in raw_bbox)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("detection requires label, numeric score, and four-value bbox") from exc
    if not label:
        raise ValueError("detection label must not be empty")
    if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
        raise ValueError("bbox must satisfy x2 > x1 and y2 > y1")
    return label, score, bbox  # type: ignore[return-value]
