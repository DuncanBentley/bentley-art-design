#!/usr/bin/env python3
"""Make one printable monthly habit tracker page as a vector PDF (US Letter).

Free "lite" skill by Duncan Bentley / Bentley Art Design. MIT licence.
Standard library only, Python 3.8+. No fonts to install: it uses the standard PDF fonts
(Helvetica and Times) that every PDF viewer and printer already has.

Examples
  python habit_tracker.py --month 11 --year 2026 --title "November Reset" \
      --habits "Drink 2 L of water" "Read 20 pages" "10-minute walk" "No phone after 10 pm"
  python habit_tracker.py --json brief.json --out trackers/habits-2026-11.pdf

brief.json: {"title": "November Reset", "month": 11, "year": 2026, "habits": ["Read 20 pages", "Stretch"]}
"""
import argparse
import calendar
import datetime
import json
import os
import re
import sys
import zlib

PAGE_W, PAGE_H = 612.0, 792.0          # US Letter, portrait, in points (1 pt = 1/72 in)
MARGIN = 40.0                           # 0.56 in: well inside the 0.25 in printer-safe zone
MAX_HABITS = 20
MIN_ROWS = 12                           # unused rows stay blank so buyers can write their own

STYLE = {                               # one clean style: slate ink, teal-slate accent
    "ink": "#2B2F36", "accent": "#4F6D7A", "muted": "#5F6673",
    "rule": "#C9D1D6", "hair": "#DDE3E7", "tint": "#EEF2F4", "circle": "#A9B4BC",
}

# ------------------------------------------------------------------ font metrics
# Advance widths (1/1000 em) for ASCII 32..126 of the standard Type 1 fonts (Adobe AFM data).
_HELV = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
         556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
         1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
         667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
         333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
         556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584]
_HELV_BOLD = [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278,
              556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611,
              975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
              667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556,
              333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611,
              611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584]
_TIMES = [250, 333, 408, 500, 500, 833, 778, 180, 333, 333, 500, 564, 250, 333, 250, 278,
          500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 278, 278, 564, 564, 564, 444,
          921, 722, 667, 667, 722, 611, 556, 722, 722, 333, 389, 722, 611, 889, 722, 722,
          556, 722, 667, 556, 611, 722, 722, 944, 722, 722, 611, 333, 278, 333, 469, 500,
          333, 444, 500, 444, 500, 444, 333, 500, 500, 278, 278, 500, 278, 778, 500, 500,
          500, 500, 333, 389, 278, 500, 500, 722, 500, 500, 444, 480, 200, 480, 541]
FONTS = {  # resource name -> (BaseFont, widths, fallback width for non-ASCII)
    "F1": ("Helvetica", _HELV, 556),
    "F2": ("Helvetica-Bold", _HELV_BOLD, 611),
    "F3": ("Times-Roman", _TIMES, 500),
    "F4": ("Helvetica-Oblique", _HELV, 556),
}
ELLIPSIS = "…"  # WinAnsi 0x85


def clean_text(text):
    """Collapse whitespace and drop characters the standard PDF fonts cannot show (emoji, CJK...).
    Returns (clean_text, dropped_characters)."""
    kept, dropped = [], []
    for ch in str(text):
        try:
            ch.encode("cp1252")
            kept.append(ch)
        except UnicodeEncodeError:
            dropped.append(ch)
    return re.sub(r"\s+", " ", "".join(kept)).strip(), dropped


def to_winansi(text):
    """Text -> bytes in the PDF WinAnsi (cp1252) encoding; unsupported characters become '?'."""
    return str(text).encode("cp1252", errors="replace")


def text_width(text, font, size, spacing=0.0):
    widths, fallback = FONTS[font][1], FONTS[font][2]
    total = 0
    data = to_winansi(text)
    for byte in data:
        if byte == 0x85:
            total += 1000
        elif 32 <= byte <= 126:
            total += widths[byte - 32]
        else:
            total += fallback
    return total * size / 1000.0 + spacing * max(len(data) - 1, 0)


