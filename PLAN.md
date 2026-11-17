# Development Plan

## Status
- Released **v1.7.0** (`0128d5a`) — usage alerts, PDF export, safe update
  download, light-theme contrast fixes, demo GIF and landing page.
- Current release target **v1.7.1** — reliability/stabilization batch on top of
  v1.7.0: fixed safe alert limits and quiet CPU/GPU alerts during games,
  Settings reset applies language/theme, Restart-as-admin handles cancel/error,
  absolute PowerShell paths + UTF-8/OEM decoding, honest restore statuses,
  ACPI temperature labeled as system temperature, COM/background-task cleanup
  and safer update redirects.
- 17 pages, 29 themes, default theme **TITANIUM**.
- Pytest suite is passing (615 tests). Ruff linter is clean.
- Sensor backend resilient on PCs without PDH counters.
- Optional update check against GitHub `releases/latest` (settings toggle,
  "Check now", release-page link).

## Accomplishments
- Unified `CardTitleLabel` / `card_heading` across all 17 pages.
- Unified card padding, radius and page rhythm (`e5622a3`).
- Processes page de-lagged: fixed column widths, unchanged renders skipped,
  async details (`cb8d039`).
- Theme default is a single source of truth (`theme.DEFAULT_THEME`).
- Regenerated release screenshots for v1.7.1.
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
- v2.0.0 Stage 1: full technical audit and stabilization.
- Optional: wire `mypy` into the verification routine and fix the first batch
  of findings.
