# Development Plan

## Status
- Released **v2.0.0** — completion of Stage 2: 22 pages, Hardware Benchmark,
  Temperature Dashboard and Export Center, Cleaner/Diagnostics 2.0, Drivers,
  System Report, extended CPU/GPU/RAM telemetry, Gaming 2.0, 803 tests.
- In progress **Stage 3 UI/UX 2.0**: grouped/collapsible navigation rail with
  persistent collapse state across theme rebuilds, compact mode and language
  switches, redesigned Dashboard with 4 sections/history/recommendations, and a
  live interface scale of 100–150%, scaled layout tokens and uniform page
  margins, WCAG-readable status/accent tokens in all 29 themes; 22 pages
  preserved, status strip with live CPU/GPU/RAM/temp/disk, localized nav
   tooltips/group counts and shared motion tokens; global search palette
   (Ctrl+K) with recent pages; 25 new tests, full suite 839 passed /
   1 skipped.
- Released **v1.7.1** (`d9f83ab`) — reliability/stabilization batch: fixed safe
  alert limits and quiet CPU/GPU alerts during games, Settings reset applies
  language/theme, Restart-as-admin handles cancel/error, absolute PowerShell
  paths + UTF-8/OEM decoding, honest restore statuses, COM/background-task
  cleanup and safer update redirects. GitHub Release and the silent `app_run`
  upgrade are done.
- Latest pushed commit is `d1b930d` (final v2.0.0 Stage 2 tools: Hardware
  Benchmark, Temperature Dashboard, Export Center + wiring/fixes); `69c6d3b`
  (docs sync), `3dc29ce` (v2.0.0 tools batch + Task lifecycle fix), `d6bb2db`
  (R68 gaming session charts, R69 per-process RAM history) and earlier
  `e05e94f`/`94d999b` are also pushed.
- v2.0.0 Stage 1 work: dedicated `tests/test_winpaths.py` (9 tests) and opt-in
  COM for background `Task`s — COM is now initialized only for hardware/health
  scans, not for psutil/subprocess work.
- v2.0.0 Stage 2 work: session peaks in Monitor/GPU pages,
  extended NVML telemetry (GPU hotspot, memory clock, honest clock-limit reason),
  Windows commit-charge / virtual-memory detail, top RAM-consuming processes,
  7-day history with advanced telemetry and per-process RAM history, and Gaming
  Mode 2.0 telemetry/profiles/session comparison charts.
- 22 pages, 29 themes, default theme **TITANIUM**.
- Newest v2 tools work (Cleaner 2.0, Diagnostics 2.0, Drivers, System Report,
  Hardware Benchmark, Temperature Dashboard, Export Center) is committed in
  `3dc29ce` and `d1b930d`; version/exe/installer are bumped to **v2.0.0**.
- Pytest suite is passing (**839 tests, 1 skipped**). Ruff linter is clean. A pre-existing
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
  advanced GPU/commit telemetry plus per-process RAM snapshots; Gaming has
  per-game profiles, ARC Raiders, honest session FPS/frametime telemetry and
   before/after comparison charts without an overlay or game injection.
- Cleaner 2.0 adds path whitelist, minimum-age targets, schedule reminders,
  leftover detection, large-file preview and new WER/crash dump/pip/npm caches.
- Diagnostics 2.0 adds read-only DISM/SFC checks, driver inventory integration
  and a prioritized recommendation table; the Drivers page is a read-only
  `Win32_PnPSignedDriver` viewer.
- System Report builds a redacted HTML/text report from saved app/hardware/health/
  optimizer/restore/benchmark/history/diagnostics data.


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
  full suite 747 passed.

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
  747 passed; `ruff` and `compileall` clean.

## v2.0.0 Stage 2 — Gaming session comparison charts
- Gaming Page now has a «SESSION COMPARISON» card with a metric selector
  (CPU/RAM/GPU load, GPU temp, FPS) and a grouped before/after bar chart built
  from the last recorded sessions.
- `session_metric_value()` / `session_metric_unit()` in `app/gaming/telemetry.py`
  keep metric extraction pure and testable; FPS honestly has no before value
  without a configured baseline.
- The summary shows the average before→after change with direction-aware colour
  (lower load/temp and higher FPS are good).
- Verification: +2 tests (helpers + UI chart/metric switch); full suite 747
  passed; `ruff` and `compileall` clean.

