"""The windowed scheduler shared by ``thread_map`` and ``thread_imap``."""

from __future__ import annotations

import contextvars
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")
R = TypeVar("R")

ProgressCallback = Callable[[int, int], None]
"""Called as ``on_progress(completed, total)`` in the calling thread after each item."""


@dataclass
class Run(Generic[T, R]):
    """One scheduled run: the settings, plus the failures collected so far."""

    fn: Callable[[T], R]
    workers: int
    window: int
    ordered: bool
    stop_on_error: bool
    copy_context: bool
    thread_name_prefix: str
    on_progress: ProgressCallback | None = None
    total: int = 0
    errors: dict[int, Exception] = field(default_factory=dict)

    def stream(self, items: Iterable[T]) -> Iterator[tuple[int, R]]:
        """Yield ``(index, value)`` for each success, in input or completion order.

        At most ``window`` items are read from ``items`` and not yet yielded at any
        moment. Whatever ends the stream early (a failure, an exception in the
        caller, the consumer closing the generator) cancels queued work and waits
        only for the tasks already running.
        """
        source = iter(items)
        pool = ThreadPoolExecutor(self.workers, thread_name_prefix=self.thread_name_prefix)
        pending: dict[Future[R], int] = {}
        ready: dict[int, R] = {}
        submitted = emitted = completed = 0
        exhausted = False
        try:
            while True:
                while not exhausted and self._has_room(submitted, emitted, len(pending)):
                    try:
                        item = next(source)
                    except StopIteration:
                        exhausted = True
                        break
                    pending[self._submit(pool, item)] = submitted
                    submitted += 1
                if not pending:
                    return
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in sorted(done, key=pending.__getitem__):
                    index = pending.pop(future)
                    settled = self._settle(future, index)
                    completed += 1
                    if self.on_progress is not None:
                        self.on_progress(completed, self.total)
                    if not settled:
                        continue
                    if self.ordered:
                        ready[index] = future.result()
                    else:
                        yield index, future.result()
                # Failed items are in ``errors``; skip them so the head can advance.
                while self.ordered and (emitted in ready or emitted in self.errors):
                    if emitted in ready:
                        yield emitted, ready.pop(emitted)
                    emitted += 1
        finally:
            pool.shutdown(wait=True, cancel_futures=True)

    def _has_room(self, submitted: int, emitted: int, in_flight: int) -> bool:
        if self.ordered:
            return submitted - emitted < self.window
        return in_flight < self.window

    def _submit(self, pool: ThreadPoolExecutor, item: T) -> Future[R]:
        if self.copy_context:
            # A Context cannot be entered by two threads at once, so copy per task.
            return pool.submit(contextvars.copy_context().run, self.fn, item)
        return pool.submit(self.fn, item)

    def _settle(self, future: Future[R], index: int) -> bool:
        """Record a finished task; True on success, False on a collected failure."""
        try:
            future.result()
        except Exception as error:
            if self.stop_on_error:
                raise
            self.errors[index] = error
            return False
        return True
