#!/usr/bin/env python3
"""Copy a HEF into playground/vision/models/ for a named suite slot."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "playground" / "vision" / "suite" / "MANIFEST.json"
MODEL_DIR = ROOT / "playground" / "vision" / "models"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slot", required=True, help="suite slot id (e.g. yolov8n)")
    parser.add_argument("--from", dest="source", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    slot = next((s for s in manifest["slots"] if s["id"] == args.slot), None)
    if slot is None:
        known = ", ".join(s["id"] for s in manifest["slots"])
        raise SystemExit(f"unknown slot {args.slot!r}; known: {known}")
    if not args.source.is_file():
        raise SystemExit(f"missing source HEF: {args.source}")
    if args.source.suffix.lower() != ".hef":
        raise SystemExit("source must be a .hef file")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    dest = MODEL_DIR / str(slot["filename"])
    if dest.exists() and not args.force:
        raise SystemExit(f"{dest} exists; pass --force to replace")
    shutil.copy2(args.source, dest)
    print(json.dumps({"slot": args.slot, "installed": str(dest)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
