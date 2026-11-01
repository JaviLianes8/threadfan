# Contributing

Thanks for taking the time. This project keeps a small, predictable shape.

## Setup

```
pip install -r requirements-dev.txt
```

## Before you open a pull request

- Keep public API in `src/threadfan/__init__.py`; internals live in `_`-prefixed modules.
- Add a test for the behaviour you change. Use events for deterministic thread
  ordering and bound every wait. Unit tests use local inputs; installed-wheel tests
  opt in with `THREADFAN_E2E=1` and use temporary directories.
- Run `scripts/check.ps1` (format, lint, types, tests) and make sure it passes.
- One logical change per commit, imperative subject line.

Open an issue first if the change is large or shifts the public API.

`python scripts/fetch_upstream.py DIRECTORY` fetches hash-pinned Python reference
documents. Set `THREADFAN_UPSTREAM` to that directory to run their tests; they skip
when the documents are absent. Set `THREADFAN_E2E_PYPI=1` with `THREADFAN_E2E=1`
to also install PyPI 0.2.0 and check upgrades and pickle compatibility.
