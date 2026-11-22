# Development Plan

## Status
- Released **v2.0.1** — Stage 3/4 UX polish plus Stage 5 monitoring profiles
  (`ECO`/`BALANCED`/`PERFORMANCE`) and an optional pythonnet/LibreHardwareMonitor
  temperature backend. 23 pages, 904 passed / 1 skipped, TITANIUM baseline,
  Geist fonts, bundled LHM DLLs, EN/UA. The local `.venv` was repaired to
  Python 3.13 after its old 3.15 home disappeared.
- Released **v2.0.0** — completion of Stage 2: 22 pages, Hardware Benchmark,
  Temperature Dashboard and Export Center, Cleaner/Diagnostics 2.0, Drivers,
  System Report, extended CPU/GPU/RAM telemetry, Gaming 2.0, 803 tests.
- Completed **Stage 3 UI/UX 2.0**: grouped/collapsible navigation rail with
  persistent collapse state across theme rebuilds, compact mode and language
  switches, redesigned Dashboard with 4 sections/history/recommendations, and a
  live interface scale of 100–150%, scaled layout tokens and uniform page
  margins, WCAG-readable status/accent tokens in all 29 themes; 23 pages now,
  localized nav tooltips/group counts and shared motion tokens; global search
  palette (Ctrl+K) with recent pages, a Notification Center with persistent read
  state and a Recent Operations Center with filters, export and page jumps;
  new tests, context menus/quick actions on four table pages, dashboard widget
  customization, full suite 904 passed / 1 skipped.
   The temporary dashboard status strip was removed at the user's request;
   installed `app_run` 2.0.0 was rebuilt and relaunched.
  - Completed **Stage 5 monitoring profiles** (`ECO`/`BALANCED`/`PERFORMANCE`)
   with live sampler/history/process-table/game-presence cadence switching, plus
   a pythonnet/LibreHardwareMonitor temperature backend (`app/sensors/lhm_backend.py`)
   with bundled DLLs in `assets/lib/lhm`; LHM hardware readings require admin and
   are honestly omitted when a board reports 0 °C or no sensor.
  - Verification: full suite split into chunks because a single 60-minute run
    stalled near the end; chunks report **904 passed / 1 skipped** (243+252+232+177),
    `ruff` and `compileall` clean. Native `access violation`/`IUnknown` messages
    at shutdown remain environmental.
- Release v2.0.1: commit `2048699`, tag `v2.0.1`, GitHub Actions Release run
  `45021250467` completed successfully; release has installer and portable zip.
  Local artifacts: `dist\PCOptimizer_PRO\PCOptimizer_PRO.exe` (`2.0.1.0`),
  `dist\PCOptimizer_PRO_2.0.1_portable.zip`,
  `dist\installer\PCOptimizer_PRO_Setup_2.0.1.exe`,
  `dist\PCOptimizer_PRO_src_v2.0.1.zip`. Smoke test passed; silent upgrade of
  `app_run` to `2.0.1.0` passed and the installed GUI was relaunched.
  Local build fix committed as `af12a48` (call operator for venv Python).


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
- 23 pages, 29 themes, default theme **TITANIUM**.
- Newest v2 tools work (Cleaner 2.0, Diagnostics 2.0, Drivers, System Report,
  Hardware Benchmark, Temperature Dashboard, Export Center) is committed in
  `3dc29ce` and `d1b930d`; version/exe/installer are bumped to **v2.0.0**.
- Pytest suite is passing (**888 tests, 1 skipped**). Ruff linter is clean. A pre-existing
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

## v2.0.0 Stage 3 — Dashboard status strip (removed)
- Later removed at the user's request; the dashboard keeps the ring cards and
  the rest of the live telemetry without the extra top strip.
- A compact top-line card showed CPU/GPU/RAM/temperature/disk values beside
  the greeting, colored by the same load/temperature levels as the rings.
- It followed live language switching and was fed from the same sensor snapshot
  as the rest of the dashboard.
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

## v2.0.0 Stage 4 — notification center
- `ActivityLog` now tracks read timestamps in `activity_read.json` (portable
  data dir): `mark_read`, `mark_all_read`, `is_read`, `unread_count`, pruned on
  compaction and cleared together with the activity history.
- New `app/ui/notifications.py` popup: title/unread counter, All / Unread /
  Warnings & errors filters, click-to-read and Clear; entries use level icons
  and bold unread rows. The bell opens it on left click (right click keeps the
  old quick menu), tints accent while unread and explains the count in the
  tooltip. The popup follows live language switching and theme rebuilds.
