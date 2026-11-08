# Development Plan

## Status
- Released **v1.6.6** (`fe183d4`) — GitHub update check, resilient sensors.
- **v1.6.7** (unreleased, committed locally): post-1.6.5 reliability audit merged
  on top of v1.6.6:
  - Steam VDF library paths are decoded without `unicode_escape`, so non-ASCII
    paths (e.g. `D:\Ігри\Steam`) stay intact.
  - Optimizer backup stores the raw HAGS DWORD and restores it exactly (a `0`
    snapshot no longer becomes `1`); `apply_profile()` refuses to change a
    setting it could not snapshot, so revert always stays possible.
  - Regression tests added for both fixes (+6 tests).
- Audit findings **A-01…A-14** (`docs/AUDIT_v1.6.1.md`) closed across v1.6.2–v1.6.5.
- 17 pages, 29 themes, default theme **TITANIUM**.
- Pytest suite is passing (562 tests). Ruff linter is clean.
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

## Next
- Build v1.6.7 exe + portable + installer, then push the `v1.6.7` tag and
  publish the GitHub release.
- Optional: light-theme (Arctic/Ivory) polish pass over all 17 pages.
- Optional: wire `mypy` into the verification routine and fix the first batch
  of findings.
