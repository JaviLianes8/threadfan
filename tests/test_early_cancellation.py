"""Ordered failures cancel queued tails while a stream consumer is suspended."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, ParamSpec, TypeVar

import pytest

import threadfan._engine
from threadfan import thread_imap

P = ParamSpec("P")
R = TypeVar("R")


def test_observed_failure_cancels_tail_before_consumer_resumes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_head = threading.Event()
    release_tail = threading.Event()
    tail_started = [threading.Event(), threading.Event()]
    futures: list[Future[Any]] = []
    calls: list[int] = []
    failure = ValueError("one")

    class ObservedPool(ThreadPoolExecutor):
        def submit(self, fn: Callable[P, R], /, *args: P.args, **kwargs: P.kwargs) -> Future[R]:
            future = super().submit(fn, *args, **kwargs)
            futures.append(future)
            if len(futures) == 2:
                future.add_done_callback(lambda _: release_head.set())
            return future

    def work(value: int) -> int:
        calls.append(value)
        if value == 0:
            assert release_head.wait(10)
        elif value == 1:
            raise failure
        else:
            if value in (2, 3):
                tail_started[value - 2].set()
            assert release_tail.wait(10)
        return value

    def source() -> Iterator[int]:
        yield from range(6)
        assert futures[0].result(timeout=10) == 0
        assert futures[1].exception(timeout=10) is failure
        # Both workers must pass their completion callbacks before the batch is drained.
        assert all(event.wait(10) for event in tail_started)

    monkeypatch.setattr(threadfan._engine, "ThreadPoolExecutor", ObservedPool)
    stream = thread_imap(work, source(), workers=2, max_pending=7)
    try:
        assert next(stream) == 0
        assert all(future.cancelled() for future in futures[4:])
        release_tail.set()
        for future in futures[2:4]:
            future.result(timeout=10)
        assert set(calls) == {0, 1, 2, 3}
        with pytest.raises(ValueError) as info:
            next(stream)
        assert info.value is failure
    finally:
        release_head.set()
        release_tail.set()
        stream.close()
