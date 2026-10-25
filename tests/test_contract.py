from __future__ import annotations

import importlib.resources

import threadfan

# The public API. Add every exported name here as the library grows; this list is the
# contract and the test below fails if the module and this list disagree.
PUBLIC_API: list[str] = [
    "ProgressCallback",
    "ThreadMapError",
    "thread_imap",
    "thread_map",
]


def test_all_lists_exactly_the_public_api() -> None:
    assert sorted(threadfan.__all__) == sorted(PUBLIC_API)


def test_nothing_else_is_public_at_the_package_top() -> None:
    public = [name for name in dir(threadfan) if not name.startswith("_")]
    assert sorted(public) == sorted(PUBLIC_API)


def test_every_exported_name_resolves() -> None:
    for name in threadfan.__all__:
        assert hasattr(threadfan, name)


def test_version_is_a_three_part_string() -> None:
    parts = threadfan.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


def test_the_package_ships_type_information() -> None:
    assert importlib.resources.files("threadfan").joinpath("py.typed").is_file()
