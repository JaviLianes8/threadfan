"""Build the wheel, install it in a throwaway venv and drive the installed package.

Slow and needs the build backend, so it runs only with THREADFAN_E2E=1.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tarfile
import venv
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    os.environ.get("THREADFAN_E2E") != "1", reason="set THREADFAN_E2E=1 to build and install"
)

PROGRAM = """
import contextvars, importlib.metadata, importlib.resources, itertools, pickle, threading
import threadfan
from threadfan import ThreadMapError, thread_imap, thread_map

assert threadfan.__file__.find("site-packages") != -1, threadfan.__file__
assert importlib.metadata.version("threadfan") == threadfan.__version__
assert importlib.resources.files("threadfan").joinpath("py.typed").is_file()

assert thread_map(lambda v: v * 2, range(100), workers=7) == [v * 2 for v in range(100)]

def fail_odd(v):
    if v % 2:
        raise ValueError(v)
    return v

try:
    thread_map(fail_odd, range(6), stop_on_error=False)
except ThreadMapError as error:
    clone = pickle.loads(pickle.dumps(error))
    assert list(clone.errors) == [1, 3, 5] and clone.results == {0: 0, 2: 2, 4: 4}
else:
    raise AssertionError("no error")

read = 0
def source():
    global read
    for v in itertools.count():
        read += 1
        yield v

stream = thread_imap(lambda v: v, source(), workers=2, max_pending=3,
                     thread_name_prefix="e2e")
assert [next(stream) for _ in range(10)] == list(range(10))
assert read - 10 < 3
stream.close()
assert not [t for t in threading.enumerate() if t.name.startswith("e2e")]

var = contextvars.ContextVar("var", default="unset")
var.set("set")
assert thread_map(lambda _: var.get(), range(2), copy_context=True) == ["set", "set"]
print("e2e ok")
"""

PICKLE_PROGRAM = """
import pathlib, pickle, sys
from threadfan import ThreadMapError, thread_imap, thread_map
folder = pathlib.Path(sys.argv[1])
mode = sys.argv[2]
for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
    path = folder / f"error-{protocol}.pickle"
    if mode == "write":
        data = (ThreadMapError({1: ValueError("bad")}, {0: "ok"}), thread_map, thread_imap)
        path.write_bytes(pickle.dumps(data, protocol))
    else:
        error, mapped, streamed = pickle.loads(path.read_bytes())
        assert error.results == {0: "ok"} and list(error.errors) == [1]
        assert error.errors[1].args == ("bad",)
        assert mapped is thread_map and streamed is thread_imap
"""


def _run(*cmd: str | Path, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, check=False, timeout=180
    )


def _consumer(python: Path, work: Path, version: str) -> subprocess.CompletedProcess[str]:
    program = PROGRAM + f"\nassert threadfan.__version__ == {version!r}\n"
    return _run(python, "-I", "-c", program, cwd=work)


def test_installed_wheel_end_to_end(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    built = _run(sys.executable, "-m", "build", "--outdir", dist, ROOT)
    assert built.returncode == 0, built.stderr
    (wheel,) = dist.glob("threadfan-*.whl")
    (sdist,) = dist.glob("threadfan-*.tar.gz")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        assert "threadfan/py.typed" in names
        assert any(name.endswith("licenses/LICENSE") for name in names)
        assert all(name.startswith(("threadfan/", "threadfan-1.0.0.dist-info/")) for name in names)
        assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)
        assert not any(name.endswith("entry_points.txt") for name in names)
    with tarfile.open(sdist) as archive:
        names = archive.getnames()
        assert "threadfan-1.0.0/LICENSE" in names
        assert "threadfan-1.0.0/GUIDE.md" in names
        assert "threadfan-1.0.0/tests/upstream/MANIFEST.json" in names
        assert not any(
            bad in name
            for name in names
            for bad in (".rst", "__pycache__", ".pyc", "CERT-", "IMPROVEMENTS-", ".venv")
        )
    checked = _run(sys.executable, "-m", "twine", "check", "--strict", wheel, sdist)
    assert checked.returncode == 0, checked.stdout + checked.stderr

    env_dir = tmp_path / "venv"
    venv.create(env_dir, with_pip=True)
    bindir = env_dir / ("Scripts" if sys.platform == "win32" else "bin")
    python = bindir / "python"
    installed = _run(python, "-m", "pip", "install", "-q", wheel)
    assert installed.returncode == 0, installed.stderr

    # Run from an empty folder so the source tree cannot shadow the install.
    work = tmp_path / "work"
    work.mkdir()
    result = _consumer(python, work, "1.0.0")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "e2e ok"

    if os.environ.get("THREADFAN_E2E_PYPI") == "1":
        installed = _run(python, "-m", "pip", "install", "--no-deps", "threadfan==0.2.0")
        assert installed.returncode == 0, installed.stderr
        old = _consumer(python, work, "0.2.0")
        assert old.returncode == 0, old.stderr
        saved = _run(python, "-I", "-c", PICKLE_PROGRAM, work, "write", cwd=work)
        assert saved.returncode == 0, saved.stderr
        installed = _run(python, "-m", "pip", "install", "--no-deps", "--upgrade", wheel)
        assert installed.returncode == 0, installed.stderr
        loaded = _run(python, "-I", "-c", PICKLE_PROGRAM, work, "read", cwd=work)
        assert loaded.returncode == 0, loaded.stderr
        result = _consumer(python, work, "1.0.0")
        assert result.returncode == 0, result.stderr
        saved = _run(python, "-I", "-c", PICKLE_PROGRAM, work, "write", cwd=work)
        assert saved.returncode == 0, saved.stderr
        installed = _run(python, "-m", "pip", "install", "--no-deps", "threadfan==0.2.0")
        assert installed.returncode == 0, installed.stderr
        loaded = _run(python, "-I", "-c", PICKLE_PROGRAM, work, "read", cwd=work)
        assert loaded.returncode == 0, loaded.stderr
        installed = _run(python, "-m", "pip", "install", "--no-deps", "--upgrade", wheel)
        assert installed.returncode == 0, installed.stderr
