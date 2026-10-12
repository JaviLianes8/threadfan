"""Validation and defaults for the pool size and the submission window."""

from __future__ import annotations

import operator
from typing import SupportsIndex

MAX_DEFAULT_WORKERS = 32
"""Default pool size cap, the same ceiling the standard library uses."""


def check_count(name: str, value: object) -> int:
    """Return ``value`` as an ``int`` if it is an integer of at least 1, raise otherwise."""
    # bool is an int subclass, but ``workers=True`` is always a mistake.
    if isinstance(value, bool):
        raise TypeError(f"{name} must be an int, got bool")
    # Accept integer-like values too (numpy integers, anything with __index__).
    if not isinstance(value, SupportsIndex):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    count = operator.index(value)
    if count < 1:
        raise ValueError(f"{name} must be at least 1, got {count}")
    return count


def resolve_workers(workers: int | None, total: int | None = None) -> int:
    """Pick the pool size: the given value or the default, never above ``total``."""
    size = MAX_DEFAULT_WORKERS if workers is None else check_count("workers", workers)
    if total is not None and total > 0:
        size = min(size, total)
    return size


def resolve_window(max_pending: int | None, workers: int) -> int:
    """Pick how many items may be submitted and not yet consumed at once."""
    if max_pending is None:
        return 2 * workers
    return check_count("max_pending", max_pending)


def check_prefix(prefix: object) -> str:
    """Return the thread name prefix if it is a string."""
    if not isinstance(prefix, str):
        raise TypeError(f"thread_name_prefix must be a str, got {type(prefix).__name__}")
    return prefix
