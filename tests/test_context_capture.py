"""Eager mapping captures context before the source can change the caller's context."""

from __future__ import annotations

from collections.abc import Iterator
from contextvars import ContextVar

import pytest

from threadfan import thread_map


@pytest.mark.parametrize("ordered", [False, True])
def test_map_captures_context_before_materializing_the_source(ordered: bool) -> None:
    request = ContextVar("request", default="unset")
    token = request.set("at-call")

    def source() -> Iterator[int]:
        request.set("during-source")
        yield from range(4)

    try:
        assert (
            thread_map(lambda _: request.get(), source(), copy_context=True, ordered=ordered)
            == ["at-call"] * 4
        )
        assert request.get() == "during-source"
    finally:
        request.reset(token)
