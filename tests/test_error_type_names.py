"""Type descriptions bypass metaclass hooks and bound the underlying class name."""

from __future__ import annotations

from typing import Any, cast

import pytest

from threadfan import ThreadMapError, thread_imap, thread_map


class Name(str):
    def __format__(self, spec: str) -> str:
        return "private-token-" * 10_000

    def __str__(self) -> str:
        return "private-token-" * 10_000

    def __len__(self) -> int:
        raise RuntimeError("length hook executed")


@pytest.fixture(params=["lookup", "format", "descriptor", "stored", "long"])
def failure_type(request: pytest.FixtureRequest) -> tuple[type[Exception], str]:
    mode = request.param

    class Meta(type):
        def __getattribute__(cls, name: str) -> Any:
            if name == "__name__":
                if mode == "lookup":
                    raise RuntimeError("type name hook executed")
                if mode == "format":
                    return Name("ShortName")
            return super().__getattribute__(name)

        @property
        def __name__(cls) -> str:  # type: ignore[override]
            # Even type.__getattribute__ would invoke a metaclass property.
            if mode == "descriptor":
                return Name("ShortName")
            return cast(str, type.__dict__["__name__"].__get__(cls))

    class TaskFailure(Exception, metaclass=Meta):
        pass

    if mode in ("stored", "long"):
        name = Name("E" * 10_000 if mode == "long" else "TaskFailure")
        type.__dict__["__name__"].__set__(TaskFailure, name)
    return TaskFailure, "E" * 57 + "..." if mode == "long" else "TaskFailure"


@pytest.mark.parametrize("streaming", [False, True])
def test_collecting_uses_a_bounded_builtin_type_name(
    failure_type: tuple[type[Exception], str], streaming: bool
) -> None:
    cls, expected_name = failure_type
    failure = cls("private task data")

    def task(value: int) -> int:
        raise failure

    call = thread_imap if streaming else thread_map
    with pytest.raises(ThreadMapError) as info:
        list(call(task, [0], stop_on_error=False))
    assert info.value.errors == {0: failure}
    assert info.value.__cause__ is failure
    assert str(info.value) == f"1 task failed; first at index 0: {expected_name}"
    assert len(str(info.value)) < 100


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("option", ["workers", "max_pending", "thread_name_prefix", "fn"])
def test_invalid_options_keep_type_errors_without_type_name_hooks(
    failure_type: tuple[type[Exception], str], streaming: bool, option: str
) -> None:
    cls, expected_name = failure_type
    call = thread_imap if streaming else thread_map
    options: dict[str, Any] = {"fn": abs, "items": [], option: cls()}
    with pytest.raises(TypeError) as info:
        call(**options)
    assert str(info.value).endswith(f", got {expected_name}")
    assert len(str(info.value)) < 120
