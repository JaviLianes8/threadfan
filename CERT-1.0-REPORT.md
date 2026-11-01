# threadfan 1.0.0 certification report

Progress:
- [x] Resume and preserve the existing release branch commit.
- [x] Stable API, typed errors, runnable docs and complete contracts (items 1-6).
- [x] Fetched ground truth, seeded properties and installed-wheel upgrade (items 7-9).
- [x] Every supported Python minor tested, including free-threaded 3.14 (item 10).
- [x] README, guide, changelog, metadata and archive inspection (items 11-14).
- [x] Four gates and 23 deliberate mutations (items 15 and 18).
- [x] Release PR [#3](https://github.com/JaviLianes8/threadfan/pull/3) prepared.
- [x] QA round 1 fixes for C-01, C-02 and E-01 through E-07, with regression evidence.
- [x] QA round 2 fixes for C-03 and E-08, with regression and mutation evidence.
- [x] QA round 3 fix for E-09, with regression and mutation evidence.
- [x] Independent review round 1 fixes for CERT-05 and CERT-06.
- [ ] Independent reviewer (item 16).
- [ ] Merge and publication (item 17).
- [ ] Five independent QA lenses (item 19).

## Scorecard

| Item | Verdict | Evidence |
| --- | --- | --- |
| 1. Stable API | PASS | Four public names; signatures, defaults and parameter names pinned; all changes in CHANGELOG. |
| 2. Exact exports | PASS | Exact `__all__`, no extra public attributes, public module paths and pickle names tested. |
| 3. Runnable docstrings | PASS | All four public docstrings, README and GUIDE examples executed. |
| 4. Strict typing | PASS | `mypy --strict src tests`; installed-wheel typing consumer; `py.typed` shipped; error results' `Any` documented. |
| 5. Errors | PASS | Typed validation errors; aggregate messages omit task text and results, bound type names and huge indices. Original caller errors remain accessible. |
| 6. Full contracts | PASS | 486 passing tests including source, options, ordering, progress, cancellation, pickles, class hooks and installed consumers. |
| 7. Ground truth | PASS | Hash-pinned Python reference examples extracted and executed; live builtin and executor comparisons. |
| 8. Real e2e | PASS | Wheel installed in a fresh venv; isolated subprocess consumer; actual 0.2.0 upgrade and bidirectional pickles. No CLI exists. |
| 9. Seeded properties | PASS | 160 seeded oracle cases plus 1,500 additional cases; 20k/80k scaling in all four scheduling modes. |
| 10. Interpreters | PASS | Seven CPython builds, 3.10 through 3.14, including 3.14 without the GIL; table below. |
| 11. README | PASS | Problem, honest executor comparison, absolute links, badge, examples and guide; strict twine check. |
| 12. CHANGELOG | PASS | Dated 1.0.0 section: 2026-11-01, including every behavior change from 0.2.0. |
| 13. Metadata | PASS | 1.0.0, Production/Stable, Python >=3.10, 3.10-3.14 classifiers, MIT, project URLs, keywords, no runtime dependencies. |
| 14. Archives | PASS | Wheel and sdist inspected; LICENSE and typing marker included; no fetched documents, caches or working notes. |
| 15. Gates | PASS | Format, lint, strict source typing and pytest exit 0; source and tests also pass strict typing together. |
| 16. Independent reviewer | PENDING | Round 1 findings CERT-05 and CERT-06 are fixed below; independent re-review remains pending. |
| 17. Release | PREPARED | PR #3, branch `release/1.0.0`; merge and publication pending. |
| 18. Mutation round | PASS | Original 23/23 variants caught; all seven round 1 survivors, round 2 N21, round 3 M05 and six independent-review regression mutations caught. |
| 19. QA lenses | PENDING | e reported FAIL in round 3; E-09 fixed below, awaiting independent re-review. Earlier lens verdicts are unchanged. |

## API and compatibility

Resumed at `4ff515a` on 2026-11-01 with no certification report or saved lens verdicts.
Baseline: 288 passed, one opt-in wheel skip, one missing-changelog failure. The existing
commit is preserved. Initial runtime validation below used `54dfbdf`; later changes add
explicit installed-version assertions and this report. QA changes are recorded
in the round 1 through round 3 sections below.

The stable exports are `thread_map`, `thread_imap`, `ThreadMapError` and
`ProgressCallback`. Count annotations now match integer-like inputs (`SupportsIndex`).
Options are evaluated before input consumption; unordered batches follow callback
arrival order. Ordered eager mapping can replenish work behind an unfinished head,
while streaming retains an exact bounded window. Error messages omit task values;
original exceptions and the chained cause still contain caller data, as documented.
Copies and pickles retain dictionary and slot attributes of exception subclasses.
Legacy 0.2.0 reconstruction paths remain readable. All differences are in the CHANGELOG.

## Ground truth

Fetched on 2026-11-01 by `scripts/fetch_upstream.py`:

- https://raw.githubusercontent.com/python/cpython/v3.14.0/Doc/library/concurrent.futures.rst
- https://raw.githubusercontent.com/python/cpython/v3.14.0/Doc/library/contextvars.rst

`tests/upstream/MANIFEST.json` records URL, revision, date, size, SHA-256 and licence.
Copies remain outside the repository; tests verify hashes and skip if files are absent.
`test_ground_truth` extracts the actual executor example operands and compares both
entry points with a real executor. It executes the context example extracted from the
fetched document, checks the extracted expected output, and checks both mapping
functions against the resulting context. Additional inputs are explicitly hand-written;
their oracle is a real executor, including the lowest-index exception and its arguments.
`test_oracle` compares with real builtin `map` across 40 seeds in four tests.

## Properties and robustness

The additional run uses seeds 211, 1207 and 99173, 500 cases each: random input sizes,
values, failure positions, worker counts, window sizes and order modes. Both functions
agree on values, error indices and partial results. All 1,500 cases pass.
For 20,000 versus 80,000 items, observed times in seconds were:

| Mode | 20k | 80k | Ratio |
| --- | --- | --- | --- |
| Ordered stream | 0.272 | 1.072 | 3.95 |
| Ordered list | 0.275 | 1.092 | 3.98 |
| Unordered stream | 0.255 | 1.038 | 4.07 |
| Unordered list | 0.289 | 1.577 | 5.45 |

Exact window contracts cover endless sources. Collected failures intentionally occupy
memory until the source ends, and the guide states this limitation. Large messages,
unprintable exceptions, huge integer indices and invalid option types are covered.
Each pytest case has a 300-second timeout. A cancellation test's timing assumption
was replaced with event-controlled queued work after the free-threaded run exposed it.

## Packaging and Python matrix

Fetched https://pypi.org/pypi/threadfan/json on 2026-11-01: 0.2.0 is published.
`test_e2e_wheel` builds both distributions, inspects contents, runs `twine check --strict`,
installs the wheel into a fresh venv, and executes a consumer via `python -I` from an
empty directory. It checks values, errors, context, bounded streaming and thread cleanup.
The opt-in upgrade test explicitly asserts 0.2.0 before upgrade and 1.0.0 afterwards;
all pickle protocols are exchanged in both directions for the shared API.
There is no CLI, `__main__` or console entry point.

The wheel has 11 entries: package modules, `py.typed`, metadata and LICENSE. The sdist
has 37 entries: source, tests, manifest, docs, development scripts and metadata. No
fetched reference text, caches, venvs or certification notes are shipped.
Initial wheel SHA-256: `2d88ee94fb4effa91057499fb50d09675df3e6bf54bd3aa0e1967acf73a5cbd7`.
Initial sdist SHA-256: `a8b8c2da212781914271a26cc73e95d3c611fbe465d5881c787a809c2a04abf6`.

The installed-wheel suite was taken from an extracted sdist with its `src` directory
removed and pytest's source path disabled. Every import resolves under `site-packages`.
The initial wheel is byte-identical to the wheel used throughout this matrix:

| CPython | Passed | Skipped |
| --- | --- | --- |
| 3.10.22 | 323 | 2 |
| 3.11.18 | 324 | 1 |
| 3.12.16 | 324 | 1 |
| 3.13.18 | 324 | 1 |
| 3.14.6 (system install) | 324 | 1 |
| 3.14.10 | 324 | 1 |
| 3.14.10 free-threaded | 324 | 1 |

The common skip is the separately executed build/e2e test; 3.10 also skips `add_note`,
which starts in 3.11. Public doctests run through the explicit documentation contract.
The free-threaded interpreter reports `sys._is_gil_enabled() == False` with test
imports loaded. Older launcher registrations were stale; isolated interpreters were
downloaded without changing registrations. No supported minor version remains untested.

## Mutation round

Each variant changes one behavior in a scratch copy of the runtime source at `54dfbdf`.
The normal contract/doctest suite runs with `-x` and the 300-second test timeout;
the optional build/e2e test is excluded. Every variant exits 1 with an actual failing
test, and the source is restored before the next variant. All 23 are killed.

| # | Deliberate bug | First failing contract |
| --- | --- | --- |
| 1 | Drop slotted exception state | `tests/test_errors.py::test_subclass_slot_attributes_survive_pickling[0]` |
| 2 | Allow one extra pending stream item | `tests/test_imap.py::test_endless_source_is_read_only_ahead_by_the_window[True]` |
| 3 | Halve the default window | `tests/test_regressions.py::test_a_stream_closed_inside_its_own_worker_does_not_join_itself` |
| 4 | Shift collected error indices by one | `doctest: ThreadMapError` |
| 5 | Disable error collection | `doctest: ThreadMapError` |
| 6 | Reuse one context for every task | `tests/test_options.py::test_context_changes_inside_tasks_do_not_leak` |
| 7 | Disable context propagation | `tests/test_docs.py::test_every_readme_example_runs_in_order` |
| 8 | Leave queued futures uncancelled | `tests/test_window_contract.py::test_eager_map_replenishes_behind_an_unfinished_head` |
| 9 | Offset progress by one | `doctest: ProgressCallback` |
| 10 | Discard callback failures | `tests/test_regressions.py::test_stop_iteration_from_progress_is_reraised_unchanged` |
| 11 | Reverse eager results | `doctest: ProgressCallback` |
| 12 | Lose partial results | `doctest: ThreadMapError` |
| 13 | Chain the highest failure | `tests/test_errors.py::test_the_first_failure_is_the_cause` |
| 14 | Keep mappings in completion order | `tests/test_errors.py::test_errors_are_sorted_by_input_index` |
| 15 | Raise the wrong error for bool counts | `tests/test_options.py::test_non_int_counts_are_type_errors[workers-True]` |
| 16 | Accept zero counts | `tests/test_imap.py::test_options_are_validated_when_called_not_when_iterated` |
| 17 | Remove the item-count worker cap | `tests/test_options.py::test_pool_size_is_capped_by_items_and_default[None-3-3]` |
| 18 | Change the default worker count to 31 | `tests/test_options.py::test_pool_size_is_capped_by_items_and_default[None-100-32]` |
| 19 | Expose task error text | `doctest: ThreadMapError` |
| 20 | Block eager work behind the head | `tests/test_window_contract.py::test_eager_map_replenishes_behind_an_unfinished_head` |
| 21 | Discard source errors | `tests/test_regressions.py::test_items_read_before_a_failing_source_are_still_yielded[True]` |
| 22 | Ignore the worker-name prefix | `tests/test_options.py::test_worker_threads_carry_the_prefix_as_the_standard_library_names_them` |
| 23 | Reverse completed callback batches | `tests/test_scheduling_contract.py::test_unordered_batches_keep_callback_order[False-False]` |

## Initial gates and remaining stages

On 2026-11-01: `ruff format --check .`, `ruff check .`, `mypy --strict src`,
`mypy --strict src tests`, and pytest with `THREADFAN_UPSTREAM`, `THREADFAN_E2E=1`
and `THREADFAN_E2E_PYPI=1` all succeed. Final source run: **329 passed, no skips**.
All Python source files are at most 200 lines. The README badge matches the reference.

Items 1-15 and 18 are complete. Independent review and lenses a-e remain pending;
no verdict is carried forward. PR #3 is open; merge and publication remain pending.

## QA lenses, round 1

Review target: `b7d3cfecdf9e54c1832458df4ac6d9e78d46ecdc`, on 2026-11-01.
Implementation commit: `125136bd6fe2989f4ecb580b480867e0dc117624`
(`fix aggregate formatting and close QA contract gaps`).
Lens c reported two medium behavior defects; lens e reported seven medium contract
gaps. All nine findings are addressed. Independent lens re-review remains pending.

| Finding | Change and regression evidence |
| --- | --- |
| C-01 | Normalize accepted integer subclasses to built-in ints in both mappings before sorting and formatting. `test_error_indices.py` covers hostile conversion/comparison hooks, reversed comparisons, and oversized bit-length output for positive and negative indices. |
| C-02 | Read names through the built-in type descriptor, convert to plain str, then enforce the existing bound. `test_error_type_names.py` covers metaclass lookup and properties, string hooks, long names, collection through both APIs, and invalid options. |
| E-01 / M29 | `test_progress_return_values_do_not_stop_results` checks False, 0, None, empty text and a truthy object in both ordering modes; all values and progress calls survive. Mutation caught. |
| E-02 / M42 | `test_observed_failure_cancels_tail_before_consumer_resumes` uses real workers and event gates to prove queued futures are cancelled while the ordered consumer is suspended. Mutation caught. |
| E-03 / M52 | `test_installed_wheel_end_to_end` exchanges actual 0.2.0 and 1.0.0 pickles for subclasses slotting results and both mappings, for protocols 0-5. Each producing version also reloads its output. Mutation caught at the old-to-new results assertion. |
| E-04 / M55 | `test_map_captures_context_before_materializing_the_source` mutates the source's ContextVar, checks tasks retain the call-time value and the caller retains the source's change. Mutation caught. |
| E-05 / M59 | `test_sorted_dictionary_inputs_are_independent_copies` mutates sorted ordinary input dictionaries and exposed mappings independently, for errors and results. Mutation caught. |
| E-06 / M60 | `test_negative_indices_sort_with_zero_and_positive_indices` checks negative, zero and positive indices in both mappings. Mutation caught. |
| E-07 / M61 | `test_boolean_indices_are_rejected_in_both_mappings` rejects False and True in errors and results. Mutation caught. |

Before production changes, the added index/type-name contracts produced **58 failures
and 8 passes** on the reviewed code. After correction, all **66 pass**. The five original
lens c subclass reproductions also pass. Each of the seven lens e mutations was applied
separately in a scratch copy; each produced a test failure (exit 1), with no collection
or environment errors. The unchanged runtime behavior behind E-01 through E-07 needed
additional contracts only. Both behavior changes are recorded in CHANGELOG and the
integer normalization is documented in the guide and public error docstring.

Validation on CPython 3.14.6: `ruff format --check .`, `ruff check .`,
`mypy --strict src`, `mypy --strict src tests`, and the complete pytest suite exit 0.
With `THREADFAN_UPSTREAM`, `THREADFAN_E2E=1` and `THREADFAN_E2E_PYPI=1`, the result is
**408 passed, no skips**, including installed-wheel, archive, typing and real-version
upgrade checks. Every pytest case has a 300-second timeout and all temporary artifacts
are under the dedicated certification scratch directory's `qa-fix-r1/` folder.
That directory retains `red.xml`, `green.xml`, `reviewer-repros.xml`, `final.xml`, and
`mutation-results.json` with the individual mutation logs and JUnit files.
All Python source files remain at most 200 lines. The initial interpreter matrix above
predates this round; no new cross-version matrix result is claimed here.

## QA lenses, round 2

Review target: `262fbb49b8e6ef2edca8a11a1f53ff7b3febca39`, on 2026-11-01.
Implementation commit: `47092016c545256563ca3d7c94bf28f374568dda`
(`fix aggregate class lookup and strengthen error contracts`).
Lens c reported one medium behavior defect; lens e reported one medium contract gap.
Both findings are addressed. Independent lens re-review remains pending.

| Finding | Change and regression evidence |
| --- | --- |
| C-03 | Validate keys using their actual type, reject bool, then normalize real integer subclasses with `int.__int__`. `test_integer_subclasses_use_builtin_order_and_storage[ClassLookupIndex-errors]` and its results case exercise a raising `__class__` hook, numeric sorting, built-in int storage and value identity. Bool and spoofed integer classes remain rejected in both mappings. |
| E-08 / N21 | `test_aggregate_type_name_bypasses_instance_class_property` checks a raising exception `__class__` property through direct construction, `thread_map` and `thread_imap`. Each case preserves the original exception and exact actual type name; collected failures retain the cause. The existing runtime type-name lookup is unchanged. N21 is caught in all three cases. |

Before the runtime fix, the focused contracts produced **2 failures and 71 passes**;
both failures were the C-03 cases and raised the reported RuntimeError. After correction,
all **73 pass**. N21 was applied only in a scratch source copy, replacing `type(value)`
with `value.__class__` in `type_name`. The three new E-08 cases passed before mutation,
failed with the intended RuntimeError under N21 (exit 1), and passed after byte-for-byte
restoration. No collection or environment errors counted as mutation failures.
The key-validation behavior change is recorded in CHANGELOG; public signatures are unchanged.

Validation on CPython 3.14.6: `ruff format --check .`, `ruff check .`,
`mypy --strict src`, `mypy --strict src tests`, and the complete pytest suite exit 0.
With freshly fetched, hash-verified references, `THREADFAN_E2E=1` and
`THREADFAN_E2E_PYPI=1`, the result is **415 passed, no skips**, including installed-wheel,
archive, typing and real-version upgrade checks. Every pytest case has a 300-second
timeout. New temporary artifacts and evidence are under the certification scratch
directory's `qa-fix-r2/` folder: `red.xml`, `green.xml`, `full.xml`, `N21-results.json`
and the corresponding console logs and mutation JUnit files.
All Python source files remain at most 200 lines. The initial interpreter matrix above
predates this round; no new cross-version matrix result is claimed here.

## QA lenses, round 3

Review target: `9c55f7fae2bc00cd61181a3a265bade5a8fca6d9`, on 2026-11-01.
Implementation commit: `28fd01e5e6164d37e4cd1de476c23724dd5f19b1`
(`test invalid aggregate key class hooks`).
Lens e reported one medium contract gap, E-09. It is addressed below;
independent lens re-review remains pending.

| Finding | Change and regression evidence |
| --- | --- |
| E-09 / M05 | `test_invalid_index_class_property_cannot_replace_type_error` supplies a non-integer key with a raising `__class__` property to each mapping. Both cases assert `TypeError`, the exact message naming the actual key type, and zero property calls. Both fail under M05. |

The current runtime already satisfies this contract. The change adds two regression
cases and records the coverage in CHANGELOG; runtime behavior and public APIs are unchanged.
All **22 index tests pass** on the original code. In a scratch source copy, M05 replaces
`issubclass(index_type, int)` with `isinstance(index, int)` in `_errors._by_index`.
The result is **2 failures and 20 passes** (exit 1): both new cases raise the hook's
RuntimeError. After byte-for-byte restoration, all **22 pass** again. The scratch runs
assert the imported source path before collection; no setup or collection error is
counted as a mutation failure.

Validation on CPython 3.14.6: `ruff format --check .`, `ruff check .`,
`mypy --strict src`, `mypy --strict src tests`, and the complete pytest suite exit 0.
With freshly fetched, hash-verified references, `THREADFAN_E2E=1` and
`THREADFAN_E2E_PYPI=1`, the result is **417 passed, no skips**, including installed-wheel,
archive, typing and real-version upgrade checks. Every pytest case has a 300-second
timeout. Temporary artifacts and evidence are under the certification scratch
directory's `qa-fix-r3/` folder. `logs/` retains `M05-results.json`, the exact patch,
original/mutant/restored console logs and JUnit files, and the release gate results.
All Python source files remain at most 200 lines. The initial interpreter matrix above
predates this round; no new cross-version matrix result is claimed here.

## QA independent review, round 1

Review target: `53f7b2b0853fbf26498589fb726e79dc1fd10772`, on 2026-11-01.
Implementation commit: `3db157c8c0addb2da19b7d7e4d336475c5ccf90b`
(`fix runtime type validation and fatal exception handling`).
The independent reviewer reported two medium findings, CERT-05 and CERT-06.
Both are addressed; independent re-review remains pending. No finding is disputed.

| Finding | Change and regression evidence |
| --- | --- |
| CERT-05 | Reject bool counts by exact type, retain index conversion, and validate prefixes, mappings and failure values by actual type inheritance. Registered mappings remain accepted. The scheduler classifies failures by actual exception inheritance, preserving fatal exception identity and precedence over ordered ordinary failures. Public signatures and defaults are unchanged; all behavior changes are in CHANGELOG. |
| CERT-06 | Add 69 public regression cases in `test_validation_hooks.py` and `test_fatal_hooks.py`: both APIs and count options, valid integer/index-convertible counts, invalid options before input access, both aggregate mappings, invalid failure values, registered mappings, and fatal exception subclasses in both ordering and collection modes. They assert exact validation errors, no class-property access, and original fatal exception identity. |

Before production edits, all **69 new contracts failed** on the reviewed code.
The independent reviewer's original reproduction separately produced **17 failures**.
After the fix, all **69 contracts and 17 reviewer checks pass**.

Six separate mutations restore each defective boundary in a scratch source copy.
Every mutation exits 1 with actual test failures and no collection or setup errors.
The original and byte-for-byte restored copies each pass all 69 focused contracts.

| Mutation | Reintroduced defect | Failing contract |
| --- | --- | --- |
| M01 | Instance-based bool rejection | `test_valid_counts_ignore_class_hooks` |
| M02 | Instance-based prefix validation | `test_invalid_options_ignore_class_hooks_before_reading_input` |
| M03 | Instance-based Mapping validation | `test_invalid_aggregate_arguments_ignore_class_hooks`, `test_registered_mappings_ignore_class_hooks` |
| M04 | Instance-based aggregate failure validation | `test_invalid_aggregate_arguments_ignore_class_hooks`, `test_constructor_rejects_fatal_exception_despite_class_hook` |
| M05 | Instance-based classification for error collection | `test_fatal_class_hooks_cannot_change_propagation` |
| M06 | Instance-based classification for ordered failures | `test_fatal_class_hooks_cannot_change_propagation`, `test_ordered_fatal_exception_preempts_an_earlier_failure` |

Validation on CPython 3.14.6: `ruff format --check .`, `ruff check .`,
`mypy --strict src`, `mypy --strict src tests`, and pytest all exit 0.
With freshly fetched, hash-verified references, `THREADFAN_E2E=1` and
`THREADFAN_E2E_PYPI=1`, the complete suite reports **486 passed, no skips**,
including wheel installation, archive checks and real 0.2.0 upgrade/pickle checks.
Each pytest case has a 300-second timeout. All Python source files remain at most
200 lines. Evidence is retained in the certification scratch directory's
`review-fix-r1/` folder: `logs/red-contracts.*`, `logs/red-reviewer.*`,
`logs/green-contracts.*`, `logs/green-reviewer.*`, `logs/final-*`,
`logs/M01.*` through `logs/M06.*` and `mutations/results.json`.

The installed wheel separately passes all **86 focused checks** (69 new contracts
and the reviewer's 17 cases), with its site-packages import path asserted before
collection. See `logs/installed-contracts.*`.

| Runtime | Passed | Skipped |
| --- | ---: | ---: |
| CPython 3.10.22 | 484 | 2 |
| CPython 3.11.18 | 485 | 1 |
| CPython 3.12.16 | 485 | 1 |
| CPython 3.13.18 | 485 | 1 |
| CPython 3.14.6 | 486 | 0 |
| CPython 3.14.10 | 485 | 1 |
| CPython 3.14.10 free-threaded, GIL disabled | 485 | 1 |

The matrix skips only the separately executed wheel test; Python 3.10 also skips
the unavailable `add_note` feature. `logs/matrix-results.json` and the per-runtime
logs and JUnit files record the new runs. No supported Python minor remains untested.
