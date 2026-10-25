"""Option validation, window bound, context copying, thread names and progress."""

from __future__ import annotations

import contextvars
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

import threadfan._engine
from threadfan import thread_imap, thread_map

REQUEST_ID: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="unset")
# Python 3.14 free-threaded builds start every thread with a copy of its starter's context.
INHERITS = bool(getattr(sys.flags, "thread_inherit_context", 0))


@pytest.mark.parametrize("bad", [True, False, 2.0, "4", b"1"])
@pytest.mark.parametrize("name", ["workers", "max_pending"])
def test_non_int_counts_are_type_errors(name: str, bad: object) -> None:
    with pytest.raises(TypeError, match=f"{name} must be an int"):
        thread_map(lambda v: v, [1], **{name: bad})  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [0, -1, -(10**30)])
@pytest.mark.parametrize("name", ["workers", "max_pending"])
def test_counts_below_one_are_value_errors(name: str, bad: int) -> None:
    with pytest.raises(ValueError, match=f"{name} must be at least 1") as info:
        thread_imap(lambda v: v, [1], **{name: bad})
    assert len(str(info.value)) < 80


@pytest.mark.parametrize("call", [thread_map, thread_imap])
def test_fn_and_on_progress_must_be_callable(call: Any) -> None:
    with pytest.raises(TypeError, match="fn must be callable, got int"):
        call(5, [])
    with pytest.raises(TypeError, match="on_progress must be callable, got str"):
        thread_map(str, [], on_progress="print")  # type: ignore[arg-type]


def test_items_must_be_iterable_when_called() -> None:
    with pytest.raises(TypeError):
        thread_map(str, 5)  # type: ignore[call-overload]
    with pytest.raises(TypeError):
        thread_imap(str, 5)  # type: ignore[call-overload]


def test_options_are_checked_before_items_are_read() -> None:
    class Lazy:
        def __iter__(self) -> Any:
            raise AssertionError("items were read")

    bad: list[dict[str, Any]] = [
        {"workers": 0},
        {"max_pending": "2"},
        {"thread_name_prefix": None},
        {"ordered": Ambiguous()},
        {"stop_on_error": Ambiguous()},
        {"copy_context": Ambiguous()},
    ]
    for options in bad:
        with pytest.raises((TypeError, ValueError)):
            thread_map(lambda v: v, Lazy(), **options)
        with pytest.raises((TypeError, ValueError)):
            thread_imap(lambda v: v, Lazy(), **options)
    with pytest.raises(TypeError):
        thread_map(lambda v: v, Lazy(), on_progress=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        thread_map(lambda v: v, [], workers=0)


class Ambiguous:
    """A flag whose truth cannot be decided, like a numpy array."""

    def __bool__(self) -> bool:
        raise ValueError("ambiguous truth value")


def test_flags_take_their_truth_value_once_when_called() -> None:
    calls: list[int] = []

    def work(value: int) -> int:
        calls.append(value)
        return value

    with pytest.raises(ValueError, match="ambiguous"):
        thread_map(work, range(5), ordered=Ambiguous())  # type: ignore[arg-type]
    assert calls == []
    assert sorted(thread_map(work, range(3), ordered=0, stop_on_error=[])) == [0, 1, 2]  # type: ignore[arg-type]


def test_thread_name_prefix_must_be_a_string() -> None:
    with pytest.raises(TypeError, match="thread_name_prefix must be a str, got NoneType"):
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
    expected = "req-42" if copy or INHERITS else "unset"
    assert seen == [expected] * 4
    assert streamed == [expected] * 4


def test_context_changes_inside_tasks_do_not_leak() -> None:
    def mutate(value: int) -> str:
        before = REQUEST_ID.get()
        REQUEST_ID.set(f"task-{value}")
        return before

    assert thread_map(mutate, range(6), workers=1, copy_context=True) == ["unset"] * 6
    assert REQUEST_ID.get() == "unset"


def test_worker_threads_carry_the_prefix_as_the_standard_library_names_them() -> None:
    names = thread_map(
        lambda _: threading.current_thread().name, range(4), workers=2, thread_name_prefix="fetcher"
    )
    assert {name.rsplit("_", 1)[0] for name in names} == {"fetcher"}
    assert {name.rsplit("_", 1)[1] for name in names} <= {"0", "1"}


def test_an_empty_prefix_keeps_the_standard_library_default_names() -> None:
    names = thread_map(lambda _: threading.current_thread().name, range(2), thread_name_prefix="")
    assert all(name.startswith("ThreadPoolExecutor-") for name in names)


def test_a_str_subclass_prefix_is_used_as_plain_text() -> None:
    class Loud(str):
        def __str__(self) -> str:
            raise AssertionError("formatted through the subclass")

    names = thread_map(lambda _: threading.current_thread().name, [1], thread_name_prefix=Loud("q"))
    assert names == ["q_0"]


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
