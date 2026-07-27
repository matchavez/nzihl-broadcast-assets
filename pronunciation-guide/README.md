# Pronunciation Guide sheet generator

Renders one A4 pronunciation/team-info PDF per NZIHL/NZWIHL club (photo,
jersey number, name, phonetic respelling, prefers/announced name if any)
plus a combined booklet, from data in this repo and three sibling repos.

**This reads `assets/pronunciations.json` (the single source of truth,
kept up to date via the ops review page) -- it does not regenerate
phonetics itself.** For that (adding fresh auto-engine baseline entries
for new players), see the separate `build_pronunciations.py` /
`phonetics.py` / `manual_overrides.py` pipeline, which as of 2026-07-28
still only exists in Claude's session workspace, not committed here.

## Inputs
- `assets/pronunciations.json` (this repo) -- name + phonetic per player/coach.
- `stats.json` from `nzihl-broadcast-rosters` / `nzwihl-broadcast-rosters`
  (roster + season stat lines).
- `nzihl.json` / `nzwihl.json` from `nzihl-season-data` (standings).
- `manifest.json` + photo files from `nzihl-player-photos`.

## Running
```
pip install -r requirements.txt
PRONUNCIATION_DATA_DIR=./_data \
PRONUNCIATION_PHOTOS_ROOT=./_photos \
PRONUNCIATION_OUT_DIR=./output \
python generate_all.py
```
`PRONUNCIATIONS_JSON` defaults to `../assets/pronunciations.json` (relative
to this folder) and normally doesn't need overriding.

See `.github/workflows/regenerate-pronunciation-guide.yml` for how CI
wires up `_data`/`_photos` from the sibling repos above before calling this.
