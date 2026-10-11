import threading
import time

import pytest

from threadfan import ThreadMapError, thread_map


def test_ordered_output_matches_input_order() -> None:
    def slow_double(value: int) -> int:
        time.sleep(0.02 if value % 2 == 0 else 0.0)
        return value * 2

    items = list(range(10))
    assert thread_map(slow_double, items, workers=4) == [value * 2 for value in items]


def test_unordered_returns_every_result() -> None:
    items = list(range(20))
    result = thread_map(lambda value: value * value, items, workers=4, ordered=False)
    assert sorted(result) == sorted(value * value for value in items)


def test_empty_input_returns_empty_list() -> None:
    assert thread_map(lambda value: value, [], workers=4) == []


def test_stop_on_error_reraises_the_original_exception() -> None:
    def boom(value: int) -> int:
        if value == 3:
            raise ValueError("bad value")
        return value

    with pytest.raises(ValueError, match="bad value"):
        thread_map(boom, range(10), workers=2, stop_on_error=True)


def test_without_stop_on_error_runs_all_and_aggregates_failures() -> None:
    attempted: set[int] = set()
    lock = threading.Lock()

    def sometimes_fail(value: int) -> int:
        with lock:
            attempted.add(value)
        if value % 2 == 0:
            raise RuntimeError(f"even {value}")
        return value

    with pytest.raises(ThreadMapError) as info:
        thread_map(sometimes_fail, range(6), workers=3, stop_on_error=False)

    assert attempted == set(range(6))
    assert set(info.value.errors) == {0, 2, 4}
    assert all(isinstance(error, RuntimeError) for error in info.value.errors.values())


def test_worker_count_is_bounded() -> None:
    active = 0
    peak = 0
    lock = threading.Lock()

    def track(value: int) -> int:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.02)
        with lock:
            active -= 1
        return value

    thread_map(track, range(12), workers=3)
    assert peak <= 3


def test_invalid_worker_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        thread_map(lambda value: value, [1, 2, 3], workers=0)


def test_progress_callback_fires_once_per_item() -> None:
    seen: list[tuple[int, int]] = []
    lock = threading.Lock()

    def record(done: int, total: int) -> None:
        with lock:
            seen.append((done, total))

    thread_map(lambda value: value, range(5), workers=2, on_progress=record)
    assert len(seen) == 5
    assert {total for _, total in seen} == {5}
    assert {done for done, _ in seen} == {1, 2, 3, 4, 5}


def test_generic_typing_maps_items_to_results() -> None:
    result = thread_map(str, [1, 2, 3], workers=2)
    assert result == ["1", "2", "3"]
    assert all(isinstance(item, str) for item in result)
