# memory.md — matchavez/nzihl-broadcast-assets

Self-context for Claude. Not written for humans — README.md is the human-facing doc, keep both in sync (see sync note at bottom). Last refreshed: 2026-07-11.

## What this repo is
Central asset + graphics repo for NZIHL/NZWIHL broadcasts. Two jobs live here:
1. **Nightly standings graphics** — `build_standings.py` scrapes both leagues' live standings and renders PNGs, committed back by CI every night.
2. **Static asset library + design mockups** — logos, fonts, brand docs (Style Guide, hex cheat sheet), per-team overlay art (Up Next, DVD Bounce loops), and in-progress design previews for graphics that eventually get deployed live in matchavez/hockey.

GitHub Pages is enabled on this repo (root). Any `.html` at repo root or in a subfolder is live at `https://matchavez.com/nzihl-broadcast-assets/<path>.html` (note: fetching the raw file serves HTML as text, you need the Pages URL to render it).

## Directory map
- `build_standings.py`, `requirements.txt` — the standings renderer (Pillow/requests/BeautifulSoup). Outputs `NZIHL_Standings.png` / `NZWIHL_Standings.png` (1920×1080 transparent, 60px margin) AND `<LEAGUE>_Standings_1840x1000.png` (opaque flat variant, added 2026-06-29). Workflow stages-then-diffs so new output files actually get committed (not just modified ones).
- `.github/workflows/update-standings.yml` — cron `0 14 * * *` (UTC) = 02:00 NZST nightly. Also `workflow_dispatch` for manual runs. Falls back to a static snapshot embedded in the script if a live scrape fails, so downstream consumers never see a missing/stale image.
- `assets/fonts/`, `assets/league/`, `assets/logos/` — TeX Gyre Heros font files, league logos, team logos (both leagues). Source of truth for team logo filenames — **Dunedin_Thunder.png** is current, "Phoenix Thunder" filename is deprecated/do not use.
- `2026-nzihl-nzwihl-style-guide.html` / `.pdf`, `2026-nzihl-nzwihl-hex-cheat-sheet.html` — brand reference docs, year-prefixed filenames on purpose (rebuild new ones each season rather than overwrite). Style guide logos are base64-embedded. PDF built via weasyprint.
- `up-next/` — per-club "UP NEXT" animated overlay source + renderer (`up-next/renderer/`) + one-click zips (`up-next/zips/`, named `<slug>_upnext.zip`, slug = full team name lowercased, spaces→underscore). `up-next/README.md` has renderer usage notes.
- `DVD Bounce Loops/` — per-team bouncing-logo screensaver loop, one subfolder per club (e.g. `AucklandMako/`, `DunedinThunder/`) plus `DVD Bounce Loops/zips/<slug>_dvd.zip`.
- `summary/` — Live Game Summary graphic project workspace: `index.html` (current mock) + `worker.js` (draft Cloudflare Worker for live data, not yet deployed). This is design/dev space; the *deployed* overlay page lives in matchavez/hockey's `summary/`.
- `previews/game-summary.html` — earlier/alternate preview build for the same Game Summary project.
- `thumbs/` — portal thumbnail PNGs/GIFs (brand.png, standings.png, rosters.png, live_game_summary.png, dvd_loops.gif, up_next.png, activity_banner.png, logos.png) — these back the section cards on the matchavez/hockey portal, not consumed here.

## Conventions / invariants
- Team logo add/rename: drop file into `assets/logos/`, add entry to the right `LeagueConfig.teams` dict in `build_standings.py` keyed by lowercase team name with trailing 2/3-letter code stripped, and update the `fallback` list in the same config.
- Standings sort: PPG desc, tiebreak Pts → GD → fewest GP → name. W/OTW/OTL render white, L renders dim grey regardless of value. Pts column gold. Point values in legend: W(3) OTW(2) OTL(1) L(0).
- Naming: "Pure NZ Admirals" (with space, no "West Auckland" prefix), "Dunedin Thunder" (never "Phoenix Thunder").
- Inter is the house font for the rest of 2026 (full weight range) for anything NOT using the standings' TeX Gyre Heros — sparse-clone from google/fonts to get it into the sandbox when needed.

## Recent history worth knowing (most recent first)
- 2026-07-10/09/08/07/...: nightly standings auto-commits (expected, routine, don't investigate unless one is *missing*).
- 2026-07-08: fixed NZWIHL Up Next / Lower Third symmetry (logo/name anchored from frame edges, EDGE_MARGIN=150/LOGO_GAP=100 both sides) since teams' logo/name widths differ; also reversed WILD nickname outline color to white (was black) per-team `stroke2` override.
- 2026-07-05: fixed standings date stamp to use NZ local date instead of runner UTC date.
- 2026-06-29: added the 1840×1000 opaque standings variant; portal now offers both 1920×1080 and 1840×1000 download buttons.

## Automation summary
| Workflow | Cron (UTC) | Purpose |
|---|---|---|
| update-standings.yml | `0 14 * * *` | rebuild + commit both leagues' standings PNGs (both size variants) |

## Related repos
- **matchavez/hockey** — portal + all *deployed* overlay pages; consumes this repo's PNGs via raw.githubusercontent.com, and its `summary/`/`scoringleaders/` design work often prototypes here first.
- **matchavez/nzihl-season-data** — game-level JSON warehouse; the Game Summary worker (`summary/worker.js`) will eventually read from it.
- **matchavez/nzihl-broadcast-rosters**, **matchavez/nzwihl-broadcast-rosters** — roster/schedule PDFs, share the same team-color/venue conventions.

## Sync note
memory.md and README.md should be updated together whenever this repo changes meaningfully. If they drift (a change landed but one file wasn't updated), flag it to Mat and get his go-ahead before editing/publishing the sync — don't do it silently.
