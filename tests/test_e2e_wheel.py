"""Build the wheel, install it in a throwaway venv and drive the installed package.

Slow and needs the build backend, so it runs only with THREADFAN_E2E=1.
"""

from __future__ import annotations

import os
import subprocess
import sys
import venv
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
assert read - 10 <= 3
stream.close()
assert not [t for t in threading.enumerate() if t.name.startswith("e2e")]

var = contextvars.ContextVar("var", default="unset")
var.set("set")
assert thread_map(lambda _: var.get(), range(2), copy_context=True) == ["set", "set"]
print("e2e ok")
"""


def _run(*cmd: str | Path, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, check=False
    )


def test_installed_wheel_end_to_end(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    built = _run(sys.executable, "-m", "build", "--wheel", "--outdir", dist, ROOT)
    assert built.returncode == 0, built.stderr
    (wheel,) = dist.glob("threadfan-*.whl")

    env_dir = tmp_path / "venv"
    venv.create(env_dir, with_pip=True)
    bindir = env_dir / ("Scripts" if sys.platform == "win32" else "bin")
    python = bindir / "python"
    installed = _run(python, "-m", "pip", "install", "-q", wheel)
    assert installed.returncode == 0, installed.stderr

    # Run from an empty folder so the source tree cannot shadow the install.
    work = tmp_path / "work"
    work.mkdir()
    result = _run(python, "-I", "-c", PROGRAM, cwd=work)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "e2e ok"
