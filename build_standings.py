#!/usr/bin/env python3
"""Render the NZIHL Standings broadcast graphic.

Run nightly on GitHub Actions. The script:
  1. Scrapes the current standings from nzihl.com.
  2. Renders a 1920x1080 RGBA PNG (60px transparent margin) using bundled
     fonts and team logos.
  3. Writes the result to ./NZIHL_Standings.png at the repo root.

All assets are bundled into this repo so the workflow has no external
dependencies beyond pip-installable libraries.
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path
from typing import List, Dict

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# --- Paths -----------------------------------------------------------------
HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
LOGOS_DIR = ASSETS / "logos"
LEAGUE_DIR = ASSETS / "league"
FONTS_DIR = ASSETS / "fonts"
OUTPUT_PNG = HERE / "NZIHL_Standings.png"

NZIHL_URL = (
    "https://www.nzihl.com/leagues/standings.cfm"
    "?clientid=7131&leagueid=35499"
)

# Map normalised team names from the website to bundled logo filenames.
LOGO_BY_TEAM = {
    "skycity stampede":                "Skycity Stampede 2000x2000.png",
    "pure nz admirals":                "West Auckland Admirals 2000x2000.png",
    "pure nz west auckland admirals":  "West Auckland Admirals 2000x2000.png",
    "west auckland admirals":          "West Auckland Admirals 2000x2000.png",
    "dunedin thunder":                 "Phoenix Thunder 2000x2000.png",
    "botany swarm":                    "Botany Swarm 2000x2000.png",
    "canterbury red devils":           "Red Devils 2000x2000r.png",
}

# Pretty display name for each team (matches broadcast convention).
DISPLAY_NAME = {
    "skycity stampede":                "SkyCity Stampede",
    "pure nz admirals":                "PureNZ West Auckland Admirals",
    "pure nz west auckland admirals":  "PureNZ West Auckland Admirals",
    "west auckland admirals":          "PureNZ West Auckland Admirals",
    "dunedin thunder":                 "Dunedin Thunder",
    "botany swarm":                    "Botany Swarm",
    "canterbury red devils":           "Canterbury Red Devils",
}


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


# --- Standings ingest ------------------------------------------------------
def _normalise(name: str) -> str:
    """Strip the 3-letter team code that nzihl.com appends (e.g. 'SkyCity StampedeSCS')."""
    return re.sub(r"[A-Z]{2,3}$", "", name).strip().lower()


def fetch_standings() -> List[Dict]:
    """Scrape the current NZIHL standings table.

    Falls back to a hard-coded snapshot if the scrape fails so the workflow
    never silently produces a stale graphic without warning.
    """
    try:
        resp = requests.get(NZIHL_URL, timeout=30,
                            headers={"User-Agent": "Mozilla/5.0 (NZIHL-Standings-Bot)"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        target = None
        for table in soup.find_all("table"):
            headers = [c.get_text(strip=True).upper()
                       for c in table.find_all(["th", "td"])][:20]
            if {"OTW", "OTL", "PTS"}.issubset(set(headers)):
                target = table
                break
        if target is None:
            raise RuntimeError("No standings table found in NZIHL page")

        rows = target.find_all("tr")
        # Header row tells us which column is which
        header_cells = [c.get_text(strip=True).upper() for c in rows[0].find_all(["th", "td"])]

        teams: List[Dict] = []
        for r in rows[1:]:
            cells = [c.get_text(strip=True) for c in r.find_all(["th", "td"])]
            if len(cells) < 6:
                continue
            data = dict(zip(header_cells, cells))
            raw_name = data.get("TEAM") or data.get("") or cells[0]
            key = _normalise(raw_name)
            if key not in DISPLAY_NAME:
                # Skip rows we can't map (e.g. legend rows, totals)
                continue
            try:
                team = {
                    "name": DISPLAY_NAME[key],
                    "logo": LOGO_BY_TEAM[key],
                    "GP":   int(data["GP"]),
                    "W":    int(data["W"]),
                    "L":    int(data["L"]),
                    "OTW":  int(data["OTW"]),
                    "OTL":  int(data["OTL"]),
                    "PTS":  int(data["PTS"]),
                    "GF":   int(data.get("GF", "0")),
                    "GA":   int(data.get("GA", "0")),
                }
            except (KeyError, ValueError):
                continue
            teams.append(team)

        if not teams:
            raise RuntimeError("Standings parse produced zero rows")
        return teams

    except Exception as exc:                                # noqa: BLE001
        print(f"[warn] live scrape failed ({exc!r}); using fallback snapshot",
              file=sys.stderr)
        return _FALLBACK_TEAMS


# Snapshot from 2026-05-20, used if scraping breaks.
_FALLBACK_TEAMS = [
    {"name": "SkyCity Stampede",              "logo": "Skycity Stampede 2000x2000.png",
     "W": 2, "OTW": 1, "OTL": 0, "L": 1, "GF": 19, "GA": 16, "PTS": 8, "GP": 4},
    {"name": "PureNZ West Auckland Admirals", "logo": "West Auckland Admirals 2000x2000.png",
     "W": 2, "OTW": 0, "OTL": 0, "L": 0, "GF": 12, "GA": 5,  "PTS": 6, "GP": 2},
    {"name": "Dunedin Thunder",               "logo": "Phoenix Thunder 2000x2000.png",
     "W": 2, "OTW": 0, "OTL": 0, "L": 2, "GF": 20, "GA": 17, "PTS": 6, "GP": 4},
    {"name": "Botany Swarm",                  "logo": "Botany Swarm 2000x2000.png",
     "W": 1, "OTW": 0, "OTL": 0, "L": 1, "GF": 7,  "GA": 10, "PTS": 3, "GP": 2},
    {"name": "Canterbury Red Devils",         "logo": "Red Devils 2000x2000r.png",
     "W": 0, "OTW": 0, "OTL": 1, "L": 3, "GF": 11, "GA": 21, "PTS": 1, "GP": 4},
]


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


def render(teams: List[Dict]) -> Image.Image:
    for t in teams:
        t["GD"] = t["GF"] - t["GA"]
        t["PPG"] = t["PTS"] / t["GP"] if t["GP"] else 0.0
    teams.sort(key=lambda t: (-t["PPG"], -t["PTS"], -t["GD"], t["GP"], t["name"]))

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

    # Shadow trimmed to inside the transparent margin
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        (PANEL[0] + 4, PANEL[1] + 10, PANEL[2] + 4, PANEL[3] + 10),
        radius=PANEL_R, fill=(0, 0, 0, 100),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    trim = Image.new("L", (W, H), 0)
    ImageDraw.Draw(trim).rectangle(
        (MARGIN, MARGIN, W - MARGIN, H - MARGIN), fill=255)
    shadow = Image.composite(shadow, Image.new("RGBA", (W, H), (0, 0, 0, 0)), trim)
    img.alpha_composite(shadow)
    img.alpha_composite(panel_img, dest=(MARGIN, MARGIN))

    draw = ImageDraw.Draw(img, "RGBA")

    def centered(d, x, y, text, fnt, fill):
        bb = d.textbbox((0, 0), text, font=fnt)
        w = bb[2] - bb[0]
        h = bb[3] - bb[1]
        d.text((x - w / 2 - bb[0], y - h / 2 - bb[1]), text, font=fnt, fill=fill)

    def left(d, x, y, text, fnt, fill):
        bb = d.textbbox((0, 0), text, font=fnt)
        h = bb[3] - bb[1]
        d.text((x - bb[0], y - h / 2 - bb[1]), text, font=fnt, fill=fill)

    def right(d, x, y, text, fnt, fill):
        bb = d.textbbox((0, 0), text, font=fnt)
        w = bb[2] - bb[0]
        h = bb[3] - bb[1]
        d.text((x - w - bb[0], y - h / 2 - bb[1]), text, font=fnt, fill=fill)

    def paste_logo(canvas, logo_path, cx, cy, size):
        try:
            logo = Image.open(logo_path).convert("RGBA")
        except FileNotFoundError:
            return
        logo.thumbnail((size, size), Image.LANCZOS)
        canvas.alpha_composite(logo, dest=(
            int(cx - logo.width / 2), int(cy - logo.height / 2)))

    PX, PY = PANEL[0], PANEL[1]
    INNER_PAD = 24
    LEFT_EDGE = PX + INNER_PAD
    RIGHT_EDGE = PANEL[2] - INNER_PAD

    TOP_STRIP_H = 130
    RED_BAR_H = TOP_STRIP_H // 2
    COL_HDR_H = 56
    FOOTER_H = 52

    ROWS_TOP = PY + TOP_STRIP_H + RED_BAR_H + COL_HDR_H
    ROWS_BOT = PANEL[3] - FOOTER_H
    ROW_H = (ROWS_BOT - ROWS_TOP) // len(teams)

    POS_W = 60
    LOGO_W = 110
    NUM_COLS = ["W", "OTW", "OTL", "L", "GD", "Pts", "GP", "PPG"]
    NUM_COL_W = 116
    NUM_TOTAL = NUM_COL_W * len(NUM_COLS)
    TEAM_W = (RIGHT_EDGE - LEFT_EDGE) - POS_W - LOGO_W - NUM_TOTAL
    NUM_START_X = LEFT_EDGE + POS_W + LOGO_W + TEAM_W

    # Top brand strip
    TOP_Y_MID = PY + TOP_STRIP_H // 2
    nzihl_logo = Image.open(LEAGUE_DIR / "NZIHL-White-2000.png").convert("RGBA")
    nzihl_logo.thumbnail((150, 150), Image.LANCZOS)
    img.alpha_composite(nzihl_logo,
                        dest=(LEFT_EDGE, int(TOP_Y_MID - nzihl_logo.height / 2)))
    wordmark_x = LEFT_EDGE + 150 + 22
    left(draw, wordmark_x, TOP_Y_MID - 18, "2026 SEASON", font(34, "bold"), FG)
    left(draw, wordmark_x, TOP_Y_MID + 18,
         "NEW ZEALAND ICE HOCKEY LEAGUE", font(18, "medium"), SUB)

    today_str = dt.date.today().strftime("%A %d %B %Y").upper()
    right(draw, RIGHT_EDGE, TOP_Y_MID, today_str, font(24, "bold"), SUB)

    # Red title bar
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

    centered(draw, (PANEL[0] + PANEL[2]) // 2, RED_Y0 + RED_BAR_H // 2,
             "Standings Ordered by Points Per Game",
             font(20, "bold"), (255, 255, 255))

    # Column header strip
    CH_Y = RED_Y0 + RED_BAR_H
    draw.rectangle((PANEL[0], CH_Y, PANEL[2], CH_Y + COL_HDR_H), fill=(28, 30, 36))
    draw.line((PANEL[0], CH_Y + COL_HDR_H, PANEL[2], CH_Y + COL_HDR_H),
              fill=GRID, width=1)
    ch_cy = CH_Y + COL_HDR_H // 2
    for i, col in enumerate(NUM_COLS):
        cx = NUM_START_X + i * NUM_COL_W + NUM_COL_W // 2
        is_pts = (col == "Pts")
        color = ACCENT if is_pts else SUB
        fnt = font(24, "black") if is_pts else font(22, "semibold")
        centered(draw, cx, ch_cy, col.upper(), fnt, color)

    # Team rows
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
        centered(draw, pill_cx, cy, str(pos), font(26, "bold"), FG)

        logo_cx = LEFT_EDGE + POS_W + LOGO_W // 2
        paste_logo(img, LOGOS_DIR / team["logo"], logo_cx, cy, 100)
        draw = ImageDraw.Draw(img, "RGBA")

        name_x = LEFT_EDGE + POS_W + LOGO_W + 14
        name = team["name"]
        name_fnt = font(32, "bold")
        if draw.textbbox((0, 0), name, font=name_fnt)[2] > TEAM_W - 18:
            name_fnt = font(28, "bold")
        left(draw, name_x, cy, name, name_fnt, FG)

        for i, col in enumerate(NUM_COLS):
            cx = NUM_START_X + i * NUM_COL_W + NUM_COL_W // 2
            if col == "GD":
                val = team["GD"]
                txt = f"+{val}" if val > 0 else (str(val) if val < 0 else "0")
                color = GREEN if val > 0 else (RED_NEG if val < 0 else DIM)
                centered(draw, cx, cy, txt, font(28, "semibold"), color)
            elif col == "PPG":
                centered(draw, cx, cy, f"{team['PPG']:.2f}",
                         font(28, "semibold"), FG)
            elif col == "Pts":
                centered(draw, cx, cy, str(team["PTS"]),
                         font(42, "black"), ACCENT)
            else:
                v = team[col]
                if col == "L":
                    color = DIM
                    fnt = font(32, "semibold")
                else:
                    color = FG
                    fnt = font(32, "bold")
                centered(draw, cx, cy, str(v), fnt, color)

    footer_y = PANEL[3] - FOOTER_H // 2
    centered(draw, (PANEL[0] + PANEL[2]) // 2, footer_y,
             "W Regulation Win (3) · OTW Overtime/Shootout Win (2) · "
             "OTL Overtime/Shootout Loss (1) · L Regulation Loss · "
             "GD Goal Differential · Pts Total Points · GP Games Played · "
             "PPG Points Per Game",
             font(19, "regular"), DIM)

    return img


def main() -> int:
    teams = fetch_standings()
    img = render(teams)
    img.save(OUTPUT_PNG, "PNG", optimize=True)
    print(f"Wrote {OUTPUT_PNG}  ({img.size[0]}x{img.size[1]})")
    for i, t in enumerate(sorted(teams, key=lambda x: (-x["PPG"], -x["PTS"])), 1):
        print(f"  {i}. {t['name']:38s}  PPG={t['PPG']:.2f}  PTS={t['PTS']}  GP={t['GP']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
