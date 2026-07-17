#!/usr/bin/env python3
"""List local Hailo HEF slots and any files found under models/artifacts."""

from __future__ import annotations

import json

from playground.vision.models import ARTIFACT_DIR, MODEL_DIR, MODELS, list_local_hefs


def main() -> int:
    slots = [
        {
            "name": spec.name,
            "path": str(spec.hef_path),
            "present": spec.hef_path.is_file(),
            "zoo_hint": spec.zoo_hint,
        }
        for spec in MODELS
    ]
    found = [str(path) for path in list_local_hefs()]
    print(
        json.dumps(
            {
                "model_dir": str(MODEL_DIR),
                "artifact_dir": str(ARTIFACT_DIR),
                "slots": slots,
                "found_hefs": found,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
