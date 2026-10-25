"""The type of the ``on_progress`` callback of ``thread_map``."""

from __future__ import annotations

from typing import Protocol


class ProgressCallback(Protocol):
    """Called as ``on_progress(completed, total)`` while :func:`thread_map` runs.

    Any callable that takes two integers fits, whatever its parameter names, and its
    return value is ignored. It runs in the thread that called :func:`thread_map`,
    once after each item that finishes and is kept (a result, or a failure collected
    with ``stop_on_error=False``), with ``completed`` going up by one from 1 and
    ``total`` the number of items. An exception it raises stops the run at once,
    whatever ``stop_on_error`` says, and reaches the caller unchanged.

    >>> from threadfan import thread_map
    >>> seen = []
    >>> def report(completed: int, total: int) -> None:
    ...     seen.append(f"{completed}/{total}")
    >>> thread_map(str.upper, ["a", "b", "c"], workers=2, on_progress=report)
    ['A', 'B', 'C']
    >>> seen
    ['1/3', '2/3', '3/3']
    """

    def __call__(self, completed: int, total: int, /) -> object: ...
