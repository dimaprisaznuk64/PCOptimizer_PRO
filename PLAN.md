# Development Plan

## Status
- Released **v1.7.1** (`d9f83ab`) — reliability/stabilization batch: fixed safe
  alert limits and quiet CPU/GPU alerts during games, Settings reset applies
  language/theme, Restart-as-admin handles cancel/error, absolute PowerShell
  paths + UTF-8/OEM decoding, honest restore statuses, COM/background-task
  cleanup and safer update redirects. GitHub Release and the silent `app_run`
  upgrade are done.
- Local commit `94d999b` (cooperative shutdown, venv-aware launcher) is still
  unpushed: `main` is one commit ahead of `origin/main`.
- Uncommitted v2.0.0 Stage 1 work: dedicated `tests/test_winpaths.py` (9 tests)
  and opt-in COM for background `Task`s — COM is now initialized only for
  hardware/health scans, not for psutil/subprocess work.
- Uncommitted v2.0.0 Stage 2 work: session peaks in Monitor/GPU pages,
  extended NVML telemetry (GPU hotspot, memory clock, honest clock-limit reason),
  Windows commit-charge / virtual-memory detail, top RAM-consuming processes,
  7-day history with advanced telemetry, and Gaming Mode 2.0 telemetry/profiles.
- 17 pages, 29 themes, default theme **TITANIUM**.
- Pytest suite is passing (**657 tests**). Ruff linter is clean. A pre-existing
  faulthandler artifact still prints native access-violation/0x80040155 traces
  during a full run; all tests pass. Two signal/thread timing flakes in task and
  dashboard tests were made deterministic.
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
- Extended monitoring telemetry without fake values: NVML hotspot / memory clock
  / clock-limit reason, session peaks for CPU/RAM/temperature and GPU metrics,
  Windows commit-charge detail for RAM.
- Monitor shows the top RAM-consuming processes; History keeps 7 days and records
  advanced GPU/commit telemetry; Gaming has per-game profiles, ARC Raiders, and
  honest session FPS/frametime telemetry without an overlay or game injection.

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

## Audit v2.0.0 — Stage 1 memory/performance profile
- Date: 2026-11-18. Offscreen probe: `%TEMP%\opencode\profile_memory.py` with an
  isolated `PCOPTIMIZER_DATA`; 3 cycles over all 17 pages plus 120 synthetic
  snapshots per cycle (360 total), feeding `MainWindow.handle_snapshot()`.
- RSS: 121.3 MB after construction → 123.5 / 125.8 / 125.8 MB after cycles 1–3.
  Python objects: 56,620 → 57,840 → 57,842 → 57,844; the steady `+1/cycle` is
  the probe's own `Counter`, not application state. No unbounded growth.
- First-cycle jump is one-time caching: ~366 `psutil.Process`, 66 `QLabel`,
  21 `Bar` objects (game-presence scan + first `apply_snapshot` layout). Bounded.
- Warm timings: construction 1.12 s (cold ~2.08 s), page switch avg 1.29 ms /
  p95 2.34 ms, snapshot avg 2.69 ms / p95 3.92 ms. Far inside the 1 s sampler
  budget; no UI-blocking hot path found.
- `shutdown()` temporarily raises RSS ~26 MB while Qt destroys the widget tree;
  teardown-only and consistent with the known faulthandler artifact. No fix.
- Conclusion: no runtime memory leak detected; Stage 1 profiling is complete.

## Audit v2.0.0 — Stage 2 monitoring extension
- Date: 2026-11-18. Goal: honest extended telemetry without fabricating values
  that Windows/NVML do not reliably expose.
- `GpuStat` now carries `temperature_hotspot`, `memory_clock_mhz`,
  `throttle_reasons` and `throttling`; `NvmlBackend` reads them best-effort and
  falls back to the last successful GPU sample.
