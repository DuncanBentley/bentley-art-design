---
name: wcag-contrast-check
description: Checks WCAG 2.x color contrast for a set of hex colors and prints a contrast matrix with AA and AAA pass/fail for normal and large text, flagging every failing pair. Use when the user asks to check color contrast, test whether text on a background is readable or accessible, audit a palette, brand colors, theme or design tokens against WCAG / accessibility (a11y) rules, compare foreground and background colors, or asks "does this pass AA?" or "is this accessible?". Report-only lite skill - it measures and flags; it does not generate palettes, color scales, tokens or automatic fixes.
---

# WCAG Contrast Check (lite)

Measure contrast instead of eyeballing it. `scripts/contrast_check.py` takes hex colors and
prints a WCAG 2.x contrast matrix, then lists every pair with its AA / AAA results for normal
and large text, lowest contrast first, with failing pairs flagged. Python 3.8+, standard
library only, no network.

## When to use

- "Check the contrast of #1A1A2E on #F5F5F5" / "does this button text pass AA?"
- "Is my palette accessible?" / "audit these brand colors for WCAG"
- Reviewing CSS variables, Tailwind colors or design tokens before shipping
- Any time you are about to claim colors are "accessible": run the numbers first

Not for: images, gradients or transparent colors (see Limitations), APCA / WCAG 3 scores.

## Quick start

```bash
# all colors against each other
python scripts/contrast_check.py ink=#1A1A2E paper=#FFFFFF brand=#E94560 muted=#777777

# only the pairings you will actually use: text colors x background colors
python scripts/contrast_check.py ink=#1A1A2E brand=#E94560 paper=#FFF cream=#FAF7F2 --fg ink brand --bg paper cream

# explicit pairs, markdown table for a report, non-zero exit if anything fails (CI)
python scripts/contrast_check.py --pair "#777" "#FFF" --pair "#E94560" "#1A1A2E" --format markdown --strict

# from a JSON file (list of hex, {"name": "#hex"}, or {"colors": ..., "fg": [...], "bg": [...], "pairs": [[fg, bg]]})
python scripts/contrast_check.py --json examples/palette.json
```

| Option | What it does |
|---|---|
| `COLOR ...` | `#RGB`, `#RRGGBB` (the `#` is optional) or named `name=#hex` |
| `--json FILE` | read colors (and optional `fg`, `bg`, `pairs`) from JSON; `-` reads stdin |
| `--fg ... --bg ...` | rows = text colors, columns = backgrounds (names or hex) |
| `--pair FG BG` | check one exact pair; repeatable; skips the matrix |
| `--level` | what counts as failing: `AA` (default, 4.5:1), `AA-large` (3:1), `AAA` (7:1), `AAA-large` (4.5:1) |
| `--format` | `text` (default), `markdown` or `json` |
| `--strict` | exit code 1 if any pair fails `--level` (exit 2 = bad input) |

## Workflow

1. **Collect the colors.** Pull hex values from the user's message, CSS, Tailwind config or token
   file. Give them short names (`ink`, `surface`, `primary`) so the report is readable.
2. **Decide the pairings.** If you know which colors are text and which are backgrounds, use
   `--fg/--bg` or `--pair`: an all-against-all matrix also flags pairs nobody will ever use
   (two light tints), which is noise. If unsure, run the full matrix and say so.
3. **Pick the right threshold** for each pair (table below). Body text needs 4.5:1 for AA;
   headings at 24px+ (or 18.66px+ bold) and icons / input borders need 3:1.
4. **Run the script** and read the `Pairs` table. Never compute ratios in your head and never
   round a ratio up: 4.47:1 is a fail for body text, even though it "looks like 4.5".
5. **Report** in this shape:
   - one line verdict ("3 of 4 intended pairs pass AA; brand red on white fails body text"),
   - a small table of the intended pairs (ratio, AA, AAA, what it is used for),
   - the failing pairs and which uses are still allowed (e.g. "3.82:1: OK for 24px+ headings and
     icons, not for body text").
6. **If the user wants a replacement color,** this lite skill does not compute fixes. You may
   suggest a direction (darker text, lighter background) but run every candidate through the
   script before you call it compliant.

## WCAG 2.x thresholds

| Use | AA | AAA | Criterion |
|---|---|---|---|
| Normal text | 4.5:1 | 7:1 | 1.4.3 / 1.4.6 |
| Large text: 24px (18pt) regular, or 18.66px (14pt) bold and up | 3:1 | 4.5:1 | 1.4.3 / 1.4.6 |
| UI components and meaningful graphics (borders, icons, focus rings) | 3:1 | - | 1.4.11 |

Matrix grades: `AAA` >= 7:1, `AA` >= 4.5:1, `LARGE` >= 3:1 (large text and UI only), `FAIL` < 3:1.
Ratios are shown truncated to two decimals (#777777 on white is 4.478:1, shown as 4.47:1), so a
displayed value never claims a pass the real value does not have. Logos and purely decorative
text have no contrast requirement.

## Example output

```
               ink         paper       brand
               #1A1A2E     #FFFFFF     #E94560
ink   #1A1A2E  -           17.05 AAA   4.45 LARGE
paper #FFFFFF  17.05 AAA   -           3.82 LARGE
brand #E94560  4.45 LARGE  3.82 LARGE  -

flag     ratio  AA    AA-lg  AAA   AAA-lg  pair
FAIL    3.82:1  fail  pass   fail  fail    paper #FFFFFF / brand #E94560
FAIL    4.45:1  fail  pass   fail  fail    ink #1A1A2E / brand #E94560
ok     17.05:1  pass  pass   pass  pass    ink #1A1A2E / paper #FFFFFF
```

## Limitations

- Solid sRGB hex colors only. Flatten transparent colors (`#RRGGBBAA`, `rgba()`) onto their real
  background first; text over images or gradients must be checked at its worst spot.
- WCAG 2.x formula only (the one current laws and audits use), not APCA / WCAG 3 drafts.
- It does not know your font sizes: you choose which threshold applies to each pair.
- Report-only: no fix suggestions, no palette scales, no tokens.

## Want more?

Want logos, color scales, Tailwind tokens and guidelines, with failing pairs fixed for you?
**Design System Starter** on Agensi turns a one-paragraph brief into 17 SVG logo files, a
WCAG-checked palette with 50-950 scales and nearest-passing fixes, CSS / Tailwind v3 + v4 /
DTCG tokens and a printable guidelines page:
https://www.agensi.io/creators/duncan-bentley

Free skill by Duncan Bentley (Bentley Art Design). MIT licence, see `LICENSE.txt`.
