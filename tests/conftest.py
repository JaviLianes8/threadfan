"""Shared helpers: the fetched reference files, each checked against its manifest entry."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

MANIFEST = Path(__file__).resolve().parent / "upstream" / "MANIFEST.json"


def upstream_text(name: str) -> str:
    """Return a fetched reference file as text, checked against its manifest entry.

    The files are not committed: ``scripts/fetch_upstream.py DIRECTORY`` fetches them.
    Their tests skip while a file is absent and fail if it differs from the manifest.
    """
    folder = os.environ.get("THREADFAN_UPSTREAM")
    if folder is None:
        pytest.skip("set THREADFAN_UPSTREAM to the fetched reference directory")
    path = Path(folder) / name
    if not path.is_file():
        pytest.skip(f"{name} is not fetched; run python scripts/fetch_upstream.py")
    entry = json.loads(MANIFEST.read_text(encoding="utf-8"))[name]
    body = path.read_bytes()
    assert hashlib.sha256(body).hexdigest() == entry["sha256"], f"{name} differs from MANIFEST"
    return body.decode("utf-8")
