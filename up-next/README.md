# UP NEXT — Matchup Overlays

Transparent **1920×1080** broadcast overlays for the stream "starting soon" countdown — one for every matchup, both home/away orderings, across NZIHL (men) and NZWIHL (women).

**NZIHL (men)** — full-frame overlays, **three variants** each:

- **`*_HERO.png`** — full 1920×1080 overlay (top *UP NEXT* band + bottom matchup bar).
- **`*_BottomBar.png`** — just the matchup bar, tightly cropped.
- **`*_BottomBar_1080frame.png`** — the matchup bar registered inside a full 1080 frame (drop-in alignment).

**NZWIHL (women)** — the women's "stream starting soon" is a **still** with a centred live countdown and social row, so these overlays sit *around* those elements (they never cover the timer or handles). **Two variants** each:

- **`*_LowerThird.png`** — colour-split lower-third strip below the social row (both logos + names + centred *UP NEXT*).
- **`*_LowerThirdWithWings.png`** — the lower third (reading *COMING UP NEXT*) **plus** team-colour wings flanking the clock (logo only in the wings).

Filenames read **`HOME_v_AWAY`** — the **home team is the folder's team** and sits on the **left**.

## Grab your club's graphics

Click your **ZIP** for a one-click download of all your overlays, or browse the folder to preview individual files.

### NZIHL (men) — 15 files each

| Club | Files | Folder | Download |
|---|---|---|---|
| **Red Devils** | 15 | [Red Devils/](./Red%20Devils/) | [⬇ Red Devils.zip](./zips/Red%20Devils.zip) |
| **Pure NZ Admirals** | 15 | [Pure NZ Admirals/](./Pure%20NZ%20Admirals/) | [⬇ Pure NZ Admirals.zip](./zips/Pure%20NZ%20Admirals.zip) |
| **Dunedin Thunder** | 15 | [Dunedin Thunder/](./Dunedin%20Thunder/) | [⬇ Dunedin Thunder.zip](./zips/Dunedin%20Thunder.zip) |
| **SkyCity Stampede** | 15 | [SkyCity Stampede/](./SkyCity%20Stampede/) | [⬇ SkyCity Stampede.zip](./zips/SkyCity%20Stampede.zip) |
| **Botany Swarm** | 15 | [Botany Swarm/](./Botany%20Swarm/) | [⬇ Botany Swarm.zip](./zips/Botany%20Swarm.zip) |
| **Auckland Mako** | 15 | [Auckland Mako/](./Auckland%20Mako/) | [⬇ Auckland Mako.zip](./zips/Auckland%20Mako.zip) |

### NZWIHL (women) — 6 files each

| Club | Files | Folder | Download |
|---|---|---|---|
| **Auckland Steel** | 6 | [Auckland Steel/](./Auckland%20Steel/) | [⬇ Auckland Steel.zip](./zips/Auckland%20Steel.zip) |
| **Canterbury Inferno** | 6 | [Canterbury Inferno/](./Canterbury%20Inferno/) | [⬇ Canterbury Inferno.zip](./zips/Canterbury%20Inferno.zip) |
| **Dunedin Thunder Women** | 6 | [Dunedin Thunder Women/](./Dunedin%20Thunder%20Women/) | [⬇ Dunedin Thunder Women.zip](./zips/Dunedin%20Thunder%20Women.zip) |
| **Wakatipu Wild** | 6 | [Wakatipu Wild/](./Wakatipu%20Wild/) | [⬇ Wakatipu Wild.zip](./zips/Wakatipu%20Wild.zip) |

## Regenerating / adding matchups

The renderer is self-contained under [`renderer/`](./renderer/) (Python + Pillow). It reads team logos from `assets/logos`, league marks from `assets/league`, and bundled fonts from `renderer/fonts`.

```bash
cd up-next/renderer
pip install pillow numpy
# hero PNG for a matchup (home team = LEFT):
OUT_DIR=. LEAGUE=nzihl LEFT=stampede RIGHT=admirals python3 overlay.py still
# bottom bar (tight crop + 1080 frame):
OUT_DIR=. LEAGUE=nzwihl LEFT=wild RIGHT=steel python3 overlay.py bottombar
# NZWIHL still-frame lower thirds — renders ALL women matchups at once:
OUT_DIR=. python3 nzwihl_still_lowerthirds.py
```

Team keys: `red_devils admirals thunder stampede swarm mako` (NZIHL) · `steel inferno thunder_w wild` (NZWIHL).

**Design lock-ins:** evergreen (no date/time/year); no "VS" (the league mark is the centre divider); seam slant matches the "I" in the league mark; team colours per the 2026 style guide. SkyCity Stampede (men) and Wakatipu Wild (women) use gold/yellow bands with navy text, so neither clashes with the navy Admirals / Steel.