def fit_text(text, font, size, max_width, min_size):
    """Shrink to min_size, then truncate with an ellipsis. Returns (text, size)."""
    while size > min_size and text_width(text, font, size) > max_width:
        size = round(size - 0.25, 2)
    if text_width(text, font, size) <= max_width:
        return text, size
    while text and text_width(text.rstrip() + ELLIPSIS, font, size) > max_width:
        text = text[:-1]
    return text.rstrip() + ELLIPSIS, size


def wrap_two_lines(text, font, size, max_width):
    """Split into at most two lines that fit max_width; the second is truncated if needed."""
    words = text.split(" ")
    first = ""
    while words:
        candidate = (first + " " + words[0]).strip()
        if text_width(candidate, font, size) > max_width:
            break
        first = candidate
        words.pop(0)
    if not first:                      # one very long word: hard truncate on one line
        return [fit_text(text, font, size, max_width, size)[0]]
    rest = " ".join(words)
    if not rest:
        return [first]
    return [first, fit_text(rest, font, size, max_width, size)[0]]


# ------------------------------------------------------------------ tiny PDF canvas

def _num(value):
    out = ("%.3f" % value).rstrip("0").rstrip(".")
    return "0" if out in ("-0", "") else out


def _rgb(hex_colour):
    h = hex_colour.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _pdf_string(data):
    out = bytearray(b"(")
    for byte in data:
        if byte in (0x28, 0x29, 0x5C):          # ( ) \
            out += b"\\" + bytes([byte])
        elif 32 <= byte <= 126:
            out.append(byte)
        else:
            out += b"\\%03o" % byte
    out += b")"
    return bytes(out)


class Canvas:
    """Collects drawing operators for one page. Origin bottom-left, units in points."""

    def __init__(self):
        self.ops = []

    def _op(self, text):
        self.ops.append(text.encode("ascii"))

    def fill_colour(self, hex_colour):
        self._op("%s %s %s rg" % tuple(_num(c) for c in _rgb(hex_colour)))

    def stroke_colour(self, hex_colour):
        self._op("%s %s %s RG" % tuple(_num(c) for c in _rgb(hex_colour)))

    def line_width(self, w):
        self._op("%s w" % _num(w))

    def rect(self, x, y, w, h, fill=None, stroke=None, width=0.5):
        self._op("q")
        if fill:
            self.fill_colour(fill)
        if stroke:
            self.stroke_colour(stroke)
            self.line_width(width)
        self._op("%s %s %s %s re %s" % (_num(x), _num(y), _num(w), _num(h),
                                        "B" if fill and stroke else ("f" if fill else "S")))
        self._op("Q")

    def round_rect(self, x, y, w, h, r, fill=None, stroke=None, width=0.5):
        k = 0.5523 * r
        path = [
            "%s %s m" % (_num(x + r), _num(y)),
            "%s %s l" % (_num(x + w - r), _num(y)),
            "%s %s %s %s %s %s c" % (_num(x + w - r + k), _num(y), _num(x + w), _num(y + r - k), _num(x + w), _num(y + r)),
            "%s %s l" % (_num(x + w), _num(y + h - r)),
            "%s %s %s %s %s %s c" % (_num(x + w), _num(y + h - r + k), _num(x + w - r + k), _num(y + h), _num(x + w - r), _num(y + h)),
            "%s %s l" % (_num(x + r), _num(y + h)),
            "%s %s %s %s %s %s c" % (_num(x + r - k), _num(y + h), _num(x), _num(y + h - r + k), _num(x), _num(y + h - r)),
            "%s %s l" % (_num(x), _num(y + r)),
            "%s %s %s %s %s %s c h" % (_num(x), _num(y + r - k), _num(x + r - k), _num(y), _num(x + r), _num(y)),
        ]
        self._paint(path, fill, stroke, width)

    def circle(self, cx, cy, r, fill=None, stroke=None, width=0.5):
        k = 0.5523 * r
        path = [
            "%s %s m" % (_num(cx + r), _num(cy)),
            "%s %s %s %s %s %s c" % (_num(cx + r), _num(cy + k), _num(cx + k), _num(cy + r), _num(cx), _num(cy + r)),
            "%s %s %s %s %s %s c" % (_num(cx - k), _num(cy + r), _num(cx - r), _num(cy + k), _num(cx - r), _num(cy)),
            "%s %s %s %s %s %s c" % (_num(cx - r), _num(cy - k), _num(cx - k), _num(cy - r), _num(cx), _num(cy - r)),
            "%s %s %s %s %s %s c h" % (_num(cx + k), _num(cy - r), _num(cx + r), _num(cy - k), _num(cx + r), _num(cy)),
        ]
        self._paint(path, fill, stroke, width)

    def _paint(self, path, fill, stroke, width):
        self._op("q")
        if fill:
            self.fill_colour(fill)
        if stroke:
            self.stroke_colour(stroke)
            self.line_width(width)
        for part in path:
            self._op(part)
        self._op("B" if fill and stroke else ("f" if fill else "S"))
        self._op("Q")

    def line(self, x1, y1, x2, y2, colour, width=0.5, dash=None):
        self._op("q")
        self.stroke_colour(colour)
        self.line_width(width)
        if dash:
            self._op("[%s] 0 d" % " ".join(_num(d) for d in dash))
        self._op("%s %s m %s %s l S" % (_num(x1), _num(y1), _num(x2), _num(y2)))
        self._op("Q")

    def text(self, x, y, text, font="F1", size=10, colour="#000000", align="left", spacing=0.0):
        width = text_width(text, font, size, spacing)
        if align == "right":
            x -= width
        elif align == "center":
            x -= width / 2.0
        self._op("q BT")
        self.fill_colour(colour)
        self._op("/%s %s Tf" % (font, _num(size)))
        if spacing:
            self._op("%s Tc" % _num(spacing))
        self._op("%s %s Td" % (_num(x), _num(y)))
        self.ops.append(_pdf_string(to_winansi(text)) + b" Tj")
        self._op("ET Q")
        return width


