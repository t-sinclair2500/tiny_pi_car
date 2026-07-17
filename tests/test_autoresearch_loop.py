from scripts.autoresearch_loop import (
    DEFAULT_CAMPAIGN,
    _last_json_object,
    better,
    extract_opencode_text,
    load_campaign,
    materialize_command,
    path_allowed,
)


def test_campaign_loads_and_has_fixed_eval():
    campaign = load_campaign(DEFAULT_CAMPAIGN)
    assert campaign.name == "reactive-policy-v0"
    assert campaign.eval_command[-1] == "--json"
    assert "playground/autoresearch/candidate.py" in campaign.editable_paths
    assert "playground/autonomy/**" in campaign.editable_paths


def test_json_and_opencode_event_parsing():
    assert _last_json_object("noise\n{\"score\": 4}\n") == {"score": 4}
    stream = (
        '{"type":"text","part":{"text":"one"}}\n'
        '{"type":"step_finish","part":{}}\n'
        '{"type":"text","part":{"text":"two"}}\n'
    )
    assert extract_opencode_text(stream) == "one\ntwo"


def test_acceptance_direction_and_scope_patterns():
    campaign = load_campaign(DEFAULT_CAMPAIGN)
    assert better(2.0, 1.0, campaign)
    assert not better(1.0, 1.0, campaign)
    assert path_allowed("playground/experiments/vision/a.py", ("playground/experiments/**",))
    assert not path_allowed("playground/autonomy/safety_gate.py", ("playground/experiments/**",))


def test_campaign_command_expands_python_root_and_required_env(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCKED_DATASET", "/private/heldout.jsonl")
    command = materialize_command(
        ("{python}", "--root", "{root}", "--data", "{env:LOCKED_DATASET}"),
        root=tmp_path,
    )
    assert command[0]
    assert command[2] == str(tmp_path)
    assert command[-1] == "/private/heldout.jsonl"


def test_campaign_command_rejects_missing_env(monkeypatch, tmp_path):
    import pytest

    monkeypatch.delenv("MISSING_DATASET", raising=False)
    with pytest.raises(ValueError, match="MISSING_DATASET"):
        materialize_command(("{env:MISSING_DATASET}",), root=tmp_path)
