"""Seeded random runs compared with the builtin ``map`` as ground truth."""

from __future__ import annotations

import contextlib
import random
import time
from collections.abc import Callable

import pytest

from threadfan import ThreadMapError, thread_imap, thread_map

SEEDS = range(40)


Case = tuple[list[int], Callable[[int], int], set[int], "int | None", "int | None"]


def _case(seed: int) -> Case:
    rng = random.Random(seed)
    items = rng.sample(range(10_000), rng.randint(0, 40))
    delays = {item: rng.choice([0.0, 0.0, 0.001, 0.003]) for item in items}
    failing = {item for item in items if rng.random() < 0.2}

    def fn(item: int) -> int:
        time.sleep(delays[item])
        if item in failing:
            raise ValueError(f"item {item}")
        return item * 3 + 1

    workers: int | None = rng.choice([None, 1, 2, 3, 8])
    pending: int | None = rng.choice([None, 1, 2, 5])
    return items, fn, failing, workers, pending


def _oracle(fn: Callable[[int], int], items: list[int], failing: set[int]) -> list[int]:
    return list(map(fn, [item for item in items if item not in failing]))


@pytest.mark.parametrize("seed", SEEDS)
def test_thread_map_matches_builtin_map(seed: int) -> None:
    items, fn, failing, workers, pending = _case(seed)
    expected = _oracle(fn, items, failing)
    if not failing:
        assert thread_map(fn, items, workers=workers, max_pending=pending) == expected
        unordered = thread_map(fn, items, ordered=False, workers=workers, max_pending=pending)
        assert sorted(unordered) == sorted(expected)
        return
    with pytest.raises(ThreadMapError) as info:
        thread_map(fn, items, stop_on_error=False, workers=workers, max_pending=pending)
    failed_indices = {index for index, item in enumerate(items) if item in failing}
    assert set(info.value.errors) == failed_indices
    assert list(info.value.results.values()) == expected
    for index, error in info.value.errors.items():
        assert str(error) == f"item {items[index]}"


@pytest.mark.parametrize("seed", SEEDS)
def test_thread_imap_matches_builtin_map(seed: int) -> None:
    items, fn, failing, workers, pending = _case(seed)
    expected = _oracle(fn, items, failing)
    seen: list[int] = []
    if failing:
        with pytest.raises(ThreadMapError) as info:
            seen.extend(
                thread_imap(fn, items, stop_on_error=False, workers=workers, max_pending=pending)
            )
        assert {items[index] for index in info.value.errors} == failing
    else:
        seen.extend(thread_imap(fn, items, workers=workers, max_pending=pending))
    assert seen == expected
    unordered = thread_imap(
        fn, items, ordered=False, stop_on_error=False, workers=workers, max_pending=pending
    )
    collected: list[int] = []
    with contextlib.suppress(ThreadMapError):
        collected.extend(unordered)
    assert sorted(collected) == sorted(expected)


@pytest.mark.parametrize("seed", SEEDS)
def test_stop_on_error_raises_one_of_the_real_failures(seed: int) -> None:
    items, fn, failing, workers, pending = _case(seed)
    if not failing:
        return
    with pytest.raises(ValueError) as info:
        thread_map(fn, items, workers=workers, max_pending=pending)
    assert str(info.value) in {f"item {item}" for item in failing}
