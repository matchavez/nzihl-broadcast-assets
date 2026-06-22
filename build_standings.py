#!/usr/bin/env python3
"""Render the NZIHL and NZWIHL standings broadcast graphics.

Run nightly on GitHub Actions. For each league the script:
  1. Scrapes the current standings from the league website.
  2. Renders a 1920x1080 RGBA PNG (60px transparent margin) using bundled
     fonts and team logos.
  3. Writes the result to <LEAGUE>_Standings.png at the repo root.
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# --- Paths -----------------------------------------------------------------
HERE       = Path(__file__).resolve().parent
ASSETS     = HERE / "assets"
LOGOS_DIR  = ASSETS / "logos"
LEAGUE_DIR = ASSETS / "league"
FONTS_DIR  = ASSETS / "fonts"

# --- Fonts -----------------------------------------------------------------
_FONT_FILES = {
    "regular":  FONTS_DIR / "texgyreheros-regular.otf",
    "medium":   FONTS_DIR / "texgyreheros-regular.otf",
    "semibold": FONTS_DIR / "texgyreheros-bold.otf",
    "bold":     FONTS_DIR / "texgyreheros-bold.otf",
    "black":    FONTS_DIR / "texgyreheros-bold.otf",
}


def font(size: int, weight: str = "bold") -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(_FONT_FILES.get(weight, _FONT_FILES["bold"])), size)


# --- League configuration --------------------------------------------------
@dataclass
class LeagueConfig:
    code: str                       # 'NZIHL' / 'NZWIHL'
    full_name: str                  # wordmark text next to the league logo
    url: str                        # standings page
    league_logo: str                # filename inside assets/league/
    teams: Dict[str, Dict]          # normalised-key -> {name, logo}
    fallback: List[Dict]            # static snapshot — only used when use_fallback=True
    use_fallback: bool              # opt-in: set True manually after editing `fallback`,
                                    # otherwise scraper failure skips the league (no PNG
                                    # overwrite) and the workflow step exits non-zero
    output_file: str                # output PNG filename


# ---------------------------------------------------------------------------
# MANUAL FALLBACK — how the `use_fallback` flag works
# ---------------------------------------------------------------------------
# Each league below has a `use_fallback` flag that should normally be False.
#
#   use_fallback=False  (default / "no")
#       If the live scrape succeeds, the rendered PNG uses live data.
#       If the live scrape FAILS, the league is skipped: the existing PNG
#       on disk is left untouched and main() returns a non-zero exit code,
#       which makes the GitHub Actions step fail loudly (email notification)
#       instead of quietly publishing stale numbers.
#
#   use_fallback=True   ("yes" — manual override)
#       Only flip this on when the live scrape is broken AND you have
#       hand-edited the `fallback=[...]` block below to reflect current
#       stats. On the next workflow run, if the scrape fails, the renderer
#       will draw the PNG from your hand-edited fallback.
#       IMPORTANT: flip it back to False once the live scraper is healthy,
#       otherwise stale fallback data can silently resurface the next time
#       the scraper breaks.
#
# Note: a successful live scrape always wins. The flag only changes what
# happens on scrape failure.
# ---------------------------------------------------------------------------

NZIHL = LeagueConfig(
    code="NZIHL",
    full_name="NEW ZEALAND ICE HOCKEY LEAGUE",
    url="https://www.nzihl.com/leagues/standings.cfm?clientid=7131&leagueid=35499",
    league_logo="NZIHL-White-2000.png",
    teams={
        "skycity stampede":      {"name": "SkyCity Stampede",
                                  "logo": "Skycity Stampede 2000x2000.png"},
        # Single canonical key for the Admirals (matches the team-code-stripped
        # form that nzihl.com currently displays, "Pure NZ AdmiralsWAA").
        "pure nz admirals":      {"name": "Pure NZ Admirals",
                                  "logo": "Pure-NZ-Admirals-2000x2000.png"},
        "dunedin thunder":       {"name": "Dunedin Thunder",
                                  "logo": "Dunedin_Thunder.png"},
        "botany swarm":          {"name": "Botany Swarm",
                                  "logo": "Botany Swarm 2000x2000.png"},
        "canterbury red devils": {"name": "Canterbury Red Devils",
                                  "logo": "Red Devils 2000x2000r.png"},
    },
    fallback=[
        {"name": "SkyCity Stampede",              "logo": "Skycity Stampede 2000x2000.png",
         "W": 1, "OTW": 1, "OTL": 1, "L": 1, "GF": 1, "GA": 1, "PTS": 1, "GP": 1},
        {"name": "Pure NZ Admirals", "logo": "Pure-NZ-Admirals-2000x2000.png",
         "W": 1, "OTW": 1, "OTL": 1, "L": 1, "GF": 1, "GA": 1,  "PTS": 1, "GP": 1},
        {"name": "Dunedin Thunder",               "logo": "Dunedin_Thunder.png",
         "W": 1, "OTW": 1, "OTL": 1, "L": 1, "GF": 1, "GA": 1, "PTS": 1, "GP": 1},
        {"name": "Botany Swarm",                  "logo": "Botany Swarm 2000x2000.png",
         "W": 1, "OTW": 1, "OTL": 1, "L": 1, "GF": 1,  "GA": 1, "PTS": 1, "GP": 1},
        {"name": "Canterbury Red Devils",         "logo": "Red Devils 2000x2000r.png",
         "W": 1, "OTW": 1, "OTL": 1, "L": 1, "GF": 1, "GA": 1, "PTS": 1, "GP": 1},
    ],
    # Flip to True ONLY after updating the fallback rows above. See the
    # MANUAL FALLBACK header comment for the full procedure.
    use_fallback=False,
    output_file="NZIHL_Standings.png",
)

NZWIHL = LeagueConfig(
    code="NZWIHL",
    full_name="NEW ZEALAND WOMEN'S ICE HOCKEY LEAGUE",
    url="https://www.nzwihl.com/leagues/standings.cfm?clientid=7132&leagueid=35501",
    league_logo="NZWIHL-Logo-White-1000px.png",
    teams={
        "auckland steel":        {"name": "Auckland Steel",
                                  "logo": "Auckland-Steel-White.png"},
        "canterbury inferno":    {"name": "Canterbury Inferno",
                                  "logo": "Inferno-White.png"},
        "dunedin thunder women": {"name": "Dunedin Thunder Women",
                                  "logo": "thunder-women-white.png"},
        "wakatipu wild":         {"name": "Wakatipu Wild",
                                  "logo": "Wakatipu-wild-white.png"},
    },
    fallback=[
        {"name": "Auckland Steel",        "logo": "Auckland-Steel-White.png",
         "W": 1, "OTW": 1, "OTL": 1, "L": 1, "GF": 1, "GA": 1,  "PTS": 1, "GP": 1},
        {"name": "Dunedin Thunder Women", "logo": "thunder-women-white.png",
         "W": 1, "OTW": 1, "OTL": 1, "L": 1, "GF": 1, "GA": 1,  "PTS": 1, "GP": 1},
        {"name": "Canterbury Inferno",    "logo": "Inferno-White.png",
         "W": 1, "OTW": 1, "OTL": 1, "L": 1, "GF": 1,  "GA": 1, "PTS": 1, "GP": 1},
        {"name": "Wakatipu Wild",         "logo": "Wakatipu-wild-white.png",
         "W": 1, "OTW": 1, "OTL": 1, "L": 1, "GF": 1,  "GA": 1, "PTS": 1, "GP": 1},
    ],
    # Flip to True ONLY after updating the fallback rows above. See the
    # MANUAL FALLBACK header comment for the full procedure.
    use_fallback=False,
    output_file="NZWIHL_Standings.png",
)


# --- Standings ingest ------------------------------------------------------
def _normalise(name: str) -> str:
    """Strip the 2-3 letter team code that the league sites append (e.g.
    'SkyCity StampedeSCS' or 'Dunedin Thunder WomenDTW')."""
    return re.sub(r"[A-Z]{2,3}$", "", name).strip().lower()


def fetch_standings(cfg: LeagueConfig) -> Optional[List[Dict]]:
    """Scrape the standings table.

    Returns the scraped rows on success. On failure, returns the static
    fallback ONLY when ``cfg.use_fallback`` is True; otherwise returns None
    so the caller can skip the league (preserving the previously-committed
    PNG) and surface a non-zero exit code from main().
    """
    try:
        base_url = "/".join(cfg.url.split("/")[:3])
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-NZ,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Referer": base_url + "/",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        resp = session.get(cfg.url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Prefer the detailed standings table (includes GF/GA) over the
        # summary table the site renders first.
        target = None
        for table in soup.find_all("table"):
            headers = [c.get_text(strip=True).upper()
                       for c in table.find_all(["th", "td"])][:25]
            hdr_set = set(headers)
            if {"OTW", "OTL", "PTS", "GF", "GA"}.issubset(hdr_set):
                target = table
                break
        if target is None:
            for table in soup.find_all("table"):
                headers = [c.get_text(strip=True).upper()
                           for c in table.find_all(["th", "td"])][:20]
                if {"OTW", "OTL", "PTS"}.issubset(set(headers)):
                    target = table
                    break
        if target is None:
            raise RuntimeError("No standings table found")

        rows = target.find_all("tr")
        header_cells = [c.get_text(strip=True).upper()
                        for c in rows[0].find_all(["th", "td"])]

        teams: List[Dict] = []
        for r in rows[1:]:
            cells = [c.get_text(strip=True) for c in r.find_all(["th", "td"])]
            if len(cells) < 6:
                continue
            data = dict(zip(header_cells, cells))
            raw_name = data.get("TEAM") or cells[0]
            key = _normalise(raw_name)
            if key not in cfg.teams:
                continue
            try:
                team_def = cfg.teams[key]
                teams.append({
                    "name": team_def["name"],
                    "logo": team_def["logo"],
                    "GP":   int(data["GP"]),
                    "W":    int(data["W"]),
                    "L":    int(data["L"]),
                    "OTW":  int(data["OTW"]),
                    "OTL":  int(data["OTL"]),
                    "PTS":  int(data["PTS"]),
                    "GF":   int(data.get("GF", "0")),
                    "GA":   int(data.get("GA", "0")),
                })
            except (KeyError, ValueError):
                continue

        if not teams:
            raise RuntimeError("Parsed zero rows")
        return teams

    except Exception as exc:                                # noqa: BLE001
        if cfg.use_fallback:
            print(f"[warn] {cfg.code} live scrape failed ({exc!r}); "
                  f"using manually-enabled fallback (sorted by Points)",
                  file=sys.stderr)
            # No website order to preserve here, so fall back to Points (desc).
            return sorted((dict(t) for t in cfg.fallback),
                          key=lambda t: -t["PTS"])
        print(f"[error] {cfg.code} live scrape failed ({exc!r}); "
              f"use_fallback=False, skipping render", file=sys.stderr)
        return None


# --- Render ----------------------------------------------------------------
W, H = 1920, 1080
MARGIN = 60
PANEL = (MARGIN, MARGIN, W - MARGIN, H - MARGIN)
PANEL_W = PANEL[2] - PANEL[0]
PANEL_H = PANEL[3] - PANEL[1]
PANEL_R = 24

BG_TOP    = (12, 14, 18)
BG_BOT    = (4, 5, 8)
ROW_A     = (22, 24, 30)
ROW_B     = (16, 18, 22)
HDR_RED_A = (180, 32, 38)
HDR_RED_B = (132, 18, 22)
ACCENT    = (255, 205, 60)
DIM       = (140, 144, 152)
FG        = (240, 242, 246)
SUB       = (190, 194, 202)
GRID      = (40, 44, 52)
GREEN     = (96, 196, 130)
RED_NEG   = (232, 96, 96)
PILL_BG   = (60, 64, 74)


def _centered(d, x, y, text, fnt, fill):
    bb = d.textbbox((0, 0), text, font=fnt)
    w = bb[2] - bb[0]
    h = bb[3] - bb[1]
    d.text((x - w / 2 - bb[0], y - h / 2 - bb[1]), text, font=fnt, fill=fill)


def _left(d, x, y, text, fnt, fill):
    bb = d.textbbox((0, 0), text, font=fnt)
    h = bb[3] - bb[1]
    d.text((x - bb[0], y - h / 2 - bb[1]), text, font=fnt, fill=fill)


def _right(d, x, y, text, fnt, fill):
    bb = d.textbbox((0, 0), text, font=fnt)
    w = bb[2] - bb[0]
    h = bb[3] - bb[1]
    d.text((x - w - bb[0], y - h / 2 - bb[1]), text, font=fnt, fill=fill)


def _paste_logo(canvas, logo_path, cx, cy, target_h, width_cap):
    """Style-guide logo sizing (2026 guide, "Logo Sizing"): scale by the
    OPAQUE ARTWORK height -- not the file canvas, whose transparent padding
    varies team to team -- clamp to a width cap so wide marks don't dominate,
    then centre the cropped artwork on the anchor. Uniform content-height means
    every crest reads at the same visual size at every rank."""
    try:
        logo = Image.open(logo_path).convert("RGBA")
    except FileNotFoundError:
        return
    bbox = logo.getbbox()
    if bbox:
        logo = logo.crop(bbox)
    scale = target_h / logo.height
    if logo.width * scale > width_cap:
        scale = width_cap / logo.width
    logo = logo.resize(
        (max(1, round(logo.width * scale)), max(1, round(logo.height * scale))),
        Image.LANCZOS)
    canvas.alpha_composite(logo, dest=(
        int(cx - logo.width / 2), int(cy - logo.height / 2)))


def render(cfg: LeagueConfig, teams: List[Dict]) -> Image.Image:
    for t in teams:
        t["GD"]  = t["GF"] - t["GA"]
        t["PPG"] = t["PTS"] / t["GP"] if t["GP"] else 0.0
    # Row order is decided upstream in fetch_standings(): a live scrape keeps
    # the league website's own standings order; the static fallback is sorted
    # by Points (desc). No PPG-based re-sort here (Mat's 2026-06-22 change).

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Dark panel with vertical gradient, masked to rounded rect
    panel_img = Image.new("RGBA", (PANEL_W, PANEL_H), (0, 0, 0, 0))
    grad = Image.new("RGB", (1, PANEL_H))
    for y in range(PANEL_H):
        t = y / max(1, PANEL_H - 1)
        grad.putpixel((0, y), (
            int(BG_TOP[0] * (1 - t) + BG_BOT[0] * t),
            int(BG_TOP[1] * (1 - t) + BG_BOT[1] * t),
            int(BG_TOP[2] * (1 - t) + BG_BOT[2] * t),
        ))
    grad = grad.resize((PANEL_W, PANEL_H)).convert("RGBA")
    mask = Image.new("L", (PANEL_W, PANEL_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, PANEL_W, PANEL_H), radius=PANEL_R, fill=255)
    panel_img.paste(grad, (0, 0), mask)

    # No drop shadow: a soft blurred shadow leaves low-alpha black pixels in
    # the rounded-corner notches, which composite to a grey halo over light
    # video. Keeping the panel edge crisp guarantees clean transparent corners
    # for broadcast keying over any background.
    img.alpha_composite(panel_img, dest=(MARGIN, MARGIN))

    draw = ImageDraw.Draw(img, "RGBA")

    PX, PY = PANEL[0], PANEL[1]
    INNER_PAD  = 48   # more breathing room at both table margins (Mat 2026-06-22)
    LEFT_EDGE  = PX + INNER_PAD
    RIGHT_EDGE = PANEL[2] - INNER_PAD

    TOP_STRIP_H = 130
    RED_BAR_H   = TOP_STRIP_H // 8   # halved again -> //8 (Mat 2026-06-22)
    COL_HDR_H   = 66                 # was 56 — column-header row a little taller
    FOOTER_H    = 52

    ROWS_TOP = PY + TOP_STRIP_H + RED_BAR_H + COL_HDR_H
    ROWS_BOT = PANEL[3] - FOOTER_H
    ROW_H = (ROWS_BOT - ROWS_TOP) // max(1, len(teams))

    POS_W       = 78    # wider ordinal column -> more room before the logo
    LOGO_W      = 124   # logo column; width cap below sits inside this with margin
    # Style-guide logo sizing: uniform opaque-artwork height with a width cap in
    # the guide's 150:190 (height:width) ratio, scaled to the row.
    TEAM_LOGO_H    = 90
    TEAM_LOGO_WCAP = 114
    NUM_COLS    = ["W", "OTW", "OTL", "L", "GD", "Pts", "GP", "PPG"]
    NUM_COL_W   = 116
    NUM_TOTAL   = NUM_COL_W * len(NUM_COLS)
    TEAM_W      = (RIGHT_EDGE - LEFT_EDGE) - POS_W - LOGO_W - NUM_TOTAL
    NUM_START_X = LEFT_EDGE + POS_W + LOGO_W + TEAM_W

    # --- Top brand strip ---------------------------------------------------
    # No more "2026 SEASON" line — the wordmark is now the league full name,
    # vertically centred to the league logo so this scales to future seasons
    # without code changes. Wordmark size auto-shrinks if it would overflow.
    TOP_Y_MID = PY + TOP_STRIP_H // 2
    # Constrain league logo by height so wide-aspect marks (NZWIHL is ~4:1)
    # still read at the same visual scale as taller marks (NZIHL is ~1.75:1).
    league_logo = Image.open(LEAGUE_DIR / cfg.league_logo).convert("RGBA")
    # Trim fully-transparent padding baked into the source PNG so every league
    # mark fills the same visual height regardless of internal whitespace.
    _lbbox = league_logo.getbbox()
    if _lbbox:
        league_logo = league_logo.crop(_lbbox)
    LOGO_TARGET_H = 84
    scale = LOGO_TARGET_H / league_logo.height
    league_logo = league_logo.resize(
        (int(league_logo.width * scale), LOGO_TARGET_H), Image.LANCZOS)
    img.alpha_composite(league_logo,
                        dest=(LEFT_EDGE, int(TOP_Y_MID - league_logo.height / 2)))

    wordmark_x = LEFT_EDGE + league_logo.width + 40
    # Reserve room for the date stamp on the right side
    date_str = dt.date.today().strftime("%A %d %B %Y").upper()
    date_w = draw.textbbox((0, 0), date_str, font=font(24, "bold"))[2]
    wordmark_max_w = RIGHT_EDGE - wordmark_x - date_w - 40
    # Pick the largest size that fits (fine 2pt steps so a long league name lands
    # just under the cap instead of dropping a big increment and undershooting).
    wm_fnt = font(44, "bold")
    for _sz in (44, 42, 40, 38, 36):
        wm_fnt = font(_sz, "bold")
        if draw.textbbox((0, 0), cfg.full_name, font=wm_fnt)[2] <= wordmark_max_w:
            break
    _left(draw, wordmark_x, TOP_Y_MID, cfg.full_name, wm_fnt, FG)
    _right(draw, RIGHT_EDGE, TOP_Y_MID, date_str, font(24, "bold"), SUB)

    # --- Red title bar -----------------------------------------------------
    RED_Y0 = PY + TOP_STRIP_H
    red_strip = Image.new("RGB", (PANEL_W - 2, RED_BAR_H))
    for x in range(red_strip.width):
        t = x / max(1, red_strip.width - 1)
        for y in range(red_strip.height):
            red_strip.putpixel((x, y), (
                int(HDR_RED_A[0] * (1 - t) + HDR_RED_B[0] * t),
                int(HDR_RED_A[1] * (1 - t) + HDR_RED_B[1] * t),
                int(HDR_RED_A[2] * (1 - t) + HDR_RED_B[2] * t),
            ))
    img.paste(red_strip, (PANEL[0] + 1, RED_Y0))
    draw = ImageDraw.Draw(img, "RGBA")

    # Red bar kept as a design divider, but the "Ordered by Points Per Game"
    # caption was removed (Mat's 2026-06-22 change) — standings now follow the
    # league website order, so the old caption no longer applies.

    # --- Column header strip ----------------------------------------------
    CH_Y = RED_Y0 + RED_BAR_H
    draw.rectangle((PANEL[0], CH_Y, PANEL[2], CH_Y + COL_HDR_H), fill=(28, 30, 36))
    draw.line((PANEL[0], CH_Y + COL_HDR_H, PANEL[2], CH_Y + COL_HDR_H),
              fill=GRID, width=1)
    ch_cy = CH_Y + COL_HDR_H // 2
    for i, col in enumerate(NUM_COLS):
        cx = NUM_START_X + i * NUM_COL_W + NUM_COL_W // 2
        is_pts = (col == "Pts")
        color = ACCENT if is_pts else SUB
        # Header font sizes bumped ~15% (Mat 2026-06-22): 24->28, 22->25
        fnt = font(28, "black") if is_pts else font(25, "semibold")
        _centered(draw, cx, ch_cy, col.upper(), fnt, color)

    # --- Team rows ---------------------------------------------------------
    for idx, team in enumerate(teams):
        ry = ROWS_TOP + idx * ROW_H
        fill_row = ROW_A if idx % 2 == 0 else ROW_B
        draw.rectangle((PANEL[0], ry, PANEL[2], ry + ROW_H), fill=fill_row)
        if idx < len(teams) - 1:
            draw.line((LEFT_EDGE, ry + ROW_H - 1, RIGHT_EDGE, ry + ROW_H - 1),
                      fill=GRID, width=1)

        cy = ry + ROW_H // 2

        pos = idx + 1
        pill_cx = LEFT_EDGE + POS_W // 2
        PILL_R = 22
        draw.rounded_rectangle(
            (pill_cx - PILL_R, cy - PILL_R, pill_cx + PILL_R, cy + PILL_R),
            radius=10, fill=PILL_BG,
        )
        pill_fg = DIM if (cfg.code == "NZIHL" and pos == 5) else FG
        _centered(draw, pill_cx, cy, str(pos), font(26, "bold"), pill_fg)

        logo_cx = LEFT_EDGE + POS_W + LOGO_W // 2
        _paste_logo(img, LOGOS_DIR / team["logo"], logo_cx, cy,
                    TEAM_LOGO_H, TEAM_LOGO_WCAP)
        draw = ImageDraw.Draw(img, "RGBA")

        name_x = LEFT_EDGE + POS_W + LOGO_W + 30
        name = team["name"]
        name_fnt = font(36, "bold")
        if draw.textbbox((0, 0), name, font=name_fnt)[2] > TEAM_W - 18:
            name_fnt = font(32, "bold")
        _left(draw, name_x, cy, name, name_fnt, FG)

        for i, col in enumerate(NUM_COLS):
            cx = NUM_START_X + i * NUM_COL_W + NUM_COL_W // 2
            if col == "GD":
                val = team["GD"]
                txt = f"+{val}" if val > 0 else (str(val) if val < 0 else "0")
                color = GREEN if val > 0 else (RED_NEG if val < 0 else DIM)
                _centered(draw, cx, cy, txt, font(36, "semibold"), color)
            elif col == "PPG":
                _centered(draw, cx, cy, f"{team['PPG']:.2f}",
                          font(36, "semibold"), FG)
            elif col == "Pts":
                _centered(draw, cx, cy, str(team["PTS"]),
                          font(54, "black"), ACCENT)
            else:
                v = team[col]
                if col == "L":
                    color = DIM
                    fnt = font(42, "semibold")
                else:
                    color = FG
                    fnt = font(42, "bold")
                _centered(draw, cx, cy, str(v), fnt, color)

    # --- Footer ------------------------------------------------------------
    footer_y = PANEL[3] - FOOTER_H // 2
    _centered(draw, (PANEL[0] + PANEL[2]) // 2, footer_y,
              "W Regulation Win (3) · OTW Overtime/Shootout Win (2) · "
              "OTL Overtime/Shootout Loss (1) · L Regulation Loss · "
              "GD Goal Differential · Pts Total Points · GP Games Played · "
              "PPG Points Per Game",
              font(19, "regular"), DIM)

    return img


def main() -> int:
    failed: List[str] = []
    for cfg in (NZIHL, NZWIHL):
        teams = fetch_standings(cfg)
        if teams is None:
            failed.append(cfg.code)
            continue
        img = render(cfg, teams)
        out = HERE / cfg.output_file
        img.save(out, "PNG", optimize=True)
        print(f"Wrote {out}  ({img.size[0]}x{img.size[1]})")
        for i, t in enumerate(teams, 1):
            print(f"  {i}. {t['name']:38s}  PTS={t['PTS']}  GP={t['GP']}  PPG={t['PPG']:.2f}")
    if failed:
        print(f"[error] scrape failed for: {', '.join(failed)} "
              f"(set use_fallback=True in build_standings.py to render "
              f"from the static snapshot)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
