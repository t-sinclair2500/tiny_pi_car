"""Offline autoresearch arena tests; no hardware or network."""

from playground.autoresearch.evaluate import evaluate


def test_baseline_is_deterministic_and_passes_hard_gates():
    first = evaluate()
    second = evaluate()
    assert first == second
    assert first.hard_gates_passed
    assert first.safety_violations == 0
    assert first.policy_errors == 0
    assert first.episodes == 16


def test_baseline_has_a_useful_nontrivial_score():
    result = evaluate()
    assert 20.0 < result.score < 99.0
    assert 0.0 <= result.success_rate <= 1.0
