"""Fetch pinned Python reference documents into an explicitly chosen local directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    manifest = Path(__file__).resolve().parents[1] / "tests/upstream/MANIFEST.json"
    entries = json.loads(manifest.read_text(encoding="utf-8"))
    args.directory.mkdir(parents=True, exist_ok=True)
    for name, entry in entries.items():
        with urllib.request.urlopen(entry["url"], timeout=60) as response:
            data = response.read()
        if len(data) != entry["size"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError(f"reference hash mismatch: {name}")
        (args.directory / name).write_bytes(data)
        print(f"verified {name}: {len(data)} bytes")


if __name__ == "__main__":
    main()
