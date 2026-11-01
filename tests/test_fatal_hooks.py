"""Hand-written contracts for fatal exceptions with misleading class properties."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future

import pytest

import threadfan._engine
from threadfan import ThreadMapError, thread_imap, thread_map


@pytest.fixture(params=[KeyboardInterrupt, SystemExit, BaseException])
def fatal(request: pytest.FixtureRequest) -> tuple[BaseException, list[str]]:
    lookups: list[str] = []

    def class_hook(self: BaseException) -> type[Exception]:
        lookups.append("__class__")
        return Exception

    cls = type("Fatal", (request.param,), {"__class__": property(class_hook)})
    return cls("task stopped"), lookups


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("ordered", [False, True])
@pytest.mark.parametrize("stop_on_error", [False, True])
def test_fatal_class_hooks_cannot_change_propagation(
    fatal: tuple[BaseException, list[str]], streaming: bool, ordered: bool, stop_on_error: bool
) -> None:
    failure, lookups = fatal

    def task(value: int) -> int:
        raise failure

    call = thread_imap if streaming else thread_map
    with pytest.raises(type(failure)) as info:
        list(call(task, [0], ordered=ordered, stop_on_error=stop_on_error))
    assert info.value is failure
    assert lookups == []


def test_constructor_rejects_fatal_exception_despite_class_hook(
    fatal: tuple[BaseException, list[str]],
) -> None:
    failure, lookups = fatal
    with pytest.raises(TypeError) as info:
        ThreadMapError({0: failure})  # type: ignore[dict-item]
    assert str(info.value) == "errors values must be exceptions, got Fatal"
    assert lookups == []


@pytest.mark.parametrize("streaming", [False, True])
def test_ordered_fatal_exception_preempts_an_earlier_failure(
    monkeypatch: pytest.MonkeyPatch, fatal: tuple[BaseException, list[str]], streaming: bool
) -> None:
    failure, lookups = fatal

    class Pool:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.futures: list[Future[int]] = []

        def submit(self, fn: Callable[[int], int], value: int) -> Future[int]:
            future: Future[int] = Future()
            self.futures.append(future)
            if value == 1:
                future.set_exception(failure)
                # The lower index finishes later and must not replace a fatal exception.
                self.futures[0].set_exception(ValueError("earlier item"))
            return future

        def shutdown(self, **kwargs: object) -> None:
            pass

    monkeypatch.setattr(threadfan._engine, "ThreadPoolExecutor", Pool)
    call = thread_imap if streaming else thread_map
    with pytest.raises(type(failure)) as info:
        list(call(abs, [0, 1], ordered=True, max_pending=2))
    assert info.value is failure
    assert lookups == []
