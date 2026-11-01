"""Deterministic scheduling contracts for callbacks, windows and option evaluation."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from concurrent.futures import Future
from typing import Any

import pytest

import threadfan._engine
from threadfan import ThreadMapError, thread_imap, thread_map


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("fail", [False, True])
def test_unordered_batches_keep_callback_order(
    monkeypatch: pytest.MonkeyPatch, streaming: bool, fail: bool
) -> None:
    class Pool:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.futures: list[Future[int]] = []

        def submit(self, fn: Callable[[int], int], value: int) -> Future[int]:
            future: Future[int] = Future()
            self.futures.append(future)
            if value == 3:
                for index in (2, 1, 0, 3):
                    if fail and index in (1, 2):
                        self.futures[index].set_exception(ValueError(index))
                    else:
                        self.futures[index].set_result(fn(index))
            return future

        def shutdown(self, **kwargs: object) -> None:
            pass

    monkeypatch.setattr(threadfan._engine, "ThreadPoolExecutor", Pool)
    call = thread_imap if streaming else thread_map
    if fail:
        with pytest.raises(ValueError) as info:
            list(call(abs, range(4), ordered=False, max_pending=4))
        assert info.value.args == (2,)
    else:
        assert list(call(abs, range(4), ordered=False, max_pending=4)) == [2, 1, 0, 3]


def test_counts_are_evaluated_once_before_input() -> None:
    class Count:
        def __init__(self) -> None:
            self.calls = 0

        def __index__(self) -> int:
            self.calls += 1
            assert self.calls == 1
            return 2

    workers, pending = Count(), Count()

    def source() -> Iterator[int]:
        assert workers.calls == pending.calls == 1
        yield from range(4)

    assert thread_map(abs, source(), workers=workers, max_pending=pending) == [0, 1, 2, 3]


@pytest.mark.parametrize("ordered", [False, True])
def test_progress_counts_collected_failures_in_the_calling_thread(ordered: bool) -> None:
    import threading

    caller = threading.get_ident()
    seen: list[tuple[int, int, int]] = []

    def report(done: int, total: int) -> str:
        seen.append((done, total, threading.get_ident()))
        return "ignored"

    with pytest.raises(ThreadMapError):
        thread_map(int, ["1", "bad", "3"], stop_on_error=False, ordered=ordered, on_progress=report)
    assert seen == [(n, 3, caller) for n in (1, 2, 3)]


def test_stream_iterates_at_call_time_but_reads_on_demand() -> None:
    steps: list[str] = []

    class Source:
        def __iter__(self) -> Iterator[int]:
            steps.append("iter")
            return self

        def __next__(self) -> int:
            steps.append("next")
            return 1

    stream = thread_imap(abs, Source(), max_pending=1)
    assert steps == ["iter"]
    assert next(stream) == 1
    assert steps == ["iter", "next"]
    stream.close()


def test_task_messages_are_never_evaluated() -> None:
    class Hostile(Exception):
        def __str__(self) -> str:
            raise KeyboardInterrupt

    error = ThreadMapError({0: Hostile("secret")})
    assert str(error) == "1 task failed; first at index 0: Hostile"


def test_a_callback_error_propagates_unchanged_when_collecting() -> None:
    marker = RuntimeError("callback")

    def report(done: int, total: int) -> None:
        raise marker

    with pytest.raises(RuntimeError) as info:
        thread_map(abs, [1, 2], on_progress=report, stop_on_error=False)
    assert info.value is marker


@pytest.mark.parametrize("flag", ["ordered", "stop_on_error", "copy_context"])
def test_each_flag_is_evaluated_once(flag: str) -> None:
    class Flag:
        calls = 0

        def __bool__(self) -> bool:
            self.calls += 1
            assert self.calls == 1
            return True

    value = Flag()
    options: dict[str, Any] = {flag: value}
    assert thread_map(abs, [1, 2], **options) == [1, 2]
    assert value.calls == 1
