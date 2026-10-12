"""Every early exit cancels queued items and returns once running tasks finish."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator

import pytest

from threadfan import thread_map


class Recorder:
    """A task that counts its calls and fails on one chosen item."""

    def __init__(self, fail_on: int, error: BaseException) -> None:
        self.calls = 0
        self.fail_on = fail_on
        self.error = error
        self.lock = threading.Lock()

    def __call__(self, value: int) -> int:
        with self.lock:
            self.calls += 1
        if value == self.fail_on:
            raise self.error
        return value


def test_first_failure_stops_submitting_beyond_the_window() -> None:
    task = Recorder(0, RuntimeError("stop"))
    with pytest.raises(RuntimeError, match="stop"):
        thread_map(task, range(1_000), workers=1)
    assert task.calls <= 2


@pytest.mark.parametrize("error", [KeyboardInterrupt(), SystemExit(3)])
def test_base_exceptions_from_tasks_propagate_even_when_collecting(error: BaseException) -> None:
    task = Recorder(0, error)
    with pytest.raises(type(error)):
        thread_map(task, range(1_000), workers=2, stop_on_error=False)
    assert task.calls <= 4


def test_a_failing_progress_callback_cancels_the_rest() -> None:
    task = Recorder(-1, RuntimeError())

    def progress(done: int, total: int) -> None:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        thread_map(task, range(1_000), workers=2, on_progress=progress)
    assert task.calls <= 4


def test_a_failing_source_cancels_the_rest() -> None:
    from threadfan import thread_imap

    task = Recorder(-1, RuntimeError())

    def source() -> Iterator[int]:
        yield from range(5)
        raise OSError("source broke")

    with pytest.raises(OSError, match="source broke"):
        list(thread_imap(task, source(), workers=2))
    assert task.calls <= 5


def test_the_pool_threads_are_gone_after_any_exit() -> None:
    def fail(value: int) -> int:
        raise ValueError(value)

    runs: list[Callable[[], object]] = [
        lambda: thread_map(fail, range(20), thread_name_prefix="gone-a"),
        lambda: thread_map(fail, range(20), stop_on_error=False, thread_name_prefix="gone-a"),
    ]
    for run in runs:
        with pytest.raises(Exception):  # noqa: B017
            run()
        assert [t for t in threading.enumerate() if t.name.startswith("gone-a")] == []


def test_items_already_queued_inside_the_window_are_cancelled() -> None:
    started = threading.Event()
    calls: list[int] = []

    def work(value: int) -> int:
        calls.append(value)
        if value == 0:
            started.set()
            raise RuntimeError("first")
        return value

    with pytest.raises(RuntimeError, match="first"):
        thread_map(work, range(10), workers=1, max_pending=10)
    assert started.is_set()
    # The single worker may pick up one more item before the caller wakes up.
    assert len(calls) <= 2
