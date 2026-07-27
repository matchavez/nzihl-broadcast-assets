"""Render one team pronunciation sheet (A4 portrait, one page) using the
same reportlab + Inter house style as the existing roster PDFs.

Layout: logo/name banner -> team info block (venue, HC/AC w/ phonetics)
-> dynamic photo-card grid (players with GP>0 this season, falling back
to the full roster if nobody has played yet -- e.g. a fresh preseason
build) -> footer.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

from reportlab.lib.pagesizes import portrait, A4
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont as PDFTrueTypeFont
from PIL import Image

import sys
sys.path.insert(0, str(Path(__file__).parent))
from team_registry import TEAMS, TeamMeta, VENUE_CAPACITY, BIRGEL_CUP, GOULDING_CUP

SYS_DIR = Path(__file__).parent
FONT_DIR = SYS_DIR / "fonts"
LOGO_DIR = SYS_DIR / "logos"
PHOTOS_ROOT = Path(os.environ.get("PRONUNCIATION_PHOTOS_ROOT", "/tmp/work/nzihl-player-photos"))

FONT_REGULAR = "Inter"
FONT_BOLD = "Inter-Bold"
FONT_SEMIBOLD = "Inter-SemiBold"
FONT_EMOJI = "NotoEmoji"
pdfmetrics.registerFont(PDFTrueTypeFont(FONT_REGULAR, str(FONT_DIR / "Inter-Regular-tnum.ttf")))
pdfmetrics.registerFont(PDFTrueTypeFont(FONT_BOLD, str(FONT_DIR / "Inter-Bold-tnum.ttf")))
pdfmetrics.registerFont(PDFTrueTypeFont(FONT_SEMIBOLD, str(FONT_DIR / "Inter-SemiBold-tnum.ttf")))
# Monochrome vector emoji font (NOT Noto Color Emoji -- reportlab can't render
# COLR/bitmap color fonts). Sourced from google/fonts ofl/notoemoji, same
# sparse-clone approach used to get Inter in-sandbox. Renders as flat black
# glyphs, which is what we want since labels are drawn in MUTED gray anyway.
pdfmetrics.registerFont(PDFTrueTypeFont(FONT_EMOJI, str(FONT_DIR / "NotoEmoji-Regular.ttf")))

EMOJI_CALENDAR = "\U0001F4C5"
EMOJI_STADIUM = "\U0001F3DF"
EMOJI_ABACUS = "\U0001F9EE"   # closest Unicode equivalent to "calculator" --
                                # there is no standalone calculator emoji in
                                # the standard set; abacus is the conventional
                                # stand-in.
EMOJI_TROPHY = "\U0001F3C6"

INK = HexColor("#0C0C0C")
SUBINK = HexColor("#404040")
MUTED = HexColor("#6A6A6A")
RULE = HexColor("#D8D8D8")
CARD_BG = HexColor("#FAFAFA")

# Note: full-stats linking (rosters_profile.cfm, clientid/leagueID/teamID/
# playerID) lives in the HTML player warehouse (matchavez/hockey's
# hockey/warehouse/), NOT on these PDF sheets -- per Mat, 2026-07-27. The
# constants/URL builder for that live in the warehouse page's JS instead.


def _jersey_sort_key(num):
    try:
        return (0, int(num))
    except (ValueError, TypeError):
        return (1, 9999)


def _photo_path(league: str, tla: str, player_id: int, manifest: dict) -> Path | None:
    team_people = manifest["leagues"].get(league, {}).get("teams", {}).get(tla, {}).get("people", {})
    entry = team_people.get(f"{league}:{tla}:player:{player_id}")
    if entry and entry.get("photo"):
        p = PHOTOS_ROOT / entry["photo"]
        return p if p.exists() else None
    return None


def _draw_initials_block(c, x, y, w, h, initials, team: TeamMeta):
    """Portrait-block photo fallback (no photo on file): solid team-color
    rect with big centred initials, same footprint as a real headshot."""
    c.setFillColor(HexColor(team.primary_hex))
    c.rect(x, y, w, h, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont(FONT_BOLD, w * 0.42)
    c.drawCentredString(x + w / 2, y + h / 2 - w * 0.15, initials)


def _draw_jersey_block(c, x, y, w, h, jersey, position, team: TeamMeta):
    """Portrait block, same footprint as the headshot, sitting to its left:
    jersey number fills the top ~60%, position fills the bottom ~40%,
    separated by a thin rule. Replaces the old overlay-badge-on-photo
    approach so the number never competes with the photo or the text."""
    c.setFillColor(HexColor(team.primary_hex))
    c.rect(x, y, w, h, stroke=0, fill=1)

    split_y = y + h * 0.38  # position band height (bottom), number band above
    num_fs = w * 0.5
    num_str = str(jersey) if jersey and jersey != "-" else "—"
    if len(num_str) >= 3:
        num_fs = w * 0.38
    accent = HexColor(team.jersey_text_hex or team.accent_hex)
    c.setFillColor(accent)
    c.setFont(FONT_BOLD, num_fs)
    num_band_center = split_y + (y + h - split_y) / 2
    c.drawCentredString(x + w / 2, num_band_center - num_fs * 0.36, num_str)

    c.setStrokeColor(accent)
    c.setLineWidth(0.6)
    c.line(x + w * 0.18, split_y, x + w * 0.82, split_y)

    pos_fs = min(w * 0.26, 11)
    c.setFillColor(accent)
    c.setFont(FONT_SEMIBOLD, pos_fs)
    pos_band_center = y + (split_y - y) / 2
    c.drawCentredString(x + w / 2, pos_band_center - pos_fs * 0.32, position or "")


def _draw_cover_image(c, path, x, y, w, h):
    """Draw `path` clipped to (x,y,w,h) filling the ENTIRE box -- crops the
    excess rather than letterboxing. Without this, drawImage's own
    preserveAspectRatio mode fits the photo *inside* the box (leaving
    whitespace on two sides for any photo whose aspect ratio doesn't match
    the box), which made the photo look smaller than the solid-filled
    jersey block next to it even though the bounding boxes were already
    identical. Cover-cropping makes the two actually look the same size."""
    with Image.open(path) as im:
        img_w, img_h = im.size
    img_aspect = img_w / img_h
    box_aspect = w / h
    if img_aspect > box_aspect:
        draw_h = h
        draw_w = h * img_aspect
    else:
        draw_w = w
        draw_h = w / img_aspect
    draw_x = x - (draw_w - w) / 2
    draw_y = y - (draw_h - h) / 2
    c.saveState()
    p = c.beginPath()
    p.rect(x, y, w, h)
    c.clipPath(p, stroke=0, fill=0)
    c.drawImage(str(path), draw_x, draw_y, draw_w, draw_h, mask="auto")
    c.restoreState()


def _initials(display_name: str) -> str:
    parts = [p for p in display_name.replace("-", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def build_team_sheet(*, out_path: str, team: TeamMeta, stats_team: dict,
                      pronunciations: dict, photo_manifest: dict,
                      standing: dict | None = None) -> str:
    PAGE = portrait(A4)
    PW, PH = PAGE
    MARGIN = 10 * mm
    c = canvas.Canvas(out_path, pagesize=PAGE)
    c.setTitle(f"{team.display_name} — Team Info and Pronunciation Guide")

    league_label = "NZIHL" if team.league == "nzihl" else "NZWIHL"

    # ---- Header banner ----
    # h1 (masthead, constant across every sheet): "Team Info and Pronunciation
    # Guide". h2 (which sheet this is): "Team Name, TLA, League". Per Mat,
    # 2026-07-28 -- previously the team name WAS the h1, this flips the
    # hierarchy so the document title is primary and the team identity reads
    # as a subtitle underneath it.
    BAND_H = 26 * mm
    c.setFillColor(HexColor(team.primary_hex))
    c.rect(0, PH - BAND_H, PW, BAND_H, stroke=0, fill=1)

    logo_path = LOGO_DIR / team.logo_file if team.logo_file else None
    logo_size = 18 * mm
    text_x = MARGIN
    if logo_path and logo_path.exists():
        chip = 20 * mm
        c.setFillColor(white)
        c.roundRect(MARGIN, PH - BAND_H + (BAND_H - chip) / 2, chip, chip, 3 * mm, stroke=0, fill=1)
        try:
            c.drawImage(str(logo_path), MARGIN + (chip - logo_size) / 2,
                        PH - BAND_H + (BAND_H - logo_size) / 2, logo_size, logo_size,
                        mask="auto", preserveAspectRatio=True)
        except Exception:
            pass
        text_x = MARGIN + chip + 6 * mm

    c.setFillColor(HexColor(team.title_hex))
    c.setFont(FONT_BOLD, 17)
    c.drawString(text_x, PH - 11 * mm, "TEAM INFO AND PRONUNCIATION GUIDE")
    c.setFont(FONT_SEMIBOLD, 12.5)
    c.drawString(text_x, PH - 19.5 * mm, f"{team.display_name}     {team.tla}     {league_label}")

    y = PH - BAND_H

    # ---- Info block ----
    # TLA / founded / venue+capacity / current standing (one line), then the
    # club's championship-cup history, then coaches -- per Mat, 2026-07-28.
    # (Color swatches were here in the previous draft; removed per Mat --
    # "those don't need to be here".)
    INFO_H = 34 * mm
    c.setFillColor(HexColor("#F2F2F2"))
    c.rect(0, y - INFO_H, PW, INFO_H, stroke=0, fill=1)

    label_col = MARGIN
    FIELD_GAP = 8 * mm
    EMOJI_GAP = 1.3 * mm

    def _label_width(emoji, text, fs):
        w = pdfmetrics.stringWidth(text, FONT_SEMIBOLD, fs)
        if emoji:
            w += pdfmetrics.stringWidth(emoji, FONT_EMOJI, fs + 1) + EMOJI_GAP
        return w

    def _field_width(emoji, label, value, label_fs=6.6, value_fs=9):
        return max(_label_width(emoji, label, label_fs),
                    pdfmetrics.stringWidth(value, FONT_SEMIBOLD, value_fs))

    def _field(x, yy, emoji, label, value, label_fs=6.6, value_fs=9):
        c.setFillColor(MUTED)
        cx = x
        if emoji:
            c.setFont(FONT_EMOJI, label_fs + 1)
            c.drawString(cx, yy, emoji)
            cx += pdfmetrics.stringWidth(emoji, FONT_EMOJI, label_fs + 1) + EMOJI_GAP
        c.setFont(FONT_SEMIBOLD, label_fs)
        c.drawString(cx, yy, label)
        c.setFillColor(INK)
        c.setFont(FONT_SEMIBOLD, value_fs)
        c.drawString(x, yy - value_fs - 0.6 * mm, value)

    # Row 1: Founded / Home venue / Current standing -- all one line. (TLA
    # dropped from here per Mat, 2026-07-28 -- it's already in the h2
    # headline right above, repeating it here was redundant.)
    row1_y = y - 6 * mm
    founded_txt = str(team.founded) if team.founded else "—"
    if team.home_venue:
        cap = VENUE_CAPACITY.get(team.home_venue)
        venue_txt = f"{team.home_venue}" + (f" (cap. {cap:,})" if cap else "")
    else:
        venue_txt = "TBC — not yet fielding a roster"
    if standing:
        standing_txt = (f"{_ordinal(standing['rank'])} · "
                         f"{standing['w']}-{standing['otw']}-{standing['otl']}-{standing['l']} · "
                         f"{standing['pts']} PTS")
    else:
        standing_txt = "No standings yet"

    cup_map = BIRGEL_CUP if team.league == "nzihl" else GOULDING_CUP
    cup_label = "BIRGEL CUP" if team.league == "nzihl" else "GOULDING CUP"
    seasons = cup_map.get(team.tla, [])
    cup_txt = " · ".join(str(s) for s in seasons) if seasons else "No titles yet"

    row1_fields = [
        (EMOJI_CALENDAR, "FOUNDED", founded_txt),
        (EMOJI_STADIUM, "HOME VENUE", venue_txt),
        (EMOJI_ABACUS, "CURRENT STANDING", standing_txt),
    ]
    title_field = (EMOJI_TROPHY, cup_label, cup_txt)

    available = PW - MARGIN - label_col  # right edge minus where fields start
    base_width = sum(_field_width(*f) for f in row1_fields) + FIELD_GAP * (len(row1_fields) - 1)
    title_width = _field_width(*title_field)
    titles_fit_on_row1 = (base_width + FIELD_GAP + title_width) <= available

    all_row1 = row1_fields + [title_field] if titles_fit_on_row1 else row1_fields
    cursor_x = label_col
    for emoji, label, value in all_row1:
        _field(cursor_x, row1_y, emoji, label, value)
        cursor_x += _field_width(emoji, label, value) + FIELD_GAP

    # Row 2: championship-cup history -- Birgel Cup (NZIHL) / Goulding Cup
    # (NZWIHL), only rendered here if it didn't fit on row1 above. Per Mat,
    # 2026-07-28: "if a team can fit their titles into the top line, put
    # them there" -- most low-title-count teams do; SCS (10 titles) and AST
    # (7 titles) are wide enough that they still need their own row.
    row2_y = y - 19 * mm
    if not titles_fit_on_row1:
        _field(label_col, row2_y, EMOJI_TROPHY, cup_label, cup_txt)

    # Row 3: coaches (same content/format as before).
    row3_y = y - 30 * mm
    coach_rows = [p for p in pronunciations.values()
                  if p["team"] == team.tla and p["league"] == team.league and p["role"] == "coach"]
    order = {"Head Coach": 0, "Assistant Coach": 1}
    coach_rows.sort(key=lambda r: order.get(r.get("coach_title", ""), 2))
    coach_bits = []
    for cr in coach_rows:
        abbrev = "HC" if cr.get("coach_title") == "Head Coach" else "AC"
        coach_bits.append(f"{abbrev} {cr['display_name']}  ({cr['phonetic']})")
    coach_line = "   ".join(coach_bits) if coach_bits else "No coaching staff on file"
    c.setFillColor(MUTED)
    c.setFont(FONT_SEMIBOLD, 6.6)
    c.drawString(label_col, row3_y, "COACHES")
    c.setFillColor(INK)
    coach_fs = 8.2
    max_w = PW - 2 * MARGIN
    while c.stringWidth(coach_line, FONT_REGULAR, coach_fs) > max_w and coach_fs > 6.5:
        coach_fs -= 0.3
    c.setFont(FONT_REGULAR, coach_fs)
    c.drawString(label_col, row3_y - coach_fs - 0.6 * mm, coach_line)

    y -= INFO_H

    # ---- Player grid ----
    FOOTER_H = 8 * mm
    grid_top = y - 3 * mm
    grid_bottom = MARGIN + FOOTER_H

    if not team.active or stats_team is None:
        c.setFont(FONT_SEMIBOLD, 13)
        c.setFillColor(MUTED)
        c.drawCentredString(PW / 2, (grid_top + grid_bottom) / 2,
                             "No active roster on file — sheet will populate once the league confirms this team.")
        _draw_footer(c, PW, MARGIN, team)
        c.showPage()
        c.save()
        return out_path

    skaters = stats_team.get("skaters", [])
    goalies = stats_team.get("goalies", [])
    active_sk = [s for s in skaters if s.get("gp", 0) > 0]
    active_go = [g for g in goalies if g.get("gp", 0) > 0]
    if not active_sk and not active_go:
        # Preseason fallback: nobody has GP yet, show the full signed roster.
        active_sk, active_go = skaters, goalies

    # Skaters and goalies are combined into one list and sorted purely by
    # jersey number -- no skaters-block-then-goalies-block grouping. A
    # goalie's number is just another number on the same roster.
    seen_ids = set()
    people = []
    for s in active_sk:
        pid = s.get("player_id")
        if not pid or pid in seen_ids:
            continue
        seen_ids.add(pid)
        people.append((pid, s["number"], s.get("position", "")))
    for g in active_go:
        pid = g.get("player_id")
        if not pid or pid in seen_ids:
            continue
        seen_ids.add(pid)
        people.append((pid, g["number"], "G"))
    people.sort(key=lambda p: _jersey_sort_key(p[1]))

    n = len(people)
    cols = min(3, n) if n else 1
    rows = math.ceil(n / cols) if n else 1
    cell_w = (PW - 2 * MARGIN) / cols
    # Portrait blocks (jersey block + headshot) drive the row height now,
    # not a fixed cell cap -- position moved into the jersey block, so
    # there's no separate bottom-anchored line to budget room for, which
    # is what lets the card get considerably shorter.
    cell_h = max(16 * mm, (grid_top - grid_bottom) / max(rows, 1))
    cell_h = min(cell_h, 24 * mm)
    used_h = rows * cell_h
    grid_top -= max(0, (grid_top - grid_bottom - used_h) / 2)

    pad = 2.4 * mm
    block_h = cell_h - 2 * pad
    PORTRAIT_RATIO = 0.72  # width = ratio * height
    block_w = block_h * PORTRAIT_RATIO

    for i, (pid, jersey, position) in enumerate(people):
        col = i % cols
        row = i // cols
        cx = MARGIN + col * cell_w
        cy = grid_top - (row + 1) * cell_h
        if cy < grid_bottom - cell_h:
            break  # ran out of page room (shouldn't happen with sizing above)

        pron = pronunciations.get(str(pid))
        display_name = pron["display_name"] if pron else f"Player {pid}"
        phonetic = pron["phonetic"] if pron else ""
        prefers = pron.get("prefers") if pron else None

        block_y = cy + pad
        jersey_x = cx + pad
        photo_x = jersey_x + block_w  # touching -- no gap between the two blocks

        _draw_jersey_block(c, jersey_x, block_y, block_w, block_h, jersey, position, team)

        photo_path = _photo_path(team.league, team.tla, pid, photo_manifest)
        if photo_path:
            try:
                _draw_cover_image(c, photo_path, photo_x, block_y, block_w, block_h)
            except Exception:
                _draw_initials_block(c, photo_x, block_y, block_w, block_h, _initials(display_name), team)
        else:
            _draw_initials_block(c, photo_x, block_y, block_w, block_h, _initials(display_name), team)
        c.setStrokeColor(RULE)
        c.setLineWidth(0.4)
        c.rect(jersey_x, block_y, block_w * 2, block_h, stroke=1, fill=0)
        c.line(photo_x, block_y, photo_x, block_y + block_h)

        text_x0 = photo_x + block_w + 2.4 * mm
        text_w = cx + cell_w - pad - text_x0
        name_fs = 8.3
        while c.stringWidth(display_name, FONT_SEMIBOLD, name_fs) > text_w and name_fs > 6.6:
            name_fs -= 0.3
        # Names that still don't fit at the floor size wrap to a second line
        # (split near the middle word boundary) instead of clipping --
        # Sebastian Chamberlin / Flynn Hayward Jones / Benjamin De Jonge all
        # got silently truncated before this.
        name_lines = [display_name]
        if c.stringWidth(display_name, FONT_SEMIBOLD, name_fs) > text_w:
            words = display_name.split(" ")
            if len(words) > 1:
                best_split = 1
                best_diff = None
                for i in range(1, len(words)):
                    l1 = " ".join(words[:i])
                    diff = abs(c.stringWidth(l1, FONT_SEMIBOLD, name_fs) - text_w / 1.4)
                    if best_diff is None or diff < best_diff:
                        best_diff, best_split = diff, i
                name_lines = [" ".join(words[:best_split]), " ".join(words[best_split:])]

        c.setFillColor(INK)
        c.setFont(FONT_SEMIBOLD, name_fs)
        line_gap = name_fs + 0.3 * mm
        name_block_h = line_gap * len(name_lines)

        phon_fs = 7.6
        while c.stringWidth(phonetic, FONT_REGULAR, phon_fs) > text_w and phon_fs > 6.0:
            phon_fs -= 0.2
        phon_lines = [phonetic]
        if c.stringWidth(phonetic, FONT_REGULAR, phon_fs) > text_w:
            words = phonetic.split(" ")
            if len(words) > 1:
                best_split, best_diff = 1, None
                for i in range(1, len(words)):
                    l1 = " ".join(words[:i])
                    diff = abs(c.stringWidth(l1, FONT_REGULAR, phon_fs) - text_w / 1.4)
                    if best_diff is None or diff < best_diff:
                        best_diff, best_split = diff, i
                phon_lines = [" ".join(words[:best_split]), " ".join(words[best_split:])]
        phon_line_gap = phon_fs + 0.2 * mm
        phon_block_h = phon_line_gap * len(phon_lines)

        prefers_fs = 6.6
        prefers_block_h = (prefers_fs + 0.8 * mm) if prefers else 0

        # Center the whole (name + phonetic [+ prefers]) text stack
        # vertically against the jersey/photo blocks -- there's no separate
        # bottom-anchored position line to leave room for anymore, position
        # lives in the jersey block now.
        total_text_h = name_block_h + phon_block_h + 1.0 * mm
        if prefers:
            total_text_h += prefers_block_h + 0.8 * mm
        text_top = block_y + (block_h + total_text_h) / 2

        c.setFillColor(INK)
        c.setFont(FONT_SEMIBOLD, name_fs)
        name_baseline = text_top - name_fs
        for li, line in enumerate(name_lines):
            c.drawString(text_x0, name_baseline - li * line_gap, line)

        c.setFillColor(HexColor(team.text_hex or team.primary_hex))
        c.setFont(FONT_REGULAR, phon_fs)
        phon_baseline = name_baseline - (len(name_lines) - 1) * line_gap - 1.0 * mm - phon_fs
        for pi, line in enumerate(phon_lines):
            c.drawString(text_x0, phon_baseline - pi * phon_line_gap, line)

        if prefers:
            c.setFillColor(MUTED)
            c.setFont(FONT_REGULAR, prefers_fs)
            prefers_baseline = phon_baseline - (len(phon_lines) - 1) * phon_line_gap - 0.8 * mm - prefers_fs
            c.drawString(text_x0, prefers_baseline, f"Prefers: {prefers}")

        c.setStrokeColor(RULE)
        c.setLineWidth(0.4)
        c.rect(cx + 1, cy + 1, cell_w - 2, cell_h - 2, stroke=1, fill=0)

    _draw_footer(c, PW, MARGIN, team)
    c.showPage()
    c.save()
    return out_path


def _draw_footer(c, PW, MARGIN, team: TeamMeta):
    c.setFillColor(MUTED)
    c.setFont(FONT_REGULAR, 6.8)
    c.drawString(MARGIN, MARGIN - 1 * mm,
                 "Full player stats: the online Player Warehouse · phonetics reviewed by broadcast production")
