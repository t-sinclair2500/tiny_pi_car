from __future__ import annotations

import pytest

from playground.autonomy.tracking import DetectionTracker, bbox_iou, centroid_distance_ratio


def detection(
    label: str = "bottle",
    bbox: tuple[float, float, float, float] = (10.0, 10.0, 30.0, 40.0),
    score: float = 0.9,
) -> dict[str, object]:
    return {"label": label, "score": score, "bbox": bbox}


def test_track_requires_three_consecutive_hits() -> None:
    tracker = DetectionTracker()

    first = tracker.update([detection()])[0]
    second = tracker.update([detection(bbox=(11.0, 10.0, 31.0, 40.0))])[0]
    third = tracker.update([detection(bbox=(12.0, 10.0, 32.0, 40.0))])[0]

    assert first.track_id == second.track_id == third.track_id
    assert not first.confirmed
    assert not second.confirmed
    assert third.confirmed
    assert third.consecutive_hits == 3
    assert tracker.current_tracks(confirmed_only=True) == (third,)


def test_missed_frame_immediately_revokes_confirmation() -> None:
    tracker = DetectionTracker(min_hits=3, max_missed=2)
    for _ in range(3):
        confirmed = tracker.update([detection()])[0]
    assert confirmed.confirmed

    assert tracker.update([]) == ()
    assert tracker.current_tracks(confirmed_only=True) == ()
    reacquired = tracker.update([detection()])[0]

    assert reacquired.track_id == confirmed.track_id
    assert reacquired.consecutive_hits == 1
    assert not reacquired.confirmed


def test_track_is_removed_after_miss_budget() -> None:
    tracker = DetectionTracker(max_missed=1)
    first = tracker.update([detection()])[0]
    tracker.update([])
    tracker.update([])
    replacement = tracker.update([detection()])[0]

    assert replacement.track_id != first.track_id


def test_association_never_crosses_labels() -> None:
    tracker = DetectionTracker(min_hits=2)
    bottle = tracker.update([detection("bottle")])[0]
    cup = tracker.update([detection("cup")])[0]

    assert cup.track_id != bottle.track_id
    assert not cup.confirmed


def test_centroid_fallback_handles_non_overlapping_small_motion() -> None:
    tracker = DetectionTracker(iou_threshold=0.5, max_centroid_distance=1.1)
    first = tracker.update([detection(bbox=(0.0, 0.0, 10.0, 10.0))])[0]
    second = tracker.update([detection(bbox=(11.0, 0.0, 21.0, 10.0))])[0]

    assert bbox_iou(first.bbox, second.bbox) == 0.0
    assert centroid_distance_ratio(first.bbox, second.bbox) < 1.1
    assert second.track_id == first.track_id


def test_rejects_invalid_detection() -> None:
    tracker = DetectionTracker()

    with pytest.raises(ValueError, match="detection requires"):
        tracker.update([{"label": "bottle", "score": 0.9}])
    with pytest.raises(ValueError, match="bbox must satisfy"):
        tracker.update([detection(bbox=(10.0, 10.0, 5.0, 20.0))])
