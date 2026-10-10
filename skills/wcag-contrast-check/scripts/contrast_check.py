#!/usr/bin/env python3
"""WCAG 2.x contrast matrix for a set of hex colors.

Free "lite" skill by Duncan Bentley / Bentley Art Design. MIT licence.
Standard library only, Python 3.8+.

Examples
  python contrast_check.py "#1A1A2E" "#FFFFFF" "#E94560"
  python contrast_check.py ink=#1A1A2E paper=#FFFFFF brand=#E94560 muted=#777
  python contrast_check.py --json palette.json --format markdown
  python contrast_check.py ink=#1A1A2E paper=#FFF brand=#E94560 --fg ink brand --bg paper
  python contrast_check.py --pair "#777" "#FFF" --pair "#E94560" "#1A1A2E"

Exit codes: 0 = done, 1 = --strict and at least one pair fails, 2 = bad input.
"""
import argparse
import json
import math
import re
import sys

LEVELS = {  # level name -> (minimum ratio, human label)
    "AA": (4.5, "AA normal text"),
    "AA-large": (3.0, "AA large text / UI graphics"),
    "AAA": (7.0, "AAA normal text"),
    "AAA-large": (4.5, "AAA large text"),
}
HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
ALPHA_RE = re.compile(r"^#?([0-9a-fA-F]{4}|[0-9a-fA-F]{8})$")


class InputError(Exception):
    pass


# ---------------------------------------------------------------- colour maths

def normalise_hex(value):
    """'#abc' / 'AABBCC' -> '#AABBCC'. Raises InputError for anything else."""
    text = str(value).strip()
    match = HEX_RE.match(text)
    if not match:
        if ALPHA_RE.match(text):
            raise InputError("%r has an alpha channel; flatten it onto its real background first" % value)
        raise InputError("%r is not a hex color (use #RGB or #RRGGBB)" % value)
    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(ch * 2 for ch in digits)
    return "#" + digits.upper()


