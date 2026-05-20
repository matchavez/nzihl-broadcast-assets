# NZIHL & NZWIHL Broadcast Assets

Generates the league standings graphics used in NZIHL and NZWIHL broadcasts.

Both graphics are rebuilt automatically every night at **02:00 NZST**
(14:00 UTC) by the workflow in `.github/workflows/update-standings.yml`. It
scrapes each league's standings page, renders a 1920×1080 PNG with a 60px
transparent margin, and commits the result back to the repo. Hot-link from
your broadcast tooling:

```
https://raw.githubusercontent.com/matchavez/nzihl-broadcast-assets/main/NZIHL_Standings.png
https://raw.githubusercontent.com/matchavez/nzihl-broadcast-assets/main/NZWIHL_Standings.png
```

## Running locally

```bash
pip install -r requirements.txt
python build_standings.py
```

Outputs `NZIHL_Standings.png` and `NZWIHL_Standings.png` next to the script.

## Layout

* 1920×1080 RGBA PNG with a 60px fully-transparent border on all sides.
* Teams sorted by **Points Per Game (PPG)** desc, tiebroken by
  Pts → Goal Differential → fewest Games Played → name.
* Columns: W / OTW / OTL / L / GD / Pts / GP / PPG.
  * W, OTW, OTL render white; L renders dim grey, regardless of value.
  * Pts is highlighted in gold.
* Point values appended to the legend: W (3), OTW (2), OTL (1), L (0).
* Top brand strip carries only the league logo and full league name —
  no season number, so the design rolls over to future seasons unchanged.

## Repo layout

```
.
├── build_standings.py            # render script (both leagues)
├── requirements.txt              # Pillow, requests, BeautifulSoup
├── NZIHL_Standings.png           # latest men's output (overwritten nightly)
├── NZWIHL_Standings.png          # latest women's output (overwritten nightly)
├── assets/
│   ├── fonts/                    # TeX Gyre Heros .otf files
│   ├── league/                   # NZIHL + NZWIHL league logos
│   └── logos/                    # team logos (both leagues)
└── .github/workflows/update-standings.yml
```

## Manual trigger

In the **Actions** tab of this repo, pick *Update Standings Graphics*
and click **Run workflow** to regenerate on demand.

## Fallback behaviour

If a league's live scrape fails (network error, page change), the script
falls back to a static snapshot included in `build_standings.py` and logs
a `[warn]` line in the Action output. The workflow still produces both
PNGs so dependent broadcasts never see a stale-or-missing image.

## Adding or renaming a team

1. Drop the team logo into `assets/logos/`.
2. In `build_standings.py`, add an entry to the appropriate `LeagueConfig`'s
   `teams` dict. The dict key is the lowercase team name with the
   trailing 2- or 3-letter team code stripped (e.g. `"Pure NZ AdmiralsWAA"` →
   `"pure nz admirals"`).
3. Update the `fallback` list in the same config so the static snapshot
   stays useful.