- 7 new tests (`tests/test_notifications.py`); full suite 846 passed, 1 skipped.

## v2.0.0 Stage 4 — recent operations center
- New 23rd page (`app/ui/operations.py`) in the Overview group: summary cards
  (all/successful/partial/failed), full history table, text search, level and
  time filters, detail pane, CSV/JSON export and confirmable clear.
- `ActivityLog.Entry` now carries an optional `source` page key (back-compatible
  with old JSONL lines); cleaner, optimizer, gaming, launcher, health, network,
  monitor alerts and update notices record where they came from. Selecting an
  entry with a source offers an «Open page» jump and marks it read.
- In-memory/read-state/compact limits grew from 30 to 200 entries so the center
  has a useful history span; notifications and the dashboard still show 4–30.
- 9 new tests (`tests/test_operations.py`) cover filtering, export helpers,
  persistence, navigation, clear confirmation, retranslation and registration.
- Verification: full suite `.venv/Scripts/python.exe -m pytest tests --no-header
  -p no:faulthandler` → **857 passed, 1 skipped in 1960.55s (0:32:40)**;
  `ruff check .`, `compileall -q app` and `git diff --check` clean. Offscreen
  1280×800 render preview: `%TEMP%\opencode\operations_preview.png` (5 rows,
  333 sampled colours). The pre-existing `IUnknown` release message at shutdown
  remains environmental.

## v2.0.0 Stage 4 — first-run wizard
- New 3-step modal `app/ui/first_run.py`: welcome/safety explanation, starter
  preferences (language, one of three curated themes, interface scale, update
  checks, temperature/usage alerts, quiet-hours and tray behaviour), and a
  finish summary with an option to jump into Settings. Skip marks the flow done
  without touching other preferences.
- Settings state: `first_run_completed` defaults to True so existing installs are
  not interrupted; `run()` flips it to False only when `settings.json` is new.
  SettingsPage gained a «Run setup wizard» button that can replay it.
- MainWindow applies the chosen language/theme/scale live immediately after the
  dialog closes and preserves the current page through the theme rebuild.
- 8 new tests (`tests/test_first_run.py`) cover defaults, legacy settings,
  applying values, skip, invalid choice, step navigation/retranslation, the
  Settings replay button and MainWindow integration.
- Verification: full suite `.venv/Scripts/python.exe -m pytest tests --no-header
  -p no:faulthandler` → **865 passed, 1 skipped in 1922.45s (0:32:02)**;
  `ruff check .`, `compileall -q app` and `git diff --check` clean. Offscreen
  720×620 render preview: `%TEMP%\opencode\first_run_wizard_preview.png`. The
  intermittent `IUnknown` release message at shutdown remains environmental.

## v2.0.0 Stage 4 — context menus / quick actions
- New reusable `app/ui/context_menu.py`: `TableContextMenu` with dynamic labels,
  separators, row-aware callbacks/enable flags and safe clipboard copy. Labels
  are resolved when the menu opens, so live EN/UA switching is respected.
- Wired into four table pages: Processes (end, copy name/PID/command),
  Startup (toggle, remove, copy name/command), Cleaner (select/deselect all,
  toggle target, copy path) and Operations (open source page, mark read, copy
  detail).
- Added 12 EN/UA `ctx_*` translation keys and 6 tests covering the helper plus
  one integration test per page (`tests/test_context_menu.py`,
  `tests/test_processes.py`, `tests/test_startup.py`, `tests/test_cleaner.py`,
  `tests/test_operations.py`).
- Test hygiene: `tests/conftest.py` now calls `gc.collect()` after joining
  background tasks, which removes a non-deterministic native crash in the full
  suite caused by deferred Qt/COM wrapper cleanup.
- Verification: `.venv/Scripts/python.exe -m pytest tests --no-header` →
  **871 passed, 1 skipped in 2360.92s (0:39:20)**; `ruff check .`,
  `compileall -q app` and `git diff --check` clean. The intermittent `IUnknown`
  release message at shutdown remains environmental.

## v2.0.0 Stage 4 — dashboard customization
- New `app/ui/dashboard_custom.py` with canonical widget keys, `parse_dashboard_hidden()`
  and `DashboardCustomizerDialog`. Settings gets a «Customize dashboard» button;
  choices are validated/canonicalized and saved to portable `data_root()` as the
  `dashboard_hidden` setting (comma-separated string).
