"""The public API is typed: mypy infers result types and rejects wrong items."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

api = pytest.importorskip("mypy.api")

SRC = Path(__file__).resolve().parents[1] / "src"

SNIPPET = """
from threadfan import ThreadMapError, thread_imap, thread_map

def label(value: int) -> str:
    return str(value)

reveal_type(thread_map(label, [1, 2]))
reveal_type(thread_imap(label, range(3)))
reveal_type(ThreadMapError({}).errors)
thread_map(label, ["not", "ints"])
thread_map(label, [1], workers="4")
"""


@pytest.fixture(scope="module")
def mypy_output(tmp_path_factory: pytest.TempPathFactory) -> str:
    folder = tmp_path_factory.mktemp("typing")
    target = folder / "snippet.py"
    target.write_text(SNIPPET, encoding="utf-8")
    config = folder / "mypy.ini"
    config.write_text(f"[mypy]\nmypy_path = {SRC.as_posix()}\n", encoding="utf-8")
    cache = str(folder / "cache")
    out, err, _ = api.run(
        ["--strict", "--config-file", str(config), "--cache-dir", cache, str(target)]
    )
    return str(out) + str(err)


def test_thread_map_returns_a_list_of_the_function_result(mypy_output: str) -> None:
    assert _revealed(mypy_output, 7) == "list[str]"


def test_thread_imap_returns_a_generator_of_the_function_result(mypy_output: str) -> None:
    assert _revealed(mypy_output, 8) == "typing.Generator[str, None, None]"


def test_the_error_exposes_typed_failures(mypy_output: str) -> None:
    assert _revealed(mypy_output, 9) == "dict[int, Exception]"


def test_wrong_item_types_are_rejected(mypy_output: str) -> None:
    assert re.search(r"snippet\.py:10: error: .*\[arg-type\]", mypy_output)


def test_wrong_option_types_are_rejected(mypy_output: str) -> None:
    assert re.search(r"snippet\.py:11: error: .*\[arg-type\]", mypy_output)


def _revealed(output: str, line: int) -> str:
    match = re.search(rf"snippet\.py:{line}: note: Revealed type is \"(.+)\"", output)
    assert match, output
    # Older mypy releases spell builtins with their module prefix.
    return match.group(1).replace("builtins.", "")
