# Guide

## Stable surface

Import `thread_map`, `thread_imap`, `ThreadMapError` and `ProgressCallback` from
`threadfan`. `__version__` is release metadata. Private modules are not API.
Both functions accept positional `fn` and `items`; all options are keyword-only.
`thread_map` additionally accepts `on_progress=None`.

| Option | Default | Contract |
| --- | --- | --- |
| `workers` | `None` | 32 threads, capped at nonempty `thread_map` input length. |
| `max_pending` | `None` | Twice the effective worker count. Can be below `workers`. |
| `ordered` | `True` | Input order; false selects completion callback arrival order. |
| `stop_on_error` | `True` | Stop on a task failure; false collects ordinary exceptions. |
| `copy_context` | `False` | True captures the caller's context at the function call. |
| `thread_name_prefix` | `"threadfan"` | Workers named `<prefix>_<number>`. |

Counts accept `SupportsIndex` (an integer or an object implementing `__index__`),
excluding bool, and must be at least one. Options are checked once before input
is read, even for empty input. Flags use their truth value once at call time.
`fn` and a non-None progress callback must be callable. The prefix must be a string;
an empty prefix uses the standard executor's default thread names.

```python
from threadfan import ProgressCallback, thread_imap, thread_map

seen: list[tuple[int, int]] = []
callback: ProgressCallback = lambda done, total: seen.append((done, total))
assert thread_map(str, [2, 4], workers=1, on_progress=callback) == ["2", "4"]
assert seen == [(1, 2), (2, 2)]
assert list(thread_imap(abs, [-2, 3], max_pending=1)) == [2, 3]
```

## Scheduling and lifetime

`thread_map` reads all input before starting workers and returns a list. Its window
limits submitted work awaiting consumption by the scheduler, independently of input
order. `thread_imap` obtains the iterator at call time but reads no item until
`next()`. Its window includes items read but not yet yielded, so it supports endless
sources. Ordered streaming can wait for a slow first item while later results wait.
Unordered results follow completion callbacks; simultaneous completions and tasks
already complete when their callbacks are attached have no promised relative order.
The window bounds pending work, not stored failures: collecting errors uses memory
proportional to the number of failures. Use a finite source when collecting them.

Close a partially consumed stream with `contextlib.closing`. A bare `break` does not
close a generator that you still reference. Closing cancels queued tasks and waits
for running tasks, whose effects may still happen. Threads cannot be killed: set IO
timeouts inside `fn`. Do not create cyclic waits between tasks or consumers.
Closing a suspended stream from its own worker skips the join to avoid self-deadlock;
remaining running workers exit after their tasks return.

```python
from contextlib import closing
from itertools import count
from threadfan import thread_imap

with closing(thread_imap(lambda n: n * n, count(), max_pending=2)) as stream:
    assert [next(stream) for _ in range(3)] == [0, 1, 4]
```

With `copy_context=True`, every task receives a separate copy, including when one
worker handles several tasks. Changes never propagate back. With false, the runtime's
native thread context rules apply; Python 3.14 free-threaded builds may inherit context
at thread creation. False does not promise a fresh context for each task.

Progress runs synchronously in the caller's thread for each consumed success or
collected failure. Counts increase from 1 to total, exactly once per item on a full
run. Its return value is ignored. A callback failure stops processing immediately.

## Errors

| Situation | Result |
| --- | --- |
| Noncallable `fn`/callback, wrong prefix or count type | `TypeError` before reading input. |
| Count below 1 | `ValueError` before reading input. |
| Invalid iterable or its iteration fails | Original exception. |
| Task failure, ordered and stopping | Lowest failing input index, unchanged. |
| Task failure, unordered and stopping | First observed failure, unchanged. |
| Task failure with collection | `ThreadMapError` after processing all items. |
| `BaseException` outside `Exception` | Immediate stop, unchanged, even when collecting. |
| Progress callback failure | Immediate stop, unchanged. |

Ordered streams yield successes preceding the lowest failure before raising it.
A streaming source's ordinary exception is deferred until previously read items are
processed, unless a stopping task failure takes precedence. A source exception takes
precedence over collected task errors. `thread_map` starts no tasks if materializing
its source fails. `StopIteration` from a task or callback is unchanged in `thread_map`;
the generator rules turn it into `RuntimeError` in `thread_imap` when stopping.

`ThreadMapError(errors, results=None)` copies mappings sorted by integer index.
Keys must be ints other than bool; error values must be `Exception` instances.
Manual construction allows empty mappings and any integer index. `errors` and
`results` are mutable dictionaries. Collected stream errors have empty `results`
because successes have already been yielded. The lowest task failure is the chained
cause when raised by either mapping function. Manual construction does not set a cause.
`results` uses `Any`: an except clause cannot retain a mapped function's result type.

The aggregate message contains the failure count, first index and a bounded type name.
It never formats task messages or results. Huge indices are described by bit length.
Original exceptions, the cause and result values remain available, and may contain
sensitive data. Tracebacks and errors propagated unchanged from caller code retain
that data. Pickling and copying retain subclass attributes when the contents support
those operations; as usual, only unpickle trusted data.

## Upgrading from 0.2.0

The function names, keyword names, defaults and result shapes remain compatible.
`ProgressCallback` is now a public structural protocol, counts are typed as
`SupportsIndex`, and pickles produced by 1.0.0 use public package paths. Old pickles
from 0.2.0 remain readable. New pickles also load with 0.2.0 for the shared API.
Error construction now validates mappings and copies them; aggregate messages omit
task text. Flags, callables and prefixes are validated before input consumption.
Unordered batches now retain callback arrival order. Ordered `thread_map` keeps
workers supplied behind a slow head; the streaming window stays bounded.
See the [CHANGELOG](https://github.com/JaviLianes8/threadfan/blob/main/CHANGELOG.md).
