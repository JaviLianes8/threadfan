"""``ThreadMapError``: sorted failures, partial results, bounded message, chaining, pickling."""

from __future__ import annotations

import copy
import pickle
import sys
import time
from collections.abc import Callable
from types import MappingProxyType

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


def test_single_failure_message_is_singular_and_empty_messages_show_the_type() -> None:
    assert str(ThreadMapError({5: ValueError()})) == "1 task failed; first at index 5: ValueError"
    assert str(ThreadMapError({})) == "0 tasks failed"


def test_the_first_failure_is_the_cause() -> None:
    error = _collect()
    assert error.__cause__ is error.errors[1]


def test_the_error_can_be_built_from_any_mapping_and_copies_it() -> None:
    given = {3: OSError("b"), 0: OSError("a")}
    error = ThreadMapError(MappingProxyType(given), MappingProxyType({1: "x"}))
    assert list(error.errors) == [0, 3]
    assert error.results == {1: "x"}
    given.clear()
    assert len(error.errors) == 2
    assert ThreadMapError({}).errors == {} and ThreadMapError({}).results == {}


@pytest.mark.parametrize(
    "build",
    [
        lambda: ThreadMapError(None),  # type: ignore[arg-type]
        lambda: ThreadMapError([(1, ValueError())]),  # type: ignore[arg-type]
        lambda: ThreadMapError({"1": ValueError()}),  # type: ignore[dict-item]
        lambda: ThreadMapError({True: ValueError()}),
        lambda: ThreadMapError({1.0: ValueError()}),  # type: ignore[dict-item]
        lambda: ThreadMapError({1: "boom"}),  # type: ignore[dict-item]
        lambda: ThreadMapError({1: KeyboardInterrupt()}),  # type: ignore[dict-item]
        lambda: ThreadMapError({}, [1]),  # type: ignore[arg-type]
        lambda: ThreadMapError({}, {"a": 1}),  # type: ignore[dict-item]
    ],
)
def test_wrong_contents_raise_type_error(build: Callable[[], object]) -> None:
    with pytest.raises(TypeError):
        build()


def test_the_message_is_cut_to_two_hundred_characters_of_detail() -> None:
    error = ThreadMapError({0: ValueError("x" * 1_000_000)})
    detail = str(error).split(": ", 1)[1]
    assert len(detail) == 200 and detail.endswith("...")
    assert detail.startswith("ValueError: xxx")
    exact = ThreadMapError({0: ValueError("y" * (200 - len("ValueError: ")))})
    assert not str(exact).endswith("...")


def test_an_unreadable_message_does_not_replace_the_error() -> None:
    class Broken(Exception):
        def __str__(self) -> str:
            raise RuntimeError("no")

    def fail(value: int) -> int:
        raise Broken

    with pytest.raises(ThreadMapError) as info:
        thread_map(fail, [1, 2], stop_on_error=False)
    assert str(info.value) == "2 tasks failed; first at index 0: Broken: <message could not be read>"
    assert info.value.results == {} and list(info.value.errors) == [0, 1]


def test_a_huge_index_is_described_by_its_size() -> None:
    error = ThreadMapError({10**5000: ValueError("x")})
    assert "an integer of 16610 bits" in str(error)
    assert len(str(error)) < 120


def test_a_huge_type_name_is_cut() -> None:
    error_type = type("E" * 10_000, (Exception,), {})
    assert len(str(ThreadMapError({0: error_type("m")}))) < 300


@pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
def test_the_error_survives_pickling_with_every_protocol(protocol: int) -> None:
    error = _collect()
    clone = pickle.loads(pickle.dumps(error, protocol))
    assert type(clone) is ThreadMapError
    assert str(clone) == str(error) and clone.args == error.args
    assert list(clone.errors) == [1, 4, 7]
    assert [str(e) for e in clone.errors.values()] == [str(e) for e in error.errors.values()]
    assert clone.results == error.results


def test_copies_keep_everything() -> None:
    error = ThreadMapError({2: ValueError("x")}, {0: [1]})
    for clone in (copy.copy(error), copy.deepcopy(error)):
        assert type(clone) is ThreadMapError and str(clone) == str(error)
        assert list(clone.errors) == [2] and clone.results == {0: [1]}
    assert copy.deepcopy(error).results[0] is not error.results[0]


@pytest.mark.skipif(sys.version_info < (3, 11), reason="add_note is new in Python 3.11")
def test_notes_survive_pickling() -> None:
    error = ThreadMapError({0: ValueError("x")})
    error.add_note("batch 7")  # type: ignore[attr-defined,unused-ignore]
    clone = pickle.loads(pickle.dumps(error))
    assert clone.__notes__ == ["batch 7"]
