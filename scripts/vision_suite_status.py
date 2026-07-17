#!/usr/bin/env python3
"""Show vision suite slots vs local HEFs (host). Optionally probe the Pi."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "playground" / "vision" / "suite" / "MANIFEST.json"
MODEL_DIR = ROOT / "playground" / "vision" / "models"
ARTIFACT_DIR = ROOT / ".autoresearch" / "artifacts"


def _local_map() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for directory in (MODEL_DIR, ARTIFACT_DIR):
        if not directory.is_dir():
            continue
        for path in directory.glob("*.hef"):
            found[path.name] = path
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="", help="if set, also ssh and list remote models/")
    parser.add_argument(
        "--remote-root",
        default="/home/tyler/Desktop/tiny_pi_car",
        help="Pi repo path for --host probe",
    )
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    local = _local_map()
    slots = []
    for slot in sorted(manifest["slots"], key=lambda s: int(s.get("priority", 99))):
        name = str(slot["filename"])
        path = local.get(name)
        slots.append(
            {
                "id": slot["id"],
                "role": slot["role"],
                "filename": name,
                "present_local": path is not None,
                "local_path": str(path) if path else None,
                "source_url": slot.get("source_url"),
                "zoo_hint": slot.get("zoo_hint"),
            }
        )

    payload: dict = {
        "hw_arch": manifest.get("hw_arch"),
        "model_dir": str(MODEL_DIR),
        "artifact_dir": str(ARTIFACT_DIR),
        "slots": slots,
        "orphan_local_hefs": sorted(
            name for name in local if name not in {s["filename"] for s in slots}
        ),
    }

    if args.host:
        root = shlex.quote(args.remote_root)
        remote_cmd = (
            "set -eu; "
            "echo hailo_dev=$(test -e /dev/h1x-0 && echo yes || echo no); "
            "echo os=$(. /etc/os-release; echo $VERSION_CODENAME); "
            f"ls -1 {root}/playground/vision/models/*.hef 2>/dev/null || true"
        )
        result = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", args.host, remote_cmd],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        payload["remote"] = {
            "host": args.host,
            "exit": result.returncode,
            "stdout": result.stdout.strip().splitlines(),
            "stderr": result.stderr.strip().splitlines()[-5:],
        }

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
