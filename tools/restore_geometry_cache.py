#!/usr/bin/env python3
"""Restore the original, byte-exact generated P5 geometry cache (standard library only)."""
from pathlib import Path
import gzip
import hashlib
import os

RELATIVE = "ARX-6-P5-Engineering/integration/geometry-meshes.json"
EXPECTED_BYTES = 18798465
EXPECTED_SHA256 = "838768d0473b4ba2ed25be1e1b0d5c34c3ac643dce99e140bb415d99f2103208"


def verified(data):
    return len(data) == EXPECTED_BYTES and hashlib.sha256(data).hexdigest() == EXPECTED_SHA256


def main():
    root = Path(__file__).resolve().parent.parent
    target = root / RELATIVE
    if target.exists():
        if not verified(target.read_bytes()):
            raise SystemExit("Existing geometry cache differs; refusing to overwrite it.")
        print("Original geometry cache is already restored and verified.")
        return
    data = gzip.decompress(target.with_suffix(".json.gz").read_bytes())
    if not verified(data):
        raise SystemExit("Compressed geometry cache failed its byte count / SHA-256 check.")
    temporary = target.with_suffix(".json.restoring")
    with temporary.open("xb") as stream:
        stream.write(data)
    os.replace(temporary, target)
    print("Restored and verified: " + RELATIVE)
    print("SHA-256: " + EXPECTED_SHA256)


if __name__ == "__main__":
    main()
