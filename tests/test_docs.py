"""The README examples run, and the package version agrees with its metadata."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import threadfan

ROOT = Path(__file__).resolve().parents[1]


def _python_blocks() -> list[str]:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    return re.findall(r"```python\n(.*?)```", text, flags=re.DOTALL)


def test_the_readme_has_examples() -> None:
    assert len(_python_blocks()) >= 5


def test_every_readme_example_runs_in_order(capsys: pytest.CaptureFixture[str]) -> None:
    namespace: dict[str, object] = {"__name__": "readme"}
    for block in _python_blocks():
        exec(compile(block, "README.md", "exec"), namespace)
    printed = capsys.readouterr().out
    assert "2 tasks failed; first at index 1: ValueError" in printed
    assert "20/20" in printed


def test_version_matches_pyproject() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', text, flags=re.MULTILINE)
    assert match is not None
    assert match.group(1) == threadfan.__version__


def test_changelog_has_an_entry_for_this_version() -> None:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{threadfan.__version__}]" in text
