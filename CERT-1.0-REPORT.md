# threadfan 1.0.0 certification report

Progress:
- [x] Resume release branch and preserve its existing commit.
- [x] Fetch current PyPI metadata: 0.2.0 is published.
- [x] Review stable API, typing, errors and runnable documentation.
- [x] Add contracts for completion order, progress and single option evaluation.
- [ ] Fetch and execute reference examples and independent comparisons.
- [ ] Build, inspect and install distributions, including a 0.2.0 upgrade.
- [ ] Run every available supported interpreter.
- [ ] Complete the mutation round and record the table.
- [ ] Run the final four gates and prepare the release PR.
- [ ] Independent review (item 16), merge and publication (item 17).
- [ ] Five independent QA lenses (item 19).

## Starting state

Resumed `release/1.0.0` at `4ff515a` on 2026-11-01; no prior certification report
or saved lens verdicts were present. Baseline: 288 passed, one opt-in wheel test
skipped, one failure for the missing 1.0.0 changelog entry.
The existing release commit is retained. PyPI metadata was fetched from
https://pypi.org/pypi/threadfan/json on 2026-11-01: current release 0.2.0.

## API review

The four public names, signatures and defaults are pinned by contract tests.
`SupportsIndex` matches the already supported integer-like counts. Protocol
callbacks accept arbitrary positional parameter names and any return value.
Aggregate errors retain original exceptions and results but do not format task
messages. The original cause and propagated task errors can still contain caller
data. Public definitions use package paths; legacy pickle reconstruction is retained.
All release changes are recorded in the dated CHANGELOG and GUIDE.

## Review stages

Items 16 and 19 are pending. No independent reviewer or lens verdict is claimed.
Merge and publication remain pending.
