# threadfan

Typed, ordered parallel map over a bounded thread pool for IO-bound fan-out.

## Install

```
pip install threadfan
```

Python 3.10 or newer. No runtime dependencies.

## Usage

The examples below run as they are. `fetch` stands in for any slow IO call:

```python
import time

from threadfan import thread_map


def fetch(url: str) -> str:
    time.sleep(0.01)  # a network call in real code
    return f"body of {url}"


urls = [f"https://example.test/{n}" for n in range(20)]

# Runs in parallel, returns results in the same order as the input.
bodies = thread_map(fetch, urls, workers=8)
assert bodies[0] == "body of https://example.test/0"
```

Results keep the input order by default. Turn that off when you only care that
every item finishes and want them as they arrive:

```python
done = thread_map(fetch, urls, workers=8, ordered=False)
assert sorted(done) == sorted(bodies)
```

### Errors

By default the first failure is re-raised unchanged, queued items are cancelled,
and the call returns once the tasks already running finish. Set
`stop_on_error=False` to run every item and collect the failures instead. The
`ThreadMapError` keeps the failures and the successful results, both keyed by
input index and sorted:

```python
from threadfan import ThreadMapError


def parse(text: str) -> int:
    return int(text)


try:
    thread_map(parse, ["1", "two", "3", "four"], stop_on_error=False)
except ThreadMapError as error:
    assert list(error.errors) == [1, 3]
    assert error.results == {0: 1, 2: 3}
    print(error)  # 2 tasks failed; first at index 1: ValueError: ...
```

`KeyboardInterrupt` and `SystemExit` are never collected: they stop the run at once.

### Progress

`on_progress(completed, total)` runs in the calling thread after each item,
failures included, with `completed` going from 1 to `total`:

```python
thread_map(fetch, urls, workers=8, on_progress=lambda done, total: print(f"{done}/{total}"))
```

### Streaming large or endless sources

`thread_map` reads `items` in full to know the total. `thread_imap` is the lazy
version: it reads `items` only as fast as you consume results, so memory stays
bounded and endless sources work:

```python
import itertools

from threadfan import thread_imap

pages = (f"https://example.test/page/{n}" for n in itertools.count())
for body in thread_imap(fetch, pages, workers=4):
    if body.endswith("/5"):
        break  # the queued pages are cancelled when the stream is released
```

At most `max_pending` items (default twice `workers`) are submitted and not yet
yielded at any time. An ordered stream waits for its oldest item before yielding
later ones; pass `ordered=False` to get results as they complete. With
`stop_on_error=False` failed items are skipped and a `ThreadMapError` is raised
once the source is done.

### Options

| Option | Default | Meaning |
| --- | --- | --- |
| `workers` | 32, capped at the item count | Pool size. Must be an `int` of at least 1. |
| `ordered` | `True` | Input order, or completion order when false. |
| `stop_on_error` | `True` | Re-raise the first failure, or collect them all. |
| `max_pending` | `2 * workers` | Items submitted and not yet consumed at once. |
| `copy_context` | `False` | Run each task in a copy of the caller's `contextvars` context. |
| `thread_name_prefix` | `"threadfan"` | Prefix for the worker thread names. |
| `on_progress` | `None` | `thread_map` only: `(completed, total)` callback. |

Options are checked before any item is read: a non-`int` count raises
`TypeError`, a count below 1 raises `ValueError`, also for empty input.

`copy_context=True` makes context variables set by the caller visible in the
tasks, as `asyncio.to_thread` does. Each task gets its own copy, so changes made
inside a task never leak back:

```python
import contextvars

request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
request_id.set("req-7")
tags = thread_map(lambda _: request_id.get(), range(3), copy_context=True)
assert tags == ["req-7", "req-7", "req-7"]
```

The functions are fully typed, so the result type follows from the mapped
function: mapping `Callable[[int], str]` gives `list[str]` from `thread_map` and
`Generator[str, None, None]` from `thread_imap`.

## Why

The standard `ThreadPoolExecutor.map` is the usual tool for IO-bound fan-out, but
its controls are thin: it collects the whole input before starting (unless you
are on Python 3.14 and pass `buffersize`), its `chunksize` does nothing for
threads, it has no ordered-versus-as-completed switch, no progress hook, and its
error handling surfaces one failure at a time as you iterate. `threadfan` keeps
the simple `map` shape and adds the controls that are missing: a hard worker
bound, a bounded submission window, an order switch, a progress callback,
context propagation, and a choice between stopping on the first error or running
everything and raising one aggregated error.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
