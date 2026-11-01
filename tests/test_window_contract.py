"""Exact defaults and eager scheduling behind an unfinished head."""

from __future__ import annotations

import queue
from collections.abc import Callable, Iterator
from concurrent.futures import Future

import pytest

import threadfan._engine
from threadfan import thread_imap, thread_map


@pytest.mark.parametrize("workers", [1, 2, 3])
def test_default_stream_window_is_twice_the_worker_count(workers: int) -> None:
    read: list[int] = []

    def source() -> Iterator[int]:
        for index in range(20):
            read.append(index)
            yield index

    stream = thread_imap(abs, source(), workers=workers)
    assert next(stream) == 0
    assert len(read) == 2 * workers
    stream.close()


def test_eager_map_replenishes_behind_an_unfinished_head(monkeypatch: pytest.MonkeyPatch) -> None:
    shutdown: list[tuple[bool, bool]] = []
    original = threadfan._engine._settled

    def settled(finished: queue.SimpleQueue[Future[int]]) -> list[Future[int]]:
        assert not finished.empty(), "scheduler waited instead of replenishing"
        return original(finished)

    class Pool:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.head: Future[int] = Future()

        def submit(self, fn: Callable[[int], int], value: int) -> Future[int]:
            if value == 0:
                return self.head
            future: Future[int] = Future()
            future.set_result(fn(value))
            if value == 4:
                self.head.set_result(fn(0))
            return future

        def shutdown(self, *, wait: bool, cancel_futures: bool) -> None:
            shutdown.append((wait, cancel_futures))

    monkeypatch.setattr(threadfan._engine, "ThreadPoolExecutor", Pool)
    monkeypatch.setattr(threadfan._engine, "_settled", settled)
    assert thread_map(abs, range(6), workers=2, max_pending=2) == list(range(6))
    assert shutdown == [(True, True)]
