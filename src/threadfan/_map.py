"""The bounded, typed parallel map and its error type."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")

ProgressCallback = Callable[[int, int], None]

_MAX_DEFAULT_WORKERS = 32


class ThreadMapError(Exception):
    """Raised when ``stop_on_error`` is off and one or more tasks failed.

    The per item failures are kept in :attr:`errors`, keyed by input index.
    """

    def __init__(self, errors: dict[int, Exception]) -> None:
        self.errors = errors
        count = len(errors)
        noun = "task" if count == 1 else "tasks"
        super().__init__(f"{count} {noun} failed")


def thread_map(
    fn: Callable[[T], R],
    items: Iterable[T],
    *,
    workers: int | None = None,
    ordered: bool = True,
    stop_on_error: bool = True,
    on_progress: ProgressCallback | None = None,
) -> list[R]:
    """Apply ``fn`` to every item across a bounded pool of worker threads.

    Results follow the input order when ``ordered`` is true, otherwise they
    arrive in completion order. With ``stop_on_error`` the first failure is
    re-raised and pending work is cancelled; without it every item runs and a
    :class:`ThreadMapError` is raised at the end if any failed. ``on_progress``
    is called with ``(completed, total)`` after each item finishes.
    """
    work = list(items)
    total = len(work)
    if total == 0:
        return []

    pool_size = _bounded_workers(workers, total)
    ordered_results: dict[int, R] = {}
    unordered_results: list[R] = []
    errors: dict[int, Exception] = {}
    completed = 0

    with ThreadPoolExecutor(max_workers=pool_size) as pool:
        futures: dict[Future[R], int] = {
            pool.submit(fn, item): index for index, item in enumerate(work)
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                value = future.result()
            except Exception as error:
                if stop_on_error:
                    for pending in futures:
                        pending.cancel()
                    raise
                errors[index] = error
            else:
                if ordered:
                    ordered_results[index] = value
                else:
                    unordered_results.append(value)
            completed += 1
            if on_progress is not None:
                on_progress(completed, total)

    if errors:
        raise ThreadMapError(errors)
    if ordered:
        return [ordered_results[index] for index in range(total)]
    return unordered_results


def _bounded_workers(workers: int | None, total: int) -> int:
    """Clamp the pool size to a sane bound, never more than the item count."""
    if workers is None:
        return min(_MAX_DEFAULT_WORKERS, total)
    if workers < 1:
        raise ValueError("workers must be at least 1")
    return min(workers, total)
