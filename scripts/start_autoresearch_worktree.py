#!/usr/bin/env python3
"""Create an isolated autoresearch branch/worktree and run the campaign there."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKTREE_PARENT = Path("/tmp/tiny_pi_car-autoresearch")
SAFE_TAG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def validate_tag(value: str) -> str:
    if not SAFE_TAG.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "tag must be 1-64 lowercase letters, digits, dots, underscores, or dashes"
        )
    return value


def warn_if_dirty() -> None:
    status = subprocess.check_output(
        ("git", "status", "--porcelain"), cwd=ROOT, text=True
    ).strip()
    if status:
        print(
            "warning: source tree is dirty; worktree still created from HEAD",
            file=sys.stderr,
        )


def branch_exists(branch: str) -> bool:
    result = subprocess.run(
        ("git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"),
        cwd=ROOT,
        check=False,
    )
    return result.returncode == 0


def build_loop_command(worktree: Path, loop_args: list[str]) -> list[str]:
    args = list(loop_args)
    if args and args[0] == "--":
        args.pop(0)
    # Commits are opt-in via --commit on the loop; do not force them.
    return [
        sys.executable,
        str(worktree / "scripts" / "autoresearch_loop.py"),
        *args,
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", type=validate_tag, required=True)
    parser.add_argument("--worktree-parent", type=Path, default=DEFAULT_WORKTREE_PARENT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "loop_args",
        nargs=argparse.REMAINDER,
        help="arguments after -- are passed to scripts/autoresearch_loop.py",
    )
    args = parser.parse_args()

    warn_if_dirty()
    branch = f"autoresearch/{args.tag}"
    worktree = (args.worktree_parent / args.tag).resolve()
    if branch_exists(branch):
        parser.error(f"branch already exists: {branch}")
    if worktree.exists():
        parser.error(f"worktree path already exists: {worktree}")

    loop_command = build_loop_command(worktree, args.loop_args)
    plan = {
        "branch": branch,
        "worktree": str(worktree),
        "loop_command": loop_command,
    }
    print(json.dumps(plan, indent=2))
    if args.dry_run:
        return 0

    worktree.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ("git", "worktree", "add", "-b", branch, str(worktree), "HEAD"),
        cwd=ROOT,
        check=True,
    )
    source_venv = ROOT / ".venv"
    target_venv = worktree / ".venv"
    if not source_venv.is_dir():
        raise RuntimeError(f"missing host virtualenv: {source_venv}")
    os.symlink(source_venv, target_venv, target_is_directory=True)

    print(f"Starting isolated run in {worktree}")
    print(f"The worktree is retained for inspection; branch is {branch}.")
    return subprocess.run(loop_command, cwd=worktree, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
