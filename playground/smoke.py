"""Tiny import / path smoke check (no motor motion)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTERPI = ROOT / "MasterPi"


def main() -> int:
    print(f"root={ROOT}")
    print(f"masterpi_exists={MASTERPI.is_dir()}")
    if str(MASTERPI) not in sys.path:
        sys.path.insert(0, str(MASTERPI))
    # SDK paths used by stock scripts
    for rel in (
        "masterpi_sdk/common_sdk",
        "masterpi_sdk/kinematics_sdk",
    ):
        p = MASTERPI / rel
        print(f"{rel}: exists={p.is_dir()}")
        if p.is_dir() and str(p) not in sys.path:
            sys.path.insert(0, str(p))
    try:
        import yaml  # noqa: F401
        import serial  # noqa: F401
        import numpy  # noqa: F401

        print("deps: numpy/yaml/serial OK")
    except ImportError as exc:
        print(f"deps: missing ({exc}) — run: pip install -e '.[dev]'")
        return 1
    print("smoke OK (no hardware exercised)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
