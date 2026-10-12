"""Regression tests for behaviour that once differed from the builtin ``map``."""

from __future__ import annotations

import contextvars
import pickle
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest

from threadfan import ThreadMapError, thread_imap, thread_map

TAG: contextvars.ContextVar[str] = contextvars.ContextVar("tag", default="unset")


def _broken_source() -> Iterator[int]:
    yield from range(5)
    raise OSError("source broke")


@pytest.mark.parametrize("ordered", [True, False])
def test_items_read_before_a_failing_source_are_still_yielded(ordered: bool) -> None:
    seen: list[int] = []
    with pytest.raises(OSError, match="source broke"):
        seen.extend(thread_imap(lambda v: v, _broken_source(), workers=2, ordered=ordered))
    assert sorted(seen) == [0, 1, 2, 3, 4]


def test_ordered_stream_yields_everything_before_the_first_failing_index() -> None:
    def work(value: int) -> int:
        if value == 0:
            time.sleep(0.2)
        if value == 1:
            raise ValueError("one")
        return value

    seen: list[int] = []
    with pytest.raises(ValueError, match="one"):
        seen.extend(thread_imap(work, range(4), workers=4))
    assert seen == [0]


def test_ordered_stream_raises_the_lowest_failing_index() -> None:
    def work(value: int) -> int:
        time.sleep(0.01 * (5 - value))
        if value in (2, 4):
            raise ValueError(f"bad {value}")
        return value

    seen: list[int] = []
    with pytest.raises(ValueError, match="bad 2"):
        seen.extend(thread_imap(work, range(6), workers=6))
    assert seen == [0, 1]


def test_stop_iteration_from_fn_is_reraised_unchanged() -> None:
    marker = StopIteration("from fn")

    def work(value: int) -> int:
        if value == 2:
            raise marker
        return value

    with pytest.raises(StopIteration) as info:
        thread_map(work, range(5), workers=2)
    assert info.value is marker


def test_stop_iteration_from_progress_is_reraised_unchanged() -> None:
    def progress(done: int, total: int) -> None:
        raise StopIteration("from progress")

    with pytest.raises(StopIteration, match="from progress"):
        thread_map(lambda v: v, range(3), on_progress=progress)


class Wrapped(ThreadMapError):
    """A subclass whose ``__init__`` takes other arguments."""

    def __init__(self, label: str, errors: dict[int, Exception]) -> None:
        super().__init__(errors)
        self.label = label
        self.attempt = 0


def test_subclass_pickling_keeps_type_failures_and_state() -> None:
    error = Wrapped("batch-1", {2: ValueError("x")})
    error.attempt = 3
    clone = pickle.loads(pickle.dumps(error))
    assert type(clone) is Wrapped
    assert list(clone.errors) == [2]
    assert clone.label == "batch-1"
    assert clone.attempt == 3
    assert str(clone) == str(error)


def test_stream_context_is_captured_when_called() -> None:
    token = TAG.set("at-call")
    stream = thread_imap(lambda _: TAG.get(), range(3), copy_context=True)
    TAG.reset(token)
    assert list(stream) == ["at-call"] * 3


class Count:
    """An integer-like value, as numpy integers are."""

    def __init__(self, value: int) -> None:
        self.value = value

    def __index__(self) -> int:
        return self.value


def test_integer_like_counts_are_accepted() -> None:
    options: dict[str, Any] = {"workers": Count(2), "max_pending": Count(3)}
    assert thread_map(lambda v: v, range(5), **options) == [0, 1, 2, 3, 4]
    with pytest.raises(ValueError, match="workers must be at least 1"):
        thread_map(lambda v: v, [1], workers=Count(0))  # type: ignore[arg-type]


@pytest.mark.filterwarnings("error::pytest.PytestUnraisableExceptionWarning")
def test_a_stream_closed_inside_its_own_worker_does_not_join_itself() -> None:
    suspended = threading.Event()
    finished = threading.Event()
    problems: list[BaseException] = []
    holder: dict[str, Any] = {}

    def work(value: int) -> int:
        if value == 3:
            suspended.wait(5)
            try:
                holder["stream"].close()
            except BaseException as error:
                problems.append(error)
            finished.set()
        return value

    holder["stream"] = thread_imap(work, range(8), workers=2)
    assert next(holder["stream"]) == 0
    suspended.set()
    assert finished.wait(5)
    assert problems == []
