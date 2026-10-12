"""Typed, ordered parallel map over a bounded thread pool for IO-bound fan-out."""

from __future__ import annotations

from ._engine import ProgressCallback
from ._errors import ThreadMapError
from ._map import thread_imap, thread_map

__version__ = "0.2.0"

__all__ = ["ProgressCallback", "ThreadMapError", "thread_imap", "thread_map"]
