"""The public entry points: ``thread_map`` (a list) and ``thread_imap`` (a stream)."""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterable
from typing import TypeVar

from ._engine import ProgressCallback, Run
from ._errors import ThreadMapError
from ._options import check_prefix, resolve_window, resolve_workers

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
    """Apply ``fn`` to every item across a bounded pool of worker threads.

    Results follow the input order when ``ordered`` is true, otherwise they
    arrive in completion order. ``items`` is read in full first so the total is
    known; use :func:`thread_imap` for sources too large to hold in memory.

    With ``stop_on_error`` the first failure (in completion order) is re-raised
    unchanged, queued items are cancelled and the call returns once the tasks
    already running finish. Without it every item runs and a
    :class:`ThreadMapError` holding the failures and the successful results is
    raised at the end if any failed.

    ``workers`` caps the pool (default 32, never more than the number of items)
    and ``max_pending`` caps the items submitted at once (default twice the pool).
    ``on_progress(completed, total)`` runs in the calling thread after each item,
    failures included. ``copy_context`` runs each task in a copy of the caller's
    :mod:`contextvars` context. Worker threads are named after
    ``thread_name_prefix``.
    """
    run = _make_run(
        fn, workers, max_pending, False, stop_on_error, copy_context, thread_name_prefix
    )
    work = list(items)
    if not work:
        return []
    run.workers = resolve_workers(workers, len(work))
    run.window = resolve_window(max_pending, run.workers)
    run.on_progress = on_progress
    run.total = len(work)
    pairs = list(run.stream(work))
    if run.errors:
        raise ThreadMapError(run.errors, dict(pairs)) from _first(run.errors)
    if ordered:
        pairs.sort(key=lambda pair: pair[0])
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
    """Lazily apply ``fn`` to ``items`` on a bounded pool, yielding results as a stream.

    ``items`` is read only as fast as results are consumed: at most
    ``max_pending`` items (default twice ``workers``) are submitted and not yet
    yielded at any time, so endless sources work. Ordered streams wait for the
    oldest item before yielding later ones; ``ordered=False`` yields in completion
    order. The options are validated when this is called, before any item is read.

    Closing the generator, or leaving a ``for`` loop over it once it is released,
    cancels queued work and waits only for the tasks already running. Errors
    behave as in :func:`thread_map`; with ``stop_on_error=False`` the failed items
    are skipped and a :class:`ThreadMapError` is raised once the source is done.
    """
    run = _make_run(
        fn, workers, max_pending, ordered, stop_on_error, copy_context, thread_name_prefix
    )
    return _stream(run, items)


def _stream(run: Run[T, R], items: Iterable[T]) -> Generator[R, None, None]:
    for _, value in run.stream(items):
        yield value
    if run.errors:
        raise ThreadMapError(run.errors) from _first(run.errors)


def _make_run(
    fn: Callable[[T], R],
    workers: int | None,
    max_pending: int | None,
    ordered: bool,
    stop_on_error: bool,
    copy_context: bool,
    thread_name_prefix: str,
) -> Run[T, R]:
    size = resolve_workers(workers)
    return Run(
        fn=fn,
        workers=size,
        window=resolve_window(max_pending, size),
        ordered=ordered,
        stop_on_error=stop_on_error,
        copy_context=copy_context,
        thread_name_prefix=check_prefix(thread_name_prefix),
    )


def _first(errors: dict[int, Exception]) -> Exception:
    return errors[min(errors)]
