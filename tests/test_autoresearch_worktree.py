import argparse
import sys
from pathlib import Path

import pytest

from scripts.start_autoresearch_worktree import build_loop_command, validate_tag


def test_validate_tag_rejects_branch_injection():
    assert validate_tag("vision-jul16") == "vision-jul16"
    for invalid in ("Vision", "../escape", "with space", "semi;colon", ""):
        with pytest.raises(argparse.ArgumentTypeError):
            validate_tag(invalid)


def test_loop_command_targets_worktree_without_forcing_commits():
    worktree = Path("/tmp/tiny_pi_car-autoresearch/test")
    command = build_loop_command(worktree, ["--", "--iterations", "2", "--council"])
    assert command[:2] == [sys.executable, str(worktree / "scripts" / "autoresearch_loop.py")]
    assert "--commit" not in command
    assert "--council" in command


def test_loop_command_preserves_explicit_commit_flag():
    command = build_loop_command(Path("/tmp/w"), ["--commit"])
    assert command.count("--commit") == 1
