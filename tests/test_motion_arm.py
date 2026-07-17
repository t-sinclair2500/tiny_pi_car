import json
from pathlib import Path

from playground.autoresearch.motion_arm import create_arm_lease, read_arm_lease


def test_arm_is_optional_and_can_expire(tmp_path: Path):
    arm_file = tmp_path / "arm.json"
    assert read_arm_lease(arm_file) is None

    lease = create_arm_lease(
        arm_file,
        stage="floor",
        ttl_s=60,
        operator_present=True,
        now=100.0,
    )
    assert read_arm_lease(arm_file, required_stage="floor", now=159.0) == lease
    assert read_arm_lease(arm_file, required_stage="floor", now=160.0) is None


def test_arm_file_is_private(tmp_path: Path):
    arm_file = tmp_path / "arm.json"
    create_arm_lease(arm_file, stage="free", ttl_s=30)
    assert arm_file.stat().st_mode & 0o777 == 0o600
    assert json.loads(arm_file.read_text())["required"] is False
