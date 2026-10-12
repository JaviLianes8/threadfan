# threadfan improvement round

Progress:
- [x] Brainstorm ranked improvements (this file)
- [x] Engine: bounded submission window, clean shutdown on every exit path
- [x] `thread_imap`: lazy, ordered or completion-order streaming with backpressure
- [x] Errors: deterministic `ThreadMapError` (sorted errors, partial results, picklable)
- [x] Options: strict `workers` validation, `max_pending`, `copy_context`, `thread_name_prefix`
- [x] Contracts: oracle against builtin `map`, laziness, shutdown, typing, README examples
- [x] Installed wheel e2e test
- [x] Docs: README, CHANGELOG, docstrings, packaging metadata
- [x] Gates: ruff format, ruff check, mypy --strict, pytest
- [x] Independent review findings fixed with regression tests
- [x] Pull request opened (#2), guard clean

Every item is additive. `thread_map` keeps its name, its positional `fn` and `items`,
every keyword it had, and its `list[R]` return type.

## Starting point

`0.1.0` turns `items` into a list, submits every item to the pool at once and walks
`as_completed`. Reading it against the standard library turned up these gaps:

- A million items means a million queued futures before the first one finishes.
  There is no lazy variant, so an endless or very large source cannot be used.
- Only `Exception` is caught. A `KeyboardInterrupt` or `SystemExit` raised by a task,
  a failing `on_progress`, or a Ctrl+C while waiting leave every queued item to run
  to the end before the call returns, because nothing cancels them.
- `ThreadMapError.errors` is in completion order, the successful results are lost,
  and the error cannot be pickled (its `__init__` does not take the message).
- `workers=0` is accepted when `items` is empty, and `workers=True` is accepted as 1.
- Context variables set by the caller are not visible inside the tasks.

## Sources (fetched 2026-10-12)

- `concurrent.futures` docs: https://docs.python.org/3/library/concurrent.futures.html
  (`Executor.map` collects the iterables immediately unless the 3.14 `buffersize` is
  given; `chunksize` has no effect for threads; the default `max_workers` is
  `min(32, os.cpu_count() + 4)`; `shutdown(cancel_futures=True)` cancels queued work;
  `thread_name_prefix` names the worker threads).
- `asyncio.to_thread` docs: https://docs.python.org/3/library/asyncio-task.html
  (the caller's `contextvars.Context` is propagated to the worker thread).

## Ranked improvements

1. **Bounded submission window.** At most `max_pending` items (default twice the
   worker count) are submitted and not yet consumed at any time. Memory no longer
   grows with the input size, and nothing past the window is read from `items`.
2. **Clean shutdown on every exit path.** First failure, a `BaseException` from a
   task or from the caller, a failing progress callback, a failing source iterator,
   or a consumer that stops early: queued items are cancelled, no new item is
   submitted, and the call waits only for tasks already running.
3. **`thread_imap`.** The same engine as a generator for large or endless sources,
   ordered (head-of-line, memory still bounded) or in completion order.
4. **Deterministic, useful errors.** `ThreadMapError.errors` sorted by index,
   `results` with every successful value, a message naming the first failing index,
   and pickling that round-trips.
5. **Ground truth.** Seeded random runs compared with the builtin `map`: same values,
   same order, same set of failing indices, for every worker and window size.
6. **Validated options.** `workers` and `max_pending` must be real `int`s of at least 1
   (`TypeError` and `ValueError`), checked before any item is read, empty input too.
7. **`copy_context` and `thread_name_prefix`.** Run each task in a copy of the
   caller's context, as `asyncio.to_thread` does, and name the worker threads.
8. **Progress guarantees.** `on_progress` runs in the calling thread, once per item,
   with `completed` strictly increasing from 1 to `total`.
9. **Typed public API, proven.** A test runs mypy on a snippet and asserts the result
   type follows the mapped function, and that a wrong item type is rejected.
10. **Docs with runnable examples.** Every Python block in the README is executed by
    the test suite. Docstrings on every public name, CHANGELOG entry.
11. **Packaging.** Classifiers for the supported versions, keywords, a test that the
    package version matches the metadata, and an installed-wheel e2e test.

## Review fixes

- A source that raises no longer drops the items already read from it.
- Ordered `thread_imap` with `stop_on_error` yields everything before the lowest
  failing index, then raises it, as `map` does.
- `StopIteration` from `fn` or `on_progress` is re-raised unchanged by `thread_map`.
- `ThreadMapError` subclasses pickle with their own attributes.
- `copy_context` captures the context when `thread_imap` is called.
- Integer-like counts (anything with `__index__`) are accepted, `bool` still is not.
- A stream finalised inside one of its own workers no longer tries to join itself.
- A per-test watchdog turns a scheduling hang into a failure.

## Out of scope

- A command line tool: mapping a Python callable has no natural shell form, and
  `xargs -P` already covers running commands in parallel.
- Timeouts that stop running tasks: threads cannot be killed, so a timeout would only
  abandon work that keeps running. Callers put timeouts in `fn` itself.
- Retries and rate limiting: they belong in `fn` or in a dedicated library.
