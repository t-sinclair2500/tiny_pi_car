#!/usr/bin/env python3
"""Download a non-executable research artifact into the gitignored lab cache."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / ".autoresearch" / "artifacts"
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")
ALLOWED_SUFFIXES = {".hef", ".onnx", ".tflite", ".json", ".yaml", ".yml", ".txt"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--sha256", help="expected digest; strongly recommended for model binaries")
    parser.add_argument("--max-mib", type=int, default=1024)
    args = parser.parse_args()

    parsed = urlparse(args.url)
    if parsed.scheme != "https" or not parsed.netloc:
        parser.error("only HTTPS URLs are allowed")
    if not SAFE_NAME.fullmatch(args.name):
        parser.error("--name must be a plain filename")
    if Path(args.name).suffix.lower() not in ALLOWED_SUFFIXES:
        parser.error(f"allowed suffixes: {sorted(ALLOWED_SUFFIXES)}")
    if not 1 <= args.max_mib <= 4096:
        parser.error("--max-mib must be between 1 and 4096")
    if args.sha256 and not re.fullmatch(r"[0-9a-fA-F]{64}", args.sha256):
        parser.error("--sha256 must be 64 hexadecimal characters")

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    destination = ARTIFACTS / args.name
    limit = args.max_mib * 1024 * 1024
    digest = hashlib.sha256()
    size = 0
    request = urllib.request.Request(args.url, headers={"User-Agent": "tiny-pi-car-autoresearch/1"})
    fd, temporary_name = tempfile.mkstemp(prefix=f".{args.name}.", dir=ARTIFACTS)
    try:
        with os.fdopen(fd, "wb") as output, urllib.request.urlopen(request, timeout=60) as response:
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise ValueError(f"artifact exceeds {args.max_mib} MiB limit")
                digest.update(chunk)
                output.write(chunk)
        actual = digest.hexdigest()
        if args.sha256 and actual.lower() != args.sha256.lower():
            raise ValueError(f"SHA256 mismatch: expected {args.sha256}, got {actual}")
        os.replace(temporary_name, destination)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise

    print(
        json.dumps(
            {"path": str(destination), "bytes": size, "sha256": digest.hexdigest(), "url": args.url},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
