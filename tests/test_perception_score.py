from playground.autoresearch.perception_score import score_records


def _truth():
    return [
        {
            "frame_id": "a",
            "objects": [{"label": "cup", "bbox_px": [10, 10, 30, 40]}],
        },
        {
            "frame_id": "b",
            "objects": [{"label": "person", "bbox_px": [0, 0, 50, 100]}],
        },
    ]


def test_perfect_predictions_pass_and_score_high():
    predictions = [
        {
            "frame_id": "a",
            "latency_ms": 20,
            "detections": [{"label": "cup", "score": 0.9, "bbox_px": [10, 10, 30, 40]}],
        },
        {
            "frame_id": "b",
            "latency_ms": 30,
            "detections": [
                {"label": "person", "score": 0.9, "bbox_px": [0, 0, 50, 100]}
            ],
        },
    ]
    result = score_records(_truth(), predictions, target_labels=frozenset({"cup"}))
    assert result.hard_gates_passed
    assert result.precision == result.recall == result.target_recall == 1.0
    assert result.score > 90.0


def test_missing_target_prediction_fails_hard_gate():
    predictions = [
        {"frame_id": "a", "latency_ms": 20, "detections": []},
        {"frame_id": "b", "latency_ms": 20, "detections": []},
    ]
    result = score_records(_truth(), predictions, target_labels=frozenset({"cup"}))
    assert not result.hard_gates_passed
    assert result.target_recall == 0.0


def test_wrong_class_and_duplicate_boxes_count_as_false_positives():
    predictions = [
        {
            "frame_id": "a",
            "latency_ms": 10,
            "detections": [
                {"label": "bottle", "score": 0.9, "bbox_px": [10, 10, 30, 40]},
                {"label": "cup", "score": 0.8, "bbox_px": [10, 10, 30, 40]},
                {"label": "cup", "score": 0.7, "bbox_px": [10, 10, 30, 40]},
            ],
        },
        {
            "frame_id": "b",
            "latency_ms": 10,
            "detections": [
                {"label": "person", "score": 0.9, "bbox_px": [0, 0, 50, 100]}
            ],
        },
    ]
    result = score_records(_truth(), predictions, target_labels=frozenset({"cup"}))
    assert result.true_positives == 2
    assert result.false_positives == 2
    assert result.precision == 0.5
