"""Typed, ordered parallel map over a bounded thread pool for IO-bound fan-out."""

from __future__ import annotations

from ._map import ProgressCallback, ThreadMapError, thread_map

__version__ = "0.1.0"

__all__ = ["ProgressCallback", "ThreadMapError", "thread_map"]