## v2.0.0 Stage 2 — per-process RAM history
- `HistorySample` now carries the top 8 RAM-consuming processes per snapshot as
  `[name, MB]` pairs; old JSONL entries stay readable with an empty process list.
- `PerformanceHistory` accepts an injectable `process_top` callback wired to
  `ProcessService.top_by_memory()`; scan failures are logged and recorded as an
  empty list without dropping the rest of the snapshot.
- History page has a «TOP RAM PROCESSES» card showing latest usage, peak usage
  and sample count per process, with EN/UA labels.
- Verification: +5 tests (roundtrip, capture, failure, summary, page rendering);
  targeted suite 50 passed; full suite 747 passed in 352.96s; `ruff` and
  `compileall` clean.

## v2.0.0 Stage 2 — final three tools
- Hardware Benchmark page combines configuration summary, CPU/RAM/disk runs,
  previous/current baseline comparison and redacted result export.
- Temperature Dashboard shows live/historical ACPI zones, NVIDIA core and
  hotspot temperatures with honest gaps, real session peaks and 1h/6h/24h/7d
  history; Refresh invalidates the history cache.
- Export Center exports Health, Benchmarks, Diagnostics, Performance History and
  System Report to CSV/JSON/HTML/PDF where supported, previews written files and
  reports partial failures honestly.
- Fixed System Report import of the removed `HistoryService`, GPU history field
  `power_draw` → `power_w`, added `PySide6.QtPdf` to the frozen build spec.
- Verification: full suite 803 passed, 1 skipped in 351.64s; `ruff` and
  `compileall` clean. Native faulthandler/COM traces remain environmental.

## v2.0.0 Stage 3 — grouped navigation and Dashboard redesign
- `NAV_KEYS` order and all 22 pages are unchanged; keys are mapped into 7 groups:
  overview, monitoring, hardware, optimization, gaming, tools, settings.
- `Sidebar` renders group headers as checkable `QPushButton` (`navGroup`) with
  `▾`/`▸` (or `─` in compact mode); collapsing hides only that group's buttons.
  Navigating to a page expands its group automatically.
- `MainWindow.apply_theme()` saves/restores `collapsed_groups()` so theme
  switching does not silently expand the rail.
- Added `nav_group_*` EN/UA keys and `QPushButton[navGroup="true"]` QSS (including
  compact styling); 5 new tests in `tests/test_ui.py`.
- Dashboard redesigned into 4 sections: **OVERVIEW**, **MONITORING & HISTORY**,
  **SYSTEM**, **ACTIVITY & RECOMMENDATIONS** with `temp_tile`, `ResourceHistoryWidget`
  (60m/120pt from `performance_history.jsonl`), and `RecommendationsWidget`
  (actionable rules for CPU/GPU/temp/disk/health with navigation).
- `MainWindow`/`build_pages` now share a single `PerformanceHistory` instance;
  5 new Dashboard tests added (layout/temp/history/recommendations/shared history).
- Fixed 1024×640 horizontal-scroll regression: `ResourceHistoryWidget` and
  `PerfChart` use `QSizePolicy.Policy.Ignored` for horizontal growth.
- Fixed post-reload theme-token drift in `tests/test_components.py` by importing
  live `components`/`theme` modules.
- Verification: `PYTHONFAULTHANDLER=0 .venv/Scripts/python.exe -m pytest tests
  --no-header && .venv/Scripts/python.exe -m ruff check . &&
  .venv/Scripts/python.exe -m compileall -q app` → **813 passed, 1 skipped in
  607.02s (0:10:07)**; `All checks passed!`; compileall clean.

## v2.0.0 Stage 3 — UI scale 100–150%
- `SettingsService` stores `ui_scale` (100–150); Settings has a live spin box
  with tooltip, applies immediately and keeps the current page.
- `theme.set_ui_scale()` recalculates all type tokens and the QSS. `main.py`
  applies the saved scale before UI modules are imported; `run()` applies it
  before `theme.apply(app)`.
- `MainWindow.apply_ui_scale()` reuses the theme rebuild path. 5 new tests in
  `tests/test_theme.py`, `tests/test_settings_page.py` and `tests/test_ui.py`.