- Idle-only NVML reason bits are not reported as throttling. Live PC probe
  showed reason `1024` and supported mask `2047`, so the UI now says
  `clock limited` / `обмеження частот` with the raw `0x...` reason instead of
  claiming thermal throttling.
- Monitor page tracks session peaks for CPU load, RAM usage and system
  temperature. GPU page tracks peak GPU temperature, hotspot and power; absent
  hotspot is shown honestly.
- CPU package power and CPU thermal throttling remain out of scope on plain
  Windows because there is no reliable source without an extra driver.
- Verification at Stage 2 completion: targeted sensors/GPU/monitor/i18n tests
  33 passed; full suite `PYTHONFAULTHANDLER=0 .venv/Scripts/python.exe -m pytest
  tests --no-header` **637 passed**; `python -m ruff check .` clean;
  `python -m compileall app` OK.

## Audit v2.0.0 — RAM commit-charge telemetry
- Date: 2026-11-18. Added honest Windows virtual-memory detail to the Memory
  card via `GlobalMemoryStatusEx` (`ullTotalPageFile` / `ullAvailPageFile`).
- New `app/sensors/win_memory.py` exposes `CommitCharge` and injectable
  `read_commit_charge()`; it returns `None` on non-Windows, missing DLL, failed
  query or zero limit, and clamps impossible negative `available` values.
- `MemoryStat` now carries optional `commit_used` / `commit_limit`;
  `PsutilBackend` populates them best-effort. The Monitor page shows a hidden
  `commit_sub` sublabel only when the source is available.
- Live probe on this PC: `CommitCharge(limit=36424519680,
  available=2806210560, used=33618309120)`.
- Verification: +5 tests (`tests/test_win_memory.py`, one sensor test, one
  monitor test); targeted suite 32 passed; final full suite
  `PYTHONFAULTHANDLER=0 .venv/Scripts/python.exe -m pytest tests --no-header`
  **642 passed in 286.98s**; `python -m ruff check .` clean;
  `python -m compileall app` OK. Native faulthandler traces remain environmental.

## v2.0.0 Stage 2 — RAM processes and long-horizon history
- Monitor page now has a «Top RAM processes» table refreshed every 5 s from
  `ProcessService.top_by_memory()`; locked/vanished processes are skipped and
  partial failures are shown in the card status.
- `PerformanceHistory` keeps up to 7 days by default and compacts every 120
  records. `HistorySample` stores GPU hotspot, memory clock, power, honest
  throttling state and commit-charge percent; old entries remain readable.
- History page has a 7-day range and commit/hotspot metric cards.
- Verification: targeted Monitor/Processes/History/i18n suites 26 + 27 passed;
  full suite 657 passed.

## v2.0.0 Stage 2 — Gaming Mode 2.0 telemetry
- Added ARC Raiders (Steam appid `1808500`, `PioneerGame.exe`) and per-game
  optimization profiles stored in `gaming_profiles.json`.
- New `app/gaming/telemetry.py`: injectable frame provider, CSV/PresentMon
  reader, session JSONL history, nearest-rank 1% / 0.1% low calculation and
  resource/temperature before/after snapshots.
- No overlay and no game injection. If PresentMon CSV is not configured, the
  Gaming page honestly reports that FPS telemetry is unavailable.
- Gaming mode state is persisted separately in `gaming_mode.json`; a plain
  BALANCED optimizer backup no longer falsely restores «mode on».
- Verification: targeted Gaming/Launcher/i18n suites 72 passed; full suite
  657 passed; `ruff` and `compileall` clean.

## Next
- v2.0.0 Stage 2 remaining: trustworthy CPU package power / thermal-throttling
  source (only if a reliable Windows API appears), per-process RAM history,
  long-term Gaming session comparison charts.
- Push `94d999b` and all uncommitted Stage 1/2 work when the user asks
  (commits/pushes are explicit requests).
- Optional: wire `mypy` into the verification routine and fix the first batch
  of findings.
