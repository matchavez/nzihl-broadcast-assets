import os
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from team_registry import TEAMS
from render_sheet import build_team_sheet

# All paths below are env-overridable so the exact same script runs both in
# an interactive dev session and inside the GitHub Actions workflow that
# calls it (.github/workflows/regenerate-pronunciation-guide.yml, in this
# same repo) -- only the env vars differ between the two, not the code.
REPO_ROOT = Path(__file__).resolve().parent.parent

OUT_DIR = Path(os.environ.get("PRONUNCIATION_OUT_DIR", "/tmp/work/output_pdfs"))
OUT_DIR.mkdir(parents=True, exist_ok=True)

PRON_PATH = Path(os.environ.get("PRONUNCIATIONS_JSON", str(REPO_ROOT / "assets" / "pronunciations.json")))
DATA_DIR = Path(os.environ.get("PRONUNCIATION_DATA_DIR", "/tmp/work/data"))

pron = json.load(open(PRON_PATH))["entries"]
photo_manifest = json.load(open(DATA_DIR / "photo_manifest.json"))
nzihl_stats = json.load(open(DATA_DIR / "nzihl_stats.json"))["teams"]
nzwihl_stats = json.load(open(DATA_DIR / "nzwihl_stats.json"))["teams"]
nzihl_season = json.load(open(DATA_DIR / "nzihl_season.json"))
nzwihl_season = json.load(open(DATA_DIR / "nzwihl_season.json"))

stats_by_league = {"nzihl": nzihl_stats, "nzwihl": nzwihl_stats}

# Build tla -> standing dict (rank = 1-indexed position in the verbatim
# derived.standings scrape, already sorted by points).
standings_by_league = {}
for lg, season in [("nzihl", nzihl_season), ("nzwihl", nzwihl_season)]:
    rows = (season.get("derived") or {}).get("standings") or []
    standings_by_league[lg] = {
        row["code"]: {"rank": i + 1, "w": row["w"], "l": row["l"],
                       "otw": row["otw"], "otl": row["otl"], "pts": row["pts"]}
        for i, row in enumerate(rows)
    }

made = []
for tla, team in TEAMS.items():
    stats_team = stats_by_league.get(team.league, {}).get(tla)
    standing = standings_by_league.get(team.league, {}).get(tla)
    out_path = OUT_DIR / f"{team.tla}_{team.display_name.replace(' ', '_')}_pronunciation.pdf"
    build_team_sheet(out_path=str(out_path), team=team, stats_team=stats_team,
                      pronunciations=pron, photo_manifest=photo_manifest, standing=standing)
    made.append(out_path)
    print("built", out_path.name)

print(f"\n{len(made)} PDFs built in {OUT_DIR}")
