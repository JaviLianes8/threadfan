"""``thread_imap``: laziness, backpressure, ordering and clean shutdown."""

from __future__ import annotations

import itertools
import threading
import time
from collections.abc import Iterator

import pytest

from threadfan import ThreadMapError, thread_imap


class CountingSource:
    """An endless source that records how many items were read from it."""

    def __init__(self) -> None:
        self.read = 0

    def __iter__(self) -> Iterator[int]:
        for value in itertools.count():
            self.read += 1
            yield value


def _threads(prefix: str) -> list[threading.Thread]:
    return [t for t in threading.enumerate() if t.name.startswith(prefix)]


def test_nothing_is_read_before_the_first_next() -> None:
    source = CountingSource()
    stream = thread_imap(lambda value: value, source, workers=2)
    assert source.read == 0
    assert next(stream) == 0
    stream.close()


@pytest.mark.parametrize("ordered", [True, False])
def test_endless_source_is_read_only_ahead_by_the_window(ordered: bool) -> None:
    source = CountingSource()
    stream = thread_imap(lambda value: value, source, workers=2, max_pending=3, ordered=ordered)
    for consumed in range(1, 51):
        next(stream)
        assert source.read - consumed <= 3
    stream.close()


def test_ordered_stream_waits_for_the_head_without_reading_ahead() -> None:
    release = threading.Event()
    source = CountingSource()

    def work(value: int) -> int:
        if value == 0:
            release.wait(5)
        return value

    stream = thread_imap(work, source, workers=4, max_pending=4)
    timer = threading.Timer(0.1, release.set)
    timer.start()
    assert [next(stream) for _ in range(6)] == [0, 1, 2, 3, 4, 5]
    assert source.read - 6 <= 4
    stream.close()
    timer.join()


def test_unordered_stream_yields_fast_items_before_a_slow_head() -> None:
    release = threading.Event()

    def work(value: int) -> int:
        if value == 0:
            release.wait(5)
        return value

    stream = thread_imap(work, range(4), workers=4, ordered=False)
    first = [next(stream) for _ in range(3)]
    release.set()
    assert sorted(first) == [1, 2, 3]
    assert list(stream) == [0]


def test_closing_the_stream_cancels_queued_work_and_joins_threads() -> None:
    calls = 0
    lock = threading.Lock()

    def work(value: int) -> int:
        nonlocal calls
        with lock:
            calls += 1
        time.sleep(0.001)
        return value

    stream = thread_imap(work, range(10_000), workers=3, thread_name_prefix="imap-close")
    assert next(stream) == 0
    stream.close()
    assert calls <= 1 + 6
    assert _threads("imap-close") == []


def test_breaking_out_of_a_loop_releases_the_pool() -> None:
    def consume() -> list[int]:
        taken: list[int] = []
        for value in thread_imap(lambda v: v, itertools.count(), thread_name_prefix="imap-break"):
            taken.append(value)
            if len(taken) == 5:
                break
        return taken

    assert consume() == [0, 1, 2, 3, 4]
    assert _threads("imap-break") == []


def test_failures_are_skipped_then_aggregated_at_the_end() -> None:
    def work(value: int) -> int:
        if value % 3 == 0:
            raise ValueError(value)
        return value

    seen: list[int] = []
    with pytest.raises(ThreadMapError) as info:
        seen.extend(thread_imap(work, range(10), workers=3, stop_on_error=False))
    assert seen == [1, 2, 4, 5, 7, 8]
    assert list(info.value.errors) == [0, 3, 6, 9]
    assert info.value.results == {}


def test_stop_on_error_reraises_and_stops_reading_the_source() -> None:
    source = CountingSource()

    def work(value: int) -> int:
        if value == 2:
            raise KeyError("two")
        return value

    with pytest.raises(KeyError):
        list(thread_imap(work, source, workers=2, max_pending=2))
    assert source.read <= 4


def test_options_are_validated_when_called_not_when_iterated() -> None:
    with pytest.raises(ValueError, match="workers"):
        thread_imap(lambda v: v, [1], workers=0)
    with pytest.raises(ValueError, match="max_pending"):
        thread_imap(lambda v: v, [1], max_pending=0)


def test_empty_source_yields_nothing() -> None:
    assert list(thread_imap(lambda v: v, [])) == []
