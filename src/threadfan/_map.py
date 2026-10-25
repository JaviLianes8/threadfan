"""The public entry points: ``thread_map`` (a list) and ``thread_imap`` (a stream)."""

from __future__ import annotations

import contextvars
from collections.abc import Callable, Generator, Iterable, Iterator
from typing import TypeVar

from ._engine import Run
from ._errors import ThreadMapError
from ._options import check_callable, check_prefix, resolve_window, resolve_workers
from ._progress import ProgressCallback

T = TypeVar("T")
R = TypeVar("R")

DEFAULT_PREFIX = "threadfan"


def thread_map(
    fn: Callable[[T], R],
    items: Iterable[T],
    *,
    workers: int | None = None,
    ordered: bool = True,
    stop_on_error: bool = True,
    on_progress: ProgressCallback | None = None,
    max_pending: int | None = None,
    copy_context: bool = False,
    thread_name_prefix: str = DEFAULT_PREFIX,
) -> list[R]:
    """Apply ``fn`` to every item on a bounded pool of worker threads and return a list.

    The results follow the input order when ``ordered`` is true and completion order
    otherwise. ``items`` is read in full, after the options are checked; use
    :func:`thread_imap` for sources too large to hold in memory.

    With ``stop_on_error`` (the default) a failure stops the run: queued items are
    cancelled, the call returns once the tasks already running finish, and the
    failure is re-raised unchanged. In input order it is the failure with the lowest
    index, the one ``map`` would raise; with ``ordered=False`` it is the first to
    fail. With ``stop_on_error=False`` every item runs and, if any failed, a
    :class:`ThreadMapError` holding every failure and every result is raised at the
    end. ``KeyboardInterrupt``, ``SystemExit`` and any other exception that is not an
    ``Exception`` stop the run at once.

    ``workers`` caps the pool (default 32, never more than the number of items) and
    ``max_pending`` the tasks submitted and not yet finished (default twice the
    pool). ``on_progress(completed, total)`` runs in the calling thread, see
    :class:`ProgressCallback`. ``copy_context`` runs each task in its own copy of the
    caller's :mod:`contextvars` context, taken when this is called. Worker threads are
    named ``<thread_name_prefix>_<n>``. A wrong option type raises ``TypeError`` and a
    count below 1 ``ValueError``, before any item is read.

    >>> from threadfan import thread_map
    >>> thread_map(len, ["a", "bb", "ccc"], workers=2)
    [1, 2, 3]
    >>> sorted(thread_map(str.upper, ["x", "y", "z"], ordered=False))
    ['X', 'Y', 'Z']
    >>> thread_map(int, ["1", "x", "y"])
    Traceback (most recent call last):
    ...
    ValueError: invalid literal for int() with base 10: 'x'
    """
    run = _prepare(
        fn, workers, max_pending, ordered, stop_on_error, copy_context, thread_name_prefix
    )
    if on_progress is not None:
        check_callable("on_progress", on_progress)
    work = list(items)
    if not work:
        return []
    run.workers = resolve_workers(workers, len(work))
    run.window = resolve_window(max_pending, run.workers)
    run.hold_unyielded = False
    run.on_progress = on_progress
    run.total = len(work)
    pairs = list(run.stream(iter(work)))
    if run.failure is not None:
        raise run.failure
    if run.errors:
        raise ThreadMapError(run.errors, dict(pairs)) from _first(run.errors)
    return [value for _, value in pairs]


def thread_imap(
    fn: Callable[[T], R],
    items: Iterable[T],
    *,
    workers: int | None = None,
    ordered: bool = True,
    stop_on_error: bool = True,
    max_pending: int | None = None,
    copy_context: bool = False,
    thread_name_prefix: str = DEFAULT_PREFIX,
) -> Generator[R, None, None]:
    """Apply ``fn`` to ``items`` on a bounded pool, yielding the results as a stream.

    ``items`` is read only as fast as the results are consumed: at most
    ``max_pending`` items (default twice ``workers``) are read and not yet yielded
    at any time, so endless sources work, and nothing is read before the first
    ``next()``. An ordered stream yields in input order, waiting for the oldest
    item; ``ordered=False`` yields in completion order. The options are checked,
    and ``iter(items)`` is called, when this is called.

    Closing the generator, or leaving a ``for`` loop over it once it is released,
    cancels queued work and waits only for the tasks already running.

    With ``stop_on_error`` an ordered stream behaves like ``map``: it yields every
    result before the lowest failing index, then raises that failure; in completion
    order the first failure is raised. With ``stop_on_error=False`` failed items are
    skipped and a :class:`ThreadMapError` is raised once the source is done. If
    ``items`` itself raises, the items read before it are still processed and
    yielded, then its exception is raised. As in any generator, a ``StopIteration``
    from ``fn`` surfaces as ``RuntimeError``. ``workers`` (default 32),
    ``copy_context`` and ``thread_name_prefix`` work as in :func:`thread_map`.

    >>> import itertools
    >>> from threadfan import thread_imap
    >>> squares = thread_imap(lambda n: n * n, itertools.count(), workers=4)
    >>> [next(squares) for _ in range(5)]
    [0, 1, 4, 9, 16]
    >>> squares.close()
    """
    run = _prepare(
        fn, workers, max_pending, ordered, stop_on_error, copy_context, thread_name_prefix
    )
    return _stream(run, iter(items))


def _stream(run: Run[T, R], source: Iterator[T]) -> Generator[R, None, None]:
    for _, value in run.stream(source):
        yield value
    if run.failure is not None:
        raise run.failure
    if run.errors:
        raise ThreadMapError(run.errors) from _first(run.errors)


def _prepare(
    fn: Callable[[T], R],
    workers: int | None,
    max_pending: int | None,
    ordered: bool,
    stop_on_error: bool,
    copy_context: bool,
    thread_name_prefix: str,
) -> Run[T, R]:
    """Check the options before any item is read and build the run."""
    check_callable("fn", fn)
    size = resolve_workers(workers)
    window = resolve_window(max_pending, size)
    prefix = check_prefix(thread_name_prefix)
    return Run(
        fn=fn,
        workers=size,
        window=window,
        ordered=bool(ordered),
        stop_on_error=bool(stop_on_error),
        thread_name_prefix=prefix,
        context=contextvars.copy_context() if copy_context else None,
    )


def _first(errors: dict[int, Exception]) -> Exception:
    return errors[min(errors)]
