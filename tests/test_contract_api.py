"""The promise of every public name: signature, type hints, docs, module and pickling."""

from __future__ import annotations

import doctest
import inspect
import pickle
import typing
from typing import Protocol

import pytest

import threadfan
import threadfan._errors
import threadfan._map
import threadfan._progress
from threadfan import ProgressCallback, ThreadMapError, thread_imap, thread_map

OPTIONS = "*, workers: 'int | None' = None, ordered: 'bool' = True, stop_on_error: 'bool' = True, "
TAIL = (
    "max_pending: 'int | None' = None, copy_context: 'bool' = False, "
    "thread_name_prefix: 'str' = 'threadfan')"
)
SIGNATURES = {
    "thread_map": "(fn: 'Callable[[T], R]', items: 'Iterable[T]', "
    + OPTIONS
    + "on_progress: 'ProgressCallback | None' = None, "
    + TAIL
    + " -> 'list[R]'",
    "thread_imap": "(fn: 'Callable[[T], R]', items: 'Iterable[T]', "
    + OPTIONS
    + TAIL
    + " -> 'Generator[R, None, None]'",
}


@pytest.mark.parametrize("name", sorted(SIGNATURES))
def test_function_signatures_are_pinned(name: str) -> None:
    assert str(inspect.signature(getattr(threadfan, name))) == SIGNATURES[name]


def test_error_and_callback_signatures_are_pinned() -> None:
    assert str(inspect.signature(ThreadMapError.__init__)) == (
        "(self, errors: 'Mapping[int, Exception]', "
        "results: 'Mapping[int, Any] | None' = None) -> 'None'"
    )
    assert str(inspect.signature(ProgressCallback.__call__)) == (
        "(self, completed: 'int', total: 'int', /) -> 'object'"
    )
    assert ThreadMapError.__mro__[1:] == (Exception, BaseException, object)
    assert Protocol in ProgressCallback.__mro__


def test_type_hints_resolve_at_run_time() -> None:
    for name in threadfan.__all__:
        typing.get_type_hints(getattr(threadfan, name))
    hints = typing.get_type_hints(thread_map)
    assert set(typing.get_args(hints["on_progress"])) == {ProgressCallback, type(None)}
    assert set(typing.get_args(hints["workers"])) == {int, type(None)}
    assert typing.get_args(typing.get_type_hints(thread_imap)["return"])[1:] == (None, None)
    assert set(typing.get_type_hints(ThreadMapError.__init__)) == {"errors", "results", "return"}
    assert typing.get_type_hints(ProgressCallback.__call__)["return"] is object


def test_every_public_name_is_documented_with_an_example() -> None:
    for name in threadfan.__all__:
        doc = inspect.getdoc(getattr(threadfan, name)) or ""
        assert ">>> " in doc, name


def test_every_example_is_collected_once_and_passes() -> None:
    finder, found = doctest.DocTestFinder(), []
    for module in (threadfan, threadfan._map, threadfan._errors, threadfan._progress):
        found += [test for test in finder.find(module) if test.examples]
    # Each public docstring is found exactly once, wherever doctest attributes it.
    assert sorted(test.name.rsplit(".", 1)[1] for test in found) == sorted(threadfan.__all__)
    runner = doctest.DocTestRunner(optionflags=doctest.ELLIPSIS)
    for test in found:
        runner.run(test)
    assert runner.summarize(verbose=False).failed == 0


def test_public_names_live_at_the_package_top() -> None:
    for name in threadfan.__all__:
        assert getattr(threadfan, name).__module__ == "threadfan", name
    assert "threadfan.ThreadMapError" in repr(ThreadMapError)
    assert "threadfan.ProgressCallback" in repr(ProgressCallback)


@pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
def test_pickles_name_only_public_paths(protocol: int) -> None:
    for value in (thread_map, thread_imap, ThreadMapError, ProgressCallback):
        data = pickle.dumps(value, protocol)
        assert pickle.loads(data) is value
        assert b"threadfan._" not in data
    data = pickle.dumps(ThreadMapError({1: ValueError("x")}, {0: "a"}), protocol)
    assert b"threadfan._" not in data and b"_rebuild" not in data


def test_the_package_keeps_no_helper_names_from_its_setup() -> None:
    assert "_public" not in vars(threadfan)
    assert "annotations" not in vars(threadfan)
