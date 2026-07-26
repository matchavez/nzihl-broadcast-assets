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
- `summary/` — Live Game Summary graphic project workspace: `index.html` (current mock) + `worker.js` (Cloudflare Worker -- CORS proxy for live data, still not deployed as the Game Summary's data source, but now ALSO carries the Player Lower Thirds control channel, see below) + `wrangler.toml` + `DEPLOY.md`. This is design/dev space; the *deployed* overlay page lives in matchavez/hockey's `summary/`.
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

## Player Lower Thirds control channel (2026-07-12)
`summary/worker.js` now also serves `/control/<team-slug>` -- a shared,
low-latency state channel between the phone control page
(`matchavez/hockey`'s `hockey/lowerthirds/`) and the Activity Banner overlay
(`matchavez/hockey`'s `activity-banner/`), backed by a **Durable Object**
(`export class ControlChannel`, SQLite-backed via `new_sqlite_classes`,
works on the Free plan -- confirmed before building, no paid-plan surprise).
GET reads state (no auth); POST `queue|fire|clear|interrupt` requires the
shared `CONTROL_TOKEN` (`l3-EXleXBAfHbgn7P1qHeJ81U1K`). State self-heals on
read (`fired` auto-expires to `queued` once `expires_at` passes) so a missed
`clear` can't wedge a team. Original CORS-proxy logic is untouched --
same worker, new route.

**DEPLOYED 2026-07-12** by Mat (`wrangler deploy` from `summary/`, per
`summary/DEPLOY.md`). Full round trip verified live immediately after:
queue -> fire -> real player rendered on `activity-banner/?team=pure-nz-admirals`
(real photo, real stats.json line, fact) -> auto-hid at the 10s `expires_at`
-> self-healed to `queued` (not `idle`, confirmed) -> manual `clear` reset to
`idle`. Box-score CORS proxy re-verified unaffected by the same deploy.
One gotcha hit + resolved during Mat's deploy: running `wrangler` commands
from `~` (not the `summary/` dir) caused a macOS Full-Disk-Access-related
`.Trash` scandir error, then a "could not detect a directory containing
static files" error (wrangler falling back to Pages-deploy detection with
no `wrangler.toml` in cwd) -- both were just a wrong-cwd issue, resolved by
`cd`-ing into `summary/` before running `wrangler deploy`. See Claude's
`nzihl-player-lower-thirds` memory for the full project design.

## Playoff-readiness audit (2026-07-13)
See `matchavez/hockey`'s `playoff-readiness.md` for the full cross-repo audit. Changes made here:

- **`summary/worker.js` CORS allowlist bug found + fixed**: `schedules.cfm` and
  `stats_hockey.cfm` were never in `ALLOWED` -- every client-side fetch through the worker for
  them has always 403'd with the worker's OWN `"forbidden"` response, not an esportsdesk-side
  failure. This is why `matchavez/hockey/preflight/`'s "leaders"/"schedule" reachability cards and
  the club board's FINAL-status chip have silently never worked. Both endpoints added to
  `ALLOWED`. **Needs Mat: `wrangler deploy` from `summary/`** to take effect -- no
  `wrangler.toml`/migration change needed, same mechanism as the existing `DEPLOY.md`.
- **`.github/workflows/force-pages-build.yml`** (new): POSTs `/pages/builds` on every push to
  main, since this repo also serves GitHub Pages (the Style Guide, standings PNGs via raw content,
  etc.) via the legacy builder that doesn't always auto-build on push. Verified green via the
  Actions API.

## Pronunciation-guide system (2026-07-27)
New `assets/pronunciations.json` -- single source of truth for player/coach phonetics and
preferred announced names (e.g. Csaba Kercso-Magos -> "Chabba"), same single-file-of-record
convention as `assets/name-overrides.json`. Keyed by esportsdesk `player_id` (players, now
also carried on `nzihl-broadcast-rosters`/`nzwihl-broadcast-rosters`'s `stats.json` for
exactly this reason) or the photo-warehouse manifest's synthetic
`league:TLA:coach:First|Last|Title` key (coaches). Seeded with a rule-based baseline for
every player + coach across both leagues, hand-verified for ~48 non-English/deceptive-
spelling names by Claude. Drives a one-page-per-team PDF sheet (logo/name banner -> venue +
coaches -> photo-card grid, GP>0 filter with a full-roster fallback for preseason builds
where nobody has GP yet) delivered directly to Mat's project folder, plus a combined
10-team booklet and an offline `pronunciation_review.html` (no backend -- Mat edits inline,
exports an updated JSON, drops it back in here). MKO (Auckland Mako) is registered with its
real locked-in brand colors from the hex cheat sheet but no team_id/logo/venue -- they
aren't fielding a team; the renderer shows a placeholder page rather than fabricating data.
Each per-player card links out to that player's `rosters_profile.cfm` full-stats page
(`www.nzihl.com`/`www.nzwihl.com`, clientid/leagueID/teamID/playerID -- all already known
constants from the roster scrapers).

## Sync note
memory.md and README.md should be updated together whenever this repo changes meaningfully. If they drift (a change landed but one file wasn't updated), flag it to Mat and get his go-ahead before editing/publishing the sync — don't do it silently.
