"""The aggregated error raised when tasks fail and the run was not stopped early."""

from __future__ import annotations

import copyreg
from collections.abc import Callable, Mapping
from typing import Any

from ._options import show_int, type_name

_DETAIL_LIMIT = 200
# The constructor that pickle protocol 2 and later name NEWOBJ; typeshed does not declare it.
_NEWOBJ: Callable[..., object] = vars(copyreg)["__newobj__"]


class ThreadMapError(Exception):
    """Raised at the end of a run with ``stop_on_error=False`` when any task failed.

    :attr:`errors` maps the input index of each failed item to its exception and
    :attr:`results` the index of each successful item to the value ``fn`` returned
    (typed ``Any``, since an ``except`` clause cannot carry the result type). Both are
    sorted by index. :func:`thread_imap` has already yielded its values, so its
    :attr:`results` is empty. The failure with the lowest index is the ``__cause__``.

    The message gives the number of failures and the first one, cut to 200 characters
    of ``Type: message``. Building one by hand takes any mapping from ``int`` indices
    to exceptions (and to results); anything else raises ``TypeError``. It pickles,
    subclasses and their attributes included, when its contents pickle.

    >>> from threadfan import ThreadMapError, thread_map
    >>> try:
    ...     thread_map(int, ["1", "x", "3", "y"], stop_on_error=False)
    ... except ThreadMapError as error:
    ...     print(error)
    ...     print(error.results, list(error.errors))
    2 tasks failed; first at index 1: ValueError: invalid literal for int() with base 10: 'x'
    {0: 1, 2: 3} [1, 3]
    """

    def __init__(
        self, errors: Mapping[int, Exception], results: Mapping[int, Any] | None = None
    ) -> None:
        # Annotated here, not on the class: the class lives at the package top, where a
        # class-level ``Any`` would not resolve for ``typing.get_type_hints``.
        self.errors: dict[int, Exception] = _by_index("errors", errors, failures=True)
        self.results: dict[int, Any] = (
            {} if results is None else _by_index("results", results, failures=False)
        )
        super().__init__(_describe(self.errors))

    def __reduce__(self) -> tuple[Any, ...]:
        # Rebuild without calling ``__init__`` (a subclass may take other arguments) and
        # restore the state (notes, extra attributes) afterwards. The pickle names only
        # ``copyreg`` and the class, never the private module that defines it.
        return (_NEWOBJ, (type(self), *self.args), self.__dict__)


def _by_index(name: str, mapping: object, *, failures: bool) -> dict[int, Any]:
    if not isinstance(mapping, Mapping):
        raise TypeError(f"{name} must be a mapping, got {type_name(mapping)}")
    pairs = list(mapping.items())
    for index, value in pairs:
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError(f"{name} keys must be int indices, got {type_name(index)}")
        if failures and not isinstance(value, Exception):
            raise TypeError(f"{name} values must be exceptions, got {type_name(value)}")
    return dict(sorted(pairs, key=lambda pair: pair[0]))


def _describe(errors: dict[int, Exception]) -> str:
    count = len(errors)
    noun = "task" if count == 1 else "tasks"
    if not errors:
        return f"{count} {noun} failed"
    index, error = next(iter(errors.items()))
    return f"{count} {noun} failed; first at index {show_int(index)}: {_summary(error)}"


def _summary(error: Exception) -> str:
    try:
        text = str(error)
    except Exception:
        # A broken ``__str__`` must not replace the error that carries every result.
        text = "<message could not be read>"
    detail = f"{type_name(error)}: {text}" if text else type_name(error)
    if len(detail) <= _DETAIL_LIMIT:
        return detail
    return detail[: _DETAIL_LIMIT - 3] + "..."
