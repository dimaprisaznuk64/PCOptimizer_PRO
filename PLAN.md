# Development Plan

## Status
- Released **v2.3.2** — reliability fixes found by a targeted audit: a
  corrupt/invalid `cleaner_whitelist.json` is quarantined as
  `.corrupt-<timestamp>`, exposes a load error, blocks cleaning instead of
  silently dropping protections, and recovers after a successful whitelist save;
  the Cleaner page shows the blocked status and a due schedule reminder, calls
  `CleanerScheduler.mark_run()` only after a successful clean, and refuses to
  clean while the whitelist is unavailable; `PerformanceHistory.record()` no
  longer throttles after a failed append; gaming mode marks its state as
  `UNKNOWN` when persisting the mode state fails instead of silently disagreeing
  with the next start. EN/UA keys added for both UI warnings. Verification:
  **1033 passed / 2 skipped in 199.04 s**; `ruff`, `mypy` (128 files),
  `compileall`, `git diff --check` clean (CRLF warnings only). Committed as
  `e89de8d`, shipped in v2.3.2.
- Released **v2.3.1** — post-v2.3.0 reliability pass: corrupt UTF-8 `settings.json` /
  `changes.jsonl` no longer break startup or journal integrity; concurrent
  journal writes keep a valid SHA-256 chain; Settings save reports disk errors;
  overlay no longer presents a stale static CSV as LIVE and recomputes 1% LOW
  from newly ingested frames; update metadata no longer hides a verified
  installer behind a checksumless asset; Operations recovery status refreshes
  after external cleanup; PresentMon 2.x CSV headers are parsed case-insensitively
  (`CPUStartTime`, `MsBetweenPresents`). Verification: **1027 collected / 1025
  passed / 2 skipped**, `ruff`, `mypy` (128 files), `compileall`, `git diff --check`
  clean (CRLF warnings only). Committed as `938ec5b`, shipped in v2.3.1.
- Released **v2.3.0** — safe FPS/CPU overlay: always-on-top borderless window,
  always-registered `Ctrl+Alt+F9` hotkey (works even while the overlay is
  hidden), tray/Settings toggle, optional external PresentMon CSV provider,
  stale-frame and timer cleanup, EN/UA strings and frozen-build hidden-imports.
  No injection, hooks, or process-memory access. Verification:
  **1013 collected / 1011 passed / 2 skipped**, `ruff`, `mypy` (128 files),
  `compileall`, `git diff --check` clean. 23 page screenshots plus an overlay
  preview regenerated as `docs/screenshots/v2.3.0_*.png`.
- Released **v2.2.0** — final audit and documentation cleanup: 23 pages × 18
  themes, EN/UA parity (1377 keys each), 100/125/150% scaling and all live
  services/journal/backups verified; no product bugs found. Corrected stale
  `29 themes` documentation and landing-page screenshot links. **996 collected /
  994 passed / 2 skipped**, `ruff`, `mypy` (125 files), `compileall`,
  `git diff --check` clean; installer + portable published.
- Shipped in **v2.1.7** — Stage 5 reliability/performance batch: chart
  decimation (3600 samples: 140.7 → 42.6 ms/repaint), thermal empty-scan cache,
  quiet-mode game watcher gating, deferred hidden-page I/O, expanded Operations
  log and visual clipping fixes; plus a telemetry typing fix.
- Released **v2.1.6** — unclean-exit detection (`app/recovery/crash.py`), snapshot
  fan-out to visible pages only, and crash-recovery report in Operations;
  23 pages, 18 themes, 980 passed / 2 skipped, TITANIUM baseline, Geist fonts,
  EN/UA. Installer and portable zip published on GitHub.
- Released **v2.1.5** — immutable system-change journal (SHA-256 hash chain,
  backup checksum sidecars, read-only Operations feed) and verified installer
  downloads; 23 pages, 18 themes, 964 passed / 2 skipped, TITANIUM baseline,
  Geist fonts, EN/UA. Installer and portable zip published on GitHub.
- Released **v2.1.1** вЂ” SHA-256 verification for downloaded GitHub installer
  assets (`UpdateInfo.sha256`, `hmac.compare_digest` after MZ/size checks,
  atomic `.part` cleanup on mismatch). No UI/layout changes; 23 pages,
  18 themes, 943 passed / 1 skipped, TITANIUM baseline, Geist fonts, EN/UA.
  Installer and portable zip published on GitHub; source zip built locally.
- Released **v2.1.0** вЂ” design-system patch (unified spacing/radius tokens),
  18 curated themes with aliases for the 11 retired names, and review-hardening
  fixes (cooperative teardown, cached stylesheet/WMI names, warning filtering).
  23 pages, 18 themes, 943 passed / 1 skipped, TITANIUM baseline, Geist fonts,
  EN/UA. Installer and portable zip published on GitHub; source zip built locally.
- Released **v2.0.1** вЂ” Stage 3/4 UX polish plus Stage 5 monitoring profiles
  (`ECO`/`BALANCED`/`PERFORMANCE`) and an optional pythonnet/LibreHardwareMonitor
  temperature backend. 23 pages, 904 passed / 1 skipped, TITANIUM baseline,
  Geist fonts, bundled LHM DLLs, EN/UA. The local `.venv` was repaired to
  Python 3.13 after its old 3.15 home disappeared.
- Released **v2.0.0** вЂ” completion of Stage 2: 22 pages, Hardware Benchmark,
  Temperature Dashboard and Export Center, Cleaner/Diagnostics 2.0, Drivers,
  System Report, extended CPU/GPU/RAM telemetry, Gaming 2.0, 803 tests.
- Completed **Stage 3 UI/UX 2.0**: grouped/collapsible navigation rail with
  persistent collapse state across theme rebuilds, compact mode and language
  switches, redesigned Dashboard with 4 sections/history/recommendations, and a
  live interface scale of 100вЂ“150%, scaled layout tokens and uniform page
  margins, WCAG-readable status/accent tokens in all palettes (18 themes now); 23 pages now,
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
   are honestly omitted when a board reports 0 В°C or no sensor.
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
- Current work: commit `c65605a` merged the Desktop style patch (`SPACING_*`/`RADIUS_*`
  scale, `normalize_spacing.py`, design docs) plus B-09 fixes (cooperative teardown,
  cached stylesheet, cached WMI names). Full suite in one run: **927 passed / 1 skipped**
  in 184 s; `ruff`, `mypy`, `compileall` clean. A follow-up fix commit adds narrow
  PySide warning filtering, a high-scale empty-hint fit, saved-theme alias startup
  resolution and a longer teardown budget for slow WMI/PowerShell tasks (935 tests).
  Both Desktop archives were reviewed:
  the patch zip was merged and `Main.dc.html` was checked for token parity. A follow-up
  commit applies the visual guide's theme proposal вЂ” 29 в†’ **18 themes**, with the 11
  removed names kept as `THEME_ALIASES` so saved settings keep working.

### Release v2.1.0 (2026-11-24)
- `main` head: `739123b` (`chore(release): bump version to 2.1.0 and refresh
  screenshots`), pushed after the earlier handoff `45e31e8`. Tag `v2.1.0` pushed.
- Version bumped in `app/__init__.py`, `assets/version_info.txt` (2.1.0.0),
  `installer/PCOptimizer_PRO.iss`, both EN/UA `sidebar_user_sub` keys and README.
- Regenerated 23 offscreen screenshots `docs/screenshots/v2.1.0_*.png` (1440Г—860,
  live sensor snapshot, EN); the v2.0.2 set was removed.
- Verification: **930 passed / 1 skipped** (~191 s); `ruff`, `mypy` (120 files),
  `compileall` and `git diff --check` clean. Frozen exe smoke: alive, log
  `starting PCOptimizer PRO 2.1.0`.
