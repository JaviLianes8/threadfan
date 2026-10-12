# threadfan

Typed, ordered parallel map over a bounded thread pool for IO-bound fan-out.

## Install

```
pip install threadfan
```

## Usage

```python
from threadfan import thread_map

urls = ["https://a.test", "https://b.test", "https://c.test"]

# Runs in parallel, returns results in the same order as the input.
bodies = thread_map(fetch, urls, workers=8)
```

Results keep the input order by default. Turn that off when you only care that
every item finishes and want them as they arrive:

```python
done = thread_map(fetch, urls, workers=8, ordered=False)
```

By default the first failure cancels the rest and is re-raised. Set
`stop_on_error=False` to run every item and collect the failures instead:

```python
from threadfan import ThreadMapError

try:
    results = thread_map(fetch, urls, workers=8, stop_on_error=False)
except ThreadMapError as error:
    for index, failure in error.errors.items():
        print(index, failure)
```

Pass `on_progress` to track completion as a `(completed, total)` pair:

```python
thread_map(fetch, urls, workers=8, on_progress=lambda done, total: print(done, total))
```

`workers` defaults to a sensible cap and is never set higher than the number of
items. The function is fully typed, so the result type follows from the mapped
function: mapping `Callable[[int], str]` yields a `list[str]`.

## Why

The standard `ThreadPoolExecutor.map` is the usual tool for IO-bound fan-out, but
its controls are thin: its `chunksize` argument does nothing for threads, it has
no ordered-versus-as-completed switch, no progress hook, and its error handling
surfaces one failure at a time as you iterate. `threadfan` keeps the simple
`map` shape and adds the controls that are missing: a hard worker bound, an
order switch, a progress callback, and a choice between stopping on the first
error or running everything and raising one aggregated error. It has no runtime
dependencies beyond the standard library.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
