# Development Plan

## Status
- Core audit of page headers completed.
- `CardTitleLabel` usage unified across all components.
- All section headers converted to `card_heading` across the 17 pages.
- Card padding / radius / page rhythm unified (`e5622a3`).
- Processes page de-lagged: fixed column widths, unchanged renders skipped, async details (`cb8d039`).
- New shipped default theme **TITANIUM** (deep cyber-blue re-skin of the palette).
- Pytest suite is passing (504 tests).
- Ruff linter is clean.
- Offscreen rendering smoke test verified.
- Release **v1.6.1** prepared (exe + portable + installer + GitHub release).

## Accomplishments
- Audit every page's section headers (cardTitle usage) + retranslate title refs (Verified).
- Convert all card section titles to card_heading (Verified).
- Bring dashboard custom cards onto shared tokens (Verified).
- Remove inline font deviations (Verified).
- Unify header badges (pageBadge) across pages (Verified).
- Fix the `CardTitleLabel` AttributeError (document property) (Verified).
- Make the theme default name a single source of truth (`theme.DEFAULT_THEME`), tests no longer hardcode `GRAPHITE` (Verified).
- Run pytest + ruff (Verified).
- Offscreen render smoke test (Verified).
- Regenerate the 17 release screenshots in the new default theme (Verified).

## Next
- Publish the v1.6.1 GitHub release and refresh the installed `app_run` build.
- Optional: light-theme (Arctic/Ivory) polish pass over all 17 pages.
- Optional: auto-update check against GitHub `releases/latest`.
