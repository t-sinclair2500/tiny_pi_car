"""Optional motion-arm marker. Agents may move without it; keep for logging if wanted."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

DEFAULT_ARM_FILE = Path("/tmp/tiny_pi_car/motion-arm.json")
MAX_TTL_S = 86400
STAGES = ("wheels-raised", "floor", "free")


def _boot_id() -> str:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return "unknown"


def create_arm_lease(
    path: Path,
    *,
    stage: str = "free",
    ttl_s: int = 3600,
    operator_present: bool = True,
    now: float | None = None,
) -> dict[str, Any]:
    """Create an optional arm marker (not required for motion)."""
    if stage not in STAGES:
        raise ValueError(f"stage must be one of {STAGES}")
    if not 1 <= ttl_s <= MAX_TTL_S:
        raise ValueError(f"ttl_s must be between 1 and {MAX_TTL_S}")
    issued_at = time.time() if now is None else now
    lease = {
        "schema": 2,
        "stage": stage,
        "issued_at_epoch_s": issued_at,
        "expires_at_epoch_s": issued_at + ttl_s,
        "boot_id": _boot_id(),
        "operator_present": bool(operator_present),
        "required": False,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(lease, sort_keys=True) + "\n")
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    return lease


def read_arm_lease(
    path: Path = DEFAULT_ARM_FILE,
    *,
    required_stage: str | None = None,
    now: float | None = None,
    required: bool = False,
) -> dict[str, Any] | None:
    """Return lease if present/valid. Unless ``required``, missing lease is OK."""
    try:
        lease = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        if required:
            raise RuntimeError("physical motion is not armed")
        return None
    current = time.time() if now is None else now
    expires = lease.get("expires_at_epoch_s")
    if not isinstance(expires, (int, float)) or current >= float(expires):
        if required:
            raise RuntimeError("physical-motion arm lease expired")
        return None
    if required_stage is not None and lease.get("stage") not in (required_stage, "free"):
        if required:
            raise RuntimeError(
                f"physical-motion lease is for {lease.get('stage')!r}, not {required_stage!r}"
            )
        return None
    return lease


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("arm", "status", "disarm"))
    parser.add_argument("--stage", choices=STAGES, default="free")
    parser.add_argument("--ttl-s", type=int, default=3600)
    parser.add_argument("--operator-present", action="store_true", default=True)
    parser.add_argument("--arm-file", type=Path, default=DEFAULT_ARM_FILE)
    args = parser.parse_args()

    if args.operation == "arm":
        lease = create_arm_lease(
            args.arm_file,
            stage=args.stage,
            ttl_s=args.ttl_s,
            operator_present=args.operator_present,
        )
        print(json.dumps(lease, sort_keys=True))
        return 0
    if args.operation == "disarm":
        args.arm_file.unlink(missing_ok=True)
        print("physical motion disarmed")
        return 0
    lease = read_arm_lease(args.arm_file)
    if lease is None:
        print("no arm lease (motion still allowed)")
        return 0
    print(json.dumps(lease, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
