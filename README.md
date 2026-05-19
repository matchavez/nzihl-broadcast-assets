# NZIHL Broadcast Assets

Generates the league standings graphic used in NZIHL broadcasts.

The graphic at `NZIHL_Standings.png` is rebuilt automatically every night at
**02:00 NZST** (14:00 UTC) by the workflow in
`.github/workflows/update-standings.yml`. It pulls the current standings from
[nzihl.com](https://www.nzihl.com/leagues/standings.cfm?clientid=7131&leagueid=35499),
renders a 1920×1080 PNG with a 60-pixel transparent margin, and commits the
result back to the repo. Hot-link the file at:

```
https://raw.githubusercontent.com/matchavez/nzihl-broadcast-assets/main/NZIHL_Standings.png
```

## Running locally

```bash
pip install -r requirements.txt
python build_standings.py
```

The output is written to `NZIHL_Standings.png` next to the script.

## Layout

* 1920×1080 RGBA PNG with a 60px fully-transparent border on all sides.
* Teams are sorted by **Points Per Game (PPG)** desc, tiebroken by
  Pts → Goal Differential → fewest Games Played → name.
* Columns: W / OTW / OTL / L / GD / Pts / GP / PPG.
  * W, OTW, OTL render white; L renders dim grey, regardless of value.
  * Pts is highlighted in gold.
* Point values appended to the legend: W (3), OTW (2), OTL (1), L (0).

## Repo layout

```
.
├── build_standings.py            # render script
├── requirements.txt              # Pillow, requests, BeautifulSoup
├── NZIHL_Standings.png           # latest output (overwritten nightly)
├── assets/
│   ├── fonts/                    # TeX Gyre Heros .otf files
│   ├── league/                   # NZIHL league logo
│   └── logos/                    # team logos
└── .github/workflows/update-standings.yml
```

## Manual trigger

In the **Actions** tab of this repo, pick *Update NZIHL Standings Graphic*
and click **Run workflow** to regenerate on demand.

## Fallback behaviour

If the live scrape from nzihl.com fails (network error, page change), the
script falls back to a static snapshot included in `build_standings.py`
and logs a `[warn]` line in the Action output. The workflow will still
produce a PNG so dependent broadcasts don't see a stale-or-missing image.
