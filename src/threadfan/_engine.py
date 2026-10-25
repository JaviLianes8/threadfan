"""The windowed scheduler shared by ``thread_map`` and ``thread_imap``."""

from __future__ import annotations

import contextvars
import queue
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from ._progress import ProgressCallback

T = TypeVar("T")
R = TypeVar("R")


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
    # Streams count the results waiting to be yielded against ``window``;
    # ``thread_map`` keeps every result anyway, so only tasks in flight count.
    hold_unyielded: bool = True
    context: contextvars.Context | None = None
    on_progress: ProgressCallback | None = None
    total: int = 0
    errors: dict[int, Exception] = field(default_factory=dict)
    failure: BaseException | None = None

    def stream(self, source: Iterator[T]) -> Iterator[tuple[int, R]]:
        """Yield ``(index, value)`` for each success, in input or completion order.

        The window caps the items read from ``source`` and not yet yielded (or, for
        ``thread_map``, the tasks in flight). Whatever ends the stream early cancels
        queued work and waits only for the tasks already running. In input order a
        failure stops the run once every lower index has finished, so the failure
        raised is the one with the lowest index, as with ``map``; a source that
        raises still has the items read before it processed.
        """
        pool = ThreadPoolExecutor(self.workers, thread_name_prefix=self.thread_name_prefix)
        # Done callbacks feed this queue: waiting costs the same whatever the window.
        finished: queue.SimpleQueue[Future[R]] = queue.SimpleQueue()
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
                    future = self._submit(pool, item)
                    pending[future] = submitted
                    future.add_done_callback(finished.put)
                    submitted += 1
                if not pending:
                    self.failure = source_error
                    return
                for future in _settled(finished, pending):
                    index = pending.pop(future)
                    if future.cancelled():
                        continue
                    error = future.exception()
                    if error is None:
                        pass
                    elif isinstance(error, Exception) and not self.stop_on_error:
                        self.errors[index] = error
                    elif isinstance(error, Exception) and self.ordered:
                        if stop_at is None:
                            _cancel_after(index, pending)
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
            # A stream closed inside one of its own workers must not join itself.
            inside = threading.current_thread() in getattr(pool, "_threads", ())
            pool.shutdown(wait=not inside, cancel_futures=True)

    def _room(self, submitted: int, emitted: int, pending: dict[Future[R], int]) -> bool:
        if self.ordered and self.hold_unyielded:
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


def _settled(
    finished: queue.SimpleQueue[Future[R]], pending: dict[Future[R], int]
) -> list[Future[R]]:
    """Wait for one task to settle, take every other settled one, sort by input index."""
    batch = [finished.get()]
    while True:
        try:
            batch.append(finished.get_nowait())
        except queue.Empty:
            return sorted(batch, key=pending.__getitem__)


def _cancel_after(index: int, pending: dict[Future[R], int]) -> None:
    """Cancel the queued tasks past ``index``: once it failed, their results cannot matter."""
    for future, position in pending.items():
        if position > index:
            future.cancel()
