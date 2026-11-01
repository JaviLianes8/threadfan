"""Aggregate indices have builtin numeric semantics and independent storage."""

from __future__ import annotations

from typing import Any

import pytest

from threadfan import ThreadMapError


class HostileIndex(int):
    def __lt__(self, other: int) -> bool:
        raise RuntimeError("comparison hook executed")

    def __gt__(self, other: int) -> bool:
        raise RuntimeError("comparison hook executed")

    def __int__(self) -> int:
        raise RuntimeError("conversion hook executed")

    def __index__(self) -> int:
        raise RuntimeError("index hook executed")


class ReverseIndex(int):
    def __lt__(self, other: int) -> bool:
        return int.__gt__(self, other)


class LeakingIndex(int):
    def bit_length(self) -> Any:
        return "private-token-" * 10_000


@pytest.mark.parametrize("mapping", ["errors", "results"])
@pytest.mark.parametrize("index_type", [HostileIndex, ReverseIndex, LeakingIndex])
def test_integer_subclasses_use_builtin_order_and_storage(
    mapping: str, index_type: type[int]
) -> None:
    given = {index_type(index): ValueError(index) for index in (2, -1, 0)}
    error = ThreadMapError(given) if mapping == "errors" else ThreadMapError({}, given)
    stored = getattr(error, mapping)
    assert list(stored) == [-1, 0, 2]
    assert all(type(index) is int for index in stored)
    assert all(stored[index] is value for index, value in given.items())


@pytest.mark.parametrize("sign", [-1, 1])
def test_integer_subclass_cannot_inject_a_bit_length(sign: int) -> None:
    error = ThreadMapError({LeakingIndex(sign * 10**20): ValueError()})
    assert str(error) == "1 task failed; first at index an integer of 67 bits: ValueError"


@pytest.mark.parametrize("mapping", ["errors", "results"])
def test_sorted_dictionary_inputs_are_independent_copies(mapping: str) -> None:
    given = {0: ValueError("zero"), 2: ValueError("two")}
    expected = given.copy()
    error = ThreadMapError(given) if mapping == "errors" else ThreadMapError({}, given)
    stored = getattr(error, mapping)
    assert stored is not given
    assert stored == expected
    stored[1] = ValueError("one")
    assert given == expected
    given.clear()
    assert stored[0] is expected[0] and stored[2] is expected[2]
    assert list(stored) == [0, 2, 1]


@pytest.mark.parametrize("mapping", ["errors", "results"])
def test_negative_indices_sort_with_zero_and_positive_indices(mapping: str) -> None:
    given = {2: ValueError(), -1: ValueError(), 0: ValueError(), -3: ValueError()}
    error = ThreadMapError(given) if mapping == "errors" else ThreadMapError({}, given)
    stored = getattr(error, mapping)
    assert list(stored) == [-3, -1, 0, 2]
    assert stored == given
    if mapping == "errors":
        assert str(error) == "4 tasks failed; first at index -3: ValueError"


@pytest.mark.parametrize("mapping", ["errors", "results"])
@pytest.mark.parametrize("index", [False, True])
def test_boolean_indices_are_rejected_in_both_mappings(mapping: str, index: bool) -> None:
    given: dict[int, Exception] = {index: ValueError()}
    with pytest.raises(TypeError, match=f"^{mapping} keys must be int indices, got bool$"):
        if mapping == "errors":
            ThreadMapError(given)
        else:
            ThreadMapError({}, given)
