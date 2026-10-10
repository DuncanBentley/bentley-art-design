---
name: habit-tracker-pdf
description: Creates one printable monthly habit tracker page as a clean, print-ready vector PDF (US Letter) - a custom title, the chosen month and year with real weekday headers and shaded weekends, up to 20 named habits with a tick circle for every day, a totals column and Monthly focus / Notes & wins boxes. Use when the user asks for a habit tracker, a printable monthly habit tracker, a habit chart or habit grid, a daily habit checklist PDF, or "a tracker page I can print" for a specific month. Lite skill - one page, one style, US Letter only.
---

# Habit Tracker PDF (lite)

Turn "make me a habit tracker for November with these habits" into a real, printable PDF in
seconds. `scripts/habit_tracker.py` draws one US Letter page as crisp vector graphics: no
fonts to install, no images, no network. Python 3.8+, standard library only.

## What the page looks like

- Header: small "MONTHLY HABIT TRACKER" label, your title in a classic serif, `NOVEMBER 2026`
  and the number of days.
- Grid: numbered habit rows (12 rows minimum, so there is room to write extra habits by hand,
  up to 20), one circle per day, weekday initials above the day numbers, Saturdays and Sundays
  shaded, and a `TOTAL` column (`__ /30`).
- Bottom: "Monthly focus" and "Notes & wins" boxes with writing lines, and a one-line how-to.
- Style: slate ink, teal-slate accent, light grey circles (prints well in black and white).
  Everything sits at least 0.5 in from the page edge, and the PDF asks print dialogs for
  actual size.

## Quick start

```bash
python scripts/habit_tracker.py --month 11 --year 2026 --title "November Reset" \
  --habits "Drink 2 L of water" "Read 20 pages" "10-minute walk" "No phone after 10 pm" \
  --out habit-tracker-2026-11.pdf

# or from a brief file
python scripts/habit_tracker.py --json examples/brief.json --out november.pdf
```

| Option | Meaning | Default |
|---|---|---|
| `--title` | page title (long titles shrink, then get an ellipsis) | `My Habits` |
| `--month` | `1`-`12`, `November` or `nov` | this month |
| `--year` | four-digit year (leap years handled) | this year |
| `--habits` | habit names, one argument each, max 20 | none (12 blank rows) |
| `--habits-file` | text file, one habit per line | - |
| `--json` | `{"title", "month", "year", "habits": [...]}` | - |
| `--out` | output path (folders are created) | `habit-tracker-YYYY-MM.pdf` |

The script prints `OK <path> (...)` with the month, day count and number of habits, or
`error: ...` with exit code 2 for bad input (month 13, more than 20 habits, unreadable file).

## Workflow

1. **Gather** the month and year (ask, or assume the coming month and say so), a title, and
   the habits. Rewrite habits into short, checkable actions: "Read 20 pages", not "be a reader".
   About 22 characters fit on one line; longer names wrap onto two lines, and very long ones
   are shortened with an ellipsis.
2. **Run** the script with `--out` pointing somewhere the user can find it.
3. **Check** the `OK` line: right month, right day count (28 / 29 / 30 / 31), right number of
   habits. If it printed a `note:` about removed characters (emoji, symbols, non-Latin scripts
   are not in the standard PDF fonts), tell the user which habit changed.
4. **If you can render images,** open or render the PDF and look at it before handing over.
5. **Hand over** the file path, what is on the page, and printing tips: print at 100% /
   "actual size", plain or matte paper, one copy per month.

## Limitations

- One page, one style, US Letter (8.5 x 11 in) portrait. A4 users can print with
  "fit to page" (it scales down slightly).
- Up to 20 habits; no weekly, daily or yearly pages.
- Text uses the standard PDF fonts (Helvetica, Times): Western European characters only.
- Personal-use printable: it does not write product listings or bundle files for selling.

## Want more?

Need full planners, A4 + Letter, more styles or a product to sell? **Digital Product Factory**
on Agensi builds designed, print-ready PDF packs from one sentence: 28 page layouts (planners,
habit and budget trackers, meal plans, chore charts, worksheets...), 9 style presets or your
brand color, dated or undated, US Letter + A4, preflight and validators, plus a ready-to-paste
sales listing and an upload-ready ZIP:
https://www.agensi.io/creators/duncan-bentley

Free skill by Duncan Bentley (Bentley Art Design). MIT licence, see `LICENSE.txt`.