- `DashboardPage(dashboard_hidden=...)` hides selected widgets, skips empty section
  headers and rebuilds the responsive grid so remaining widgets occupy freed cells.
  Hidden network/process widgets also skip their background pollers.
- Live apply is wired through `SettingsPage(on_dashboard_hidden_applied=...)` →
  `MainWindow.apply_dashboard_hidden()` → `DashboardPage.set_hidden_widgets()`;
  theme rebuilds preserve the saved layout.
- Added 21 EN/UA `dash_custom_*` keys, 5 tests for dialog/parse/serialize, hide
  behavior, live apply and settings persistence. Verification: targeted
  `tests/test_dashboard.py tests/test_settings_page.py tests/test_i18n.py
  tests/test_settings.py` → **77 passed**; full suite → **876 passed, 1 skipped in
  2250.78s (0:37:30)**; `ruff check .`, `compileall -q app`, `git diff --check` clean.
  The intermittent `IUnknown`/access-violation shutdown artifact remains environmental.

## v2.0.0 Stage 4 — screenshots + live verification
- Generated a fresh offscreen screenshot set for all 23 pages in both languages
  (`UA/` and `EN/`) plus Dashboard Customizer and First-Run Wizard previews.
  Script: `%TEMP%\opencode\shoot_stage4.py`; staging:
  `%TEMP%\opencode\screenshots_stage4` (48 PNG, 0 blank).
- Desktop archive: `PCOptimizer_PRO_screenshots_v2.0.0_stage4.zip` (6.52 MB,
  51 entries) on the real Desktop folder via `[Environment]::GetFolderPath('Desktop')`.
- Launched the current source build from the project venv; GUI process 22228 has
  the visible `PCOptimizer PRO` window. Log confirms
  `starting PCOptimizer PRO 2.0.0`. No version bump, build or commit.

## Design baseline (approved 2026-11-21)
- Keep the current dashboard/brand style as the final corporate look: dark
  graphite background, blue outlines, cyan accents and compact cards. No
  redesign of the core concept.
- Score from the live-PC review: 9/10 overall; structure/colors/layout 9/10,
  readability 8/10, informativeness 9/10.

## Stage 3/4 audit fixes (2026-11-21)
- Offscreen audit of all 23 pages at 100/125/150% and 1440x860 / 1280x800 /
  1120x680 found real vertical squashing: controls were 13px high instead of
  38px on Gaming and other dense pages. `MainWindow` now wraps every page in a
  transparent `QScrollArea#pageScroll` (horizontal scroll off, vertical as
  needed); all stack consumers unwrap through `_page_widget()`.
- `PerfChart` header split into title/legend and segmented tabs rows, so the
  title, legend pills and tab buttons keep their size hints. `CardTitleLabel`,
  Monitor summaries and Launcher tile text wrap instead of clipping.
  `QSpinBox` internal line-edit padding was removed, compact danger buttons use
  the shared compact QSS, and `GaugeCard` is wide enough for 150% VRAM values.
- Re-audit: clipped labels 0 at all scales; clipped controls 14 / 26 / 46 at
  100 / 125 / 150% (remaining cases are fixed-width combos/line-edits with
  elided text and 3px spinbox hint deltas); small charts 0; table horizontal
  scroll is expected on dense tables at narrow widths.
- Verification: full `PYTHONFAULTHANDLER=0 .venv/Scripts/python.exe -m pytest
  tests --no-header -p no:faulthandler` = **888 passed, 1 skipped in
  2960.55s (0:49:20)**; `ruff`, `compileall` and `git diff --check` clean.

## Readability pass (2026-11-21)
- `PerfChart` now has a segmented range switch (60s / 5m / 15m / 1h) and an
  expand toggle. `_ChartCanvas` filters history by the selected window for the
  curves, Y axis, time-axis labels and hover readout; the dashboard chart keeps
  3600 samples so all ranges are available. EN/UA keys and tests added.
- Secondary text (`cardSub`, `cardRow`, nav/group labels) uses the bundled Geist
  font explicitly with slightly heavier weight and letter spacing for
  readability at 100–150% scale.
- Health Score now shows an explicit per-category deduction breakdown grouped
  from non-OK findings using `SEVERITY_PENALTY`, localized through
  `localize_finding()`, with an honest "no deductions" state.