- Verification: `.venv/Scripts/python.exe -m pytest tests --no-header
  -p no:faulthandler` → **818 passed, 1 skipped in 1614.65s (0:26:54)**;
  ruff and compileall clean. Native COM artifacts remain environmental.

## v2.0.0 Stage 3 — scaled layout density
- `theme.ls()` grows paddings/margins/radii/control sizes at half the font rate;
  `set_ui_scale()` refreshes every layout token, including topbar/sidebar widths.
- Topbar, sidebar, icon tiles, gauges, empty hints and all 16 page roots now use
  the shared tokens instead of hardcoded sizes.
- Fixed startup scale: `main.py` exports `PCOPTIMIZER_UI_SCALE` before the UI
  package import, so the saved scale reaches topbar/sidebar/pages on first build.
- Verification: `.venv/Scripts/python.exe -m pytest tests --no-header
  -p no:faulthandler` → **820 passed, 1 skipped in 1558.82s (0:25:58)**;
  ruff and compileall clean.

## v2.0.0 Stage 3 — 29-theme contrast pass
- Every palette is normalized at import: `TEXT_DIM`, `ACCENT`, `OK`, `WARN`,
  `DANGER` are blended until they reach 4.5:1 on BG/PANEL/PANEL_ALT, and
  `ON_ACCENT` is checked against `ACCENT`.
- Added a regression test covering all 29 themes / 7 foreground tokens.
- Verification: `.venv/Scripts/python.exe -m pytest tests --no-header
  -p no:faulthandler` → **821 passed, 1 skipped in 1742.83s (0:29:02)**;
  ruff and compileall clean.

## v2.0.0 Stage 3 — Dashboard status strip
- A compact top-line card now shows CPU/GPU/RAM/temperature/disk values beside
  the greeting, colored by the same load/temperature levels as the rings.
- It follows live language switching and is fed from the same sensor snapshot
  as the rest of the dashboard; 1 new test in `tests/test_dashboard.py`.
- Verification: `.venv/Scripts/python.exe -m pytest tests --no-header
  -p no:faulthandler` → **822 passed, 1 skipped in 1450.35s (0:24:10)**;
  ruff and compileall clean.

## v2.0.0 Stage 3 — navigation polish and tooltips
- Sidebar buttons now carry localized `tip_nav_*` tooltips; compact mode shows
  label + description, group headers show the localized item count and a summary
  tooltip. The topbar status pill also explains its current state.
- Shared `MOTION_FAST/BASE/VALUE/AMOUNT/PULSE` tokens in `theme.py` unify page
  fades, ring/gauge animations and the status pulse.
- Fixed a live scan bug: `Shell.Application` size wraps above 2 GB, so the
  recycle-bin scan now sums real item lengths as `uint64` and clamps negatives.
- Verification: `.venv/Scripts/python.exe -m pytest tests --no-header
  -p no:faulthandler` → **828 passed, 1 skipped** (829 collected, rc 0);
  ruff and compileall clean.

## v2.0.0 Stage 4 — global search palette
- New `app/ui/command_palette.py`: `SearchEntry`, `build_entries()` and pure
  `search_entries()` match page labels, groups, descriptions and keys; recent
  pages are pinned first when opened from the current navigation history.
- `TopBar` gained a search button and `search_requested`; `MainWindow` wires
  `Ctrl+K`, reuses one palette across theme rebuilds and retranslates it with
  the rest of the shell. Arrow keys, Enter and Escape work from the search box.
- Added the search glyph, palette QSS and 4 EN/UA keys; 11 new tests in
  `tests/test_command_palette.py`.
- Verification: `.venv/Scripts/python.exe -m pytest tests --no-header
  -p no:faulthandler` → **839 passed, 1 skipped in 1668.67s (0:27:48)**;
  ruff and compileall clean. A pre-existing `IUnknown` release message remains
  environmental.

## Next
- Stage 4 usability (remaining): notification center, recent operations center,
  first-run wizard, dashboard customization and context menus / quick actions.
- Stage 3 UI/UX 2.0: grouped navigation, tooltips, motion tokens, status strip
  and global search are done; a structured review of panels/tables and final
  visual consistency across the 22 pages is still open.
- v2.0.x reliability: trustworthy CPU package power / thermal-throttling source
  only if a reliable Windows API appears.
- Optional: wire `mypy` into the verification routine and fix the first batch
  of findings.
