# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- `workers` must be a real `int` (`TypeError` for `bool`, `float`, `str`) and is
  checked before `items` is read, also for empty input.

### Fixed

- A `KeyboardInterrupt` or `SystemExit` from a task, a failing `on_progress` or a
  failing source left every queued item running before the call returned. Every
  early exit now cancels queued items and waits only for running tasks.
- `ThreadMapError` could not be pickled.

## [0.1.0]

- First release: `thread_map` runs a typed function over an iterable on a bounded
  thread pool, with ordered or completion-order results, worker caps, a progress
  callback, and a choice between early stop and aggregated `ThreadMapError`.