- Verification: targeted `tests/test_health.py tests/test_theme.py
  tests/test_components.py tests/test_i18n.py` = 100 passed; full
  `PYTHONFAULTHANDLER=0 .venv/Scripts/python.exe -m pytest tests --no-header
  -p no:faulthandler` = **888 passed, 1 skipped in 2699.28s (0:44:59)**;
  `ruff check .`, `compileall -q app`, `git diff --check` clean. Pre-existing
   native `access violation`/`IUnknown` shutdown artifacts remain environmental.

### CPU / motherboard / GPU temperatures (2026-11-21)
- New `app/sensors/temperature_names.py` classifies temperature sources as CPU,
  motherboard, GPU, hotspot or generic system; LHM-style names are canonicalized
  without claiming a motherboard/CPU value from an anonymous ACPI zone.
- `ThermalBackend` now keeps ACPI `InstanceName` labels and falls back to the
  optional LibreHardwareMonitor WMI namespace (`root\OpenHardwareMonitor`) when
  ACPI is unavailable to a non-elevated process.
- Dashboard thermals and the Temperature page show explicit CPU / Motherboard /
  GPU rows with honest `—` when no sensor exists; GPU comes from NVML.
- i18n: `temp_target_cpu`, `temp_target_board`, `temp_target_gpu` in EN/UA.
- Verification: targeted sensors/temperature/dashboard/i18n = 74 passed; full
  `PYTHONFAULTHANDLER=0 .venv/Scripts/python.exe -m pytest tests --no-header
  -p no:faulthandler` = **888 passed, 1 skipped in 3063.58s (0:51:03)**;
  `ruff`, `compileall -q app` clean. Pre-existing native shutdown artifacts remain.

### Temperature source diagnostics + HWiNFO reader (2026-11-22)
- Added `app/sensors/hwinfo.py`: read-only HWiNFO shared-memory reader
  (`HWiS`, `HWiNFO_SENS_SM2`) with CPU/board/GPU/hotspot classification,
  unsigned/positive-value filtering and graceful unavailable status. No admin
  rights are needed when HWiNFO itself is running with Sensor Sharing enabled.
- `ThermalBackend` now merges HWiNFO + pythonnet LHM + LHM WMI + ACPI with an
  explicit source priority and carries honest `notes`/`sources` into
  `ThermalStat`. Missing CPU/board sensors, `0°C` LHM CPU readings, disabled
  HWiNFO, ACPI access denied and LHM WMI failures are no longer swallowed.
- LHM reader keeps raw readings for diagnostics and filters non-positive values
  in `pick_temperatures()` instead of losing the reason.
- `TemperaturePage` now shows the backend notes inline, sets explanatory
  tooltips on missing CPU/board values and adds a «Restart as admin» button.
  Dashboard thermal card exposes the same notes via tooltip.
- i18n: 11 EN/UA keys (`temp_admin*`, `temp_note_*`, `temp_sources_label`).
- Fixed mojibake in `tests/test_temperature.py` literals (`В°C`, `Р...`)
  that only failed in the full suite when the real translations were active.
- Verification: targeted sensors/hwinfo/lhm/temperature/i18n/dashboard =
  **90 passed**; full suite in two parts = **913 passed, 1 skipped**
  (`tests --ignore=tests/test_ui.py` = 884 + `test_ui.py` = 29; UI hang test
  run separately); `ruff check .`, `compileall -q app`, `git diff --check`
  clean. `pyi-archive_viewer -r` confirms `app.sensors.hwinfo`,
  `app.sensors.temperature_names`, `app.sensors.thermal_backend` and
  `app.temperature.service` are bundled.
- Local `app_run` was rebuilt from the updated sources and relaunched
  (PID 8344). Version remains 2.0.1; no installer/release was rebuilt yet.

## Next

- The baseline design is frozen and the 23-module / 100-150% scaling audit is
  complete; no further structural UI changes without a new request.
- Readability follow-ups from the approved baseline are done and shipped in
  v2.0.1; user review of the live charts / Health Score breakdown is complete.
- v2.0.x reliability: trustworthy CPU package power / thermal-throttling source
  only if a reliable Windows API appears.
- `mypy` is wired into CI as non-blocking. Dev dependency is pinned to
  `>=1.11,<2` after mypy 2.4.1 crashed internally on this tree. First batch
  fixed: all 28 PySide6 `QSizePolicy` enum errors (`Policy.Expanding`,
  `Policy.Preferred`, `Policy.Fixed`, `Policy.MinimumExpanding`); mypy count
  dropped from 135 to 107 errors in 35 files. Remaining findings are mostly
  `attr-defined`/`arg-type`/`union-attr` in reports/UI code.
