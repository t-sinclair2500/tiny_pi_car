#!/usr/bin/env python3
"""Deploy the bounded playground research runtime to the Pi without running it."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.remote_perception_eval import (  # noqa: E402
    _validate_host,
    _validate_remote_root,
    deploy_command,
    ensure_remote_dirs_command,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", type=_validate_host, default="rpicarbox.local")
    parser.add_argument("--remote-root", type=_validate_remote_root, default="/tmp/tiny_pi_car")
    parser.add_argument("--timeout-s", type=int, default=180)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.timeout_s <= 900:
        parser.error("--timeout-s must be between 1 and 900")

    ensure = ensure_remote_dirs_command(
        args.host,
        args.remote_root,
        "/tmp/tiny_pi_car_autoresearch_datasets",
    )
    deploy = deploy_command(args.host, args.remote_root)
    if args.dry_run:
        print(shlex.join(ensure))
        print(shlex.join(deploy))
        return 0
    subprocess.run(ensure, timeout=args.timeout_s, check=True)
    subprocess.run(deploy, timeout=args.timeout_s, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