def write_pdf(path, canvas, title, producer):
    content = zlib.compress(b"\n".join(canvas.ops), 9)
    font_ids = {}
    objects = []  # index i -> object number i + 1

    def add(body):
        objects.append(body)
        return len(objects)

    catalog = add(None)
    pages = add(None)
    page = add(None)
    stream = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(content) + content + b"\nendstream")
    for res, (base, _, _) in FONTS.items():
        font_ids[res] = add(("<< /Type /Font /Subtype /Type1 /BaseFont /%s /Encoding /WinAnsiEncoding >>" % base).encode("ascii"))
    now = datetime.datetime.now().strftime("D:%Y%m%d%H%M%S")
    info = add(b"<< /Title " + _pdf_string(to_winansi(title)) + b" /Producer " + _pdf_string(to_winansi(producer))
               + b" /Creator " + _pdf_string(b"habit-tracker-pdf") + (" /CreationDate (%s) >>" % now).encode("ascii"))
    fonts = " ".join("/%s %d 0 R" % (res, oid) for res, oid in font_ids.items())
    objects[catalog - 1] = ("<< /Type /Catalog /Pages %d 0 R /ViewerPreferences << /PrintScaling /None >> >>" % pages).encode("ascii")
    objects[pages - 1] = ("<< /Type /Pages /Kids [%d 0 R] /Count 1 >>" % page).encode("ascii")
    objects[page - 1] = ("<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %s %s] /Contents %d 0 R /Resources << /Font << %s >> >> >>"
                         % (pages, _num(PAGE_W), _num(PAGE_H), stream, fonts)).encode("ascii")

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    file_id = zlib.crc32(bytes(out)) & 0xFFFFFFFF
    out += (b"trailer\n<< /Size %d /Root %d 0 R /Info %d 0 R /ID [<%08X> <%08X>] >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objects) + 1, catalog, info, file_id, file_id, xref))
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(bytes(out))
    return len(out)


# ------------------------------------------------------------------ the page

def draw_tracker(title, year, month, habits):
    s = STYLE
    c = Canvas()
    days = calendar.monthrange(year, month)[1]
    month_name = calendar.month_name[month]
    left, right = MARGIN, PAGE_W - MARGIN

    # header
    c.text(left, 744, "MONTHLY HABIT TRACKER", "F2", 7.5, s["accent"], spacing=1.4)
    c.text(right, 744, "%d DAYS" % days, "F2", 7.5, s["muted"], align="right", spacing=1.4)
    month_label = "%s %d" % (month_name.upper(), year)
    month_w = c.text(right, 712, month_label, "F2", 11, s["accent"], align="right", spacing=1.2)
    shown, size = fit_text(title, "F3", 30, right - left - month_w - 24, 16)
    c.text(left, 710, shown, "F3", size, s["ink"])
    c.line(left, 694, right, 694, s["accent"], 1.0)

    # grid geometry
    name_w, total_w, gap = 122.0, 30.0, 4.0
    grid_x = left + name_w
    grid_r = right - total_w - gap
    cell_w = (grid_r - grid_x) / days
    rows = max(len(habits), MIN_ROWS)
    grid_top, grid_bottom = 652.0, 300.0
    row_h = (grid_top - grid_bottom) / rows
    radius = min(cell_w * 0.33, row_h * 0.30, 5.5)

    # weekend bands (Saturday and Sunday), behind everything else
    for d in range(1, days + 1):
        if calendar.weekday(year, month, d) >= 5:
            x = grid_x + (d - 1) * cell_w
            c.rect(x + 0.6, grid_bottom, cell_w - 1.2, 684 - grid_bottom, fill=s["tint"])

    # column headings
    c.text(left, 662, "HABIT", "F2", 6.5, s["muted"], spacing=1.2)
    c.text(right, 662, "TOTAL", "F2", 6.5, s["muted"], align="right", spacing=0.6)
    for d in range(1, days + 1):
        cx = grid_x + (d - 0.5) * cell_w
        letter = "MTWTFSS"[calendar.weekday(year, month, d)]
        c.text(cx, 674, letter, "F1", 6.5, s["muted"], align="center")
        c.text(cx, 662, str(d), "F2", 6.5 if d >= 10 else 7, s["ink"], align="center")

    # rows
    c.line(left, grid_top, right, grid_top, s["rule"], 0.8)
    for i in range(rows):
        top = grid_top - i * row_h
        bottom = top - row_h
        mid = (top + bottom) / 2.0
        c.line(left, bottom, right, bottom, s["hair"] if i < rows - 1 else s["rule"], 0.5 if i < rows - 1 else 0.8)
        c.text(left, mid - 2.4, "%02d" % (i + 1), "F2", 6.5, s["accent"])
        if i < len(habits):
            label_w = name_w - 22
            if text_width(habits[i], "F1", 9) <= label_w:
                c.text(left + 16, mid - 3.2, habits[i], "F1", 9, s["ink"])
            elif row_h >= 21:          # tall rows: wrap onto two lines
                lines = wrap_two_lines(habits[i], "F1", 8, label_w)
                if len(lines) == 1:
                    c.text(left + 16, mid - 2.8, lines[0], "F1", 8, s["ink"])
                else:
                    c.text(left + 16, mid + 1.6, lines[0], "F1", 8, s["ink"])
                    c.text(left + 16, mid - 7.4, lines[1], "F1", 8, s["ink"])
            else:                      # short rows: shrink a little, then truncate
                shown, size = fit_text(habits[i], "F1", 9, label_w, 7.5)
                c.text(left + 16, mid - size * 0.35, shown, "F1", size, s["ink"])
        for d in range(days):
            c.circle(grid_x + (d + 0.5) * cell_w, mid, radius, stroke=s["circle"], width=0.6)
        c.line(right - total_w + 2, mid - 4, right - 13, mid - 4, s["rule"], 0.5)
        c.text(right, mid - 3.2, "/%d" % days, "F1", 6, s["muted"], align="right")

    # notes area
    box_top, box_bottom = 282.0, 62.0
    box_w = (right - left - 16) / 2.0
    for idx, heading in enumerate(("MONTHLY FOCUS", "NOTES & WINS")):
        x = left + idx * (box_w + 16)
        c.round_rect(x, box_bottom, box_w, box_top - box_bottom, 6, stroke=s["rule"], width=0.7)
        c.text(x + 12, box_top - 18, heading, "F2", 7, s["accent"], spacing=1.2)
        y = box_top - 44
        while y > box_bottom + 12:
            c.line(x + 12, y, x + box_w - 12, y, s["hair"], 0.5)
            y -= 22

    c.text(PAGE_W / 2.0, 44, "Fill a circle each day you keep the habit, then add up your circles in TOTAL at the end of the month.",
           "F4", 7.5, s["muted"], align="center")
    return c


# ------------------------------------------------------------------ CLI

def parse_month(value):
    text = str(value).strip().lower()
    if text.isdigit() and 1 <= int(text) <= 12:
        return int(text)
    for i in range(1, 13):
        if text in (calendar.month_name[i].lower(), calendar.month_abbr[i].lower()):
            return i
    raise ValueError("month must be 1-12 or an English month name, got %r" % value)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass
    today = datetime.date.today()
    ap = argparse.ArgumentParser(description="Make one printable monthly habit tracker page (US Letter vector PDF).")
    ap.add_argument("--title", help='page title, e.g. "November Reset" (default "My Habits")')
    ap.add_argument("--month", help="1-12 or a month name (default: this month)")
    ap.add_argument("--year", type=int, help="e.g. 2026 (default: this year)")
    ap.add_argument("--habits", nargs="+", metavar="HABIT", help="habit names, one argument each (max %d)" % MAX_HABITS)
    ap.add_argument("--habits-file", help="text file with one habit per line")
    ap.add_argument("--json", help='brief file: {"title", "month", "year", "habits": [...]}')
    ap.add_argument("--out", help="output PDF path (default habit-tracker-YYYY-MM.pdf)")
    args = ap.parse_args(argv)

    brief = {}
    try:
        if args.json:
            with open(args.json, encoding="utf-8") as fh:
                brief = json.load(fh)
            if not isinstance(brief, dict):
                raise ValueError("the JSON brief must be an object")
        title = args.title or brief.get("title") or "My Habits"
        month = parse_month(args.month if args.month is not None else brief.get("month", today.month))
        year = int(args.year if args.year is not None else brief.get("year", today.year))
        if not 1900 <= year <= 2999:
            raise ValueError("year must be between 1900 and 2999")
        habits = list(brief.get("habits") or [])
        if args.habits_file:
            with open(args.habits_file, encoding="utf-8") as fh:
                habits += [line for line in fh.read().splitlines()]
        if args.habits:
            habits += args.habits
        dropped = []
        title, lost = clean_text(title)
        dropped += lost
        cleaned = []
        for h in habits:
            h, lost = clean_text(h)
            dropped += lost
            if h:
                cleaned.append(h)
        habits = cleaned
        title = title or "My Habits"
        if len(habits) > MAX_HABITS:
            raise ValueError("%d habits given; one page fits at most %d" % (len(habits), MAX_HABITS))
    except (OSError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    out = args.out or "habit-tracker-%d-%02d.pdf" % (year, month)
    canvas = draw_tracker(title, year, month, habits)
    size = write_pdf(out, canvas, "%s - %s %d" % (title, calendar.month_name[month], year),
                     "habit-tracker-pdf (free skill by Bentley Art Design)")
    print("OK %s  (US Letter, 1 page, %s %d, %d days, %d habits + %d blank rows, %.1f KB)" % (
        out, calendar.month_name[month], year, calendar.monthrange(year, month)[1], len(habits),
        max(MIN_ROWS - len(habits), 0), size / 1024.0))
    if dropped:
        print("note: removed %d character(s) the standard PDF fonts cannot print (emoji, symbols or non-Latin script): %s"
              % (len(dropped), " ".join("U+%04X" % ord(ch) for ch in dropped)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
