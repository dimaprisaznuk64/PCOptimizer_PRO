# Development Plan

## Status
- Version bumped to **v1.6.6** (unreleased): update check, sensor resilience,
  refreshed docs; local portable exe built and smoke-tested.
- Released **v1.6.5** (`48db527`) — installer, portable build and GitHub release.
- Audit findings **A-01…A-14** (`docs/AUDIT_v1.6.1.md`) closed across v1.6.2–v1.6.5.
- 17 pages, 29 themes, default theme **TITANIUM**.
- Pytest suite is passing (556 tests).
- Ruff linter is clean.
- Offscreen rendering smoke test verified.
- Sensor backend made resilient on PCs where Windows performance counters are
  disabled: `psutil.swap_memory()` / `cpu_freq()` failures no longer drop every
  other metric (regression test added).
- Optional update check against GitHub `releases/latest` added: startup check
  (can be turned off in Settings), "Check now" button, version display and
  release-page link; results go to the activity log + tray notification.

## Accomplishments
- Unified `CardTitleLabel` / `card_heading` across all 17 pages.
- Unified card padding, radius and page rhythm (`e5622a3`).
- Processes page de-lagged: fixed column widths, unchanged renders skipped,
  async details (`cb8d039`).
- Theme default is a single source of truth (`theme.DEFAULT_THEME`).
- Regenerated release screenshots for v1.6.5.
- Hardened sensors for machines without PDH counters.
- Added the GitHub release update check with injected fetcher for tests.

## Next
- Commit v1.6.6 and push the `v1.6.6` tag — CI builds the installer, portable
  zip and GitHub release.
- Optional: light-theme (Arctic/Ivory) polish pass over all 17 pages.
- Optional: wire `mypy` into the verification routine and fix the first batch
  of findings.
