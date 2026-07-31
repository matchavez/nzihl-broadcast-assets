"""Unified team registry for the pronunciation-sheet system, covering both
leagues in one place (the roster-PDF repos keep separate per-league
registries; this system needs colors/logos/venue for all 9 active teams
plus MKO placeholder in one lookup).

MKO (Auckland Mako) has real, already-locked-in brand colors from the
canonical hex cheat sheet, but no esportsdesk team_id, no bundled logo,
and no current roster -- they aren't fielding a team right now. Per Mat
(2026-07-27): keep them registered so the pipeline is ready the moment
the league confirms they're playing again, but the sheet-generator must
skip them (no fabricated team_id/venue/logo) until real data exists.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class TeamMeta:
    league: str            # "nzihl" / "nzwihl"
    tla: str
    display_name: str
    team_id: int | None    # esportsdesk teamID; None = no active roster
    primary_hex: str
    accent_hex: str
    title_hex: str
    text_hex: str
    home_venue: str | None
    logo_file: str | None  # relative to this system's logos/ dir; None = no logo yet
    active: bool            # False = registered but not currently fielding a team
    founded: int | None = None  # franchise founding year -- researched, see note below
    jersey_text_hex: str | None = None  # override for jersey-number/position block text;
                                         # None = use accent_hex. Set explicitly for teams
                                         # whose brand keeps this text white to match the
                                         # headline banner rather than the usual secondary
                                         # color (Canterbury Red Devils, Canterbury Inferno --
                                         # Mat's call 2026-07-27: "text should have remained
                                         # white on both, just as the headlines are").


# Researched via web search 2026-07-28 (Wikipedia / club sites) -- NOT scraped
# from any esportsdesk source, so treat as best-effort and flag to Mat if
# anything looks off. NZIHL founded 2005 with 4 charter clubs (Canterbury Red
# Devils, West Auckland Admirals -> Mat's "Pure NZ Admirals", Southern
# Stampede -> SkyCity Stampede, South Auckland Swarm -> Botany Swarm).
# Dunedin Thunder (men's) joined 2008. Auckland Mako added 2021 (NZIHL's
# newest club). NZWIHL founded 2014 (Auckland Steel, Canterbury Devilettes ->
# Canterbury Inferno, Southern Storm). Southern Storm split into Dunedin
# Thunder Women and Wakatipu Wild in 2020.
FOUNDED: dict[str, int] = {
    "ADM": 2005, "BSW": 2005, "CRD": 2005, "SCS": 2005, "DUN": 2008, "MKO": 2021,
    "AST": 2014, "INF": 2014, "DTW": 2020, "WLD": 2020,
}

# Also researched 2026-07-28 (Wikipedia / venue sites), keyed by venue since
# several teams share a home rink.
VENUE_CAPACITY: dict[str, int] = {
    "Paradice Avondale": 500,
    "Paradice Botany": 400,
    "Alpine Ice Centre": 700,
    "Dunedin Ice Stadium": 1850,
    "Queenstown Ice Arena": 642,
}


# Birgel Cup (NZIHL championship trophy) winning seasons per team, researched
# 2026-07-28 (nzihl.com news posts + Wikipedia). Franchise-lineage aware:
# SCS's 2015 title was won as "Southern Stampede" (same franchise, renamed
# 2016); CRD's 2009 title predates the Birgel Cup's 2010 introduction but is
# widely reported as part of the same championship lineage. NZIHL's own
# reporting says Stampede have "10 titles all-time" -- web research only
# turned up 8 (2009-2025 range searched); Mat confirmed directly (2026-07-28)
# that the missing two are 2005 and 2006, won as "Southern Stampede" before
# the SkyCity rename -- added per his correction, not web-sourced, and this
# now reconciles the count to 10.
# NZWIHL has a separate trophy (the Goulding Cup, only formally named since
# 2024) -- not included here since Mat asked specifically for Birgel Cup;
# flagged to him separately.
BIRGEL_CUP: dict[str, list[int]] = {
    "SCS": [2005, 2006, 2015, 2016, 2017, 2019, 2022, 2023, 2024, 2025],
    "CRD": [2009, 2012, 2013, 2014],
    "BSW": [2010, 2011],
    "ADM": [2018],
    "DUN": [],
    "MKO": [],
}


# Goulding Cup (NZWIHL championship trophy, named after Jan Goulding, formally
# adopted from the 2024 finals onward -- earlier seasons' champions are
# still listed here under the same lineage). Researched 2026-07-28
# (nzwihl.com news posts + Wikipedia). Auckland Steel's "7-time champions"
# claim matches this list exactly (2014/16/17/19/23/24/25). The 2018 title
# was won by "Southern Storm", the shared predecessor franchise that split
# into Dunedin Thunder Women AND Wakatipu Wild in 2020 -- deliberately NOT
# credited to either successor team here, since which one (if either)
# inherits that title is unresolved. 2020/2021 champion not found in
# research (possibly a COVID gap, unconfirmed) -- left out rather than
# guessed.
GOULDING_CUP: dict[str, list[int]] = {
    "AST": [2014, 2016, 2017, 2019, 2023, 2024, 2025],
    "INF": [2015],
    "DTW": [],
    "WLD": [2022],
}


TEAMS: dict[str, TeamMeta] = {
    # ---- NZIHL ----
    "ADM": TeamMeta("nzihl", "ADM", "Pure NZ Admirals", 674110,
                     "#081D48", "#F7BE11", "#F7BE11", "#081D48",
                     "Paradice Avondale", "adm.png", True, FOUNDED["ADM"]),
    "BSW": TeamMeta("nzihl", "BSW", "Botany Swarm", 674109,
                     "#782738", "#F7AF28", "#F7AF28", "#782738",
                     "Paradice Botany", "bsw.png", True, FOUNDED["BSW"]),
    "CRD": TeamMeta("nzihl", "CRD", "Canterbury Red Devils", 675633,
                     "#DC0000", "#000000", "#FFFFFF", "#DC0000",
                     "Alpine Ice Centre", "crd.png", True, FOUNDED["CRD"],
                     jersey_text_hex="#FFFFFF"),
    "DUN": TeamMeta("nzihl", "DUN", "Dunedin Thunder", 675634,
                     "#025B3D", "#FDAD19", "#FDAD19", "#025B3D",
                     "Dunedin Ice Stadium", "dun.png", True, FOUNDED["DUN"]),
    "SCS": TeamMeta("nzihl", "SCS", "SkyCity Stampede", 675635,
                     "#FAC805", "#1D3056", "#1D3056", "#1D3056",
                     "Queenstown Ice Arena", "scs.png", True, FOUNDED["SCS"]),
    "MKO": TeamMeta("nzihl", "MKO", "Auckland Mako", None,
                     "#62656A", "#202222", "#202222", "#62656A",
                     None, None, False, FOUNDED["MKO"]),

    # ---- NZWIHL ----
    "AST": TeamMeta("nzwihl", "AST", "Auckland Steel", 675636,
                     "#1A2A44", "#8A9BB0", "#FFFFFF", "#1A2A44",
                     "Paradice Avondale", "ast.png", True, FOUNDED["AST"]),
    "INF": TeamMeta("nzwihl", "INF", "Canterbury Inferno", 675637,
                     "#B00020", "#FF6A13", "#FFFFFF", "#B00020",
                     "Alpine Ice Centre", "inf.png", True, FOUNDED["INF"],
                     jersey_text_hex="#FFFFFF"),
    "DTW": TeamMeta("nzwihl", "DTW", "Dunedin Thunder Women", 675638,
                     "#025B3D", "#FDAD19", "#FDAD19", "#025B3D",
                     "Dunedin Ice Stadium", "dtw.png", True, FOUNDED["DTW"]),
    "WLD": TeamMeta("nzwihl", "WLD", "Wakatipu Wild", 675639,
                     "#FAC805", "#1D3056", "#1D3056", "#1D3056",
                     "Queenstown Ice Arena", "wld.png", True, FOUNDED["WLD"]),
}


def active_teams() -> list[TeamMeta]:
    return [t for t in TEAMS.values() if t.active]
