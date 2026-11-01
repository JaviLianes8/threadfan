"""Hand-written contracts for validation without instance class lookup."""

from __future__ import annotations

from collections.abc import ItemsView, Iterator, Mapping
from typing import Any

import pytest

from threadfan import ThreadMapError, thread_imap, thread_map


class ClassHook:
    lookups = 0
    pretend: type[object] | None = None

    @property  # type: ignore[misc]
    def __class__(self) -> type[object]:  # type: ignore[override]
        self.lookups += 1
        if self.pretend is None:
            raise RuntimeError("class property executed")
        return self.pretend


class IntegerCount(ClassHook, int):
    pass


class IndexCount(ClassHook):
    index_calls = 0

    def __index__(self) -> int:
        self.index_calls += 1
        return 1


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("option", ["workers", "max_pending"])
@pytest.mark.parametrize("integer", [False, True])
@pytest.mark.parametrize("pretend", [None, bool])
def test_valid_counts_ignore_class_hooks(
    streaming: bool, option: str, integer: bool, pretend: type[object] | None
) -> None:
    count = IntegerCount(1) if integer else IndexCount()
    count.pretend = pretend
    options: dict[str, Any] = {option: count}
    call = thread_imap if streaming else thread_map
    assert list(call(abs, [-1, -2], **options)) == [1, 2]
    assert count.lookups == 0
    if type(count) is IndexCount:
        assert count.index_calls == 1


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("option", ["workers", "max_pending", "thread_name_prefix"])
@pytest.mark.parametrize("spoof", [False, True])
def test_invalid_options_ignore_class_hooks_before_reading_input(
    streaming: bool, option: str, spoof: bool
) -> None:
    class Source:
        def __iter__(self) -> Iterator[int]:
            raise AssertionError("input was read before validation")

    expected = "a str" if option == "thread_name_prefix" else "an int"
    invalid = ClassHook()
    invalid.pretend = (str if option == "thread_name_prefix" else bool) if spoof else None
    options: dict[str, Any] = {option: invalid}
    call = thread_imap if streaming else thread_map
    with pytest.raises(TypeError) as info:
        call(abs, Source(), **options)
    assert type(info.value) is TypeError
    assert str(info.value) == f"{option} must be {expected}, got ClassHook"
    assert invalid.lookups == 0


@pytest.mark.parametrize("field", ["errors", "results", "failure"])
@pytest.mark.parametrize("spoof", [False, True])
def test_invalid_aggregate_arguments_ignore_class_hooks(field: str, spoof: bool) -> None:
    invalid: Any = ClassHook()
    invalid.pretend = (Exception if field == "failure" else Mapping) if spoof else None
    with pytest.raises(TypeError) as info:
        if field == "errors":
            ThreadMapError(invalid)
        elif field == "results":
            ThreadMapError({}, invalid)
        else:
            ThreadMapError({0: invalid})
    expected = (
        "errors values must be exceptions" if field == "failure" else f"{field} must be a mapping"
    )
    assert type(info.value) is TypeError
    assert str(info.value) == f"{expected}, got ClassHook"
    assert invalid.lookups == 0


@pytest.mark.parametrize("field", ["errors", "results"])
def test_registered_mappings_ignore_class_hooks(field: str) -> None:
    failure = ValueError("task")

    @Mapping.register
    class RegisteredMapping(ClassHook):
        def items(self) -> ItemsView[int, Exception]:
            return {2: failure}.items()

    given: Any = RegisteredMapping()
    error = ThreadMapError(given) if field == "errors" else ThreadMapError({}, given)
    stored = getattr(error, field)
    assert list(stored) == [2]
    assert stored[2] is failure
    assert given.lookups == 0
