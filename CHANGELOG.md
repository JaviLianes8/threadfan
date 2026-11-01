# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-11-01

### Stable

- `thread_map`, `thread_imap`, `ThreadMapError` and `ProgressCallback`: bounded
  thread scheduling, input or completion ordering, context copying, progress,
  error collection and cancellation of queued tasks on early exits.

### Changed

- Export `ProgressCallback` as a structural protocol accepting two positional
  integers and any return value. Count annotations accept `SupportsIndex`.
- Validate callables and prefixes before reading input. Store a string subclass
  prefix as plain text. Evaluate flags and integer-like counts once at call time.
  `thread_imap` now calls `iter(items)` immediately, while item reads remain lazy.
- `ThreadMapError` accepts and copies mappings, sorts indices, and rejects
  noninteger or bool keys, nonmapping arguments and non-Exception failures.
  Its message omits task messages and results; long type names and huge integers
  have bounded descriptions. Original failures, results and cause remain accessible.
- Public definitions and new pickles use package-level names. Existing 0.2.0
  pickle paths remain readable; subclasses and their attributes still round-trip.
- Ordered `thread_map` bounds in-flight work separately from buffered results,
  keeping workers supplied behind a slow head. Streaming keeps its original bound.

### Fixed

- Unordered mode preserves completion callback arrival order within each batch
  instead of reordering that batch by input index. Simultaneous completions can tie.
- Cancel queued higher-index tasks as soon as an ordered task failure is observed.
- Drain a completion queue instead of rescanning all pending futures on each wakeup.
- Explicitly close the inner scheduler when a stream is closed.
- Preserve slotted subclass attributes when copying or pickling aggregate errors.

### Documentation and packaging

- Runnable examples, guide, Python 3.10 to 3.14 support and stable package metadata.
- Contract tests, standard-library comparisons, installed-wheel upgrade checks,
  seeded scheduling properties and deliberate mutation checks.

## [0.2.0]

### Added

- `thread_imap`: a lazy, typed generator over the same engine, for large or
  endless sources, in input or completion order.
- `max_pending`: at most this many items (default twice `workers`) are submitted
  and not yet consumed at once, so memory no longer grows with the input.
- `copy_context`: run each task in a copy of the caller's `contextvars` context.
- `thread_name_prefix`: name the worker threads.
- `ThreadMapError.results` keeps every successful value by input index, the
  message names the first failing index, and the first failure is the cause.

### Changed

- `ThreadMapError.errors` is sorted by input index instead of completion order.
- `workers` must be an integer (`TypeError` for `bool`, `float`, `str`; integer-like
  values such as numpy integers are accepted) and is checked before `items` is
  read, also for empty input.
- A `StopIteration` raised by `fn` or `on_progress` is re-raised unchanged.

### Fixed

- A `KeyboardInterrupt` or `SystemExit` from a task, a failing `on_progress` or a
  failing source left every queued item running before the call returned. Every
  early exit now cancels queued items and waits only for running tasks.
- `ThreadMapError` could not be pickled. Subclasses and their extra attributes
  now round-trip too.

## [0.1.0]

- First release: `thread_map` runs a typed function over an iterable on a bounded
  thread pool, with ordered or completion-order results, worker caps, a progress
  callback, and a choice between early stop and aggregated `ThreadMapError`.
