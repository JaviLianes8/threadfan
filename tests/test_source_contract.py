"""Contracts for source failures, early close, and retained exception identities."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from threadfan import ThreadMapError, thread_imap, thread_map


@pytest.mark.parametrize("ordered", [True, False])
def test_source_failure_takes_precedence_over_collected_task_errors(ordered: bool) -> None:
    marker = OSError("source")

    def source() -> Iterator[str]:
        yield from ["1", "bad", "3"]
        raise marker

    values: list[int] = []
    with pytest.raises(OSError) as info:
        values.extend(thread_imap(int, source(), stop_on_error=False, ordered=ordered))
    assert info.value is marker
    assert sorted(values) == [1, 3]


def test_eager_source_failure_starts_no_tasks() -> None:
    calls: list[int] = []
    marker = OSError("source")

    def source() -> Iterator[int]:
        yield 1
        raise marker

    with pytest.raises(OSError) as info:
        thread_map(calls.append, source())
    assert info.value is marker
    assert calls == []


def test_a_stopping_task_error_takes_precedence_over_a_source_error() -> None:
    task = ValueError("task")

    def source() -> Iterator[int]:
        yield 1
        raise OSError("source")

    def work(value: int) -> int:
        raise task

    with pytest.raises(ValueError) as info:
        list(thread_imap(work, source(), max_pending=4))
    assert info.value is task


@pytest.mark.parametrize("ordered", [True, False])
def test_stream_failure_keeps_identity_and_lowest_cause(ordered: bool) -> None:
    failures = {1: ValueError("one"), 3: OSError("three")}

    def work(index: int) -> int:
        if index in failures:
            raise failures[index]
        return index

    values: list[int] = []
    with pytest.raises(ThreadMapError) as info:
        values.extend(thread_imap(work, range(5), stop_on_error=False, ordered=ordered))
    assert sorted(values) == [0, 2, 4]
    assert info.value.errors == failures
    assert info.value.__cause__ is failures[1]
    assert info.value.results == {}


def test_stopping_stream_wraps_stop_iteration_with_original_cause() -> None:
    marker = StopIteration("task")

    def work(index: int) -> int:
        raise marker

    with pytest.raises(RuntimeError) as info:
        list(thread_imap(work, [1]))
    assert info.value.__cause__ is marker


def test_collecting_stream_keeps_stop_iteration_as_a_task_failure() -> None:
    marker = StopIteration("task")

    def work(index: int) -> int:
        raise marker

    with pytest.raises(ThreadMapError) as info:
        list(thread_imap(work, [1], stop_on_error=False))
    assert info.value.errors == {0: marker}


def test_close_before_first_next_does_not_read_source() -> None:
    def source() -> Iterator[int]:
        raise AssertionError("read")
        yield 1

    stream = thread_imap(abs, source())
    stream.close()
    assert list(stream) == []
