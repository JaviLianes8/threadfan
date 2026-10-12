"""The aggregated error raised when tasks fail and the run was not stopped early."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class ThreadMapError(Exception):
    """Raised at the end of a run with ``stop_on_error=False`` when any task failed.

    :attr:`errors` maps each failing input index to its exception and :attr:`results`
    maps each successful input index to its value. Both are sorted by index. For
    :func:`thread_imap` the successful values were already yielded, so
    :attr:`results` is empty.
    """

    errors: dict[int, Exception]
    results: dict[int, Any]

    def __init__(
        self, errors: Mapping[int, Exception], results: Mapping[int, Any] | None = None
    ) -> None:
        self.errors = dict(sorted(errors.items()))
        self.results = dict(sorted((results or {}).items()))
        super().__init__(_describe(self.errors))

    def __reduce__(self) -> tuple[Any, ...]:
        # The default pickling replays ``args`` (the message) into ``__init__``, and
        # subclasses may take other arguments, so rebuild without calling theirs and
        # restore the instance state (notes, extra attributes) afterwards.
        return (_rebuild, (type(self), self.errors, self.results), self.__dict__)


def _rebuild(
    cls: type[ThreadMapError], errors: Mapping[int, Exception], results: Mapping[int, Any]
) -> ThreadMapError:
    error = cls.__new__(cls)
    ThreadMapError.__init__(error, errors, results)
    return error


def _describe(errors: dict[int, Exception]) -> str:
    count = len(errors)
    noun = "task" if count == 1 else "tasks"
    if not errors:
        return f"{count} {noun} failed"
    index, error = next(iter(errors.items()))
    detail = f"{type(error).__name__}: {error}" if str(error) else type(error).__name__
    return f"{count} {noun} failed; first at index {index}: {detail}"