- Local artifacts: exe **2.1.0.0**, portable zip 54.1 MB, installer 39.3 MB,
  source zip 9 MB. GitHub Actions Release run `45369199779` = success;
  [Release v2.1.0](https://github.com/dimaprisaznuk64/PCOptimizer_PRO/releases/tag/v2.1.0)
  published with installer + portable. `UpdateService(current='2.0.1').check()`
  reports latest 2.1.0 and the correct installer URL.
- Installed `app_run` silently upgraded 2.0.1.0 в†’ **2.1.0.0**; Desktop shortcut
  points at `app_run\PCOptimizer_PRO.exe`.
- Review checklist remains done: UI scale 100/125/150% has no real clipping, all
  18 themes apply, `COBALT` starts as `MIDNIGHT`, table headers match data
  alignment, and HWiNFO shared-memory smoke returned 21/21 fresh samples.

### Current work (source-only, 2026-11-25)
- Update integrity is now fail-closed. `_find_asset()` accepts only a GitHub
  installer whose embedded version matches the release tag and whose `digest`
  is a valid `sha256:`; mismatches produce `download_unavailable` reasons
  (`no_asset` / `version_mismatch` / `no_checksum`) and a localized Settings
  warning instead of a dead download button. `download_installer()` rejects a
  missing/invalid digest **before any network request**, always compares the
  streamed SHA-256 with `hmac.compare_digest`, cleans `.part` on every failure,
  and the error points to the release page. New EN/UA keys:
  `set_upd_unverified`, `set_upd_asset_mismatch`.
- CI release step now clears stale `dist/` and publishes only the exact
  versioned installer/portable names from `RELEASE_VERSION`;
  `scripts/build_installer.ps1` fails loudly on a version mismatch.
- Cleaner path safety: `_is_link_or_junction()` rejects symlinks/junctions;
  scan and clean prune both from directory walks, clean walks top-down and
  removes empty folders afterwards, and `is_safe_root()` now rejects the
  filesystem root on POSIX as well as Windows drive roots. New regression
  tests cover a symlinked directory, a junction emulation via monkeypatched
  `os.path.isjunction`, a missing checksum, and `os.sep` as a target.
- `README.md` encoding was repaired (double cp1251/UTF-8 mojibake) and the
  portable instructions now point at `PCOptimizer_PRO.exe` in the archive root.
- Verification: targeted `94 passed, 1 skipped`; full suite **951 passed,
  2 skipped (953 collected)**; `ruff`, `mypy` (120 files), `compileall`,
  `git diff --check` clean. These fixes ship in **v2.1.4**.

### Release v2.1.4 (2026-11-25)
- Version bumped to **2.1.4** in `app/__init__.py`, `assets/version_info.txt`
  (also fixed stale fixed-version tuples `2.1.1` → `2.1.4`), installer, and
  EN/UA `sidebar_user_sub`.
- Regenerated all **23** offscreen 1440×860 screenshots as
  `docs/screenshots/v2.1.4_*.png`; removed the obsolete `v2.1.3_*` set.
- README version badge, screenshot links, and installer/portable names updated
  to v2.1.4; test count is **953** (2 skipped).
- Commit/tag/push: `52b2567` on `main`, tag `v2.1.4` pushed.
- Local build: exe `2.1.4.0`, `dist\PCOptimizer_PRO_2.1.4_portable.zip`,
  `dist\installer\PCOptimizer_PRO_Setup_2.1.4.exe`, and source zip. Smoke test
  OK; silent upgrade of `app_run` to `2.1.4.0` succeeded and the desktop
  shortcut points at `app_run\PCOptimizer_PRO.exe`.
- CI Release run `45595182850` = success; [Release v2.1.4](https://github.com/dimaprisaznuk64/PCOptimizer_PRO/releases/tag/v2.1.4)
  published with installer + portable assets (SHA-256 digests available from
  the GitHub API).

### Release v2.1.5 (2026-11-25)
- Version bumped to **2.1.5** in `app/__init__.py`, `assets/version_info.txt`
  (filevers/prodvers/StringStruct `2.1.5.0`), installer, and EN/UA
  `sidebar_user_sub`.
- Regenerated all **23** offscreen 1440×860 screenshots as
  `docs/screenshots/v2.1.5_*.png`; removed the obsolete `v2.1.4_*` set.
- README badge, screenshot links, and installer/portable names updated.
- Includes the immutable system-change journal from commit `799b34a`:
  SHA-256 hash chain, backup checksum sidecars and a read-only feed in
  Operations.
- Verification: **964 passed, 2 skipped in 191.69 s**; `ruff`, `mypy` (122
  files), `compileall`, `git diff --check` clean.
- Commits/tag/push: `799b34a` (journal) and `b6017d0` (release bump); annotated
  tag `v2.1.5` and `main` at `b6017d0`.
- Local build: exe `2.1.5.0` (PYZ TOC contains `app.changes` and
  `app.changes.service`), `dist\PCOptimizer_PRO_2.1.5_portable.zip`
  (56,773,075 B), `dist\installer\PCOptimizer_PRO_Setup_2.1.5.exe`
  (41,303,450 B) and `dist\PCOptimizer_PRO_src_v2.1.5.zip` (9,330,048 B).
  Smoke OK for both the frozen exe and the installed copy; `app_run` silently
  upgraded `2.1.4.0` → `2.1.5.0`, desktop shortcut target unchanged.
- CI Release run `45612185493` = success; CI run `45612176191` = success;
  [Release v2.1.5](https://github.com/dimaprisaznuk64/PCOptimizer_PRO/releases/tag/v2.1.5)
  published with installer + portable assets. Stale v2.1.4 artifacts removed.

### Stage 5 follow-up — update integrity (shipped in v2.1.5)
- GitHub release assets publish a `digest` (`sha256:...`). `UpdateInfo` now carries
  it, and `download_installer()` hashes the stream and refuses to save a file when
  the digest mismatches (fail-closed on malformed metadata too). The UI reports
  `(SHA-256 verified)` via new EN/UA `set_upd_downloaded_verified` key.
- Fixed drift in `docs/landing.html` (29 → 18 themes) and README (test count).
- Verification: **943 passed / 1 skipped** (~231 s); `ruff`, `mypy` (120 files),
  `compileall` clean. Shipped in release v2.1.5.

### Stage 5 follow-up — immutable system-change journal (shipped in v2.1.5)
- New `app/changes` service: append-only `system_changes.jsonl` with a SHA-256
  hash chain (`genesis -> prev_hash -> hash`), schema version, `integrity()`
  report and immutable read API. `read` never clears or marks entries; the
  activity feed stays separate and still supports Clear/Mark read.
- Backup integrity: `write_checksum`/`verify_checksum` sidecars for
  `optimizer_backup.json` and `startup_backup/history.jsonl`; legacy sidecar-free
  files are accepted, mismatches are quarantined and fail closed. Optimizer and
  Startup now use the same checksum helpers.
- Operations recorded into the new journal: `optimizer.apply`/`revert`,
  `restore.point`/`protection`, `startup.enable`/`disable`/`remove`/`undo`, and
  `cleaner.clean` (outcome `ok`/`warn`/`error`, with reasons/locked files).
- `OperationsPage` gained a read-only feed switch between Activity and System
  Changes, an integrity status line, and new EN/UA keys; no new page or nav item.
- Verification: targeted `155 passed, 1 skipped`; chunked full suite
  **964 passed, 2 skipped (966 collected)**; `ruff`, `mypy` (122 files),
  `compileall`, `git diff --check` clean. Shipped in release v2.1.5.

### Release v2.1.6 (2026-11-26)
- Version bumped to **2.1.6** in `app/__init__.py`, `assets/version_info.txt`
  (filevers/prodvers/StringStruct `2.1.6.0`), installer, README and EN/UA
  `sidebar_user_sub`.
- Includes `1564834` (unclean-exit detection): a live `session.json` marker is
  refreshed from sampler snapshots; a stale marker from a dead PID is reported
  on the next start via tray, ActivityLog and the log, then replaced. Clean exit
  removes the marker; a corrupt marker is quarantined for `RecoveryService`.
- Also includes snapshot fan-out to visible pages only (`fbbed21`) and the
  read-only crash-recovery report in Operations (`e199019`).
- Regenerated all **23** offscreen 1440×860 screenshots as
  `docs/screenshots/v2.1.6_*.png`; removed the obsolete `v2.1.5_*` set.
- Verification: **982 collected / 980 passed / 2 skipped**; `ruff`, `mypy`
  (125 files), `compileall`, `git diff --check` clean. Offscreen stale-marker
  probe confirmed the localized warning and clean marker removal.
- Commits/tag/push: `1564834` (feature) and `e68c017` (release bump); annotated
  tag `v2.1.6` pushed to `origin/main`.
- Local build: exe `2.1.6.0` (PYZ TOC contains `app.recovery.crash`), portable
  `dist\PCOptimizer_PRO_2.1.6_portable.zip` (56,782,487 B), installer
  `dist\installer\PCOptimizer_PRO_Setup_2.1.6.exe` (41,310,079 B) and source
  `dist\PCOptimizer_PRO_src_v2.1.6.zip` (9,172,363 B). Smoke OK for the frozen
  exe; `app_run` silently upgraded `2.1.5.0` → `2.1.6.0`, desktop/Start-menu
  shortcut targets unchanged. Stale v2.1.5 artifacts removed.
- CI Release run `45784515243` = success;
  [Release v2.1.6](https://github.com/dimaprisaznuk64/PCOptimizer_PRO/releases/tag/v2.1.6)
  published with installer (sha256
  `88b01ba874c4781e8fa24be1358ce699adf26a7e83e24c46ea44773243ab2b8d`) and
  portable (sha256
  `e0164e718a3c660264cecfffa5738c6ae52c4619e803763e392c90c17e1f1ac6`).

### Release v2.1.7 (2026-11-26)
- Version bumped to **2.1.7** in `app/__init__.py`, `assets/version_info.txt`
  (filevers/prodvers/StringStruct `2.1.7.0`), installer, README and EN/UA
  `sidebar_user_sub`. Regenerated all **23** offscreen 1440×860 screenshots as
  `docs/screenshots/v2.1.7_*.png`; removed the obsolete `v2.1.6_*` set.
- Includes `b01823b`: `PerfChart` decimation (3600 samples: 140.7 → 42.6 ms per
  repaint), a 15 s negative cache for empty thermal scans, game-presence watcher
  gated by `alerts_quiet_during_games`, deferred JSONL/recovery I/O for hidden
  History/Operations pages, and the visual clipping fixes from the 23-page audit.
  `a46cd57` narrows CSV values in the gaming telemetry helper for mypy.
- Verification: **996 collected / 994 passed / 2 skipped**; `ruff`, `mypy`
  (125 files), `compileall` and `git diff --check` clean. Frozen exe smoke test
  logged `starting PCOptimizer PRO 2.1.7`.
- Commits/tag/push: `a46cd57` (typing) and `f7f6373` (release bump) pushed to
  `main`; annotated tag `v2.1.7` pushed.
- Local build: exe `2.1.7.0`, portable `dist\PCOptimizer_PRO_2.1.7_portable.zip`
  (56,784,334 B), installer `dist\installer\PCOptimizer_PRO_Setup_2.1.7.exe`
  (41,312,356 B) and source `dist\PCOptimizer_PRO_src_v2.1.7.zip` (9,233,906 B).
  `app_run` silently upgraded `2.1.4.0` → `2.1.7.0`, desktop shortcut target
  unchanged; the installed GUI was relaunched (PID 5124). Stale v2.1.6 artifacts
  removed.
- CI Release run `45901419267` = success;
  [Release v2.1.7](https://github.com/dimaprisaznuk64/PCOptimizer_PRO/releases/tag/v2.1.7)
  published with installer (sha256
  `c4bf4222d335bfd978af15431f5133430880bc5eed2c5aa1a3a7fea30f8cc128`) and
  portable (sha256
  `109d1dc7241720975425e3133edbed2ce2574222768358fcf2ac2b7870ebe456`).

### Release v2.2.0 (2026-11-27)
- Final audit: offscreen EN/UA × 100/125/150% at 1440×860 across all **23**
  pages — 0 real clipped labels; functional probe **43/43** checks covering
  i18n parity (1377 keys per language), all **18** palettes, settings defaults,
  sensors/GPU/thermal, hardware/diagnostics, journal/backup integrity, recovery
  and MainWindow page rendering. Non-admin `list_points()` returned an honest
  `Access denied`, which is expected and already covered by `tests/test_restore.py`.
- Documentation drift fixed: `PLAN.md` and `docs/THEMES_REVIEW.md` now state the
  current 18-theme palette set (older 29-theme pass kept as history),
  `docs/landing.html` points at `v2.2.0_*` screenshots, README gained a final-audit
  bullet. Version bumped to **2.2.0** in `app/__init__.py`,
  `assets/version_info.txt` (`2.2.0.0`), installer, README and EN/UA
  `sidebar_user_sub`. Regenerated all **23** offscreen screenshots as
  `docs/screenshots/v2.2.0_*.png`; removed the `v2.1.7_*` set.
- Verification: **996 collected / 994 passed / 2 skipped**; `ruff`, `mypy`
  (125 files), `compileall` and `git diff --check` clean. Frozen exe smoke test
  logged `starting PCOptimizer PRO 2.2.0` and stayed alive.
- Commits/tag/push: `125351f` (release bump) pushed to `main`; annotated tag
  `v2.2.0` pushed. Local build: exe `2.2.0.0`, portable
  `dist\PCOptimizer_PRO_2.2.0_portable.zip` (56,785,626 B), installer
  `dist\installer\PCOptimizer_PRO_Setup_2.2.0.exe` (41,298,358 B), source
  `dist\PCOptimizer_PRO_src_v2.2.0.zip` (9,232,526 B). `app_run` silently
  upgraded `2.1.7.0` → `2.2.0.0`, desktop shortcut target unchanged. Stale
  v2.1.7 artifacts removed.
- CI Release run `45907374441` = success;
  [Release v2.2.0](https://github.com/dimaprisaznuk64/PCOptimizer_PRO/releases/tag/v2.2.0)
  published with installer (sha256
  `574784a8f3ae0c741545d1b886247511c4eb49e3359836726ed7fe43221226f9`) and
  portable (sha256
  `1c9cb9dc488e8d2aaca9de656356d382d4ffd6ffc31ceb6282e037c00a8d9c56`).

- Released **v1.7.1** (`d9f83ab`) вЂ” reliability/stabilization batch: fixed safe
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
  COM for background `Task`s вЂ” COM is now initialized only for hardware/health
  scans, not for psutil/subprocess work.
- v2.0.0 Stage 2 work: session peaks in Monitor/GPU pages,
  extended NVML telemetry (GPU hotspot, memory clock, honest clock-limit reason),
  Windows commit-charge / virtual-memory detail, top RAM-consuming processes,
  7-day history with advanced telemetry and per-process RAM history, and Gaming
  Mode 2.0 telemetry/profiles/session comparison charts.
- 23 pages, 18 themes now (29 at the earlier Stage 3 contrast pass), default theme **TITANIUM**.
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


## Audit v1.6.6 вЂ” step 1 (critical errors)
- Date: 2026-11-04.
- Symptom: a full `pytest` run printed `Windows fatal exception: access
  violation` (and `Win32 exception occurred releasing IUnknown`) at
  interpreter shutdown.
- Cause: pywin32 COM dispatch objects (startup scan via `WScript.Shell` and
  Task Scheduler) were released **after** `pythoncom.CoUninitialize()` had torn
  the apartment down.
- Fix: `app/wincom.py::run_in_com` initializes COM for the current thread and
  leaves apartment teardown to thread/process exit вЂ” no premature
  `CoUninitialize`. COM calls in `app/startup/service.py` (`_resolve_lnk`,
  `_task_items`, `_task_set_enabled`) now run through it.
- Regression test: `tests/test_startup.py::test_com_teardown_does_not_crash`
  runs the scan in a subprocess with `-X faulthandler` and asserts there is no
  access violation or IUnknown release error.
- Verified: full faulthandler run reports zero violations; `ruff` clean.

## Audit v2.0.0 вЂ” Stage 1 memory/performance profile
- Date: 2026-11-18. Offscreen probe: `%TEMP%\opencode\profile_memory.py` with an
  isolated `PCOPTIMIZER_DATA`; 3 cycles over all 17 pages plus 120 synthetic
  snapshots per cycle (360 total), feeding `MainWindow.handle_snapshot()`.
- RSS: 121.3 MB after construction в†’ 123.5 / 125.8 / 125.8 MB after cycles 1вЂ“3.
  Python objects: 56,620 в†’ 57,840 в†’ 57,842 в†’ 57,844; the steady `+1/cycle` is
  the probe's own `Counter`, not application state. No unbounded growth.
- First-cycle jump is one-time caching: ~366 `psutil.Process`, 66 `QLabel`,
  21 `Bar` objects (game-presence scan + first `apply_snapshot` layout). Bounded.
- Warm timings: construction 1.12 s (cold ~2.08 s), page switch avg 1.29 ms /
  p95 2.34 ms, snapshot avg 2.69 ms / p95 3.92 ms. Far inside the 1 s sampler
  budget; no UI-blocking hot path found.
- `shutdown()` temporarily raises RSS ~26 MB while Qt destroys the widget tree;
  teardown-only and consistent with the known faulthandler artifact. No fix.
- Conclusion: no runtime memory leak detected; Stage 1 profiling is complete.

## Audit v2.0.0 вЂ” Stage 2 monitoring extension
- Date: 2026-11-18. Goal: honest extended telemetry without fabricating values
  that Windows/NVML do not reliably expose.
- `GpuStat` now carries `temperature_hotspot`, `memory_clock_mhz`,
  `throttle_reasons` and `throttling`; `NvmlBackend` reads them best-effort and
  falls back to the last successful GPU sample.
- Idle-only NVML reason bits are not reported as throttling. Live PC probe
  showed reason `1024` and supported mask `2047`, so the UI now says
  `clock limited` / `РѕР±РјРµР¶РµРЅРЅСЏ С‡Р°СЃС‚РѕС‚` with the raw `0x...` reason instead of
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

## Audit v2.0.0 вЂ” RAM commit-charge telemetry
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

## v2.0.0 Stage 2 вЂ” RAM processes and long-horizon history
- Monitor page now has a В«Top RAM processesВ» table refreshed every 5 s from
  `ProcessService.top_by_memory()`; locked/vanished processes are skipped and
  partial failures are shown in the card status.
- `PerformanceHistory` keeps up to 7 days by default and compacts every 120
  records. `HistorySample` stores GPU hotspot, memory clock, power, honest
  throttling state and commit-charge percent; old entries remain readable.
- History page has a 7-day range and commit/hotspot metric cards.
- Verification: targeted Monitor/Processes/History/i18n suites 26 + 27 passed;
  full suite 747 passed.

## v2.0.0 Stage 2 вЂ” Gaming Mode 2.0 telemetry
- Added ARC Raiders (Steam appid `1808500`, `PioneerGame.exe`) and per-game
  optimization profiles stored in `gaming_profiles.json`.
- New `app/gaming/telemetry.py`: injectable frame provider, CSV/PresentMon
  reader, session JSONL history, nearest-rank 1% / 0.1% low calculation and
  resource/temperature before/after snapshots.
- No overlay and no game injection. If PresentMon CSV is not configured, the
  Gaming page honestly reports that FPS telemetry is unavailable.
- Gaming mode state is persisted separately in `gaming_mode.json`; a plain
  BALANCED optimizer backup no longer falsely restores В«mode onВ».
- Verification: targeted Gaming/Launcher/i18n suites 72 passed; full suite
  747 passed; `ruff` and `compileall` clean.

## v2.0.0 Stage 2 вЂ” Gaming session comparison charts
- Gaming Page now has a В«SESSION COMPARISONВ» card with a metric selector
  (CPU/RAM/GPU load, GPU temp, FPS) and a grouped before/after bar chart built
  from the last recorded sessions.
- `session_metric_value()` / `session_metric_unit()` in `app/gaming/telemetry.py`
  keep metric extraction pure and testable; FPS honestly has no before value
  without a configured baseline.
- The summary shows the average beforeв†’after change with direction-aware colour
  (lower load/temp and higher FPS are good).
- Verification: +2 tests (helpers + UI chart/metric switch); full suite 747
  passed; `ruff` and `compileall` clean.

## v2.0.0 Stage 2 вЂ” per-process RAM history
- `HistorySample` now carries the top 8 RAM-consuming processes per snapshot as
  `[name, MB]` pairs; old JSONL entries stay readable with an empty process list.
- `PerformanceHistory` accepts an injectable `process_top` callback wired to
  `ProcessService.top_by_memory()`; scan failures are logged and recorded as an
  empty list without dropping the rest of the snapshot.
- History page has a В«TOP RAM PROCESSESВ» card showing latest usage, peak usage
  and sample count per process, with EN/UA labels.
- Verification: +5 tests (roundtrip, capture, failure, summary, page rendering);
  targeted suite 50 passed; full suite 747 passed in 352.96s; `ruff` and
  `compileall` clean.

## v2.0.0 Stage 2 вЂ” final three tools
- Hardware Benchmark page combines configuration summary, CPU/RAM/disk runs,
  previous/current baseline comparison and redacted result export.
- Temperature Dashboard shows live/historical ACPI zones, NVIDIA core and
  hotspot temperatures with honest gaps, real session peaks and 1h/6h/24h/7d
  history; Refresh invalidates the history cache.
- Export Center exports Health, Benchmarks, Diagnostics, Performance History and
  System Report to CSV/JSON/HTML/PDF where supported, previews written files and
  reports partial failures honestly.
- Fixed System Report import of the removed `HistoryService`, GPU history field
  `power_draw` в†’ `power_w`, added `PySide6.QtPdf` to the frozen build spec.
- Verification: full suite 803 passed, 1 skipped in 351.64s; `ruff` and
  `compileall` clean. Native faulthandler/COM traces remain environmental.

## v2.0.0 Stage 3 вЂ” grouped navigation and Dashboard redesign
- `NAV_KEYS` order and all 22 pages are unchanged; keys are mapped into 7 groups:
  overview, monitoring, hardware, optimization, gaming, tools, settings.
- `Sidebar` renders group headers as checkable `QPushButton` (`navGroup`) with
  `в–ѕ`/`в–ё` (or `в”Ђ` in compact mode); collapsing hides only that group's buttons.
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
- Fixed 1024Г—640 horizontal-scroll regression: `ResourceHistoryWidget` and
  `PerfChart` use `QSizePolicy.Policy.Ignored` for horizontal growth.
- Fixed post-reload theme-token drift in `tests/test_components.py` by importing
  live `components`/`theme` modules.
- Verification: `PYTHONFAULTHANDLER=0 .venv/Scripts/python.exe -m pytest tests
  --no-header && .venv/Scripts/python.exe -m ruff check . &&
  .venv/Scripts/python.exe -m compileall -q app` в†’ **813 passed, 1 skipped in
  607.02s (0:10:07)**; `All checks passed!`; compileall clean.

## v2.0.0 Stage 3 вЂ” UI scale 100вЂ“150%
- `SettingsService` stores `ui_scale` (100вЂ“150); Settings has a live spin box
  with tooltip, applies immediately and keeps the current page.
- `theme.set_ui_scale()` recalculates all type tokens and the QSS. `main.py`
  applies the saved scale before UI modules are imported; `run()` applies it
  before `theme.apply(app)`.
- `MainWindow.apply_ui_scale()` reuses the theme rebuild path. 5 new tests in
  `tests/test_theme.py`, `tests/test_settings_page.py` and `tests/test_ui.py`.
- Verification: `.venv/Scripts/python.exe -m pytest tests --no-header
  -p no:faulthandler` в†’ **818 passed, 1 skipped in 1614.65s (0:26:54)**;
  ruff and compileall clean. Native COM artifacts remain environmental.

## v2.0.0 Stage 3 вЂ” scaled layout density
- `theme.ls()` grows paddings/margins/radii/control sizes at half the font rate;
  `set_ui_scale()` refreshes every layout token, including topbar/sidebar widths.
- Topbar, sidebar, icon tiles, gauges, empty hints and all 16 page roots now use
  the shared tokens instead of hardcoded sizes.
- Fixed startup scale: `main.py` exports `PCOPTIMIZER_UI_SCALE` before the UI
  package import, so the saved scale reaches topbar/sidebar/pages on first build.
- Verification: `.venv/Scripts/python.exe -m pytest tests --no-header
  -p no:faulthandler` в†’ **820 passed, 1 skipped in 1558.82s (0:25:58)**;
  ruff and compileall clean.

## v2.0.0 Stage 3 вЂ” 29-theme contrast pass
- Every palette is normalized at import: `TEXT_DIM`, `ACCENT`, `OK`, `WARN`,
  `DANGER` are blended until they reach 4.5:1 on BG/PANEL/PANEL_ALT, and
  `ON_ACCENT` is checked against `ACCENT`.
- Added a regression test covering all 29 themes / 7 foreground tokens.
- Verification: `.venv/Scripts/python.exe -m pytest tests --no-header
  -p no:faulthandler` в†’ **821 passed, 1 skipped in 1742.83s (0:29:02)**;
  ruff and compileall clean.

## v2.0.0 Stage 3 вЂ” Dashboard status strip (removed)
- Later removed at the user's request; the dashboard keeps the ring cards and
  the rest of the live telemetry without the extra top strip.
- A compact top-line card showed CPU/GPU/RAM/temperature/disk values beside
  the greeting, colored by the same load/temperature levels as the rings.
- It followed live language switching and was fed from the same sensor snapshot
  as the rest of the dashboard.
- Verification: `.venv/Scripts/python.exe -m pytest tests --no-header
  -p no:faulthandler` в†’ **822 passed, 1 skipped in 1450.35s (0:24:10)**;
  ruff and compileall clean.

## v2.0.0 Stage 3 вЂ” navigation polish and tooltips
- Sidebar buttons now carry localized `tip_nav_*` tooltips; compact mode shows
  label + description, group headers show the localized item count and a summary
  tooltip. The topbar status pill also explains its current state.
- Shared `MOTION_FAST/BASE/VALUE/AMOUNT/PULSE` tokens in `theme.py` unify page
  fades, ring/gauge animations and the status pulse.
- Fixed a live scan bug: `Shell.Application` size wraps above 2 GB, so the
  recycle-bin scan now sums real item lengths as `uint64` and clamps negatives.
- Verification: `.venv/Scripts/python.exe -m pytest tests --no-header
  -p no:faulthandler` в†’ **828 passed, 1 skipped** (829 collected, rc 0);
  ruff and compileall clean.

## v2.0.0 Stage 4 вЂ” global search palette
- New `app/ui/command_palette.py`: `SearchEntry`, `build_entries()` and pure
  `search_entries()` match page labels, groups, descriptions and keys; recent
  pages are pinned first when opened from the current navigation history.
- `TopBar` gained a search button and `search_requested`; `MainWindow` wires
  `Ctrl+K`, reuses one palette across theme rebuilds and retranslates it with
  the rest of the shell. Arrow keys, Enter and Escape work from the search box.
- Added the search glyph, palette QSS and 4 EN/UA keys; 11 new tests in
  `tests/test_command_palette.py`.
- Verification: `.venv/Scripts/python.exe -m pytest tests --no-header
  -p no:faulthandler` в†’ **839 passed, 1 skipped in 1668.67s (0:27:48)**;
  ruff and compileall clean. A pre-existing `IUnknown` release message remains
  environmental.

## v2.0.0 Stage 4 вЂ” notification center
- `ActivityLog` now tracks read timestamps in `activity_read.json` (portable
  data dir): `mark_read`, `mark_all_read`, `is_read`, `unread_count`, pruned on
  compaction and cleared together with the activity history.
- New `app/ui/notifications.py` popup: title/unread counter, All / Unread /
  Warnings & errors filters, click-to-read and Clear; entries use level icons
  and bold unread rows. The bell opens it on left click (right click keeps the
  old quick menu), tints accent while unread and explains the count in the
  tooltip. The popup follows live language switching and theme rebuilds.
- 7 new tests (`tests/test_notifications.py`); full suite 846 passed, 1 skipped.

## v2.0.0 Stage 4 вЂ” recent operations center
- New 23rd page (`app/ui/operations.py`) in the Overview group: summary cards
  (all/successful/partial/failed), full history table, text search, level and
  time filters, detail pane, CSV/JSON export and confirmable clear.
- `ActivityLog.Entry` now carries an optional `source` page key (back-compatible
  with old JSONL lines); cleaner, optimizer, gaming, launcher, health, network,
  monitor alerts and update notices record where they came from. Selecting an
  entry with a source offers an В«Open pageВ» jump and marks it read.
- In-memory/read-state/compact limits grew from 30 to 200 entries so the center
  has a useful history span; notifications and the dashboard still show 4вЂ“30.
- 9 new tests (`tests/test_operations.py`) cover filtering, export helpers,
  persistence, navigation, clear confirmation, retranslation and registration.
- Verification: full suite `.venv/Scripts/python.exe -m pytest tests --no-header
  -p no:faulthandler` в†’ **857 passed, 1 skipped in 1960.55s (0:32:40)**;
  `ruff check .`, `compileall -q app` and `git diff --check` clean. Offscreen
  1280Г—800 render preview: `%TEMP%\opencode\operations_preview.png` (5 rows,
  333 sampled colours). The pre-existing `IUnknown` release message at shutdown
  remains environmental.

## v2.0.0 Stage 4 вЂ” first-run wizard
- New 3-step modal `app/ui/first_run.py`: welcome/safety explanation, starter
  preferences (language, one of three curated themes, interface scale, update
  checks, temperature/usage alerts, quiet-hours and tray behaviour), and a
  finish summary with an option to jump into Settings. Skip marks the flow done
  without touching other preferences.
- Settings state: `first_run_completed` defaults to True so existing installs are
  not interrupted; `run()` flips it to False only when `settings.json` is new.
  SettingsPage gained a В«Run setup wizardВ» button that can replay it.
- MainWindow applies the chosen language/theme/scale live immediately after the
  dialog closes and preserves the current page through the theme rebuild.
- 8 new tests (`tests/test_first_run.py`) cover defaults, legacy settings,
  applying values, skip, invalid choice, step navigation/retranslation, the
  Settings replay button and MainWindow integration.
- Verification: full suite `.venv/Scripts/python.exe -m pytest tests --no-header
  -p no:faulthandler` в†’ **865 passed, 1 skipped in 1922.45s (0:32:02)**;
  `ruff check .`, `compileall -q app` and `git diff --check` clean. Offscreen
  720Г—620 render preview: `%TEMP%\opencode\first_run_wizard_preview.png`. The
  intermittent `IUnknown` release message at shutdown remains environmental.

## v2.0.0 Stage 4 вЂ” context menus / quick actions
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
- Verification: `.venv/Scripts/python.exe -m pytest tests --no-header` в†’
  **871 passed, 1 skipped in 2360.92s (0:39:20)**; `ruff check .`,
  `compileall -q app` and `git diff --check` clean. The intermittent `IUnknown`
  release message at shutdown remains environmental.

## v2.0.0 Stage 4 вЂ” dashboard customization
- New `app/ui/dashboard_custom.py` with canonical widget keys, `parse_dashboard_hidden()`
  and `DashboardCustomizerDialog`. Settings gets a В«Customize dashboardВ» button;
  choices are validated/canonicalized and saved to portable `data_root()` as the
  `dashboard_hidden` setting (comma-separated string).
- `DashboardPage(dashboard_hidden=...)` hides selected widgets, skips empty section
  headers and rebuilds the responsive grid so remaining widgets occupy freed cells.
  Hidden network/process widgets also skip their background pollers.
- Live apply is wired through `SettingsPage(on_dashboard_hidden_applied=...)` в†’
  `MainWindow.apply_dashboard_hidden()` в†’ `DashboardPage.set_hidden_widgets()`;
  theme rebuilds preserve the saved layout.
- Added 21 EN/UA `dash_custom_*` keys, 5 tests for dialog/parse/serialize, hide
  behavior, live apply and settings persistence. Verification: targeted
  `tests/test_dashboard.py tests/test_settings_page.py tests/test_i18n.py
  tests/test_settings.py` в†’ **77 passed**; full suite в†’ **876 passed, 1 skipped in
  2250.78s (0:37:30)**; `ruff check .`, `compileall -q app`, `git diff --check` clean.
  The intermittent `IUnknown`/access-violation shutdown artifact remains environmental.

## v2.0.0 Stage 4 вЂ” screenshots + live verification
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
  readability at 100вЂ“150% scale.
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
  GPU rows with honest `вЂ”` when no sensor exists; GPU comes from NVML.
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
  `ThermalStat`. Missing CPU/board sensors, `0В°C` LHM CPU readings, disabled
  HWiNFO, ACPI access denied and LHM WMI failures are no longer swallowed.
- LHM reader keeps raw readings for diagnostics and filters non-positive values
  in `pick_temperatures()` instead of losing the reason.
- `TemperaturePage` now shows the backend notes inline, sets explanatory
  tooltips on missing CPU/board values and adds a В«Restart as adminВ» button.
  Dashboard thermal card exposes the same notes via tooltip.
- i18n: 11 EN/UA keys (`temp_admin*`, `temp_note_*`, `temp_sources_label`).
- Fixed mojibake in `tests/test_temperature.py` literals (`Р’В°C`, `Р ...`)
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

## v2.0.2 (unreleased) вЂ” sensors/typing fixes after the 2026-11-22 review

- Fixed regression in `temperature_kind`: the canonical-key shortcut turned a raw
  SuperIO sensor literally named `System` into the `system` kind, so LHM lost its
  board temperature. Added `raw_temperature_kind` (no shortcut) for backends and
  kept `temperature_kind` (canonical keys pass through) for the merged snapshot,
  UI and services. Two `tests/test_lhm.py` tests had caught it.
- New `disk` temperature kind: HWiNFO S.M.A.R.T. drive temperature is no longer
  mislabelled as `system`; `zone_label` now translates `hotspot`/`system`/`disk`.
- HWiNFO reader: ignores stale shared memory (poll stamp older than 120 s; an
  absent/implausible stamp is "unknown" and never hides data), wording now says
  *Shared Memory Support*, plus a 12-hour free-version hint (EN/UA).
- Real bug found by mypy: `psutil.TimeoutOccurred` does not exist
  (`TimeoutExpired`); a slow-to-exit process raised `AttributeError` instead of
  `terminate()` returning `False`. Regression test added.
- mypy: 10 existing errors fixed (0 errors on `mypy app` with the project config).
- Repo hygiene: `.venv*/` ignored, `pythonnet` added to `pyproject.toml`,
  `requires-python` capped at `<3.15`, README badge no longer hard-codes a test count.

## v2.1.1 (released) вЂ” update download integrity

- `app/update/service.py`: `_asset_sha256()` validates the 64-hex `digest` from
  the GitHub release API and `_find_asset()` now returns `(url, name, sha256)`.
- `app/update/download.py`: the stream is hashed with `hashlib.sha256`; after the
  MZ/size checks the digest is compared with `hmac.compare_digest`. Invalid or
  mismatched metadata raises `UpdateDownloadError`, removes `.part`, and never
  saves the file. `SettingsPage` reports verified downloads via a new EN/UA key.
- Tests: `tests/test_update.py` +5 (digest extraction, md5/ malformed digest
  ignored, verified download, mismatch, invalid metadata). Full suite
  `943 passed, 1 skipped in 175.86s`; `ruff`, `mypy` (120 files), `compileall`
  and `git diff --check` clean.
- Release: version bumped in `app/__init__.py`, `assets/version_info.txt`,
  `installer/PCOptimizer_PRO.iss` and EN/UA sidebar label. 23 screenshots
  regenerated as `docs/screenshots/v2.1.1_*.png` (EN, live snapshot, seeded
  history/activity). Frozen exe `2.1.1.0` built and smoke-tested; portable zip
  and installer built locally; tag/release published on GitHub.

## Next

- v2.3.2 is committed as `e89de8d` and released from `6399f20`; the shipped
  reliability fixes cover Cleaner whitelist/schedule safety, history append
  retries and honest gaming-mode state on persistence failure.
- The baseline design is frozen and the 23-module / 100-150% scaling audit is
  complete; no further structural UI changes without a new request.
- Readability follow-ups from the approved baseline are done and shipped in
  v2.0.1; user review of the live charts / Health Score breakdown is complete.
- v2.0.x reliability: trustworthy CPU package power / thermal-throttling source
  only if a reliable Windows API appears.
- `mypy` is wired into CI as non-blocking. Dev dependency stays pinned to
  `>=1.11,<2` because mypy 2.4.1 crashed internally on this tree. All remaining
   typing errors were fixed in `e0d244f`; `python -m mypy app` now reports
   **Success: no issues found in 125 source files**.
- Release v2.1.0 is published: tag `v2.1.0` points to `739123b`, GitHub Actions
  Release run `45369199779` completed successfully, and the GitHub release has
  `PCOptimizer_PRO_Setup_2.1.0.exe` + `PCOptimizer_PRO_2.1.0_portable.zip`.
- Release v2.1.1: tag `a7c327e`, GitHub Actions Release run `45381697565`
  completed successfully; assets `PCOptimizer_PRO_Setup_2.1.1.exe` +
  `PCOptimizer_PRO_2.1.1_portable.zip` (installer sha256
  `6a0f77bfc90c2c85f23bca27a3ef0be72abc765118fcda5070207b971449f150`).
- Release v2.1.2: tag `v2.1.2` / `8c72666` published, but its Release CI rerun
  failed because the tag points to pre-i18n-fix code; assets were built from
  that old commit. Superseded by v2.1.3.
- Release v2.1.3: tag `v2.1.3` / `f6c18c1` (over `9bdbb0c` i18n mojibake fix +
  `e973b5d` `.editorconfig`), GitHub Actions Release run `45520158504`
  completed successfully; assets `PCOptimizer_PRO_Setup_2.1.3.exe` +
  `PCOptimizer_PRO_2.1.3_portable.zip` published.
- Release v2.1.5: tag `v2.1.5` / `b6017d0`; CI Release run `45612185493`
  (success). Assets `PCOptimizer_PRO_Setup_2.1.5.exe` (sha256
  `e1f589f3b060d1ac805f9e16b9207b9e31abf75c4ed0f43326c8858b9685170f`) and
  `PCOptimizer_PRO_2.1.5_portable.zip` (sha256
  `0f439ba16eb437acbb82920036e4b03552cfb671d9c151e09b51aed4ef3cb50c`).
- Release v2.1.6: tag `v2.1.6` / `e68c017`; CI Release run `45784515243`
  (success). Assets `PCOptimizer_PRO_Setup_2.1.6.exe` (sha256
  `88b01ba874c4781e8fa24be1358ce699adf26a7e83e24c46ea44773243ab2b8d`) and
  `PCOptimizer_PRO_2.1.6_portable.zip` (sha256
  `e0164e718a3c660264cecfffa5738c6ae52c4619e803763e392c90c17e1f1ac6`).
- Release v2.1.7: tag `v2.1.7` / `f7f6373`; CI Release run `45901419267`
  (success). Assets `PCOptimizer_PRO_Setup_2.1.7.exe` (sha256
  `c4bf4222d335bfd978af15431f5133430880bc5eed2c5aa1a3a7fea30f8cc128`) and
  `PCOptimizer_PRO_2.1.7_portable.zip` (sha256
  `109d1dc7241720975425e3133edbed2ce2574222768358fcf2ac2b7870ebe456`).
- Release v2.2.0: tag `v2.2.0` / `125351f`; CI Release run `45907374441`
  (success). Assets `PCOptimizer_PRO_Setup_2.2.0.exe` (sha256
  `574784a8f3ae0c741545d1b886247511c4eb49e3359836726ed7fe43221226f9`) and
  `PCOptimizer_PRO_2.2.0_portable.zip` (sha256
  `1c9cb9dc488e8d2aaca9de656356d382d4ffd6ffc31ceb6282e037c00a8d9c56`).
- Release v2.3.0: tag `v2.3.0` / `2a227ef`; CI Release run `45975255005`
  (success). Assets `PCOptimizer_PRO_Setup_2.3.0.exe` (sha256
  `555c359014eb786126f096ae72fe5d4ffe3b6b1aa1bc9362de06fb1d1dbcf4f1`) and
  `PCOptimizer_PRO_2.3.0_portable.zip` (sha256
  `bd78f104bbc2e8a9194f69485df8e7c85f7f5c1eb79cc4c0b2f299d921eda2c0`).
- Audit follow-ups (from `docs/AUDIT_v2.0.1.md`): B-09 is fixed — full pytest
  single run now passes (943 / 1 skipped); B-10 is skipped by owner decision
  (HWiNFO is not installed, live `poll_time` check is not required).

## R107 safe FPS/CPU overlay (source-only, 2026-11-28)
- Approved scope: «Базовий + PresentMon opt-in (Recommended)». Implemented the
  anti-cheat-safe variant: a separate Qt `Tool` window with
  `FramelessWindowHint`, `WindowStaysOnTopHint`, `WindowDoesNotAcceptFocus`,
  translucent background and transparent mouse events; no DLL injection,
  detours/hooks, process-memory access, or game control.
- New `app/overlay/`: `hotkey.py` (`OverlayHotkey` with Win32
  `RegisterHotKey`/`UnregisterHotKey` via `ctypes`, `Ctrl+Alt+F9`, native event
  filter registered for the app lifetime, safe non-Windows no-op) and `widget.py` (`OverlayWidget`,
  `OverlayService(QObject)`, 250 ms poll timer, live snapshot application,
  idempotent close, theme/font/language refresh).
- FPS source priority: Settings `presentmon_csv_path` → env
  `PCOPTIMIZER_PRESENTMON_CSV` → static unavailable value. `app/gaming/telemetry.py`
  now has bounded tail reads and `latest_frame()` on CSV providers, so only the
  newest PresentMon frame is used for overlay FPS.
- Settings addition: `overlay_enabled` (default `False`) and
  `presentmon_csv_path` (default `""`) with Browse and live apply. Tray gained a
  checkable «FPS overlay» action; `MainWindow` wires tray/hotkey/settings,
  replays snapshots into the overlay, and closes it on shutdown/theme rebuild.
- Caveats documented for users: PresentMon is not bundled and live CSV may need
  admin or `Performance Log Users`; HAGS may distort some GPU timings;
  OpenGL/Vulkan can be less exact; exclusive fullscreen may cover the overlay
  (borderless/windowed is recommended).
- `PCOptimizer_PRO.spec` hidden-imports `app.overlay`, `app.overlay.hotkey`,
  `app.overlay.widget`. EN/UA keys and an AST parity test cover all overlay
  translation keys.
- Verification: targeted overlay/settings/tray/UI/i18n/telemetry tests pass;
  full suite **1013 collected / 1011 passed / 2 skipped**; `ruff check .`,
  `mypy app` (Success: no issues in 128 files), `compileall -q app`, and
  `git diff --check` clean (CRLF warnings only). At that point the work was
  source-only; the v2.3.0 release below ships it.
- Hotkey follow-up: `Ctrl+Alt+F9` is now registered for the whole app lifetime,
  so it can also turn a hidden overlay on; `set_enabled()` no longer
  re-registers/unregisters and `close()` unregisters once. Added a regression
  test that emits the hotkey signal while the overlay is hidden. An offscreen
  paint probe produced a non-blank 300×156 preview.

### Release v2.3.0 (2026-11-28)
- Version bumped to **2.3.0** in `app/__init__.py`, `assets/version_info.txt`
  (filevers/prodvers/StringStruct `2.3.0.0`), installer and EN/UA
  `sidebar_user_sub`; README badge, install commands and screenshot links updated.
- Regenerated all **23** page screenshots plus `v2.3.0_overlay.png` at 1440×860
  (overlay preview 300×156); removed the obsolete `v2.2.0_*` set.
- Verification after the bump: **1013 collected / 1011 passed / 2 skipped**;
  `ruff`, `mypy` (Success, 128 files), `compileall`, `git diff --check` clean.
- Local build commands: `powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1`,
  `powershell -ExecutionPolicy Bypass -File scripts/create_portable.ps1`,
  `powershell -ExecutionPolicy Bypass -File scripts/build_installer.ps1`, and
  `git archive -o "dist/PCOptimizer_PRO_src_v2.3.0.zip" HEAD`. Built artifacts:
  `dist\PCOptimizer_PRO\PCOptimizer_PRO.exe` (2.3.0.0, 5,795,286 B, sha256
  `a575c1514029caf1fb5cd08733d4de9c322380102d03a0b888bf46d48dea73f2`),
  `dist\PCOptimizer_PRO_2.3.0_portable.zip` (56,806,789 B, sha256
  `4e6f1e43bbaab83e8a5d047b809e3db1bfa4eee3612753391d92f31f885c384f`),
  `dist\installer\PCOptimizer_PRO_Setup_2.3.0.exe` (41,333,568 B, sha256
  `433b7d139d67007ee8acbbec9445e5e4061f4cde3df2e5e90f5b6cab91b0b28c`), and
  `dist\PCOptimizer_PRO_src_v2.3.0.zip` (9,253,684 B, sha256
  `b58b18a92219849bc0f32609d38d459451aed70a794bfde5ac99564d371a87c4`).
  `PYZ-00.toc` has `app.overlay`, `app.overlay.hotkey`, `app.overlay.widget`,
  `app.reports.pdf`, `app.update.download`, `app.changes.service`, and
  `app.recovery.crash`; `COLLECT-00.toc` has Geist and Geist Mono fonts.
  Frozen smoke: `starting PCOptimizer PRO 2.3.0` in
  `C:\Users\Admin\AppData\Local\Temp\pcopt_v230_smoke_data\logs\PCOptimizer_PRO.log`;
  process stayed alive for 10 s. Silent upgrade of `app_run` from 2.2.0.0 to
  2.3.0.0 succeeded and the Desktop shortcut targets `app_run\PCOptimizer_PRO.exe`.
  Stale 2.2.0 portable/source/installer artifacts were removed.
- CI Release run `45975255005` (`https://github.com/dimaprisaznuk64/PCOptimizer_PRO/actions/runs/45975255005`,
  job `140425267345`) completed with `success`; all steps including Pytest,
  Build exe, Verify built exe, Build installer, Portable zip and Create GitHub
  Release succeeded. [Release v2.3.0](https://github.com/dimaprisaznuk64/PCOptimizer_PRO/releases/tag/v2.3.0)
  is published with `PCOptimizer_PRO_Setup_2.3.0.exe` (43,420,995 B, sha256
  `555c359014eb786126f096ae72fe5d4ffe3b6b1aa1bc9362de06fb1d1dbcf4f1`) and
  `PCOptimizer_PRO_2.3.0_portable.zip` (62,353,919 B, sha256
  `bd78f104bbc2e8a9194f69485df8e7c85f7f5c1eb79cc4c0b2f299d921eda2c0`).

### R110 post-release reliability pass (source-only, after v2.3.0)
- `app/settings/service.py`: `_valid_json_file()` handles `OSError`,
  `UnicodeDecodeError` and `json.JSONDecodeError`; `load()` records a visible
  `load_error` and falls back to defaults on invalid UTF-8 instead of crashing.
  Migration replaces an invalid non-UTF-8 destination file.
- `app/changes/service.py`: added `ChangeJournalError`, an `RLock` around
  append/read/integrity/clear, and an integrity check before append. A corrupt
  non-UTF-8 journal is reported through `integrity()` and blocks further writes
  rather than silently breaking the SHA-256 chain.
- `app/ui/settings.py`: `SettingsPage.save()` catches `OSError` and shows it in
  the UI instead of leaking an unhandled disk exception.
- `app/gaming/telemetry.py`: `FrameProvider.read_new_frames(since_ts=...)` and
  `CsvFrameProvider` tail tracking let the overlay ingest each PresentMon row
  once; `resource_metrics()` now excludes GPU sensors from the system/board
  temperature value.
- `app/overlay/widget.py`: duplicate frame signatures are ignored, stale frames
  clear FPS/percentile values, changing the source clears samples, and all
  overlay service actions become no-ops after `close()`. Hotkey registration
  failure is logged instead of being silent.
- `app/update/service.py`: a checksumless installer no longer masks a later
  verified installer in the same GitHub release payload.
- `app/ui/operations.py`: recovery status now refreshes when the activity log
  changes, so external cleanup is reflected without reopening the page.
- `app/gaming/telemetry.py`: CSV column lookup is case-insensitive and accepts
  real PresentMon 2.x headers (`CPUStartTime`, `MsBetweenPresents`), so the
  official CSV works without manual column renaming; README documents the
  official download and a sample `--process_name/--output_file` command.
- Tests added for all findings. Verification: targeted 138 passed; full suite
  **1027 collected / 1025 passed / 2 skipped in 207.23 s**; `ruff check .`,
  `mypy app` (Success, 128 files), `compileall -q app tests` and
  `git diff --check` clean (CRLF warnings only).

### Release v2.3.1 (2026-11-28)
- Version bumped to **2.3.1** in `app/__init__.py`, `assets/version_info.txt`
  (filevers/prodvers/StringStruct `2.3.1.0`), installer and EN/UA
  `sidebar_user_sub`; README badge, install names and screenshot links and
  `docs/landing.html` screenshot links updated.
- Regenerated all **23** page screenshots plus `v2.3.1_overlay.png` at 1440×860
  (overlay preview 300×156); removed the obsolete `v2.3.0_*` set. Helper:
  `%TEMP%\opencode\shoot_v231.py` with an isolated `PCOPTIMIZER_DATA`.
- Verification after the bump: **1027 collected / 1025 passed / 2 skipped in
  209.47 s**; `ruff check .`, `mypy app` (Success, 128 files), `compileall -q app`
  and `git diff --check` clean (CRLF warnings only).
- Commits/tag: `938ec5b` (reliability fixes, pushed `10aa48b..938ec5b`),
  `f79bd6a` (`chore(release): bump version to 2.3.1 and refresh screenshots`),
  annotated tag `v2.3.1` (`Release v2.3.1`), pushed `main` and tag.
- Local build commands: `powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1`,
  `powershell -ExecutionPolicy Bypass -File scripts/create_portable.ps1`,
  `powershell -ExecutionPolicy Bypass -File scripts/build_installer.ps1`, and
  `git archive -o "dist/PCOptimizer_PRO_src_v2.3.1.zip" HEAD`. Built artifacts:
  `dist\PCOptimizer_PRO\PCOptimizer_PRO.exe` (2.3.1.0, 5,797,162 B, sha256
  `633a9f0a335c94fe99f5aefbe1558b8591515efa303ec50e94024085891dc1e2`),
  `dist\PCOptimizer_PRO_2.3.1_portable.zip` (56,809,384 B, sha256
  `1f80f6f6ca31e05ac71927620ce9237f5d39de50b812efdd82077e8fd4342576`),
  `dist\installer\PCOptimizer_PRO_Setup_2.3.1.exe` (41,332,160 B, ProductVersion
  2.3.1, sha256 `cdde0f6e9df54c5f8c5f910d9493be41c75aab3d119a0cb59aa3d1b44c9c6a85`),
  and `dist\PCOptimizer_PRO_src_v2.3.1.zip` (9,386,370 B, sha256
  `a64f7b27ed65c13a2577778ecc710c7d362e2811a139dec40afbaf1baa387eb1`).
  `PYZ-00.toc` has `app.overlay*`, `app.reports.pdf`, `app.update.download`,
  `app.changes.service` and `app.recovery.crash` modules.
  Frozen smoke: `starting PCOptimizer PRO 2.3.1` in
  `C:\Users\Admin\AppData\Local\Temp\pcopt_v231_smoke_data\logs\PCOptimizer_PRO.log`;
  process stayed alive for 10 s. Silent upgrade of `app_run` from 2.3.0.0 to
  2.3.1.0 succeeded and the Desktop shortcut targets `app_run\PCOptimizer_PRO.exe`.
  Stale 2.3.0 portable/source/installer artifacts were removed.
- CI Release run `46077783826` (`https://github.com/dimaprisaznuk64/PCOptimizer_PRO/actions/runs/46077783826`,
  job `140769464297`) completed with `success`; all steps including Pytest,
  Build exe, Verify built exe, Build installer, Portable zip and Create GitHub
  Release succeeded. [Release v2.3.1](https://github.com/dimaprisaznuk64/PCOptimizer_PRO/releases/tag/v2.3.1)
  is published with `PCOptimizer_PRO_Setup_2.3.1.exe` (43,422,737 B, sha256
  `0702c2c0da4867251ad12d78c316fc160767cfd11bdd22bd6c0c1fb7d1f22efb`) and
  `PCOptimizer_PRO_2.3.1_portable.zip` (62,354,195 B, sha256
  `5ea3963096f91a5a7b0b3038fd44c5e7fad6bff0086466255dbb0dd5fdf7e4c2`).

### Release v2.3.2 (2026-11-28)
- Version bumped to **2.3.2** in `app/__init__.py`, `assets/version_info.txt`
  (filevers/prodvers/StringStruct `2.3.2.0`), installer and EN/UA
  `sidebar_user_sub`; README badge, install names and screenshot links and
  `docs/landing.html` screenshot links updated.
- Regenerated all **23** page screenshots plus `v2.3.2_overlay.png` at 1440×860
  (overlay preview 300×156); removed the obsolete `v2.3.1_*` screenshot set.
  Helper: `%TEMP%\opencode\shoot_v232.py` with an isolated `PCOPTIMIZER_DATA`.
- Verification after the bump: **1033 passed / 2 skipped in 199.04 s**;
  `ruff check .`, `mypy app` (Success, 128 files), `compileall -q app` and
  `git diff --check` clean (CRLF warnings only).
- Commits/tag: `e89de8d` (`fix(reliability): harden cleaner whitelist, schedule
  and state persistence`, pushed `d8f437d..e89de8d`), `6399f20`
  (`chore(release): bump version to 2.3.2 and refresh screenshots`), annotated
  tag `v2.3.2` (`Release v2.3.2`), pushed `main` and tag.
- Local build commands: `powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1`,
  `powershell -ExecutionPolicy Bypass -File scripts/create_portable.ps1`,
  `powershell -ExecutionPolicy Bypass -File scripts/build_installer.ps1`, and
  `git archive -o "dist/PCOptimizer_PRO_src_v2.3.2.zip" HEAD`. Built artifacts:
  `dist\PCOptimizer_PRO\PCOptimizer_PRO.exe` (2.3.2.0, 5,800,147 B, sha256
  `850bd8d5b9e13e49b4a419f2dfa16e656dd407b13df93e26a2cea51b15489f09`),
  `dist\PCOptimizer_PRO_2.3.2_portable.zip` (56,811,430 B, sha256
  `8908be7d01be327a513907755fa8f02e5d0b3659c2c8e2cf4e0e2b8edce5b7da`),
  `dist\installer\PCOptimizer_PRO_Setup_2.3.2.exe` (41,336,003 B, ProductVersion
  2.3.2, sha256 `0754b34eaff347c522bcf3d5a986bd7b559b3fdb4b271343a060131b8e252d6a`),
  and `dist\PCOptimizer_PRO_src_v2.3.2.zip` (8,922,433 B, sha256
  `c0407e0f9b35194c8b20308974127932b34ef0cc501bee42097db802f1c4064`).
  Frozen archive listing confirmed `app.overlay*`, `app.reports.pdf`,
  `app.update.download`, `app.changes.service`, `app.recovery.crash` and
  `app.ui.launcher`. Frozen smoke: `starting PCOptimizer PRO 2.3.2` in
  `%TEMP%\pcopt_v232_smoke\logs\PCOptimizer_PRO.log`; process stayed alive for
  10 s. Silent upgrade of `app_run` from 2.3.1.0 to 2.3.2.0 succeeded, the
  Desktop and Start Menu shortcuts target `app_run\PCOptimizer_PRO.exe`, and a
  smoke launch of the installed exe logged `starting PCOptimizer PRO 2.3.2`.
  Stale 2.3.1 portable/source/installer artifacts were removed.
- CI Release run `46135629935`
  (`https://github.com/dimaprisaznuk64/PCOptimizer_PRO/actions/runs/46135629935`)
  completed with `success`. [Release v2.3.2](https://github.com/dimaprisaznuk64/PCOptimizer_PRO/releases/tag/v2.3.2)
  is published with `PCOptimizer_PRO_Setup_2.3.2.exe` (43,423,250 B, sha256
  `54bf35dcd19602006476c40c3acc316b7a3e49acec13da1f11fe14c14ca394ed`) and
  `PCOptimizer_PRO_2.3.2_portable.zip` (62,359,527 B, sha256
  `267462c52275dd33335a032a94c123ee068aed9be9d8160448b80722af3b5a88`).
