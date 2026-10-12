"""A watchdog so a scheduling regression fails the run instead of hanging it."""

from __future__ import annotations

import faulthandler
from collections.abc import Iterator

import pytest

TEST_TIMEOUT_SECONDS = 120


@pytest.fixture(autouse=True)
def _watchdog() -> Iterator[None]:
    faulthandler.dump_traceback_later(TEST_TIMEOUT_SECONDS, exit=True)
    yield
    faulthandler.cancel_dump_traceback_later()