def _linear(channel_8bit):
    c = channel_8bit / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex6):
    r, g, b = (int(hex6[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def contrast_ratio(hex_a, hex_b):
    la, lb = relative_luminance(hex_a), relative_luminance(hex_b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def truncate2(ratio):
    """Two decimals, never rounded up (4.4999 -> 4.49), so a shown 4.50 always passes 4.5."""
    return math.floor(ratio * 100 + 1e-9) / 100


def grade(ratio):
    if ratio >= 7.0:
        return "AAA"
    if ratio >= 4.5:
        return "AA"
    if ratio >= 3.0:
        return "LARGE"
    return "FAIL"


# ---------------------------------------------------------------- input parsing

def parse_colour_token(token):
    """'#fff', 'paper=#fff' or 'paper:#fff' -> (name, hex)."""
    token = token.strip()
    for sep in ("=", ":"):
        if sep in token:
            name, value = token.split(sep, 1)
            name = name.strip()
            if not name:
                raise InputError("empty color name in %r" % token)
            return name, normalise_hex(value)
    hexed = normalise_hex(token)
    return hexed, hexed


def colours_from_json(data):
    """Accepts a list of hex strings, a {name: hex} object, or {"colors": ..., "fg": [...], "bg": [...], "pairs": [[fg, bg], ...]}."""
    extra = {}
    if isinstance(data, dict) and any(k in data for k in ("colors", "colours")):
        extra = {k: data.get(k) for k in ("fg", "bg", "pairs") if data.get(k)}
        data = data.get("colors", data.get("colours"))
    out = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                if "hex" not in item:
                    raise InputError("JSON color objects need a 'hex' field: %r" % item)
                hexed = normalise_hex(item["hex"])
                out.append((str(item.get("name") or hexed), hexed))
            else:
                out.append(parse_colour_token(str(item)))
    elif isinstance(data, dict):
        for name, value in data.items():
            if isinstance(value, dict):
                value = value.get("hex", value.get("value", ""))
            out.append((str(name), normalise_hex(value)))
    else:
        raise InputError("JSON must be a list of hex colors or an object of name: hex")
    return out, extra


class Palette:
    def __init__(self):
        self.order = []
        self.by_name = {}

    def add(self, name, hexed):
        if name in self.by_name and self.by_name[name] != hexed:
            raise InputError("color name %r is defined twice with different values" % name)
        if name not in self.by_name:
            self.by_name[name] = hexed
            self.order.append(name)
        return name

    def resolve(self, ref):
        """A colour reference is a name already defined, a hex value, or name=hex."""
        ref = str(ref).strip()
        if ref in self.by_name:
            return ref
        name, hexed = parse_colour_token(ref)
        if name in self.by_name and self.by_name[name] == hexed:
            return name
        # a bare hex that matches an existing named colour -> reuse that name
        if name == hexed:
            for existing in self.order:
                if self.by_name[existing] == hexed:
                    return existing
        return self.add(name, hexed)


# ---------------------------------------------------------------- evaluation

def evaluate(palette, fg_names, bg_names, explicit_pairs, symmetric):
    pairs = []
    seen = set()
    if explicit_pairs:
        combos = explicit_pairs
    else:
        combos = [(f, b) for f in fg_names for b in bg_names]
    for fg, bg in combos:
        if fg == bg and not explicit_pairs:
            continue
        key = tuple(sorted((fg, bg))) if symmetric else (fg, bg)
        if key in seen:
            continue
        seen.add(key)
        ratio = contrast_ratio(palette.by_name[fg], palette.by_name[bg])
        pairs.append({
            "fg": fg, "fg_hex": palette.by_name[fg],
            "bg": bg, "bg_hex": palette.by_name[bg],
            "ratio": ratio, "ratio_display": truncate2(ratio),
            "aa": ratio >= 4.5, "aa_large": ratio >= 3.0,
            "aaa": ratio >= 7.0, "aaa_large": ratio >= 4.5,
            "grade": grade(ratio),
        })
    return pairs


# ---------------------------------------------------------------- output

def label(palette, name, named):
    hexed = palette.by_name[name]
    return "%s %s" % (name, hexed) if named and name != hexed else hexed


def render_text(palette, rows, cols, pairs, level, matrix, named):
    threshold, level_label = LEVELS[level]
    lines = []
    shape = "rows = text color, columns = background" if matrix else "explicit pairs"
    lines.append("WCAG 2.x contrast check: %d colors, %d %s (%s)" % (
        len(palette.order), len(pairs), "pair" if len(pairs) == 1 else "pairs", shape))
    lines.append("")
    if matrix:
        lookup = {}
        for p in pairs:
            lookup[(p["fg"], p["bg"])] = p
            lookup[(p["bg"], p["fg"])] = p
        name_w = max([len(n[:14]) for n in rows] + [4]) if named else 0
        head_w = name_w + (1 if named else 0) + 7 + 2
        cell_w = 12
        if named:
            lines.append(" " * head_w + "".join(n[:cell_w - 2].ljust(cell_w) for n in cols).rstrip())
        lines.append(" " * head_w + "".join(palette.by_name[n].ljust(cell_w) for n in cols).rstrip())
        for r in rows:
            prefix = (r[:14].ljust(name_w) + " " if named else "") + palette.by_name[r] + "  "
            cells = []
            for c in cols:
                p = lookup.get((r, c))
                if r == c or p is None:
                    cells.append("-".ljust(cell_w))
                else:
                    cells.append(("%.2f %s" % (p["ratio_display"], p["grade"])).ljust(cell_w))
            lines.append(prefix + "".join(cells).rstrip())
        lines.append("")
        lines.append("Grades: AAA >= 7:1 | AA >= 4.5:1 | LARGE >= 3:1 (large text and UI graphics only) | FAIL < 3:1")
        lines.append("Large text = at least 24px (18pt) regular or 18.66px (14pt) bold. Ratios are truncated, never rounded up.")
        lines.append("")
    joiner = " / " if (matrix and rows == cols) else " on "
    pf = lambda ok: "pass" if ok else "fail"
    lines.append("Pairs, lowest contrast first (flag = %s, needs %.1f:1)" % (level_label, threshold))
    row_fmt = "%-5s %8s  %-5s %-6s %-5s %-7s %s%s%s"
    lines.append((row_fmt % ("flag", "ratio", "AA", "AA-lg", "AAA", "AAA-lg", "pair", "", "")).rstrip())
    for p in sorted(pairs, key=lambda p: p["ratio"]):
        flag = "FAIL" if p["ratio"] < threshold else "ok"
        lines.append(row_fmt % (
            flag, "%.2f:1" % p["ratio_display"], pf(p["aa"]), pf(p["aa_large"]), pf(p["aaa"]), pf(p["aaa_large"]),
            label(palette, p["fg"], named), joiner, label(palette, p["bg"], named)))
    failing = sum(1 for p in pairs if p["ratio"] < threshold)
    lines.append("")
    lines.append("Result: %d failing, %d passing for %s (%.1f:1)." % (
        failing, len(pairs) - failing, level_label, threshold))
    return "\n".join(lines) + "\n"


def render_markdown(palette, rows, cols, pairs, level, matrix, named):
    threshold, level_label = LEVELS[level]
    yes = lambda b: "pass" if b else "**fail**"
    out = ["### WCAG 2.x contrast check", ""]
    if matrix:
        lookup = {}
        for p in pairs:
            lookup[(p["fg"], p["bg"])] = p
            lookup[(p["bg"], p["fg"])] = p
        head = ["text \\ background"] + [label(palette, c, named) for c in cols]
        out.append("| " + " | ".join(head) + " |")
        out.append("|" + "---|" * len(head))
        for r in rows:
            cells = [label(palette, r, named)]
            for c in cols:
                p = lookup.get((r, c))
                cells.append("-" if (r == c or p is None) else "%.2f %s" % (p["ratio_display"], p["grade"]))
            out.append("| " + " | ".join(cells) + " |")
        out.append("")
        out.append("AAA >= 7:1, AA >= 4.5:1, LARGE >= 3:1 (large text and UI graphics only), FAIL < 3:1. Ratios truncated, never rounded up.")
        out.append("")
    out.append("| Pair | Ratio | AA | AA large | AAA | AAA large | Flag (%s) |" % level)
    out.append("|---|---|---|---|---|---|---|")
    joiner = " / " if (matrix and rows == cols) else " on "
    for p in sorted(pairs, key=lambda p: p["ratio"]):
        flag = "**FAIL**" if p["ratio"] < threshold else "ok"
        out.append("| %s%s%s | %.2f:1 | %s | %s | %s | %s | %s |" % (
            label(palette, p["fg"], named), joiner, label(palette, p["bg"], named), p["ratio_display"],
            yes(p["aa"]), yes(p["aa_large"]), yes(p["aaa"]), yes(p["aaa_large"]), flag))
    failing = sum(1 for p in pairs if p["ratio"] < threshold)
    out.append("")
    out.append("**Result: %d failing, %d passing for %s (%.1f:1).**" % (
        failing, len(pairs) - failing, level_label, threshold))
    return "\n".join(out) + "\n"


def render_json(palette, pairs, level):
    threshold, level_label = LEVELS[level]
    data = {
        "standard": "WCAG 2.x (SC 1.4.3, 1.4.6, 1.4.11)",
        "level": level, "threshold": threshold,
        "colors": [{"name": n, "hex": palette.by_name[n],
                    "luminance": round(relative_luminance(palette.by_name[n]), 6)} for n in palette.order],
        "pairs": [dict(p, ratio=round(p["ratio"], 4), flagged=p["ratio"] < threshold) for p in pairs],
        "summary": {"pairs": len(pairs), "failing": sum(1 for p in pairs if p["ratio"] < threshold)},
    }
    return json.dumps(data, indent=2) + "\n"


# ---------------------------------------------------------------- main

def build_parser():
    ap = argparse.ArgumentParser(
        description="Print a WCAG 2.x contrast matrix (AA/AAA, normal/large text) for hex colors and flag failing pairs.")
    ap.add_argument("colors", nargs="*", metavar="COLOR",
                    help="hex colors: '#1A1A2E', 'fff', or named 'ink=#1A1A2E'")
    ap.add_argument("--json", metavar="FILE", help="read colors from a JSON file ('-' = stdin)")
    ap.add_argument("--fg", nargs="+", metavar="COLOR", help="only these as text colors (names or hex)")
    ap.add_argument("--bg", nargs="+", metavar="COLOR", help="only these as backgrounds (names or hex)")
    ap.add_argument("--pair", nargs=2, action="append", metavar=("FG", "BG"),
                    help="check one text/background pair (repeatable); skips the matrix")
    ap.add_argument("--level", choices=list(LEVELS), default="AA",
                    help="which requirement counts as failing (default AA = 4.5:1 for normal text)")
    ap.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    ap.add_argument("--strict", action="store_true", help="exit with code 1 if any pair fails --level")
    return ap


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(errors="replace")
        except Exception:
            pass
    args = build_parser().parse_args(argv)
    palette = Palette()
    try:
        extra = {}
        if args.json:
            try:
                raw = sys.stdin.read() if args.json == "-" else open(args.json, encoding="utf-8").read()
                data = json.loads(raw)
            except (OSError, ValueError) as exc:
                raise InputError("could not read JSON from %s: %s" % (args.json, exc))
            entries, extra = colours_from_json(data)
            for name, hexed in entries:
                palette.add(name, hexed)
        for token in args.colors:
            palette.add(*parse_colour_token(token))

        fg_refs = args.fg or extra.get("fg")
        bg_refs = args.bg or extra.get("bg")
        pair_refs = args.pair or extra.get("pairs")

        explicit = None
        if pair_refs:
            explicit = []
            for pr in pair_refs:
                if not isinstance(pr, (list, tuple)) or len(pr) != 2:
                    raise InputError("each pair needs exactly two colors: %r" % (pr,))
                explicit.append((palette.resolve(pr[0]), palette.resolve(pr[1])))
        fg_names = [palette.resolve(r) for r in fg_refs] if fg_refs else None
        bg_names = [palette.resolve(r) for r in bg_refs] if bg_refs else None

        if explicit is None:
            fg_names = fg_names or list(palette.order)
            bg_names = bg_names or list(palette.order)
            if len(set(fg_names) | set(bg_names)) < 2:
                raise InputError("give at least two colors")
    except InputError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    named = any(n != palette.by_name[n] for n in palette.order)
    if explicit is not None:
        pairs = evaluate(palette, None, None, explicit, symmetric=False)
        rows = cols = None
        matrix = False
    else:
        symmetric = fg_names == bg_names
        pairs = evaluate(palette, fg_names, bg_names, None, symmetric=symmetric)
        rows, cols = fg_names, bg_names
        matrix = True
        if not pairs:
            print("error: no pairs to check (text and background lists are identical single colors)", file=sys.stderr)
            return 2

    if args.format == "json":
        sys.stdout.write(render_json(palette, pairs, args.level))
    elif args.format == "markdown":
        sys.stdout.write(render_markdown(palette, rows, cols, pairs, args.level, matrix, named))
    else:
        sys.stdout.write(render_text(palette, rows, cols, pairs, args.level, matrix, named))

    threshold = LEVELS[args.level][0]
    if args.strict and any(p["ratio"] < threshold for p in pairs):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
