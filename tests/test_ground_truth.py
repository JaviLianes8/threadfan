"""Fetched official examples and real standard-library executions as independent oracles."""

from __future__ import annotations

import contextvars
import re
import textwrap
from concurrent.futures import ThreadPoolExecutor
from typing import cast

import pytest
from conftest import upstream_text

from threadfan import thread_imap, thread_map


def test_fetched_executor_example_matches_both_entry_points() -> None:
    # The official submit example supplies the operands; no remembered vector.
    text = upstream_text("futures.rst")
    match = re.search(r"executor.submit\(pow, (\d+), (\d+)\)", text)
    assert match
    base, exponent = map(int, match.groups())
    with ThreadPoolExecutor(1) as pool:
        expected = pool.submit(pow, base, exponent).result()
    assert thread_map(lambda n: pow(n, exponent), [base]) == [expected]
    assert list(thread_imap(lambda n: pow(n, exponent), [base])) == [expected]


def test_fetched_context_example_and_task_isolation(capsys: pytest.CaptureFixture[str]) -> None:
    text = upstream_text("contextvars.rst")
    match = re.search(
        r"Example:\s+\.\. testcode::\n(.*?)\n      \.\. testoutput::\n"
        r"         :hide:\n\n(.*?)\n\n",
        text,
        re.DOTALL,
    )
    assert match
    code, output = map(textwrap.dedent, match.groups())
    namespace: dict[str, object] = {}
    contextvars.Context().run(exec, compile(code, "contextvars.rst", "exec"), namespace)
    assert capsys.readouterr().out.strip() == output.strip()
    var = cast(contextvars.ContextVar[str], namespace["var"])
    ctx = cast(contextvars.Context, namespace["ctx"])
    expected = ctx.copy().run(var.get)
    assert ctx.run(thread_map, lambda _: var.get(), range(5), copy_context=True) == [expected] * 5
    stream = ctx.run(thread_imap, lambda _: var.get(), range(5), copy_context=True)
    assert list(stream) == [expected] * 5


@pytest.mark.parametrize("workers", [1, 2, 7])
def test_live_executor_map_agrees_on_values_and_lowest_failure(workers: int) -> None:
    # Hand-written inputs; the oracle is the real executor running in this test.
    values = [-9, 0, 7, 2**70, -(2**70)]
    with ThreadPoolExecutor(workers) as pool:
        expected = list(pool.map(str, values))
    assert thread_map(str, values, workers=workers) == expected
    assert list(thread_imap(str, values, workers=workers)) == expected
    for execute in (thread_map, thread_imap):
        with ThreadPoolExecutor(workers) as pool:
            oracle = pool.map(int, ["1", "wrong", "2", "also wrong"])
            assert next(oracle) == 1
            with pytest.raises(ValueError) as original:
                list(oracle)
        with pytest.raises(ValueError) as actual:
            list(execute(int, ["1", "wrong", "2", "also wrong"], workers=workers))
        assert actual.value.args == original.value.args
