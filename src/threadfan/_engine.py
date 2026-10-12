"""The windowed scheduler shared by ``thread_map`` and ``thread_imap``."""

from __future__ import annotations

import contextvars
import threading
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
    """One scheduled run: the settings, the collected failures and what stopped it.

    ``stream`` never raises the exception that ends a run early: it stores it in
    ``failure`` and returns, and the caller raises it. Raising inside a generator
    would turn a ``StopIteration`` from ``fn`` into a ``RuntimeError``.
    """

    fn: Callable[[T], R]
    workers: int
    window: int
    ordered: bool
    stop_on_error: bool
    thread_name_prefix: str
    context: contextvars.Context | None = None
    on_progress: ProgressCallback | None = None
    total: int = 0
    errors: dict[int, Exception] = field(default_factory=dict)
    failure: BaseException | None = None

    def stream(self, items: Iterable[T]) -> Iterator[tuple[int, R]]:
        """Yield ``(index, value)`` for each success, in input or completion order.

        At most ``window`` items are read from ``items`` and not yet yielded at any
        moment. Whatever ends the stream early cancels queued work and waits only
        for the tasks already running. An ordered stream with ``stop_on_error``
        yields every result before the first failing index, as ``map`` does, and
        a source that raises still has the items read before it processed.
        """
        source = iter(items)
        pool = ThreadPoolExecutor(self.workers, thread_name_prefix=self.thread_name_prefix)
        pending: dict[Future[R], int] = {}
        ready: dict[int, R] = {}
        submitted = emitted = completed = 0
        exhausted = False
        source_error: Exception | None = None
        stop_at: int | None = None
        stop_error: Exception | None = None
        try:
            while True:
                while not exhausted and stop_at is None and self._room(submitted, emitted, pending):
                    try:
                        item = next(source)
                    except StopIteration:
                        exhausted = True
                        break
                    except Exception as broken:
                        source_error, exhausted = broken, True
                        break
                    pending[self._submit(pool, item)] = submitted
                    submitted += 1
                if not pending:
                    self.failure = source_error
                    return
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in sorted(done, key=pending.__getitem__):
                    index = pending.pop(future)
                    error = future.exception()
                    if error is None:
                        pass
                    elif isinstance(error, Exception) and not self.stop_on_error:
                        self.errors[index] = error
                    elif isinstance(error, Exception) and self.ordered:
                        if stop_at is None or index < stop_at:
                            stop_at, stop_error = index, error
                        continue
                    else:
                        self.failure = error
                        return
                    completed += 1
                    if not self._report(completed):
                        return
                    if error is not None:
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
                if stop_at is not None and emitted == stop_at:
                    self.failure = stop_error
                    return
        finally:
            # A stream collected inside one of its own workers must not join itself.
            inside = threading.current_thread() in getattr(pool, "_threads", ())
            pool.shutdown(wait=not inside, cancel_futures=True)

    def _room(self, submitted: int, emitted: int, pending: dict[Future[R], int]) -> bool:
        if self.ordered:
            return submitted - emitted < self.window
        return len(pending) < self.window

    def _submit(self, pool: ThreadPoolExecutor, item: T) -> Future[R]:
        if self.context is not None:
            # A Context cannot be entered by two threads at once, so copy per task.
            return pool.submit(self.context.copy().run, self.fn, item)
        return pool.submit(self.fn, item)

    def _report(self, completed: int) -> bool:
        """Call ``on_progress``; False (with ``failure`` set) if it raised."""
        if self.on_progress is None:
            return True
        try:
            self.on_progress(completed, self.total)
        except BaseException as error:
            self.failure = error
            return False
        return True
