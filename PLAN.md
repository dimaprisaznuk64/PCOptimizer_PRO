# Development Plan

## Status
- Released **v1.6.7** (`3470bbd`) — post-1.6.5 reliability audit merged on top
  of v1.6.6 (exe + portable + installer built, tag pushed, GitHub release
  published):
  - Steam VDF library paths are decoded without `unicode_escape`, so non-ASCII
    paths (e.g. `D:\Ігри\Steam`) stay intact.
  - Optimizer backup stores the raw HAGS DWORD and restores it exactly (a `0`
    snapshot no longer becomes `1`); `apply_profile()` refuses to change a
    setting it could not snapshot, so revert always stays possible.
  - Regression tests added for both fixes (+6 tests).
- Unreleased on top of v1.6.7: refreshed **TITANIUM** palette (deeper cyber
  blue, brighter accent), optional thermal-sensor warning hidden on boards
  without ACPI zones, and the COM-apartment teardown fix (`app/wincom.py`)
  that removes the interpreter-shutdown access violation.
- Audit findings **A-01…A-14** (`docs/AUDIT_v1.6.1.md`) closed across v1.6.2–v1.6.5.
- 17 pages, 29 themes, default theme **TITANIUM**.
- Pytest suite is passing (563 tests). Ruff linter is clean.
- Sensor backend resilient on PCs without PDH counters.
- Optional update check against GitHub `releases/latest` (settings toggle,
  "Check now", release-page link).

## Accomplishments
- Unified `CardTitleLabel` / `card_heading` across all 17 pages.
- Unified card padding, radius and page rhythm (`e5622a3`).
- Processes page de-lagged: fixed column widths, unchanged renders skipped,
  async details (`cb8d039`).
- Theme default is a single source of truth (`theme.DEFAULT_THEME`).
- Regenerated release screenshots for v1.6.5.
- Hardened sensors for machines without PDH counters.
- Added the GitHub release update check with injected fetcher for tests.
- Decoded Steam library paths safely; snapshot the exact HAGS DWORD.

## Audit v1.6.6 — step 1 (critical errors)
- Date: 2026-11-04.
- Symptom: a full `pytest` run printed `Windows fatal exception: access
  violation` (and `Win32 exception occurred releasing IUnknown`) at
  interpreter shutdown.
- Cause: pywin32 COM dispatch objects (startup scan via `WScript.Shell` and
  Task Scheduler) were released **after** `pythoncom.CoUninitialize()` had torn
  the apartment down.
- Fix: `app/wincom.py::run_in_com` initializes COM for the current thread and
  leaves apartment teardown to thread/process exit — no premature
  `CoUninitialize`. COM calls in `app/startup/service.py` (`_resolve_lnk`,
  `_task_items`, `_task_set_enabled`) now run through it.
- Regression test: `tests/test_startup.py::test_com_teardown_does_not_crash`
  runs the scan in a subprocess with `-X faulthandler` and asserts there is no
  access violation or IUnknown release error.
- Verified: full faulthandler run reports zero violations; `ruff` clean.

## Next
- Optional: light-theme (Arctic/Ivory) polish pass over all 17 pages.
- Optional: wire `mypy` into the verification routine and fix the first batch
  of findings.
