"""Option validation, window bound, context copying, thread names and progress."""

from __future__ import annotations

import contextvars
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

import threadfan._engine
from threadfan import thread_imap, thread_map

REQUEST_ID: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="unset")


@pytest.mark.parametrize("bad", [True, False, 2.0, "4"])
@pytest.mark.parametrize("name", ["workers", "max_pending"])
def test_non_int_counts_are_type_errors(name: str, bad: object) -> None:
    with pytest.raises(TypeError, match=name):
        thread_map(lambda v: v, [1], **{name: bad})  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [0, -1])
@pytest.mark.parametrize("name", ["workers", "max_pending"])
def test_counts_below_one_are_value_errors(name: str, bad: int) -> None:
    with pytest.raises(ValueError, match=f"{name} must be at least 1"):
        thread_map(lambda v: v, [1], **{name: bad})  # type: ignore[arg-type]


def test_options_are_checked_before_items_are_read() -> None:
    def never() -> list[int]:
        raise AssertionError("items were read")

    class Lazy:
        def __iter__(self) -> object:
            return iter(never())

    with pytest.raises(ValueError):
        thread_map(lambda v: v, Lazy(), workers=0)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        thread_map(lambda v: v, [], workers=0)


def test_thread_name_prefix_must_be_a_string() -> None:
    with pytest.raises(TypeError, match="thread_name_prefix"):
        thread_map(lambda v: v, [1], thread_name_prefix=None)  # type: ignore[arg-type]


def test_max_pending_caps_concurrency_below_the_pool() -> None:
    active = peak = 0
    lock = threading.Lock()

    def track(value: int) -> int:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.005)
        with lock:
            active -= 1
        return value

    assert thread_map(track, range(30), workers=8, max_pending=2) == list(range(30))
    assert peak <= 2


@pytest.mark.parametrize("copy", [True, False])
def test_copy_context_controls_context_variables(copy: bool) -> None:
    token = REQUEST_ID.set("req-42")
    try:
        seen = thread_map(lambda _: REQUEST_ID.get(), range(4), workers=2, copy_context=copy)
        streamed = list(thread_imap(lambda _: REQUEST_ID.get(), range(4), copy_context=copy))
    finally:
        REQUEST_ID.reset(token)
    expected = "req-42" if copy else "unset"
    assert seen == [expected] * 4
    assert streamed == [expected] * 4


def test_context_changes_inside_tasks_do_not_leak() -> None:
    def mutate(value: int) -> str:
        REQUEST_ID.set(f"task-{value}")
        return REQUEST_ID.get()

    assert thread_map(mutate, range(3), copy_context=True) == ["task-0", "task-1", "task-2"]
    assert REQUEST_ID.get() == "unset"


def test_worker_threads_carry_the_prefix() -> None:
    names = thread_map(
        lambda _: threading.current_thread().name, range(4), workers=2, thread_name_prefix="fetcher"
    )
    assert all(name.startswith("fetcher_") for name in names)


def test_progress_runs_in_the_caller_thread_strictly_increasing() -> None:
    calls: list[tuple[int, int, str]] = []

    def progress(done: int, total: int) -> None:
        calls.append((done, total, threading.current_thread().name))

    def maybe_fail(value: int) -> int:
        if value == 3:
            raise ValueError
        return value

    caller = threading.current_thread().name
    with pytest.raises(Exception):  # noqa: B017
        thread_map(maybe_fail, range(8), workers=4, on_progress=progress, stop_on_error=False)
    assert calls == [(done, 8, caller) for done in range(1, 9)]


@pytest.mark.parametrize(
    ("workers", "count", "expected"), [(None, 3, 3), (None, 100, 32), (8, 5, 5), (2, 9, 2)]
)
def test_pool_size_is_capped_by_items_and_default(
    monkeypatch: pytest.MonkeyPatch, workers: int | None, count: int, expected: int
) -> None:
    sizes: list[int | None] = []

    class Recording(ThreadPoolExecutor):
        def __init__(self, max_workers: int | None = None, **kwargs: Any) -> None:
            sizes.append(max_workers)
            super().__init__(max_workers, **kwargs)

    monkeypatch.setattr(threadfan._engine, "ThreadPoolExecutor", Recording)
    assert thread_map(lambda v: v, range(count), workers=workers) == list(range(count))
    assert sizes == [expected]
