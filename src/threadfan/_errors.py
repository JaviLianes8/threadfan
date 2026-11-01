"""The aggregated error raised when tasks fail and the run was not stopped early."""

from __future__ import annotations

import copyreg
from collections.abc import Callable, Mapping
from typing import Any

from ._options import show_int, type_name

# The constructor that pickle protocol 2 and later name NEWOBJ; typeshed does not declare it.
_NEWOBJ: Callable[..., object] = vars(copyreg)["__newobj__"]
_SLOTNAMES: Callable[[type[object]], list[str]] = vars(copyreg)["_slotnames"]


class ThreadMapError(Exception):
    """Raised at the end of a run with ``stop_on_error=False`` when any task failed.

    :attr:`errors` maps the input index of each failed item to its exception and
    :attr:`results` the index of each successful item to the value ``fn`` returned
    (typed ``Any``, since an ``except`` clause cannot carry the result type). Both are
    sorted by index. :func:`thread_imap` has already yielded its values, so its
    :attr:`results` is empty. The failure with the lowest index is the ``__cause__``.

    The message gives the number of failures, first index and exception type, without
    formatting task messages or results. The original exceptions and cause still hold
    the caller's data; handle those explicitly before logging a full traceback.
    Integer subclasses are stored as built-in ints.
    Building one by hand takes any mapping from ``int`` indices
    to exceptions (and to results); anything else raises ``TypeError``. It pickles,
    subclasses and their attributes included, when its contents pickle.

    >>> from threadfan import ThreadMapError, thread_map
    >>> try:
    ...     thread_map(int, ["1", "x", "3", "y"], stop_on_error=False)
    ... except ThreadMapError as error:
    ...     print(error)
    ...     print(error.results, list(error.errors))
    2 tasks failed; first at index 1: ValueError
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
        slots = {
            name: getattr(self, name) for name in _SLOTNAMES(type(self)) if hasattr(self, name)
        }
        state = {**self.__dict__, **slots}
        return (_NEWOBJ, (type(self), *self.args), state)


def _by_index(name: str, mapping: object, *, failures: bool) -> dict[int, Any]:
    if not isinstance(mapping, Mapping):
        raise TypeError(f"{name} must be a mapping, got {type_name(mapping)}")
    pairs = []
    for index, value in mapping.items():
        index_type = type(index)
        if index_type is bool or not issubclass(index_type, int):
            raise TypeError(f"{name} keys must be int indices, got {type_name(index)}")
        if failures and not isinstance(value, Exception):
            raise TypeError(f"{name} values must be exceptions, got {type_name(value)}")
        pairs.append((int.__int__(index), value))
    return dict(sorted(pairs, key=lambda pair: pair[0]))


def _describe(errors: dict[int, Exception]) -> str:
    count = len(errors)
    noun = "task" if count == 1 else "tasks"
    if not errors:
        return f"{count} {noun} failed"
    index, error = next(iter(errors.items()))
    return f"{count} {noun} failed; first at index {show_int(index)}: {type_name(error)}"


def _rebuild(
    cls: type[ThreadMapError], errors: Mapping[int, Exception], results: Mapping[int, Any]
) -> ThreadMapError:
    # Published 0.2.0 pickles refer to this function, so keep it for existing data.
    error = cls.__new__(cls)
    ThreadMapError.__init__(error, errors, results)
    return error
