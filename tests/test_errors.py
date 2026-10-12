"""``ThreadMapError``: sorted failures, partial results, message, chaining, pickling."""

from __future__ import annotations

import pickle
import time

import pytest

from threadfan import ThreadMapError, thread_map


def _late_failures(value: int) -> int:
    # Low indices fail last, so completion order differs from index order.
    time.sleep(0.002 * (10 - value))
    if value in (1, 4, 7):
        raise LookupError(f"missing {value}")
    return value * 10


def _collect() -> ThreadMapError:
    with pytest.raises(ThreadMapError) as info:
        thread_map(_late_failures, range(10), workers=10, stop_on_error=False)
    return info.value


def test_errors_are_sorted_by_input_index() -> None:
    assert list(_collect().errors) == [1, 4, 7]


def test_successful_results_are_kept_by_index() -> None:
    results = _collect().results
    assert results == {i: i * 10 for i in range(10) if i not in (1, 4, 7)}
    assert list(results) == sorted(results)


def test_message_names_the_count_and_the_first_failure() -> None:
    assert str(_collect()) == "3 tasks failed; first at index 1: LookupError: missing 1"


def test_single_failure_message_is_singular() -> None:
    error = ThreadMapError({5: ValueError()})
    assert str(error) == "1 task failed; first at index 5: ValueError"


def test_the_first_failure_is_the_cause() -> None:
    error = _collect()
    assert error.__cause__ is error.errors[1]


def test_the_error_survives_pickling() -> None:
    error = _collect()
    clone = pickle.loads(pickle.dumps(error))
    assert isinstance(clone, ThreadMapError)
    assert str(clone) == str(error)
    assert list(clone.errors) == [1, 4, 7]
    assert clone.results == error.results


def test_the_error_can_be_built_from_any_mapping() -> None:
    error = ThreadMapError({3: OSError("b"), 0: OSError("a")}, {1: "x"})
    assert list(error.errors) == [0, 3]
    assert error.results == {1: "x"}
    assert ThreadMapError({}).errors == {}
