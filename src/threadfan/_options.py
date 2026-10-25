"""Validation and defaults for the options, all checked before any item is read."""

from __future__ import annotations

import operator
from typing import SupportsIndex, cast

MAX_DEFAULT_WORKERS = 32
"""Default pool size cap, the same ceiling the standard library uses."""

_NAME_LIMIT = 60
_SMALL = 10**15


def type_name(value: object) -> str:
    """The name of ``value``'s type, cut so that a huge class name stays out of messages."""
    name = type(value).__name__
    return name if len(name) <= _NAME_LIMIT else name[: _NAME_LIMIT - 3] + "..."


def show_int(value: int) -> str:
    """``value`` in decimal, or its size when the digits would flood a message."""
    if -_SMALL < value < _SMALL:
        return int.__repr__(value)
    return f"an integer of {value.bit_length()} bits"


def check_count(name: str, value: object) -> int:
    """Return ``value`` as an ``int`` if it is an integer of at least 1, raise otherwise."""
    # bool is an int subclass, but ``workers=True`` is always a mistake.
    if isinstance(value, bool):
        raise TypeError(f"{name} must be an int, got bool")
    # Integer-like values work too (numpy integers, anything with __index__).
    try:
        count = operator.index(cast(SupportsIndex, value))
    except TypeError:
        raise TypeError(f"{name} must be an int, got {type_name(value)}") from None
    if count < 1:
        raise ValueError(f"{name} must be at least 1, got {show_int(count)}")
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
    """Return the thread name prefix as a plain ``str``, raise if it is not a string."""
    if not isinstance(prefix, str):
        raise TypeError(f"thread_name_prefix must be a str, got {type_name(prefix)}")
    # A plain copy: a str subclass could override how the pool formats the names.
    return str.__str__(prefix)


def check_callable(name: str, value: object) -> None:
    """Raise ``TypeError`` unless ``value`` can be called."""
    if not callable(value):
        raise TypeError(f"{name} must be callable, got {type_name(value)}")
