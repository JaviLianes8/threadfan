"""Typed, ordered parallel map over a bounded thread pool for IO-bound fan-out."""

from ._errors import ThreadMapError
from ._map import thread_imap, thread_map
from ._progress import ProgressCallback

__version__ = "1.0.0"

# The public names show and pickle as threadfan.<name>, so nothing outside depends on
# the private module that defines them.
for _public in (ProgressCallback, ThreadMapError, thread_imap, thread_map):
    _public.__module__ = __name__
del _public

__all__ = ["ProgressCallback", "ThreadMapError", "thread_imap", "thread_map"]
