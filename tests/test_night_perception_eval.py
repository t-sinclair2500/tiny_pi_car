from scripts.night_perception_eval import evaluate_payload, parse_summary, score_latency


def test_score_latency_monotone():
    assert score_latency(latency_p50_ms=50) == 100.0
    assert score_latency(latency_p50_ms=500) == 0.0
    mid = score_latency(latency_p50_ms=130)
    assert 80.0 < mid < 90.0
    assert score_latency(latency_p50_ms=100) > score_latency(latency_p50_ms=200)


def test_parse_and_gates():
    text = """
output_path: /tmp/x.jsonl
frame_count: 15
valid_frame_count: 15
detection_count: 0
inference_p50_ms: 28.0
inference_p90_ms: 30.0
latency_p50_ms: 130.0
latency_p90_ms: 140.0
"""
    summary = parse_summary(text)
    payload = evaluate_payload(
        summary,
        budget_ms=500.0,
        floor_ms=50.0,
        max_inference_ms=150.0,
        max_latency_ms=2000.0,
    )
    assert payload["hard_gates_passed"] is True
    assert payload["score"] == score_latency(latency_p50_ms=130.0)


def test_hard_gate_fails_on_slow_infer():
    summary = parse_summary(
        "frame_count: 10\nvalid_frame_count: 10\ndetection_count: 0\n"
        "inference_p50_ms: 400.0\nlatency_p50_ms: 500.0\n"
    )
    payload = evaluate_payload(
        summary,
        budget_ms=500.0,
        floor_ms=50.0,
        max_inference_ms=150.0,
        max_latency_ms=2000.0,
    )
    assert payload["hard_gates_passed"] is False
    assert payload["score"] < 0.0
