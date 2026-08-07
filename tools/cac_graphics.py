"""
cac_graphics.py — CAC CISO Toolkit SVG graphics library.

16 marks for executive and operational reporting.
Stdlib only: html, math, sys. Python 3.9+.

Usage:
  python3 cac_graphics.py self-test
  python3 cac_graphics.py gallery /path/to/out.html
"""
import html as _html
import math as _math
import sys as _sys

# ── Colour contract ────────────────────────────────────────────────────────────
# RAG — four variants per band.
#   fill  — saturated; use for bars, dots, line strokes where the mark IS status.
#   text  — dark, accessible; use on tint backgrounds (chips) and as value labels.
#   tint  — pale; chip/badge backgrounds. Never on data.
#   mid   — desaturated zone band fill; replaces opacity compositing on bullet zones.
_RAG = {
    "good":     {"fill": "#30915B", "text": "#25764A", "tint": "#E3EDE4", "mid": "#86BE9C"},
    "medium":   {"fill": "#e8c547", "text": "#7A6410", "tint": "#FBF3D6", "mid": "#F0DC92"},
    "high":     {"fill": "#e08e0b", "text": "#8F5B06", "tint": "#F7EBD9", "mid": "#EEC17E"},
    "critical": {"fill": "#c0392b", "text": "#8B2119", "tint": "#F6E0DC", "mid": "#DFA096"},
}
_MEASURE       = "#2E6FA7"   # data without thresholds
_MEASURE_TRACK = "#D8E4F1"   # track / background of measure bars
_PATINA        = "#2FA98C"   # decorative chrome only — never a data mark, never read
_INK           = "#14171C"   # brand ink (dark chrome / body text)
_MUTED         = "#4A4F58"   # brand muted (secondary text)
_BG            = "#F6F4EE"   # brand workbench

# The brand patina sits at 2.93:1 on white — below the 3:1 floor for a graphical
# object and well below the 4.5:1 a 9px label needs. That is acceptable for a
# purely decorative rule and unacceptable the moment a reader has to *read* the
# thing, and the TODAY marker on a timeline is squarely the second case: it is
# the reference point every bar is judged against. So the hue splits the same way
# RAG does, into a decorative fill and an accessible text variant, and every
# informative use takes the accessible one.
_PATINA_TEXT   = "#25846D"   # 4.57:1 on white — patina wherever it carries meaning

# Font stacks — brand tokens with system fallbacks
_FONT_DISPLAY = "'Space Grotesk',system-ui,sans-serif"  # numbers, kickers
_FONT_BODY    = "'Manrope',system-ui,sans-serif"         # labels, axis text

# Gantt phase-status chip vocabulary (spec: executive-indicator-system §2)
_GANTT_CHIP = {
    "good":     "ON TRACK",
    "medium":   "WATCH",
    "high":     "AT RISK",
    "critical": "LATE",
}


def _sev_colour(sev, variant="fill"):
    """RAG colour for sev. variant = fill | text | tint | mid. MEASURE when absent."""
    if sev and sev in _RAG:
        return _RAG[sev][variant]
    return _MEASURE


def chip(sev):
    """The (ground, text) pair for a status chip in band `sev`.

    Every skill draws these chips and every skill used to spell the pair out itself. The
    two halves had half converged: the grounds matched this table exactly while the text
    colours did not, so a chip and a mark that meant the same thing drew it in two
    different reds on the same page. Both sets cleared AA, which is exactly why no check
    caught it — the defect was consistency, not contrast.
    """
    return (_RAG[sev]["tint"], _RAG[sev]["text"])


# Sequential MEASURE ramp — composition WITHOUT risk semantics.
# A stack over incident source, asset class or control family is not a stack over
# severity. Painting those categories red/amber/green asserts a danger the data
# never claimed, so categorical composition stays inside the MEASURE bucket and
# separates by lightness instead of by hue.
_CAC_MEASURE_RAMP = ["#1B4E7A", "#2E6FA7", "#5B9BD0", "#94BEE2", "#C4DAEE", "#E4EEF7"]
_MEASURE_RAMP = list(_CAC_MEASURE_RAMP)
_UNASSESSED   = "#D6D2C7"   # a band-less segment in an otherwise-RAG stack

_SURFACE = "#FFFFFF"   # every mark carries its own surface


def _svg_size(svg):
    """(width, height) declared on an SVG string, or (0, 0)."""
    if not svg:
        return (0, 0)
    head = svg[:400]
    out = []
    for attr in ("width", "height"):
        tag = f'{attr}="'
        i = head.find(tag)
        if i < 0:
            return (0, 0)
        raw = head[i + len(tag):head.find('"', i + len(tag))]
        try:
            out.append(float(raw))
        except ValueError:
            return (0, 0)
    return (out[0], out[1])


def _relative_luminance(hex_colour):
    """WCAG relative luminance for a #rrggbb string."""
    c = hex_colour.lstrip("#")
    out = []
    for i in (0, 2, 4):
        v = int(c[i:i + 2], 16) / 255.0
        out.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def _on(bg):
    """Ink or white on a given ground, whichever has more contrast."""
    lum = _relative_luminance(bg)
    white_ratio = 1.05 / (lum + 0.05)
    ink_ratio = (lum + 0.05) / (_relative_luminance(_INK) + 0.05)
    return _SURFACE if white_ratio >= ink_ratio else _INK


def _surf():
    """
    Opening surface rect. Marks get embedded into board packs, decks, PDFs and
    mail clients whose background we do not control; a transparent SVG with
    hard-coded ink text becomes unreadable the moment it lands on a dark ground.
    The palette is validated light-only, so the surface is pinned light too.
    """
    return f'<rect width="100%" height="100%" fill="{_SURFACE}"/>'


# The ground for a cell with nothing behind it. A flat tint cannot do this job:
# measured against the lightest step of the intensity ramp, the grey it replaces
# sat at 1.19:1, so "not rated at all" and "rated, and the lowest on the page"
# were the same cell to a reader. That is the confusion the brand doc names
# first -- nothing-rated must never read as rated-and-weak, and must never read
# as fully-covered either.
#
# A hatch separates on texture instead of lightness, so it holds at any position
# on any ramp, in greyscale, and in forced-colours mode. nist-csf's brand.md
# already specified exactly this treatment for its untargeted and unrated
# states; the library simply had no way to draw it.
_HATCH_ID = "cacHatch"
_HATCH_BG = "#F1EFE9"
_HATCH_FG = "#C8C3B6"


def _hatch_def():
    """The <defs> block for the empty-cell hatch. Emitted only when one is used."""
    return (
        f'<defs><pattern id="{_HATCH_ID}" width="6" height="6" '
        f'patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
        f'<rect width="6" height="6" fill="{_HATCH_BG}"/>'
        f'<line x1="0" y1="0" x2="0" y2="6" stroke="{_HATCH_FG}" '
        f'stroke-width="2"/></pattern></defs>'
    )


# ── Client brand override ─────────────────────────────────────────────────────
# A client may re-colour the *chrome* and the *measure* bucket. A client may not
# re-colour RAG.
#
# That asymmetry is the whole point. The RAG hexes are not decoration: green↔red
# is ΔE 6.2 under deuteranopia and medium↔high is ΔE 13.3, and the four `text`
# variants were each darkened until they cleared 4.5:1 on the workbench ground.
# A client palette substituted into those four slots would silently discard every
# one of those measurements while still producing a plausible-looking chart — the
# worst possible failure, because nothing about the output would look wrong.
# Status therefore renders in toolkit colours in every deck the toolkit produces,
# and the client's identity lives in the chrome around it.
#
# What *is* overridable still gets validated rather than trusted, against the
# same floors the defaults were built to.

DEFAULT_BRAND = {
    "ink":          _INK,
    "muted":        _MUTED,
    "measure":      _MEASURE,
    "measureTrack": _MEASURE_TRACK,
    "patina":       _PATINA,
    "patinaText":   _PATINA_TEXT,
    "bg":           _BG,
    "wordmark":     "A Cyber Aware Creation",
    "mark":         "Cyber Aware Creations",
    "whiteLabel":   False,
}

_COLOUR_KEYS = ("ink", "muted", "measure", "measureTrack", "patina",
                "patinaText", "bg")
_TEXT_KEYS   = ("wordmark", "mark")
_FLAG_KEYS   = ("whiteLabel",)

# The NIST disclaimer is not branding, and white-labelling cannot remove it.
_DISCLAIMER = "Not affiliated with NIST"
# The bodies named by default. A list rather than the baked string so a page reproducing
# more than one framework's material can name all of them through the same function, instead
# of hand-rolling a second disclaimer that then drifts from this one.
_UNAFFILIATED = ("NIST",)


def _unaffiliated(names) -> str:
    names = [str(n).strip() for n in names if str(n).strip()]
    if not names:
        names = list(_UNAFFILIATED)
    if len(names) == 1:
        joined = names[0]
    elif len(names) == 2:
        joined = "%s or %s" % (names[0], names[1])
    else:
        joined = "%s, or %s" % (", ".join(names[:-1]), names[-1])
    return "Not affiliated with " + joined


def footer(*extra, **kwargs):
    """
    The attribution line every deliverable carries.

    White-labelling drops the maker's name and keeps the disclaimer. Those two
    clauses look alike on the page and are not alike at all: one says who built
    the thing, which a client is entitled to replace, and the other says the
    thing is not a NIST product, which is a statement about the world that stays
    true no matter whose logo is on the cover. A white-label switch that removed
    both would let a client ship an unaffiliated document that reads as endorsed.

    `extra` clauses follow the disclaimer and are **never** dropped by
    white-labelling, on exactly that reasoning. "Not legal advice" is a statement
    about what the document is, not about who made it, and a client rebranding a
    deliverable does not thereby acquire the standing to remove it.

    `unaffiliated` replaces the list of bodies named in the disclaimer, for pages
    that reproduce more than one framework's material — a CSF-to-ISO-to-CIS
    crosswalk has three organisations to be unaffiliated with, and naming only
    the first would leave the other two implied.

    Callers should call this at render time rather than binding it to a module
    constant at import. The brand is process-global and can be rebound after the
    module loads, and a constant captured at import would keep printing the maker
    name on a white-labelled page — the exact failure this function exists to
    prevent, reintroduced one layer up.
    """
    unaffiliated = kwargs.pop("unaffiliated", None)
    if kwargs:
        raise TypeError("footer() got unexpected keyword arguments: %s"
                        % ", ".join(sorted(kwargs)))
    parts = [_unaffiliated(unaffiliated or _UNAFFILIATED)]
    parts.extend(str(x).strip() for x in extra if str(x).strip())
    if not _brand.get("whiteLabel"):
        parts.insert(0, _brand["wordmark"])
    return " · ".join(parts)

# `surface` is deliberately absent. Every contrast number in this file was
# measured against white, and _surf() pins the surface light for exactly that
# reason. Letting a client darken it would invalidate the whole palette at once.

_brand = dict(DEFAULT_BRAND)


class BrandError(ValueError):
    """A supplied brand block was rejected. Carries every problem, not the first."""


def contrast(a, b):
    """WCAG contrast ratio between two #rrggbb colours."""
    la, lb = _relative_luminance(a), _relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _is_hex(v):
    if not isinstance(v, str) or len(v) != 7 or not v.startswith("#"):
        return False
    try:
        int(v[1:], 16)
    except ValueError:
        return False
    return True


def _mix(colour, toward, f):
    """Blend `colour` toward `toward` by fraction f."""
    c = colour.lstrip("#")
    t = toward.lstrip("#")
    out = "#"
    for i in (0, 2, 4):
        a = int(c[i:i + 2], 16)
        b = int(t[i:i + 2], 16)
        out += "%02X" % round(a + (b - a) * f)
    return out


def _derive_ramp(measure):
    """
    Six sequential steps from a client measure hue.

    The shipped CAC ramp is hand-tuned and is NOT reproduced by this function —
    it stays a literal, so overriding nothing changes nothing. This is the
    fallback for a client hue nobody has hand-tuned: one step darker, the hue
    itself, then four mixes toward white. Monotone in lightness by construction,
    which is the property a sequential ramp has to have.
    """
    return [_mix(measure, "#000000", 0.30), measure] + [
        _mix(measure, "#FFFFFF", f) for f in (0.30, 0.55, 0.75, 0.90)
    ]


def validate_brand(brand):
    """
    Every problem with a candidate brand block, as a list of strings. Empty = usable.

    Returned rather than raised so a caller can report all of them at once; a
    client handed one contrast failure at a time will iterate four times.
    """
    problems = []

    for key in sorted(brand):
        if key in _RAG or key in ("rag", "good", "medium", "high", "critical",
                                  "severity", "status"):
            problems.append(
                "%s: RAG is not overridable. The status ramp carries measured "
                "contrast and colour-vision-deficiency separation; a substituted "
                "palette would discard both silently. Override the chrome instead."
                % key)
        elif key not in DEFAULT_BRAND:
            problems.append("%s: unknown brand key (known: %s)"
                            % (key, ", ".join(sorted(DEFAULT_BRAND))))

    for key in _TEXT_KEYS:
        v = brand.get(key, DEFAULT_BRAND[key])
        if not isinstance(v, str) or not v.strip():
            problems.append("%s: must be a non-empty string" % key)

    for key in _FLAG_KEYS:
        v = brand.get(key, DEFAULT_BRAND[key])
        if not isinstance(v, bool):
            problems.append("%s: must be true or false, got %r" % (key, v))

    for key in _COLOUR_KEYS:
        v = brand.get(key, DEFAULT_BRAND[key])
        if not _is_hex(v):
            problems.append("%s: %r is not a #rrggbb colour" % (key, v))

    if problems:
        return problems   # ratios on a malformed hex would raise, not report

    m = dict(DEFAULT_BRAND)
    m.update(brand)

    def floor(name, fg, bg, need, why):
        r = contrast(fg, bg)
        if r < need:
            problems.append("%s: %s on %s is %.2f:1, needs %.1f:1 (%s)"
                            % (name, fg, bg, r, need, why))

    # Text floors. Body and secondary text must clear AA on both grounds a mark
    # can present them on: its own white surface, and the workbench panel.
    floor("ink", m["ink"], _SURFACE, 4.5, "body text on a mark surface")
    floor("ink", m["ink"], m["bg"], 4.5, "body text on the workbench ground")
    floor("muted", m["muted"], _SURFACE, 4.5, "secondary text")
    floor("muted", m["muted"], m["bg"], 4.5, "secondary text on the workbench")
    floor("patinaText", m["patinaText"], _SURFACE, 4.5, "kickers and the TODAY label")

    # Graphical floors.
    floor("measure", m["measure"], _SURFACE, 3.0, "a data mark against its surface")
    floor("measure", m["measure"], m["measureTrack"], 3.0,
          "the filled part of a bar against its own track")

    if _relative_luminance(m["measureTrack"]) <= _relative_luminance(m["measure"]):
        problems.append(
            "measureTrack: %s is not lighter than measure %s. The track is the "
            "unfilled remainder; a track darker than the fill inverts the mark."
            % (m["measureTrack"], m["measure"]))

    # `patina` carries no floor, and that is a deliberate exemption rather than an
    # oversight: it is the one token barred from carrying information, so there is
    # nothing on it for a floor to protect. Anything a reader must read uses
    # `patinaText`, which is floored above.

    # The consequence of RAG being fixed: a client `bg` has to work with it.
    for sev in ("good", "medium", "high", "critical"):
        floor("bg", _RAG[sev]["text"], m["bg"], 4.5,
              "RAG %s label on the client ground; RAG cannot move, so bg must" % sev)

    return problems


def set_brand(brand=None):
    """
    Apply a client brand override process-wide, or reset to CAC with no argument.

    Raises BrandError listing every problem if the block fails validation. Absent
    keys keep their CAC value, so a block naming only `ink` is a legal block.

    This rebinds module state, so it is process-wide and not thread-safe. Marks
    are built from these tokens in ~40 places; threading a palette through every
    signature would be a far larger change than the feature justifies, and every
    caller in this toolkit is a single-threaded CLI. Call it once, before
    rendering.
    """
    global _brand, _INK, _MUTED, _MEASURE, _MEASURE_TRACK, _PATINA
    global _PATINA_TEXT, _BG, _MEASURE_RAMP

    if brand is None:
        brand = {}
    problems = validate_brand(brand)
    if problems:
        raise BrandError("brand override rejected:\n  - " + "\n  - ".join(problems))

    m = dict(DEFAULT_BRAND)
    m.update(brand)
    _brand = m

    _INK, _MUTED = m["ink"], m["muted"]
    _MEASURE, _MEASURE_TRACK = m["measure"], m["measureTrack"]
    _PATINA, _PATINA_TEXT = m["patina"], m["patinaText"]
    _BG = m["bg"]

    _MEASURE_RAMP = (_CAC_MEASURE_RAMP if m["measure"] == DEFAULT_BRAND["measure"]
                     else _derive_ramp(m["measure"]))


def brand():
    """The active brand, as a copy. Renderers read `wordmark` and `mark` here."""
    return dict(_brand)


def _normalize_direction(direction):
    """Accept 'higher'/'higher-better' and 'lower'/'lower-better'."""
    if direction in ("higher", "higher-better"):
        return "higher"
    if direction in ("lower", "lower-better"):
        return "lower"
    raise ValueError(f"unrecognised direction: {direction!r}")


def _validate_iso(d, context=""):
    """Raise ValueError if d is not a recognisable ISO date string."""
    parts = str(d).split("-")
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
        raise ValueError(
            f"malformed date {d!r}" + (f" in {context}" if context else "")
        )
    return str(d)


def _date_ord(d):
    """
    ISO date -> approximate day ordinal, for proportional positioning.
    Accepts YYYY-MM and YYYY-MM-DD.
    """
    parts = [int(p) for p in str(d).split("-")]
    y = parts[0]
    m = parts[1] if len(parts) > 1 else 1
    day = parts[2] if len(parts) > 2 else 1
    return y * 365.25 + (m - 1) * 30.44 + day


def zones_from_threshold(threshold, direction):
    """
    Convert an engine threshold dict to a zones list for bullet().

    threshold = {"target": x, "warn": y, "critical": z}
    direction = "higher-better" | "lower-better" (or without the -better suffix)
    Returns [(threshold_value, sev), ...] for bullet() and _zone_sev().

    `target` is deliberately NOT a band boundary. The metrics engine bands on
    `critical` and `warn` only -- anything past `warn` is `ok` -- so promoting
    `target` to a boundary invents a fourth band the engine does not have, and a
    value sitting between warn and target then renders a green status tile beside
    a yellow bullet band. Same class of contradiction as painting zone bands from
    the wrong direction: the mark disagrees with the number next to it.

    The target is the mark's *tick*. Pass it as bullet(value, target, ...), where
    it says "here is what we are aiming at" without claiming the gap is a band.

    A caller whose engine genuinely bands on four levels can build the list by
    hand; bullet() draws whatever bands it is given.
    """
    direction = _normalize_direction(direction)
    zones = []
    w = threshold.get("warn")
    c = threshold.get("critical")
    if direction == "higher":
        if c is not None:
            zones.append((c, "critical"))
        if w is not None:
            zones.append((w, "high"))
    else:
        if w is not None:
            zones.append((w, "high"))
        if c is not None:
            zones.append((c, "critical"))
    return zones


def _esc(s):
    return _html.escape(str(s))


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _fmt(v):
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    if isinstance(v, float):
        return f"{v:.1f}"
    return str(v)


def _zone_sev(value, zones, direction="higher"):
    """Compute RAG severity from zone list [(threshold, sev), ...]."""
    direction = _normalize_direction(direction)
    sorted_z = sorted(zones, key=lambda z: z[0])
    if direction == "higher":
        for thresh, s in sorted_z:
            if value < thresh:
                return s
        return "good"
    else:
        for thresh, s in reversed(sorted_z):
            if value >= thresh:
                return s
        return "good"


# ── Mark 1: KPI Tile ───────────────────────────────────────────────────────────

def kpi_tile(value, label, delta="", unit="", sev="", delta_sev=None):
    """Stat tile. RAG only if sev passed. Delta coloured by delta_sev, never by sign."""
    w, h = 200, 110
    fill = _sev_colour(sev) if sev else _MEASURE
    vtext = f"{_esc(str(value))}{_esc(unit)}"
    # A big reassuring figure is exactly the shape a vanity metric takes, so the
    # tile has to hold one without spilling. Step the display size down past the
    # width 32px can carry, rather than letting "2,140,000" run off the card.
    vsize = 32 if len(vtext) <= 8 else (26 if len(vtext) <= 11 else 21)
    delta_svg = ""
    if delta:
        delta_col = _sev_colour(delta_sev, "text") if delta_sev and delta_sev in _RAG else _MUTED
        delta_svg = (
            f'<text x="{w // 2}" y="82" text-anchor="middle" '
            f'font-size="13" fill="{delta_col}">{_esc(str(delta))}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">{_surf()}'
        f'<rect width="{w}" height="{h}" rx="6" fill="{_BG}" '
        f'stroke="#E0E0E0" stroke-width="1"/>'
        f'<rect x="0" y="0" width="4" height="{h}" rx="2" fill="{fill}"/>'
        f'<text x="{w // 2}" y="55" text-anchor="middle" font-size="{vsize}" '
        f'font-family="{_FONT_DISPLAY}" font-weight="700" '
        f'fill="{_INK}">{vtext}</text>'
        f'{delta_svg}'
        # No label, no node. An empty <text> is still walked by a screen reader
        # and still has to be explained to whoever reads this next.
        + (f'<text x="{w // 2}" y="100" text-anchor="middle" font-size="12" '
           f'font-family="{_FONT_BODY}" fill="{_MUTED}">{_esc(label)}</text>'
           if str(label).strip() else "")
        + f'</svg>'
    )


# ── Mark 2: RAG Chip ───────────────────────────────────────────────────────────

def rag_chip(sev, label):
    """Status chip: tint background + coloured dot + accessible dark text."""
    if sev not in _RAG:
        return ""
    tint = _sev_colour(sev, "tint")
    dot_fill = _sev_colour(sev, "fill")
    text_col = _sev_colour(sev, "text")
    h = 24
    dot_r = 4
    dot_cx = 10 + dot_r
    text_x = dot_cx + dot_r + 5
    ch_w = max(70, text_x + len(label) * 7 + 10)
    cy = h // 2
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ch_w}" height="{h}" '
        f'viewBox="0 0 {ch_w} {h}">'
        f'<rect width="{ch_w}" height="{h}" rx="{cy}" fill="{tint}"/>'
        f'<circle cx="{dot_cx}" cy="{cy}" r="{dot_r}" fill="{dot_fill}"/>'
        f'<text x="{text_x}" y="{cy + 4}" '
        f'font-size="12" font-family="{_FONT_BODY}" '
        f'font-weight="600" fill="{text_col}">{_esc(label)}</text>'
        f'</svg>'
    )


# ── Mark 3: Bullet Graph ───────────────────────────────────────────────────────

def bullet(value, target, zones, direction="higher", unit="", labels=True,
           axis_max=None):
    """
    Bullet graph. zones=[(threshold, sev), ...]. Bar fill = zone of value.

    axis_max: explicit scale ceiling (use 100 for percent metrics). Defaults to
    1.1× the largest value/threshold. Set explicitly to make a metric wall
    comparable — different auto-scales make bars unreadable side by side.
    """
    w, h = 280, 72
    bar_y, bar_h = 26, 24
    all_thresh = [z[0] for z in zones] + [value, target]
    scale_max = axis_max if axis_max is not None else max(all_thresh) * 1.1
    if scale_max == 0:
        scale_max = 1
    chart_w = w - 40

    def to_x(v):
        return _clamp(v / scale_max * chart_w, 0, chart_w) + 20

    sorted_z = sorted(zones, key=lambda z: z[0])
    end_x = to_x(scale_max)

    # Band colours are DERIVED from _zone_sev, never assumed. The zones list is
    # direction-dependent: under "higher", (t, s) means values BELOW t are s;
    # under "lower", it means values AT OR ABOVE t are s. Painting bands from the
    # "higher" reading silently inverts every lower-better mark. Asking _zone_sev
    # what a mid-band value scores makes the bands and the bar the same claim.
    edges = [0.0] + [z[0] for z in sorted_z] + [scale_max]
    zone_rects = ""
    for lo, hi in zip(edges, edges[1:]):
        if hi <= lo:
            continue
        band_sev = _zone_sev((lo + hi) / 2.0, zones, direction)
        zone_rects += (
            f'<rect x="{to_x(lo):.1f}" y="{bar_y}" '
            f'width="{to_x(hi) - to_x(lo):.1f}" height="{bar_h}" '
            f'fill="{_sev_colour(band_sev, "mid")}"/>'
        )

    bar_sev = _zone_sev(value, zones, direction)
    bar_fill = _sev_colour(bar_sev, "fill")
    bar_text = _sev_colour(bar_sev, "text") if bar_sev in _RAG else _MUTED
    val_x = to_x(value)

    # White measure lane punches through the zone colours, and the bar carries a
    # white keyline on top of it. Adjacent bands differ in hue at similar
    # lightness (critical mid vs high mid vs medium mid), so a bar sitting in its
    # own band would otherwise dissolve into the ground behind it.
    lane = (
        f'<rect x="20" y="{bar_y + 5}" width="{end_x - 20:.1f}" '
        f'height="{bar_h - 10}" fill="{_SURFACE}"/>'
    )
    val_bar = (
        f'<rect x="20" y="{bar_y + 7}" width="{val_x - 20:.1f}" '
        f'height="{bar_h - 14}" rx="2" fill="{bar_fill}" '
        f'stroke="{_SURFACE}" stroke-width="1.5"/>'
    )

    # Value label above the bar tip, in the zone's text colour
    val_label = (
        f'<text x="{val_x:.1f}" y="{bar_y - 4}" '
        f'text-anchor="middle" font-size="10" '
        f'font-family="{_FONT_BODY}" fill="{bar_text}">'
        f'{_esc(_fmt(value))}{_esc(unit)}</text>'
    )

    tgt_x = to_x(target)
    # Target tick: white halo first so it reads through the bar when value > target
    target_line = (
        f'<line x1="{tgt_x:.1f}" y1="{bar_y - 2}" '
        f'x2="{tgt_x:.1f}" y2="{bar_y + bar_h + 2}" '
        f'stroke="#FFFFFF" stroke-width="5"/>'
        f'<line x1="{tgt_x:.1f}" y1="{bar_y - 2}" '
        f'x2="{tgt_x:.1f}" y2="{bar_y + bar_h + 2}" '
        f'stroke="{_INK}" stroke-width="2.4"/>'
    )

    label_svg = ""
    if labels:
        ly = bar_y + bar_h + 14

        # The axis carries whichever numbers actually help, in priority order,
        # and drops any that would collide with one already placed.
        #
        # Thresholds outrank the axis ends. A bullet whose axis reads only "0"
        # and "100" tells a reader the scale and nothing about where the bands
        # begin -- and the bands are the entire claim the mark is making. The
        # target outranks both: it is what the tick is pointing at, and an
        # unlabelled tick is a line the reader has to guess the value of.
        #
        # `medium` and `high` sit ΔE 13.3 apart, below the 15 floor and
        # unfixable by darkening, so a four-band bullet in particular cannot
        # rely on colour to separate them. Labelling every boundary is what
        # makes that separable, and it costs nothing on a three-band one.
        cand = [(to_x(target), f"{_fmt(target)}{unit}", True)]
        for thresh, _s in sorted_z:
            cand.append((to_x(thresh), f"{_fmt(thresh)}{unit}", False))
        cand.append((20.0, f"0{unit}", False))
        cand.append((end_x, f"{_fmt(scale_max)}{unit}", False))

        placed = []
        for x, text, is_target in cand:
            if any(abs(x - px) < 28 for px, _, _ in placed):
                continue
            placed.append((x, text, is_target))

        for x, text, is_target in sorted(placed, key=lambda p: p[0]):
            # Anchor the extremes inward so neither runs off the canvas.
            anchor = ("start" if x <= 20.5 else
                      "end" if x >= end_x - 0.5 else "middle")
            if not is_target and 20.5 < x < end_x - 0.5:
                label_svg += (
                    f'<line x1="{x:.1f}" y1="{bar_y + bar_h}" '
                    f'x2="{x:.1f}" y2="{bar_y + bar_h + 3}" '
                    f'stroke="{_MUTED}" stroke-width="1"/>')
            # The target's number is inked, not muted: it is the one figure on
            # the axis that is a commitment rather than a gradation.
            fill = _INK if is_target else _MUTED
            weight = ' font-weight="600"' if is_target else ""
            label_svg += (
                f'<text x="{x:.1f}" y="{ly}" text-anchor="{anchor}" '
                f'font-size="10" font-family="{_FONT_BODY}"{weight} '
                f'fill="{fill}">{_esc(text)}</text>')

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">{_surf()}'
        f'{zone_rects}{lane}{val_bar}{val_label}{target_line}{label_svg}'
        f'</svg>'
    )


# ── Mark 4: Progress Bar ───────────────────────────────────────────────────────

def progress_bar(value, goal, label="", sev=""):
    """Progress bar. MEASURE if no sev."""
    w, h = 280, 50
    pct = _clamp(value / goal, 0, 1) if goal else 0
    fill = _sev_colour(sev) if sev else _MEASURE
    bar_w = (w - 40) * pct
    pct_label = f"{int(pct * 100)}%"
    lbl_svg = ""
    if label:
        lbl_svg = (
            f'<text x="20" y="44" font-size="11" '
            f'font-family="{_FONT_BODY}" fill="{_MUTED}">{_esc(label)}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">{_surf()}'
        # Value sits ABOVE the track — inside it, ink on measure blue is ~2.7:1
        # and at 100% the label lands on the fill entirely.
        f'<text x="{w - 20}" y="10" text-anchor="end" font-size="11" '
        f'font-family="{_FONT_BODY}" fill="{_INK}">{pct_label}</text>'
        f'<rect x="20" y="14" width="{w - 40}" height="16" rx="8" '
        f'fill="{_MEASURE_TRACK}"/>'
        f'<rect x="20" y="14" width="{bar_w:.1f}" height="16" rx="8" fill="{fill}"/>'
        f'{lbl_svg}'
        f'</svg>'
    )


# ── Mark 5: Fuel Tank ──────────────────────────────────────────────────────────

def fuel_tank(value, goal, label=""):
    """Vertical fill gauge. Always neutral/measure."""
    w, h = 80, 140
    tank_x, tank_y, tank_w, tank_h = 20, 10, 40, 100
    pct = _clamp(value / goal, 0, 1) if goal else 0
    fill_h = tank_h * pct
    fill_y = tank_y + tank_h - fill_h
    lbl_svg = ""
    if label:
        lbl_svg = (
            f'<text x="{w // 2}" y="{h - 4}" text-anchor="middle" font-size="11" '
            f'font-family="{_FONT_BODY}" fill="{_MUTED}">{_esc(label)}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">{_surf()}'
        f'<rect x="{tank_x}" y="{tank_y}" width="{tank_w}" height="{tank_h}" '
        f'rx="4" fill="{_MEASURE_TRACK}" stroke="#C0C0C0" stroke-width="1"/>'
        f'<rect x="{tank_x}" y="{fill_y:.1f}" width="{tank_w}" '
        f'height="{fill_h:.1f}" rx="2" fill="{_MEASURE}"/>'
        f'<text x="{tank_x + tank_w // 2}" y="{tank_y + tank_h // 2 + 5}" '
        f'text-anchor="middle" font-size="14" font-weight="700" '
        f'font-family="{_FONT_BODY}" fill="{_INK}">{int(pct * 100)}%</text>'
        f'{lbl_svg}'
        f'</svg>'
    )


# ── Mark 6: Radial Gauge ───────────────────────────────────────────────────────

def radial_gauge(value, min_v, max_v, zones=None, sev="", direction="higher",
                 target=None, unit=""):
    """
    Dial gauge: mid-tone zone arcs, tapered needle in the band's fill, target
    tick, value and status word below the hub.

    A plain fill arc is a bent progress bar and duplicates progress_bar(); the
    needle is what makes this a dial, the target tick is what makes it
    comparable to a bullet, and the status word is what makes it survive
    greyscale. large-arc-flag is always 0 — the sweep never exceeds 180°.
    """
    direction = _normalize_direction(direction)
    w, h = 200, 132
    cx, cy, r = 100, 96, 72
    rng = max_v - min_v if max_v != min_v else 1
    pct = _clamp((value - min_v) / rng, 0, 1)

    # Sweep from left (π) towards right (0); counter-clockwise in math, but
    # SVG y-axis is flipped so sweep-flag=1 is visually clockwise (upward arc).
    def ang(fraction):
        return _math.pi - _math.pi * _clamp(fraction, 0, 1)

    def polar(a, radius=r):
        return cx + radius * _math.cos(a), cy - radius * _math.sin(a)

    def arc(f0, f1, colour, width):
        if f1 - f0 < 0.004:
            return ""
        x0, y0 = polar(ang(f0))
        x1, y1 = polar(ang(f1))
        # large-arc-flag MUST be 0 (sweep always ≤ 180°)
        return (f'<path d="M {x0:.2f} {y0:.2f} A {r} {r} 0 0 1 {x1:.2f} {y1:.2f}" '
                f'fill="none" stroke="{colour}" stroke-width="{width}" '
                f'stroke-linecap="butt"/>')

    band_sev = None
    if zones:
        band_sev = _zone_sev(value, zones, direction)
    elif sev:
        band_sev = sev
    needle_col = _sev_colour(band_sev, "fill") if band_sev else _MEASURE

    # Zone arcs in mid tones, derived from _zone_sev exactly as the bullet does
    if zones:
        edges = [min_v] + sorted(z[0] for z in zones) + [max_v]
        track = ""
        for lo, hi in zip(edges, edges[1:]):
            if hi <= lo:
                continue
            s_ = _zone_sev((lo + hi) / 2.0, zones, direction)
            track += arc((lo - min_v) / rng, (hi - min_v) / rng,
                         _sev_colour(s_, "mid"), 13)
    else:
        track = arc(0.0, 1.0, _MEASURE_TRACK, 13)

    # Target tick across the band
    tick = ""
    if target is not None:
        ta = ang((target - min_v) / rng)
        tx0, ty0 = polar(ta, r - 9)
        tx1, ty1 = polar(ta, r + 9)
        tick = (f'<line x1="{tx0:.1f}" y1="{ty0:.1f}" x2="{tx1:.1f}" y2="{ty1:.1f}" '
                f'stroke="{_SURFACE}" stroke-width="5"/>'
                f'<line x1="{tx0:.1f}" y1="{ty0:.1f}" x2="{tx1:.1f}" y2="{ty1:.1f}" '
                f'stroke="{_INK}" stroke-width="2.4"/>')

    # Tapered needle: a triangle from the hub shoulders to the tip
    na = ang(pct)
    tipx, tipy = polar(na, r - 14)
    lx, ly = polar(na + _math.pi / 2, 5)
    rx, ry = polar(na - _math.pi / 2, 5)
    needle = (
        f'<polygon points="{tipx:.1f},{tipy:.1f} {lx:.1f},{ly:.1f} '
        f'{rx:.1f},{ry:.1f}" fill="{needle_col}"/>'
        f'<circle cx="{cx}" cy="{cy}" r="6" fill="{needle_col}"/>'
        f'<circle cx="{cx}" cy="{cy}" r="2.5" fill="{_SURFACE}"/>'
    )

    # Value and status word BELOW the hub — inside the arc they collide with it
    word = _GANTT_CHIP.get(band_sev, "") if band_sev else ""
    val_label = (
        f'<text x="{cx}" y="{cy + 22}" text-anchor="middle" '
        f'font-size="21" font-weight="700" font-family="{_FONT_DISPLAY}" '
        f'fill="{_INK}">{_esc(str(value))}{_esc(unit)}</text>'
    )
    if word:
        val_label += (
            f'<text x="{cx}" y="{cy + 34}" text-anchor="middle" font-size="9" '
            f'font-weight="600" font-family="{_FONT_BODY}" '
            f'fill="{_sev_colour(band_sev, "text")}">{_esc(word)}</text>'
        )

    lx0, ly0 = polar(ang(0.0))
    lx1, ly1 = polar(ang(1.0))
    range_labels = (
        f'<text x="{lx0:.1f}" y="{ly0 + 15:.1f}" text-anchor="middle" font-size="9" '
        f'font-family="{_FONT_BODY}" fill="{_MUTED}">{_esc(str(min_v))}</text>'
        f'<text x="{lx1:.1f}" y="{ly1 + 15:.1f}" text-anchor="middle" font-size="9" '
        f'font-family="{_FONT_BODY}" fill="{_MUTED}">{_esc(str(max_v))}</text>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">{_surf()}'
        f'{track}{tick}{needle}{val_label}{range_labels}'
        f'</svg>'
    )


# ── Mark 7: Sparkline ─────────────────────────────────────────────────────────

def sparkline(readings, unit="", sev=""):
    """Returns a note SVG if fewer than 4 readings — never a bare empty string."""
    if len(readings) < 4:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="160" height="20" '
            f'viewBox="0 0 160 20">{_surf()}'
            f'<text x="0" y="14" font-size="10" font-family="{_FONT_BODY}" '
            f'fill="{_MUTED}">≥4 readings needed</text>'
            f'</svg>'
        )
    w, h, pad = 160, 50, 6
    mn, mx = min(readings), max(readings)
    rng = mx - mn if mx != mn else 1

    def to_xy(i, v):
        x = pad + i / (len(readings) - 1) * (w - 2 * pad)
        y = h - pad - (v - mn) / rng * (h - 2 * pad)
        return x, y

    pts = [to_xy(i, v) for i, v in enumerate(readings)]
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    fill = _sev_colour(sev) if sev else _MEASURE
    lx, ly = pts[-1]
    last_val = f"{_esc(str(readings[-1]))}{_esc(unit)}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">{_surf()}'
        f'<polyline points="{polyline}" fill="none" stroke="{fill}" '
        f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3" fill="{fill}"/>'
        f'<text x="{lx + 4:.1f}" y="{ly + 4:.1f}" font-size="10" '
        f'font-family="{_FONT_BODY}" fill="{_INK}">{last_val}</text>'
        f'</svg>'
    )


# ── Mark 8: Slope ─────────────────────────────────────────────────────────────

def slope(readings, labels=None, unit="", sev=""):
    """Two-point slope chart. Exactly 2 readings required."""
    if len(readings) != 2:
        return ""
    w, h = 180, 80
    pad_x, pad_y = 40, 14
    mn = min(readings) * 0.85
    mx = max(readings) * 1.15 if max(readings) > 0 else 1.0
    rng = mx - mn if mx != mn else 1

    def to_y(v):
        return pad_y + (1 - (v - mn) / rng) * (h - 2 * pad_y)

    x0, x1 = pad_x, w - pad_x
    y0, y1 = to_y(readings[0]), to_y(readings[1])
    fill = _sev_colour(sev) if sev else _MEASURE
    # Period labels are omitted entirely when absent. Emitting an empty <text>
    # for each leaves two invisible nodes that a screen reader still walks and a
    # maintainer still has to explain.
    lbl = labels or []
    period_svg = ""
    for x, text in ((x0, lbl[0] if len(lbl) > 0 else ""),
                    (x1, lbl[1] if len(lbl) > 1 else "")):
        if str(text).strip():
            period_svg += (
                f'<text x="{x}" y="{h - 2}" text-anchor="middle" font-size="10" '
                f'font-family="{_FONT_BODY}" fill="{_MUTED}">{_esc(text)}</text>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">{_surf()}'
        f'<line x1="{x0}" y1="{y0:.1f}" x2="{x1}" y2="{y1:.1f}" '
        f'stroke="{fill}" stroke-width="2.5" stroke-linecap="round"/>'
        f'<circle cx="{x0}" cy="{y0:.1f}" r="4" fill="{fill}"/>'
        f'<circle cx="{x1}" cy="{y1:.1f}" r="4" fill="{fill}"/>'
        f'<text x="{x0}" y="{y0 - 6:.1f}" text-anchor="middle" font-size="11" '
        f'font-family="{_FONT_BODY}" fill="{_INK}">'
        f'{_esc(_fmt(readings[0]))}{_esc(unit)}</text>'
        f'<text x="{x1}" y="{y1 - 6:.1f}" text-anchor="middle" font-size="11" '
        f'font-family="{_FONT_BODY}" fill="{_INK}">'
        f'{_esc(_fmt(readings[1]))}{_esc(unit)}</text>'
        f'{period_svg}'
        f'</svg>'
    )


# ── Mark 9: Line Chart ────────────────────────────────────────────────────────

def line_chart(readings, labels=None, unit="", sev=""):
    """Line chart. Requires at least 4 readings."""
    if len(readings) < 4:
        return ""
    w, h = 300, 120
    pad_x, pad_y, pad_b = 30, 14, 26
    mn, mx = min(readings), max(readings)
    rng = mx - mn if mx != mn else 1
    chart_w = w - 2 * pad_x
    chart_h = h - pad_y - pad_b

    def to_xy(i, v):
        x = pad_x + i / (len(readings) - 1) * chart_w
        y = pad_y + (1 - (v - mn) / rng) * chart_h
        return x, y

    pts = [to_xy(i, v) for i, v in enumerate(readings)]
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    fill = _sev_colour(sev) if sev else _MEASURE

    axis = (
        f'<line x1="{pad_x}" y1="{pad_y + chart_h}" '
        f'x2="{w - pad_x}" y2="{pad_y + chart_h}" '
        f'stroke="#E0E0E0" stroke-width="1"/>'
    )

    x_labels = ""
    if labels:
        step = max(1, len(readings) // 5)
        for i in range(0, len(readings), step):
            x, _ = to_xy(i, readings[i])
            lbl = labels[i] if i < len(labels) else ""
            x_labels += (
                f'<text x="{x:.1f}" y="{h - 4}" text-anchor="middle" '
                f'font-size="9" font-family="{_FONT_BODY}" '
                f'fill="{_MUTED}">{_esc(str(lbl))}</text>'
            )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">{_surf()}'
        f'{axis}'
        f'<polyline points="{polyline}" fill="none" stroke="{fill}" '
        f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
        f'{x_labels}'
        f'</svg>'
    )


# ── Mark 10: Column Trend ─────────────────────────────────────────────────────

def column_trend(readings, labels=None, unit=""):
    """Bar-column trend. Always MEASURE — no sev parameter."""
    if not readings:
        return ""
    w, h = 300, 120
    pad_x, pad_y, pad_b = 20, 10, 24
    mx = max(readings) if max(readings) > 0 else 1
    chart_w = w - 2 * pad_x
    chart_h = h - pad_y - pad_b
    n = len(readings)
    gap = chart_w / n
    col_w = gap * 0.7

    cols = ""
    for i, v in enumerate(readings):
        bh = v / mx * chart_h
        x = pad_x + i * gap + (gap - col_w) / 2
        y = pad_y + chart_h - bh
        cols += (
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{col_w:.1f}" '
            f'height="{bh:.1f}" rx="2" fill="{_MEASURE}"/>'
        )
        if labels and i < len(labels):
            cols += (
                f'<text x="{x + col_w / 2:.1f}" y="{h - 4}" '
                f'text-anchor="middle" font-size="9" '
                f'font-family="{_FONT_BODY}" '
                f'fill="{_MUTED}">{_esc(str(labels[i]))}</text>'
            )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">{_surf()}'
        f'<line x1="{pad_x}" y1="{pad_y + chart_h}" '
        f'x2="{w - pad_x}" y2="{pad_y + chart_h}" '
        f'stroke="#E0E0E0" stroke-width="1"/>'
        f'{cols}'
        f'</svg>'
    )


# ── Mark 11: Bar Chart ────────────────────────────────────────────────────────

def bar_chart(items, categorical=False):
    """
    Horizontal bar chart. items = [(label, value)] or [(label, value, sev)].

    Palette follows the same rule as stacked_bar: any item carrying a `sev`
    makes this a RAG chart; otherwise the bars are a single MEASURE blue,
    because a bar chart over unbanded values compares magnitudes and does not
    need to distinguish the rows by colour — the row labels already do that.

    Pass categorical=True when the rows ARE the categories being compared and
    should be told apart at a glance (source, asset class, business unit). They
    then take the sequential MEASURE ramp, never RAG.
    """
    if not items:
        return ""
    pad_x, pad_y = 90, 10
    row_h = 28
    h = pad_y * 2 + len(items) * row_h
    w = 300
    chart_w = w - pad_x - 20
    # A value of None means "not assessed", and it is not the same claim as zero. Zero says
    # the thing was measured and found to be nothing; None says nobody looked. Drawing the
    # second as the first is the confusion the hatch exists to prevent, and it is worse on a
    # bar than on a heat cell: a zero-length bar in a row of long ones reads as the worst
    # result on the chart rather than as an absent one.
    #
    # Unassessed rows are excluded from the scale as well as from the bars. A None in the
    # max() would raise on Python 3, and silently treating it as zero would let an
    # unassessed row set the floor of a scale it was never part of.
    measured = [item[1] for item in items if item[1] is not None]
    mx = max(measured) if measured else 1
    if mx == 0:
        mx = 1

    is_rag = any(len(item) > 2 and item[2] for item in items)
    needs_hatch = any(item[1] is None for item in items)

    bars = ""
    for i, item in enumerate(items):
        lbl = item[0]
        val = item[1]
        sev = item[2] if len(item) > 2 else None
        y = pad_y + i * row_h
        if val is None:
            # Full-width hatch, so the row reads as "this was not measured" rather than as
            # a measurement near zero, and says so in words as well — the texture carries it
            # in greyscale and forced-colours, the words carry it for a screen reader.
            bars += (
                f'<text x="{pad_x - 6}" y="{y + row_h // 2 + 4}" '
                f'text-anchor="end" font-size="11" '
                f'font-family="{_FONT_BODY}" fill="{_INK}">{_esc(str(lbl))}</text>'
                f'<rect x="{pad_x}" y="{y + 4}" width="{chart_w}" '
                f'height="{row_h - 8}" rx="2" fill="url(#{_HATCH_ID})"/>'
                f'<text x="{pad_x + 6}" y="{y + row_h // 2 + 4}" '
                f'font-size="10" font-family="{_FONT_BODY}" '
                f'fill="{_MUTED}">not assessed</text>'
            )
            continue
        if sev:
            fill = _sev_colour(sev, "fill")
        elif categorical and not is_rag:
            fill = _MEASURE_RAMP[i % len(_MEASURE_RAMP)]
        else:
            fill = _MEASURE
        bw = val / mx * chart_w
        bars += (
            f'<text x="{pad_x - 6}" y="{y + row_h // 2 + 4}" '
            f'text-anchor="end" font-size="11" '
            f'font-family="{_FONT_BODY}" fill="{_INK}">{_esc(str(lbl))}</text>'
            f'<rect x="{pad_x}" y="{y + 4}" width="{bw:.1f}" '
            f'height="{row_h - 8}" rx="2" fill="{fill}"/>'
            f'<text x="{pad_x + bw + 4:.1f}" y="{y + row_h // 2 + 4}" '
            f'font-size="10" font-family="{_FONT_BODY}" '
            f'fill="{_MUTED}">{_esc(str(val))}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">{_surf()}'
        f'{_hatch_def() if needs_hatch else ""}{bars}</svg>'
    )


# ── Mark 12: Heat Matrix ──────────────────────────────────────────────────────

def heat_matrix(cells, row_labels=None, col_labels=None):
    """
    Heat matrix. cells[i][j] = {sev?, value?, label?} or None.

    Same rule as the other composition marks:

      * any cell carries `sev` -> RAG matrix, cells take the band's `mid` tone.
      * no cell carries `sev`  -> INTENSITY matrix. Cells carrying a numeric
        `value` are shaded along the sequential MEASURE ramp, darkest = highest.
        A count of findings per control family is not a severity, and colouring
        it red would assert one.
    """
    if not cells:
        return ""
    is_rag = any(c and c.get("sev") for row in cells for c in row)

    # Intensity scale for the no-sev case, darkest step = highest value
    vals = [c["value"] for row in cells for c in row
            if c and isinstance(c.get("value"), (int, float))]
    vmin = min(vals) if vals else 0
    vmax = max(vals) if vals else 0
    vspan = (vmax - vmin) or 1

    def _intensity(v):
        # ramp runs dark -> light, so invert: high value gets the dark step
        frac = (v - vmin) / vspan
        idx = int(round((1 - frac) * (len(_MEASURE_RAMP) - 2)))
        return _MEASURE_RAMP[_clamp(idx, 0, len(_MEASURE_RAMP) - 1)]

    used_hatch = False
    nrows = len(cells)
    ncols = max(len(row) for row in cells)
    cell_sz = 44
    lbl_x = 60 if row_labels else 10
    lbl_y = 30 if col_labels else 10
    w = lbl_x + ncols * cell_sz + 10
    h = lbl_y + nrows * cell_sz + 10

    out = ""
    if col_labels:
        for j, cl in enumerate(col_labels):
            out += (
                f'<text x="{lbl_x + j * cell_sz + cell_sz // 2}" y="20" '
                f'text-anchor="middle" font-size="10" '
                f'font-family="{_FONT_BODY}" '
                f'fill="{_MUTED}">{_esc(str(cl))}</text>'
            )

    for i, row in enumerate(cells):
        if row_labels and i < len(row_labels):
            out += (
                f'<text x="{lbl_x - 6}" '
                f'y="{lbl_y + i * cell_sz + cell_sz // 2 + 4}" '
                f'text-anchor="end" font-size="10" '
                f'font-family="{_FONT_BODY}" '
                f'fill="{_MUTED}">{_esc(str(row_labels[i]))}</text>'
            )
        for j, cell in enumerate(row):
            x = lbl_x + j * cell_sz
            y = lbl_y + i * cell_sz
            # mid tone + the band's dark text: no opacity compositing (which a
            # colour-pair check cannot validate), passes contrast for all four
            # bands, and makes a cell read as the same object as a bullet band.
            if cell is None:
                # Hatched, not tinted -- see _hatch_def(). A cell with nothing
                # behind it must be unmistakable at any point on the ramp.
                fill = f"url(#{_HATCH_ID})"
                used_hatch = True
                txt = ""
                sev = ""
                txt_col = _MUTED
            else:
                sev = cell.get("sev", "")
                txt = cell.get("label", "")
                if sev:
                    fill = _sev_colour(sev, "mid")
                    txt_col = _sev_colour(sev, "text")
                elif not is_rag and isinstance(cell.get("value"), (int, float)):
                    fill = _intensity(cell["value"])
                    txt_col = _on(fill)
                else:
                    fill = _MEASURE_TRACK
                    txt_col = _MUTED
            out += (
                f'<rect x="{x + 1}" y="{y + 1}" '
                f'width="{cell_sz - 2}" height="{cell_sz - 2}" '
                f'rx="3" fill="{fill}"/>'
            )
            if txt:
                out += (
                    f'<text x="{x + cell_sz // 2}" '
                    f'y="{y + cell_sz // 2 + 4}" '
                    f'text-anchor="middle" font-size="11" '
                    f'font-weight="600" font-family="{_FONT_BODY}" '
                    f'fill="{txt_col}">{_esc(str(txt))}</text>'
                )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">{_surf()}'
        f'{_hatch_def() if used_hatch else ""}{out}</svg>'
    )


# ── Mark 13: Stacked Bar ──────────────────────────────────────────────────────

def stacked_bar(periods):
    """
    Stacked bar. periods = [{label, segments:[{value, sev?, label?}]}].

    The palette is chosen by what the segments actually encode:

      * any segment carries `sev`  -> RAG stack. Segments are risk bands, so they
        take the band's `mid` tone. A segment with no `sev` in that stack is
        genuinely unassessed and takes a neutral grey — not a band colour.
      * no segment carries `sev`   -> CATEGORICAL stack. Segments are categories
        (incident source, asset class, control family), which have no severity, so
        they take the sequential MEASURE ramp. Painting them RAG would assert a
        danger the data never claimed.

    Segment order is preserved bottom-to-top; ramp steps are assigned in that
    order and are consistent across periods, so a category keeps its colour.
    _PATINA is never a segment fill.
    """
    if not periods:
        return ""
    pad_x, pad_y, pad_b = 20, 10, 24
    w = max(280, len(periods) * 60 + 40)
    h = 140
    chart_h = h - pad_y - pad_b

    # One decision for the whole chart — a mark cannot be half status, half category.
    is_rag = any(s.get("sev") for p in periods for s in p.get("segments", []))

    # Categorical: a category keeps one ramp step across every period. Key on the
    # segment label when present, else on stack position.
    ramp_key = {}
    if not is_rag:
        for p in periods:
            for idx, s in enumerate(p.get("segments", [])):
                k = s.get("label", idx)
                if k not in ramp_key:
                    ramp_key[k] = len(ramp_key)

    totals = [sum(s.get("value", 0) for s in p.get("segments", [])) for p in periods]
    mx = max(totals) if totals else 1
    if mx == 0:
        mx = 1

    n = len(periods)
    gap = (w - 2 * pad_x) / n
    # Narrower than the column, so a segment too short for an inside label has
    # somewhere to put one without colliding with the next period's bar.
    bar_w = gap * 0.5

    out = ""
    for i, period in enumerate(periods):
        x = pad_x + i * gap + (gap - bar_w) / 2
        y_cur = pad_y + chart_h
        for idx, seg in enumerate(period.get("segments", [])):
            sev = seg.get("sev", "")
            val = seg.get("value", 0)
            # A segment is a REGION, not a single value — so a RAG segment takes
            # the mid tone, same as a bullet zone band and a heat cell. White on
            # good (#30915B) is 3.9:1, under the floor; band text on mid passes.
            if is_rag:
                fill = _sev_colour(sev, "mid") if sev else _UNASSESSED
                txt_col = _sev_colour(sev, "text") if sev else _MUTED
            else:
                step = ramp_key.get(seg.get("label", idx), idx)
                fill = _MEASURE_RAMP[step % len(_MEASURE_RAMP)]
                txt_col = _on(fill)
            seg_h = val / mx * chart_h
            y_cur -= seg_h
            out += (
                f'<rect x="{x:.1f}" y="{y_cur:.1f}" '
                f'width="{bar_w:.1f}" height="{seg_h:.1f}" fill="{fill}"/>'
            )
            # Mandatory label. ΔE 13.3 between medium and high means colour alone
            # cannot separate them, so every segment carries its value -- and
            # "every" has to mean every.
            #
            # This used to skip any segment under 14px, which dropped the label
            # exactly where it was most needed: a small count is usually the
            # severe band, so on a real register the two segments losing their
            # numbers were High and Critical. A rule that lapses on its most
            # important case is not a rule.
            #
            # So a segment too short to hold its label puts it outside, to the
            # right, in ink on the page ground rather than on the fill.
            if val:
                if seg_h >= 14:
                    out += (
                        f'<text x="{x + bar_w / 2:.1f}" '
                        f'y="{y_cur + seg_h / 2 + 4:.1f}" '
                        f'text-anchor="middle" font-size="9" '
                        f'font-family="{_FONT_BODY}" fill="{txt_col}">'
                        f'{_esc(_fmt(val))}</text>'
                    )
                else:
                    out += (
                        f'<line x1="{x + bar_w:.1f}" y1="{y_cur + seg_h / 2:.1f}" '
                        f'x2="{x + bar_w + 4:.1f}" y2="{y_cur + seg_h / 2:.1f}" '
                        f'stroke="{_MUTED}" stroke-width="1"/>'
                        f'<text x="{x + bar_w + 6:.1f}" '
                        f'y="{y_cur + seg_h / 2 + 3:.1f}" '
                        f'font-size="9" font-family="{_FONT_BODY}" '
                        f'fill="{_INK}">{_esc(_fmt(val))}</text>'
                    )
        lbl = period.get("label", "")
        out += (
            f'<text x="{x + bar_w / 2:.1f}" y="{h - 4}" '
            f'text-anchor="middle" font-size="10" '
            f'font-family="{_FONT_BODY}" '
            f'fill="{_MUTED}">{_esc(str(lbl))}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">{_surf()}'
        f'<line x1="{pad_x}" y1="{pad_y + chart_h}" '
        f'x2="{w - pad_x}" y2="{pad_y + chart_h}" '
        f'stroke="#E0E0E0" stroke-width="1"/>'
        f'{out}'
        f'</svg>'
    )


# ── Mark 14: Small Multiples ──────────────────────────────────────────────────

def small_multiples(metrics, mark_fn, axis_max=None):
    """
    Grid of the same mark. mark_fn(metric) -> SVG string.

    axis_max is merged into every metric dict before mark_fn sees it. Without a
    shared ceiling each bullet auto-scales to its own data and the wall stops
    being comparable — which is the only reason to build a wall.
    """
    if not metrics:
        return ""
    if axis_max is not None:
        metrics = [dict(m, axis_max=axis_max) for m in metrics]

    rendered = [mark_fn(m) for m in metrics]

    # Cell size comes from the marks themselves. A hardcoded cell silently clips
    # any mark wider than it — the next cell's surface rect paints over the
    # overflow, so value and axis-max labels vanish with no error anywhere.
    gap = 20
    mark_w = int(_math.ceil(max((_svg_size(s)[0] for s in rendered), default=0)))
    mark_h = int(_math.ceil(max((_svg_size(s)[1] for s in rendered), default=0)))
    if not mark_w or not mark_h:
        return ""
    cell_w = mark_w + gap
    cell_h = mark_h + gap

    cols = min(3, len(metrics))
    rows = (len(metrics) + cols - 1) // cols
    w = cols * cell_w - gap
    h = rows * cell_h - gap

    out = ""
    for idx, inner in enumerate(rendered):
        col = idx % cols
        row = idx // cols
        out += (
            f'<g transform="translate({col * cell_w},{row * cell_h})">'
            f'{inner}'
            f'</g>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" style="max-width:100%;height:auto">'
        f'{_surf()}{out}</svg>'
    )


# ── Mark 15: Milestone Timeline ───────────────────────────────────────────────

def milestone_timeline(events, today=""):
    """
    Horizontal chronology. events = [{label, date, sev}].

    x is proportional to date — that spacing IS the mark's value. Evenly spaced
    rows would make "3 days" and "a month" look identical, which turns a
    chronology into a changelog. It also keeps the time axis running the same
    way as the gantt when both sit on one page.

    Labels alternate above/below so near dates do not collide.
    Dots: RAG if sev, else INK. Today: vertical PATINA dashed line.
    """
    if not events:
        return ""
    w = 520
    pad_x = 46
    chart_w = w - 2 * pad_x
    axis_y = 76
    h = 152

    dated = [e for e in events if e.get("date")]
    for e in dated:
        _validate_iso(e["date"], f'milestone "{e.get("label", "")}"')
    if today:
        _validate_iso(today, "today")
    if not dated:
        return ""

    ords = [_date_ord(e["date"]) for e in dated]
    if today:
        ords.append(_date_ord(today))
    lo, hi = min(ords), max(ords)
    span = (hi - lo) or 1.0

    def to_x(d):
        return pad_x + (_date_ord(d) - lo) / span * chart_w

    out = (
        f'<line x1="{pad_x - 10}" y1="{axis_y}" x2="{w - pad_x + 10}" y2="{axis_y}" '
        f'stroke="#C8C4BA" stroke-width="1.5"/>'
    )

    for i, ev in enumerate(sorted(dated, key=lambda e: _date_ord(e["date"]))):
        sev = ev.get("sev", "")
        fill = _sev_colour(sev, "fill") if sev else _INK
        cx = to_x(ev["date"])
        above = (i % 2 == 0)
        stem_end = axis_y - 20 if above else axis_y + 20
        lbl_y = axis_y - 26 if above else axis_y + 32
        date_y = axis_y - 40 if above else axis_y + 46
        out += (
            f'<line x1="{cx:.1f}" y1="{axis_y}" x2="{cx:.1f}" y2="{stem_end}" '
            f'stroke="#C8C4BA" stroke-width="1"/>'
            f'<circle cx="{cx:.1f}" cy="{axis_y}" r="6" fill="{fill}" '
            f'stroke="{_SURFACE}" stroke-width="2"/>'
            f'<text x="{cx:.1f}" y="{lbl_y}" text-anchor="middle" font-size="11" '
            f'font-family="{_FONT_BODY}" fill="{_INK}">'
            f'{_esc(ev.get("label", ""))}</text>'
            f'<text x="{cx:.1f}" y="{date_y}" text-anchor="middle" font-size="9" '
            f'font-family="{_FONT_BODY}" fill="{_MUTED}">'
            f'{_esc(str(ev["date"]))}</text>'
        )

    if today:
        tx = to_x(today)
        out += (
            f'<line x1="{tx:.1f}" y1="12" x2="{tx:.1f}" y2="{h - 12}" '
            f'stroke="{_PATINA_TEXT}" stroke-width="1.5" stroke-dasharray="5,3"/>'
            f'<text x="{tx + 4:.1f}" y="{h - 14}" font-size="9" font-weight="600" '
            f'font-family="{_FONT_BODY}" fill="{_PATINA_TEXT}">TODAY</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" style="max-width:100%;height:auto">'
        f'{_surf()}{out}</svg>'
    )


# ── Mark 16: Gantt ────────────────────────────────────────────────────────────

def gantt(phases, today="", milestones=None):
    """
    Executive gantt chart.

    phases = [{label, start, end, pct=1.0, sev=None}]
      bars  = MEASURE_TRACK (planned) + MEASURE fill (% complete).
      chip  = RAG + spec vocabulary: ON TRACK / WATCH / AT RISK / LATE.
      pct   = float 0..1 shown as muted text in the right column.

    milestones = [{label, date}]  — rendered as INK diamonds on the timeline.
    today      = ISO date string  — renders as PATINA dashed vertical line.
    """
    if not phases:
        return ""
    lbl_w = 110
    pad_y = 30
    row_h = 36
    chip_col_w = 92   # dot + "ON TRACK" at 9px — needs ~88px
    pct_col_w  = 32
    w = 568           # 568 = lbl_w + chart_w(326) + pct_col_w + chip_col_w + 8

    # Build date index (lexicographic ISO = chronological); validate on entry
    all_dates = []
    for p in phases:
        if p.get("start"):
            all_dates.append(_validate_iso(p["start"], f'phase "{p.get("label","")}" start'))
        if p.get("end"):
            all_dates.append(_validate_iso(p["end"], f'phase "{p.get("label","")}" end'))
    if milestones:
        for m in milestones:
            if m.get("date"):
                all_dates.append(str(m["date"]))
    if not all_dates:
        return ""
    if today:
        all_dates.append(today)
    chart_w = w - lbl_w - pct_col_w - chip_col_w - 8
    h = pad_y + len(phases) * row_h + 20

    # x is proportional to DATE, not to position in the sorted list of dates.
    #
    # The ordinal version spaced unique dates evenly, which made a bar's LENGTH
    # mean nothing: a one-day phase and a two-month phase drew identical bars,
    # and the today line landed wherever the sort happened to put it. A gantt
    # whose bar length is not its duration is not a gantt.
    #
    # Same rule and same helper as milestone_timeline, so a gantt and a timeline
    # on one page share a time axis instead of quietly disagreeing about it.
    ords = [_date_ord(d) for d in all_dates]
    lo, hi = min(ords), max(ords)
    span = (hi - lo) or 1.0

    def to_x(d):
        return lbl_w + (_date_ord(d) - lo) / span * chart_w

    out = ""
    for i, phase in enumerate(phases):
        y = pad_y + i * row_h
        cy = y + row_h // 2

        out += (
            f'<text x="{lbl_w - 6}" y="{cy + 4}" text-anchor="end" '
            f'font-size="11" font-family="{_FONT_BODY}" '
            f'fill="{_INK}">{_esc(str(phase.get("label", "")))}</text>'
        )

        if phase.get("start") and phase.get("end"):
            x0 = to_x(phase["start"])
            x1 = to_x(phase["end"])
            bw = max(x1 - x0, 4)
            out += (
                f'<rect x="{x0:.1f}" y="{cy - 7}" width="{bw:.1f}" height="14" '
                f'rx="3" fill="{_MEASURE_TRACK}"/>'
            )
            pct = phase.get("pct", 1.0)
            if pct and pct > 0:
                out += (
                    f'<rect x="{x0:.1f}" y="{cy - 7}" '
                    f'width="{bw * pct:.1f}" height="14" '
                    f'rx="3" fill="{_MEASURE}"/>'
                )
            # % complete — muted text in right-hand column
            pct_x = lbl_w + chart_w + 4
            out += (
                f'<text x="{pct_x}" y="{cy + 4}" font-size="10" '
                f'font-family="{_FONT_BODY}" fill="{_MUTED}">'
                f'{int((pct or 0) * 100)}%</text>'
            )

        # Status chip: tint bg + coloured dot + accessible dark word
        sev = phase.get("sev", "")
        if sev and sev in _RAG:
            chip_x = lbl_w + chart_w + pct_col_w + 4
            chip_label = _GANTT_CHIP.get(sev, sev.upper())
            chip_tint = _sev_colour(sev, "tint")
            chip_dot  = _sev_colour(sev, "fill")
            chip_txt  = _sev_colour(sev, "text")
            cw = chip_col_w - 4
            out += (
                f'<rect x="{chip_x}" y="{cy - 9}" width="{cw}" '
                f'height="18" rx="9" fill="{chip_tint}"/>'
                f'<circle cx="{chip_x + 9}" cy="{cy}" r="4" fill="{chip_dot}"/>'
                f'<text x="{chip_x + 17}" y="{cy + 4}" '
                f'font-size="9" font-weight="600" '
                f'font-family="{_FONT_BODY}" fill="{chip_txt}">'
                f'{_esc(chip_label)}</text>'
            )

    # Milestone diamonds — ink coloured
    if milestones:
        for ms in milestones:
            if not ms.get("date"):
                continue
            mx_ = to_x(ms["date"])
            lbl = ms.get("label", "")
            # Diamond: rotated square
            d = 6
            out += (
                f'<polygon points="{mx_:.1f},{pad_y - d - 2} '
                f'{mx_ + d:.1f},{pad_y - 2} '
                f'{mx_:.1f},{pad_y + d - 2} '
                f'{mx_ - d:.1f},{pad_y - 2}" '
                f'fill="{_INK}"/>'
            )
            if lbl:
                out += (
                    f'<text x="{mx_:.1f}" y="{pad_y - d - 6}" '
                    f'text-anchor="middle" font-size="9" '
                    f'font-family="{_FONT_BODY}" fill="{_INK}">'
                    f'{_esc(lbl)}</text>'
                )

    # Today line. Drawn whenever a today was given: with a proportional axis it
    # lands at its real position, so it no longer has to coincide with one of the
    # phase dates to be placeable.
    if today:
        tx = to_x(today)
        out += (
            f'<line x1="{tx:.1f}" y1="{pad_y - 10}" '
            f'x2="{tx:.1f}" y2="{h - 10}" '
            f'stroke="{_PATINA_TEXT}" stroke-width="1.5" stroke-dasharray="5,3"/>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" style="max-width:100%;height:auto">{_surf()}{out}</svg>'
    )


# ── Self-test ─────────────────────────────────────────────────────────────────

def _self_test():
    checks = 0
    fails = 0

    def ok(name):
        nonlocal checks
        checks += 1
        print(f"  ok    {name}")

    def bad(name, detail=""):
        nonlocal checks, fails
        checks += 1
        fails += 1
        print(f"  FAIL  {name}" + (f"\n         {detail}" if detail else ""))

    def chk(name, svg, present=None, absent=None):
        for s in (present or []):
            if s not in svg:
                bad(name, f"expected {s!r} not found")
                return
        for s in (absent or []):
            if s in svg:
                bad(name, f"unexpected {s!r} found")
                return
        ok(name)

    rag_vals = [v["fill"] for v in _RAG.values()]

    # 1. kpi_tile no sev → no RAG hex
    chk("kpi_tile no sev → no RAG colour", kpi_tile(42, "Score"), absent=rag_vals)

    # 2. kpi_tile sev=critical → #c0392b
    chk("kpi_tile sev=critical → #c0392b", kpi_tile(42, "Score", sev="critical"),
        present=['fill="#c0392b"'])

    # 3. kpi_tile positive delta → no #30915B (delta not coloured by sign)
    chk("kpi_tile +delta → no green", kpi_tile(42, "Score", delta="+5"),
        absent=["#30915B"])

    # 4. kpi_tile negative delta → no #c0392b
    chk("kpi_tile -delta → no red", kpi_tile(42, "Score", delta="-5"),
        absent=["#c0392b"])

    # 5. progress_bar no sev → no RAG hex
    chk("progress_bar no sev → no RAG", progress_bar(50, 100), absent=rag_vals)

    # 6. progress_bar sev=critical → #c0392b
    chk("progress_bar sev=critical → #c0392b",
        progress_bar(50, 100, sev="critical"), present=['fill="#c0392b"'])

    # 7. fuel_tank → no RAG hex
    chk("fuel_tank → no RAG", fuel_tank(60, 100, label="Capacity"), absent=rag_vals)

    # 8. column_trend → no RAG hex
    chk("column_trend → no RAG", column_trend([10, 20, 30, 25]), absent=rag_vals)

    # 9. column_trend → MEASURE present
    chk("column_trend → MEASURE", column_trend([10, 20, 30, 25]),
        present=[_MEASURE])

    # 10. sparkline 3 readings → note SVG (not empty, not a polyline)
    s = sparkline([1, 2, 3])
    if s and "polyline" not in s:
        ok("sparkline <4 readings → note (not empty, not a polyline)")
    else:
        bad("sparkline <4 readings → note", "was empty or contained a polyline")

    # 11. sparkline 4 readings → non-empty
    s = sparkline([1, 2, 3, 4])
    if s:
        ok("sparkline 4 readings → non-empty")
    else:
        bad("sparkline 4 readings → non-empty", "empty returned")

    # 12. sparkline sev=medium → #e8c547
    chk("sparkline sev=medium → #e8c547",
        sparkline([1, 2, 3, 4], sev="medium"), present=['stroke="#e8c547"'])

    # 13. slope sev=medium → #e8c547 (not coloured by direction of change)
    chk("slope sev=medium → #e8c547 (declining ok)",
        slope([10, 5], sev="medium"), present=['stroke="#e8c547"'])

    # 14. bullet value in high zone → #e08e0b
    chk("bullet value in high zone → #e08e0b",
        bullet(65, 90, [(50, "critical"), (80, "high"), (100, "medium")]),
        present=['fill="#e08e0b"'])

    # 15. bullet value in crit zone → #c0392b
    chk("bullet value in crit zone → #c0392b",
        bullet(30, 90, [(50, "critical"), (80, "high"), (100, "medium")]),
        present=['fill="#c0392b"'])

    # 16. bullet lower-better high value → crit fill
    chk("bullet lower-better high value → crit",
        bullet(95, 70, [(80, "high"), (90, "critical")], direction="lower"),
        present=['fill="#c0392b"'])

    # 17. heat_matrix sev=critical → #c0392b
    chk("heat_matrix sev=critical → critical mid tone",
        heat_matrix([[{"sev": "critical", "label": "H"}]]),
        present=[f'fill="{_RAG["critical"]["mid"]}"'])

    # 18. heat_matrix no sev → MEASURE
    chk("heat_matrix no sev → measure track",
        heat_matrix([[{"label": "X"}]]),
        present=[f'fill="{_MEASURE_TRACK}"'])

    # 19. stacked_bar critical segment → #c0392b
    chk("stacked_bar critical segment → critical mid tone",
        stacked_bar([{"label": "Q1",
                      "segments": [{"sev": "critical", "value": 5}]}]),
        present=[f'fill="{_RAG["critical"]["mid"]}"'])

    # 20. stacked_bar → no PATINA in segment fills
    chk("stacked_bar → no patina",
        stacked_bar([{"label": "Q1",
                      "segments": [{"sev": "good", "value": 3},
                                   {"sev": "high", "value": 2}]}]),
        absent=[_PATINA, _PATINA_TEXT])

    # 21. milestone_timeline event no sev → no RAG hex
    chk("milestone no-sev event → no RAG",
        milestone_timeline([{"label": "Kick-off", "date": "2026-01"}]),
        absent=rag_vals)

    # 22. milestone_timeline event with sev=high → #e08e0b
    chk("milestone sev=high → #e08e0b",
        milestone_timeline([{"label": "Deadline", "date": "2026-06",
                             "sev": "high"}]),
        present=['fill="#e08e0b"'])

    # 23. milestone_timeline today → the ACCESSIBLE patina, not the decorative one.
    #     The TODAY marker is read, so it may not use the 2.93:1 brand hue.
    chk("milestone today → accessible patina, decorative absent",
        milestone_timeline([{"label": "Now", "date": "2026-03"}],
                           today="2026-03"),
        present=[_PATINA_TEXT], absent=[_PATINA])

    # 24. gantt → MEASURE present
    chk("gantt → MEASURE present",
        gantt([{"label": "Ph1", "start": "2026-01", "end": "2026-06",
                "pct": 0.5}]),
        present=[_MEASURE])

    # 25. gantt no phase status → no RAG hex
    chk("gantt no status → no RAG",
        gantt([{"label": "Ph1", "start": "2026-01", "end": "2026-06"}]),
        absent=rag_vals)

    # 26. gantt with sev → RAG hex in chip + spec vocabulary label
    chk("gantt with status → RAG chip + ON TRACK label",
        gantt([{"label": "Ph1", "start": "2026-01", "end": "2026-06",
                "sev": "good"}]),
        present=['fill="#30915B"', "ON TRACK"])

    # 27. gantt today → the ACCESSIBLE patina, not the decorative one
    chk("gantt today → accessible patina, decorative absent",
        gantt([{"label": "Ph1", "start": "2026-01", "end": "2026-06"}],
              today="2026-03"),
        present=[_PATINA_TEXT], absent=[_PATINA])

    # 28. rag_chip "good" → #30915B
    chk("rag_chip good → #30915B", rag_chip("good", "On Track"),
        present=['fill="#30915B"'])

    # 29. rag_chip "critical" → #c0392b
    chk("rag_chip critical → #c0392b", rag_chip("critical", "At Risk"),
        present=['fill="#c0392b"'])

    # 30. column_trend → no PATINA
    chk("column_trend → no patina", column_trend([5, 10, 8, 12]),
        absent=[_PATINA, _PATINA_TEXT])

    # 31. bar_chart no sev → MEASURE
    chk("bar_chart no sev → MEASURE",
        bar_chart([("Item A", 10), ("Item B", 20)]),
        present=[_MEASURE])

    # 32. bar_chart sev=critical → #c0392b
    chk("bar_chart sev=critical → #c0392b",
        bar_chart([("Item A", 10, "critical")]),
        present=['fill="#c0392b"'])

    # 33. radial_gauge → large-arc-flag is 0 (not 1)
    # Arc syntax: A rx ry rotation large-arc-flag sweep x y
    # Correct: "A 75 75 0 0 1 ..." — large-arc-flag=0
    # Wrong:   "A 75 75 0 1 ..."  — large-arc-flag=1
    s = radial_gauge(75, 0, 100)
    if f"{75} 0 1 " in s:
        bad("radial_gauge → large-arc-flag must be 0",
            "found 'r 0 1 ' pattern (large-arc-flag=1) in arc")
    else:
        ok("radial_gauge → large-arc-flag is 0")

    # 34. line_chart sev=high → #e08e0b
    chk("line_chart sev=high → #e08e0b stroke",
        line_chart([10, 20, 15, 25, 18], sev="high"),
        present=['stroke="#e08e0b"'])

    # ── Contrast / accessibility checks (P1) ─────────────────────────────────

    # 35. rag_chip medium → no white text (amber fill; white = 1.64:1, fails WCAG)
    chk("rag_chip medium → no #FFFFFF text",
        rag_chip("medium", "Watch"), absent=['fill="#FFFFFF">'])

    # 36. rag_chip high → no white text (orange fill; white = 2.54:1, fails WCAG)
    chk("rag_chip high → no #FFFFFF text",
        rag_chip("high", "At Risk"), absent=['fill="#FFFFFF">'])

    # 37. rag_chip medium → dark text colour (#7A6410)
    chk("rag_chip medium → dark text #7A6410",
        rag_chip("medium", "Watch"), present=[_RAG["medium"]["text"]])

    # 38. rag_chip high → dark text colour (#8F5B06)
    chk("rag_chip high → dark text #8F5B06",
        rag_chip("high", "At Risk"), present=[_RAG["high"]["text"]])

    # 39. gantt chip with medium sev → no white text
    chk("gantt chip medium → no #FFFFFF",
        gantt([{"label": "Ph1", "start": "2026-01", "end": "2026-06",
                "sev": "medium"}]),
        absent=['fill="#FFFFFF">'])

    # 49. heat_matrix medium cell → the band's text colour on a mid ground
    chk("heat_matrix medium cell → band text colour",
        heat_matrix([[{"sev": "medium", "label": "M"}]]),
        present=[f'fill="{_RAG["medium"]["mid"]}"', f'fill="{_RAG["medium"]["text"]}">M'])

    # 50. stacked_bar high segment → the band's text colour on a mid ground
    chk("stacked_bar high segment → band text colour",
        stacked_bar([{"label": "Q1", "segments": [{"sev": "high", "value": 10}]}]),
        present=[f'fill="{_RAG["high"]["mid"]}"', f'fill="{_RAG["high"]["text"]}">10'])

    # ── Structural guards ────────────────────────────────────────────────────
    # These are the checks that would have caught round-2's shipped bugs. They
    # assert over EVERY mark, not one example, so a new call site cannot slip past.

    def _all_marks():
        """Every mark, exercising the branches the gallery does not."""
        z_hi = zones_from_threshold({"target": 90, "warn": 75, "critical": 60},
                                    "higher-better")
        z_lo = zones_from_threshold({"target": 5, "warn": 8, "critical": 12},
                                    "lower-better")
        return {
            "kpi_tile": kpi_tile(98, "Cov", delta="+3", sev="high", delta_sev="high"),
            "rag_chip": rag_chip("medium", "Watch"),
            "bullet_hi": bullet(72, 90, z_hi, axis_max=100),
            "bullet_lo": bullet(9, 5, z_lo, direction="lower-better", axis_max=15),
            "progress_bar": progress_bar(100, 100, label="Done", sev="good"),
            "fuel_tank": fuel_tank(73, 100, label="Budget"),
            # zones= branch, NOT sev= — this is the branch every renderer uses
            "radial_gauge_zones": radial_gauge(68, 0, 100, zones=z_hi),
            "radial_gauge_sev": radial_gauge(68, 0, 100, sev="medium"),
            "sparkline": sparkline([1, 2, 3, 4, 5], sev="good"),
            "sparkline_short": sparkline([1, 2]),
            "slope": slope([42, 67], labels=["Q3", "Q4"], sev="medium"),
            "line_chart": line_chart([1, 2, 3, 4, 5], sev="high"),
            "column_trend": column_trend([5, 10, 8]),
            "bar_chart": bar_chart([("A", 10, "good"), ("B", 20, "critical")]),
            # all four bands adjacent
            "heat_matrix": heat_matrix(
                [[{"sev": "good", "label": "G"}, {"sev": "medium", "label": "M"}],
                 [{"sev": "high", "label": "H"}, {"sev": "critical", "label": "C"}]]),
            "stacked_bar": stacked_bar([{"label": "Q1", "segments": [
                {"sev": "good", "value": 8}, {"sev": "medium", "value": 6},
                {"sev": "high", "value": 5}, {"sev": "critical", "value": 4}]}]),
            "small_multiples": small_multiples(
                [{"v": 1, "l": "a"}], lambda m: kpi_tile(m["v"], m["l"])),
            # sev= branch on every event
            "milestone_timeline": milestone_timeline(
                [{"label": "A", "date": "2026-02", "sev": "high"},
                 {"label": "B", "date": "2026-04", "sev": "good"}], today="2026-04"),
            "gantt": gantt([{"label": "P", "start": "2026-01", "end": "2026-06",
                             "pct": 0.5, "sev": "medium"}], today="2026-03"),
        }

    all_marks = _all_marks()

    # 40. No mark leaks a Python repr into an attribute. The token model went
    # str -> dict and two call sites kept indexing it directly; the resulting
    # fill="{'fill': '#e08e0b', ...}" is an invalid paint, so the browser drops
    # back to the initial value and the mark silently loses its colour.
    leaked = [n for n, s in all_marks.items()
              if "{'" in s or '{"' in s or ": '#" in s]
    if leaked:
        bad("no mark leaks a dict repr into an attribute",
            f"leaked in: {', '.join(sorted(leaked))}")
    else:
        ok("no mark leaks a dict repr into an attribute")

    # 41. No mark composites opacity. An opacity-blended colour is never what a
    # colour-pair check validated, so the contract cannot be enforced on it.
    op = [n for n, s in all_marks.items() if "opacity=" in s]
    if op:
        bad("no mark emits opacity=", f"found in: {', '.join(sorted(op))}")
    else:
        ok("no mark emits opacity=")

    # 42. No white text anywhere on a good/medium/high fill or mid tone. White on
    # good #30915B is 3.9:1; on amber 2.54:1; on yellow 1.64:1.
    white_on_light = []
    for n, s in all_marks.items():
        if '"#FFFFFF"' not in s:
            continue
        for frag in s.split("<text")[1:]:
            head = frag.split(">")[0]
            if 'fill="#FFFFFF"' in head:
                white_on_light.append(n)
                break
    if white_on_light:
        bad("no white text on a light RAG ground",
            f"found in: {', '.join(sorted(set(white_on_light)))}")
    else:
        ok("no white text on a light RAG ground")

    # 43. Every mark carries its own surface, so it stays legible pasted into a
    # deck, a PDF or a mail client whose ground we do not control.
    no_surf = []
    for n, s in all_marks.items():
        body = s.split(">", 1)[1] if ">" in s else ""
        if not body.lstrip().startswith("<rect width="):
            no_surf.append(n)
    if no_surf:
        bad("every mark opens with a surface rect",
            f"missing in: {', '.join(sorted(no_surf))}")
    else:
        ok("every mark opens with a surface rect")

    # 44. Bullet bands are DERIVED from _zone_sev, so they can never disagree with
    # the bar. Property test over 40 samples in both directions — the example-based
    # version of this check passed for two rounds while every lower-better band
    # was inverted and an amber bar sat on a red band.
    import re as _re
    band_ok = True
    detail = ""
    for direction, zt in (("higher-better", {"target": 90, "warn": 75, "critical": 60}),
                          ("lower-better", {"target": 5, "warn": 8, "critical": 12})):
        zs = zones_from_threshold(zt, direction)
        amax = 100 if direction == "higher-better" else 15
        svg = bullet(zs[0][0], zs[-1][0], zs, direction=direction, axis_max=amax)
        mid2sev = {_RAG[s]["mid"]: s for s in _RAG}
        bands = []
        for mx, mw, mf in _re.findall(
                r'<rect x="([\d.]+)" y="\d+" width="([\d.]+)" height="\d+" '
                r'fill="(#[0-9A-Fa-f]{6})"/>', svg):
            if mf in mid2sev:
                lo = (float(mx) - 20) / 240 * amax
                hi = lo + float(mw) / 240 * amax
                bands.append((lo, hi, mid2sev[mf]))
        if not bands:
            band_ok = False
            detail = f"{direction}: no bands parsed"
            break
        for i in range(40):
            x = amax * (i + 0.5) / 40
            drawn = next((s for lo, hi, s in bands if lo <= x < hi), None)
            expect = _zone_sev(x, zs, direction)
            if drawn != expect:
                band_ok = False
                detail = (f"{direction}: at {x:.2f} band is {drawn}, "
                          f"_zone_sev says {expect}")
                break
        if not band_ok:
            break
    if band_ok:
        ok("bullet bands agree with _zone_sev in both directions (40 samples)")
    else:
        bad("bullet bands agree with _zone_sev in both directions", detail)

    # 45. The gauge's zones= branch paints a real needle in the band's colour.
    chk("radial_gauge zones= branch → needle in band colour",
        all_marks["radial_gauge_zones"], present=['<polygon points=', 'fill="#e08e0b"'])

    # 46. Timeline sev dots paint a real fill.
    chk("milestone_timeline sev= → real dot fill",
        all_marks["milestone_timeline"], present=['fill="#e08e0b"'])

    # 47. Progress % label sits above the track, never on the fill.
    m = _re.search(r'<text x="\d+" y="(\d+)"[^>]*>100%</text>',
                   all_marks["progress_bar"])
    if m and int(m.group(1)) < 14:
        ok("progress_bar % label clears the track")
    else:
        bad("progress_bar % label clears the track",
            f"label y={m.group(1) if m else 'not found'}, track starts at 14")

    # 48. A four-band bullet ticks its zone boundaries — medium and high are
    # ΔE 13.3 apart and cannot be told apart by colour alone. Built by hand:
    # zones_from_threshold deliberately emits three bands (target is the tick,
    # not a boundary), so only a caller that really bands on four reaches this.
    chk("four-band bullet ticks its zone boundaries",
        bullet(72, 88, [(60, "critical"), (75, "high"), (88, "medium")],
               direction="higher-better", unit="%", axis_max=100),
        present=[">75%<", ">60%<"])

    # 54. A categorical stack emits NO RAG colour. Segments that encode category
    # rather than severity must not borrow the risk palette — that asserts a
    # danger the data never claimed.
    cat_stack = stacked_bar([
        {"label": "Q1", "segments": [{"label": "Phishing", "value": 12},
                                     {"label": "Web", "value": 7},
                                     {"label": "Insider", "value": 4}]},
        {"label": "Q2", "segments": [{"label": "Phishing", "value": 9},
                                     {"label": "Web", "value": 9},
                                     {"label": "Insider", "value": 3}]}])
    rag_any = [v[k] for v in _RAG.values() for k in ("fill", "mid", "tint")]
    chk("categorical stacked_bar → no RAG colour", cat_stack, absent=rag_any)

    # 55. A category keeps the same ramp step in every period, or the chart is
    # unreadable across time.
    seg_fills = _re.findall(
        r'width="[\d.]+" height="[\d.]+" fill="(#[0-9A-Fa-f]{6})"', cat_stack)
    if len(seg_fills) == 6 and seg_fills[:3] == seg_fills[3:]:
        ok("categorical stack keeps each category's colour across periods")
    else:
        bad("categorical stack keeps each category's colour across periods",
            f"got {seg_fills}")

    # 56. A band-less segment inside a RAG stack is unassessed, not a band.
    chk("band-less segment in a RAG stack → neutral, not a band colour",
        stacked_bar([{"label": "Q1", "segments": [
            {"sev": "good", "value": 8}, {"value": 3},
            {"sev": "critical", "value": 2}]}]),
        present=[f'fill="{_UNASSESSED}"'])

    # 57. The bullet bar carries a white keyline. Adjacent mid tones differ in hue
    # at similar lightness, so a bar sitting inside its own band dissolves into it.
    chk("bullet bar carries a white keyline",
        all_marks["bullet_hi"],
        present=[f'fill="{_RAG["high"]["fill"]}" stroke="{_SURFACE}"'])

    # 58. small_multiples sizes its cells from the marks. A hardcoded cell clips
    # any wider mark — the next cell's surface paints over the overflow, so value
    # and axis labels vanish with no error raised anywhere.
    wide = small_multiples(
        [{"n": 1}, {"n": 2}, {"n": 3}],
        lambda m: bullet(72, 90,
                         zones_from_threshold(
                             {"target": 90, "warn": 75, "critical": 60},
                             "higher-better"),
                         direction="higher-better", unit="%", axis_max=100))
    sm_w = _svg_size(wide)[0]
    if sm_w >= 3 * 280:
        ok("small_multiples cell fits the mark it renders")
    else:
        bad("small_multiples cell fits the mark it renders",
            f"3×280px marks laid out in only {sm_w}px")

    # 59. A categorical bar chart uses the ramp, never RAG.
    chk("categorical bar_chart → ramp, no RAG",
        bar_chart([("Phishing", 45), ("Web", 72), ("Insider", 31)],
                  categorical=True),
        present=[_MEASURE_RAMP[0]], absent=rag_any)

    # 60. An intensity heat matrix uses the ramp, never RAG. A count of findings
    # per control family is not a severity.
    chk("intensity heat_matrix → ramp, no RAG",
        heat_matrix([[{"value": 12, "label": "12"}, {"value": 3, "label": "3"}],
                     [{"value": 7, "label": "7"}, {"value": 1, "label": "1"}]]),
        present=[_MEASURE_RAMP[0]], absent=rag_any)

    # 61. Intensity is monotonic: the highest value takes the darkest step.
    hm = heat_matrix([[{"value": 12, "label": "hi"}, {"value": 1, "label": "lo"}]])
    order = _re.findall(r'rx="3" fill="(#[0-9A-Fa-f]{6})"', hm)
    if (len(order) == 2
            and _relative_luminance(order[0]) < _relative_luminance(order[1])):
        ok("heat_matrix intensity is monotonic (highest value darkest)")
    else:
        bad("heat_matrix intensity is monotonic", f"got {order}")

    # 62. zones_from_threshold must reproduce the metrics engine's own banding.
    # The engine bands on critical and warn only; `target` is the tick, not a
    # boundary. Promoting it to a boundary invented a fourth band, so a value
    # between warn and target drew a yellow band under a green status tile.
    def _engine_status(v, thr, direction):
        """Mirror of metrics_analysis.threshold_status."""
        c, w = thr.get("critical"), thr.get("warn")
        if direction == "higher-better":
            if c is not None and v < c:
                return "critical"
            if w is not None and v < w:
                return "warn"
        else:
            if c is not None and v > c:
                return "critical"
            if w is not None and v > w:
                return "warn"
        return "ok"

    STATUS_TO_SEV = {"ok": "good", "warn": "high", "critical": "critical"}
    agree = True
    detail = ""
    for direction, thr, lo, hi in (
            ("higher-better", {"target": 95.0, "warn": 90.0, "critical": 80.0}, 0, 100),
            ("lower-better", {"target": 2.0, "warn": 5.0, "critical": 10.0}, 0, 15)):
        zs = zones_from_threshold(thr, direction)
        for i in range(60):
            v = lo + (hi - lo) * (i + 0.5) / 60
            want = STATUS_TO_SEV[_engine_status(v, thr, direction)]
            got = _zone_sev(v, zs, direction)
            if got != want:
                agree = False
                detail = (f"{direction} at {v:.2f}: engine says {want}, "
                          f"zone says {got}")
                break
        if not agree:
            break
    if agree:
        ok("zones_from_threshold reproduces the engine's banding (120 samples)")
    else:
        bad("zones_from_threshold reproduces the engine's banding", detail)

    # 63. A bullet labels its target. An unlabelled tick is a line the reader has
    # to guess the value of, and the target is the one figure on the axis that is
    # a commitment rather than a gradation.
    chk("bullet labels its target tick",
        bullet(88, 95, zones_from_threshold(
            {"target": 95.0, "warn": 90.0, "critical": 80.0}, "higher-better"),
            direction="higher-better", unit="%", axis_max=100),
        present=[">95%<"])

    # 64. Thresholds outrank the axis ends. A bullet whose axis reads only 0 and
    # 100 states the scale and nothing about where the bands begin -- and the
    # bands are the whole claim the mark makes.
    chk("bullet labels a threshold in preference to an axis end",
        bullet(40, 100, zones_from_threshold(
            {"target": 100.0, "warn": 75.0, "critical": 50.0}, "higher-better"),
            direction="higher-better", unit="%", axis_max=100),
        present=[">50%<", ">75%<"])

    # 65. No mark emits an empty text node. A screen reader still walks one.
    empties = [n for n, s in all_marks.items() if "></text>" in s]
    empties += [n for n, s in (("slope_nolabels", slope([11, 8], unit=" d")),
                               ("tile_nolabel", kpi_tile(42, "")))
                if "></text>" in s]
    if empties:
        bad("no mark emits an empty text node", ", ".join(sorted(set(empties))))
    else:
        ok("no mark emits an empty text node")

    # 66. A slope formats its readings rather than stringifying them: a float that
    # is a whole number reads "11", not "11.0".
    chk("slope formats whole-number readings without a trailing .0",
        slope([11.0, 8.0], unit=" d"), present=[">11 d<", ">8 d<"],
        absent=["11.0", "8.0"])

    # 67. A tile steps its display size down rather than letting a long figure
    # run off the card -- a vanity metric is a big number by construction.
    big = kpi_tile("2,140,000", "Attacks blocked")
    small = kpi_tile("4", "Open P1s")
    import re as _re2
    b = int(_re2.search(r'font-size="(\d+)"[^>]*font-weight="700"', big).group(1))
    s_ = int(_re2.search(r'font-size="(\d+)"[^>]*font-weight="700"', small).group(1))
    if b < s_:
        ok("kpi_tile shrinks its display size for a long figure")
    else:
        bad("kpi_tile shrinks its display size for a long figure",
            f"long={b}px, short={s_}px")

    # 68. A gantt bar's LENGTH is its duration. The ordinal version spaced unique
    # dates evenly, so a one-day phase and a two-month phase drew identical bars
    # and the today line landed wherever the sort happened to put it.
    g_dur = gantt([
        {"label": "A", "start": "2026-01-01", "end": "2026-01-02", "pct": 1.0},
        {"label": "B", "start": "2026-01-02", "end": "2026-03-03", "pct": 1.0}])
    tracks = _re.findall(
        r'<rect x="[\d.]+" y="\d+" width="([\d.]+)" height="14" rx="3" '
        r'fill="' + _MEASURE_TRACK + '"', g_dur)
    if len(tracks) == 2 and float(tracks[1]) > float(tracks[0]) * 20:
        ok("gantt bar length is proportional to duration")
    else:
        bad("gantt bar length is proportional to duration",
            f"1-day vs 60-day bars measured {tracks}")

    # 69. Every stacked-bar segment carries its value, including one too short to
    # hold the label inside. The old rule skipped anything under 14px, which
    # dropped the number exactly where it mattered most: a small count is usually
    # the severe band, so on a real register High and Critical were the two that
    # lost theirs. A rule that lapses on its most important case is not a rule.
    sb = stacked_bar([{"label": "Now", "segments": [
        {"sev": "good", "value": 9}, {"sev": "medium", "value": 8},
        {"sev": "high", "value": 2}, {"sev": "critical", "value": 1}]}])
    printed = _re.findall(r'font-size="9"[^>]*>([^<]+)</text>', sb)
    if all(v in printed for v in ("9", "8", "2", "1")):
        ok("every stacked-bar segment carries its value, however short")
    else:
        bad("every stacked-bar segment carries its value, however short",
            f"printed {printed}, expected 9, 8, 2 and 1")

    # 70. An empty heat cell is hatched, not tinted. Against the lightest step of
    # the intensity ramp the old grey measured 1.19:1, so "not rated" and "lowest
    # on the page" were the same cell to a reader.
    hm_empty = heat_matrix([[{"value": 12, "label": "12"}, None]])
    hm_full = heat_matrix([[{"value": 12, "label": "12"},
                            {"value": 3, "label": "3"}]])
    if (f'url(#{_HATCH_ID})' in hm_empty and "<pattern" in hm_empty
            and "<pattern" not in hm_full):
        ok("an empty heat cell is hatched, and the defs ship only when used")
    else:
        bad("an empty heat cell is hatched, and the defs ship only when used",
            "hatch missing on the empty case, or emitted on the full one")

    # ── Design-intent checks (P2) ─────────────────────────────────────────────

    # 40. bullet zones use mid tones, not opacity compositing
    chk("bullet zones → no opacity='0.20'",
        bullet(65, 85, [(50, "critical"), (75, "high"), (85, "medium")]),
        absent=["opacity"])

    # ── Integration / direction normalisation (P3) ───────────────────────────

    # 41. bullet accepts direction="higher-better" without error
    try:
        bullet(65, 85, [(50, "critical"), (75, "high")], direction="higher-better")
        ok("bullet accepts direction='higher-better'")
    except ValueError as e:
        bad("bullet accepts direction='higher-better'", str(e))

    # 42. _zone_sev accepts direction="lower-better" without error
    try:
        _zone_sev(30, [(50, "high"), (80, "critical")], direction="lower-better")
        ok("_zone_sev accepts direction='lower-better'")
    except ValueError as e:
        bad("_zone_sev accepts direction='lower-better'", str(e))

    # ── Client brand override (P5) ───────────────────────────────────────────

    # 43. the shipped defaults pass the floors they are validated against.
    #     A validator its own defaults fail is a validator nobody can use.
    problems = validate_brand({})
    if problems:
        bad("CAC defaults pass their own floors", "; ".join(problems))
    else:
        ok("CAC defaults pass their own floors")

    # 44. a legal override reaches the marks
    try:
        set_brand({"ink": "#101820", "measure": "#7A3E9D",
                   "wordmark": "Northwind Group", "mark": "NW"})
        svg = progress_bar(50, 100)
        if "#7A3E9D" in svg and DEFAULT_BRAND["measure"] not in svg:
            ok("an override re-colours the measure bucket")
        else:
            bad("an override re-colours the measure bucket",
                "client hue absent, or the CAC hue survived")
    finally:
        set_brand()

    # 45. …and resetting restores CAC exactly, so nothing leaks between renders
    set_brand({"measure": "#7A3E9D"})
    set_brand()
    if (_MEASURE == DEFAULT_BRAND["measure"]
            and _MEASURE_RAMP == _CAC_MEASURE_RAMP
            and brand() == DEFAULT_BRAND):
        ok("reset restores CAC exactly")
    else:
        bad("reset restores CAC exactly", f"measure={_MEASURE} ramp={_MEASURE_RAMP[:2]}")

    # 46. no override at all leaves the marks byte-identical
    before = bar_chart([("A", 10), ("B", 20)])
    set_brand()
    if bar_chart([("A", 10), ("B", 20)]) == before:
        ok("set_brand() with no argument changes no output")
    else:
        bad("set_brand() with no argument changes no output")

    # 47. an overridden measure derives a ramp; adjacent steps stay ordered
    set_brand({"measure": "#7A3E9D"})
    lums = [_relative_luminance(c) for c in _MEASURE_RAMP]
    if (len(_MEASURE_RAMP) == 6 and _MEASURE_RAMP[1] == "#7A3E9D"
            and all(lums[i] < lums[i + 1] for i in range(5))):
        ok("an overridden measure derives a monotone ramp")
    else:
        bad("an overridden measure derives a monotone ramp", str(_MEASURE_RAMP))
    set_brand()

    # 48-53. every refusal fires, one guard at a time. Each block is legal in
    #        every respect except the one named, so a passing check proves *that*
    #        guard fired and not a neighbour's.
    refusals = [
        ("RAG is not overridable", {"critical": "#FF0000"}, "not overridable"),
        ("an unknown key is refused", {"accent": "#123456"}, "unknown brand key"),
        ("a malformed hex is refused", {"ink": "blue"}, "not a #rrggbb"),
        ("ink below 4.5:1 is refused", {"ink": "#AAAAAA"}, "needs 4.5:1"),
        ("a measure below 3:1 is refused", {"measure": "#CCE0F5"}, "needs 3.0:1"),
        ("a track darker than its fill is refused",
         {"measureTrack": "#0A0A0A"}, "inverts the mark"),
    ]
    for name, block, needle in refusals:
        try:
            set_brand(block)
            bad(name, "accepted a block that should have been refused")
            set_brand()
        except BrandError as e:
            if needle in str(e):
                ok(name)
            else:
                bad(name, f"refused for the wrong reason: {e}")

    # 54. a refused override leaves the previous brand untouched — a client whose
    #     palette fails gets CAC, never a half-applied hybrid.
    set_brand()
    try:
        set_brand({"ink": "#AAAAAA"})
    except BrandError:
        pass
    if _INK == DEFAULT_BRAND["ink"] and brand()["ink"] == DEFAULT_BRAND["ink"]:
        ok("a refused override leaves the active brand untouched")
    else:
        bad("a refused override leaves the active brand untouched", _INK)

    # 55. RAG survives an override. The whole point of the asymmetry.
    set_brand({"ink": "#101820", "measure": "#7A3E9D", "bg": "#FFFFFF"})
    svg = kpi_tile(4, "Open P1", sev="critical")
    if 'fill="#c0392b"' in svg:
        ok("RAG survives a brand override")
    else:
        bad("RAG survives a brand override", "critical no longer renders in #c0392b")
    set_brand()

    # 56-59. bar_chart: an unassessed row is not a zero row.
    b = bar_chart([("GV", 40), ("ID", 60), ("DE", None)])
    chk("an unassessed bar row hatches", b,
        present=[f'url(#{_HATCH_ID})', "not assessed", _HATCH_FG])
    chk("and a fully-measured chart ships no hatch defs",
        bar_chart([("GV", 40), ("ID", 60)]), absent=[_HATCH_ID])

    # The row must not appear as a measurement. A zero-width bar would be drawn as
    # width="0.0" and read as the worst result on the chart rather than an absent one.
    chk("an unassessed row draws no bar", b, absent=['width="0.0"'])

    # A chart with nothing measured at all still has to render. That case breaks a naive
    # implementation two ways at once — max() over an empty sequence, and a scale of zero to
    # divide by — and it is not exotic: it is a framework nobody has begun assessing, which
    # is precisely when a reader most needs to see the shape of what is missing.
    try:
        allnone = bar_chart([("DE", None), ("RS", None), ("RC", None)])
        if allnone.count("not assessed") == 3 and _HATCH_ID in allnone:
            ok("a chart with nothing measured renders as unassessed rows")
        else:
            bad("a chart with nothing measured renders as unassessed rows",
                f"{allnone.count('not assessed')} unassessed rows drawn")
    except Exception as exc:                                   # noqa: BLE001
        bad("a chart with nothing measured renders as unassessed rows",
            f"{type(exc).__name__}: {exc}")

    # 60. the default footer carries both clauses
    set_brand()
    if footer() == "A Cyber Aware Creation · Not affiliated with NIST":
        ok("the default footer carries maker and disclaimer")
    else:
        bad("the default footer carries maker and disclaimer", footer())

    # 57. white-labelling drops the maker and KEEPS the disclaimer
    set_brand({"whiteLabel": True, "wordmark": "Northwind Group"})
    f = footer()
    if _DISCLAIMER in f and "Cyber Aware" not in f and "Northwind" not in f:
        ok("white-label drops the maker, keeps the NIST disclaimer")
    else:
        bad("white-label drops the maker, keeps the NIST disclaimer", f)
    set_brand()

    # 57b. extra clauses survive white-labelling, and the maker name does not.
    #
    # "Not legal advice" is a statement about what the document IS, not about who made it.
    # A client rebranding a deliverable does not thereby acquire the standing to drop it,
    # so it sits on the same side of the line as the NIST disclaimer.
    set_brand({"whiteLabel": True, "wordmark": "Northwind Group"})
    wl = footer("Not legal advice")
    if ("Not legal advice" in wl and _DISCLAIMER in wl
            and "Cyber Aware" not in wl and "Northwind" not in wl):
        ok("white-label keeps an extra clause and still drops the maker")
    else:
        bad("white-label keeps an extra clause and still drops the maker", wl)
    set_brand()
    if footer("Not legal advice") == ("A Cyber Aware Creation · Not affiliated with NIST "
                                      "· Not legal advice"):
        ok("and an extra clause follows the disclaimer, not the maker")
    else:
        bad("and an extra clause follows the disclaimer, not the maker",
            footer("Not legal advice"))
    if footer("", "  ") == footer():
        ok("an empty extra clause adds no stray separator")
    else:
        bad("an empty extra clause adds no stray separator", footer("", "  "))

    # 57c. a page reproducing more than one framework names all of them. Naming only the
    # first would leave the other two implied, which is the overclaim this line exists to
    # rule out rather than commit.
    cases = [(("NIST",), "Not affiliated with NIST"),
             (("NIST", "ISO"), "Not affiliated with NIST or ISO"),
             (("NIST", "ISO", "CIS"), "Not affiliated with NIST, ISO, or CIS")]
    for names, want in cases:
        got = footer(unaffiliated=names)
        if got.endswith(want):
            ok("the disclaimer names %d body/bodies correctly" % len(names))
        else:
            bad("the disclaimer names %d body/bodies correctly" % len(names), got)
    if footer(unaffiliated=()) == footer():
        ok("an empty body list falls back to the default rather than to nothing")
    else:
        bad("an empty body list falls back to the default rather than to nothing",
            footer(unaffiliated=()))
    try:
        footer(unaffilated=("NIST",))          # deliberate typo
        bad("a misspelled keyword is refused", "accepted it silently")
    except TypeError:
        ok("a misspelled keyword is refused, not silently ignored")

    # 58. whiteLabel is a flag, not a truthy string — "false" must not enable it
    try:
        set_brand({"whiteLabel": "false"})
        bad("whiteLabel refuses a non-boolean", "accepted the string 'false'")
        set_brand()
    except BrandError as e:
        if "must be true or false" in str(e):
            ok("whiteLabel refuses a non-boolean")
        else:
            bad("whiteLabel refuses a non-boolean", str(e))

    print()
    if checks != 98:
        print(f"self-test: ran {checks} checks, expected 98")
        _sys.exit(1)
    if fails:
        print(f"self-test: {fails} of {checks} checks FAILED")
        _sys.exit(1)
    print(f"self-test: {checks}/{checks} checks passed")


# ── Gallery ───────────────────────────────────────────────────────────────────

def _gallery(out_path):
    marks = [
        ("1 · KPI Tile — no sev",
         kpi_tile(98, "Patch Coverage", delta="+3 pp", unit="%")),
        ("1 · KPI Tile — critical",
         kpi_tile(4, "Open P1 Incidents", sev="critical")),
        ("2 · RAG Chip — good",
         rag_chip("good", "On Track")),
        ("2 · RAG Chip — high",
         rag_chip("high", "At Risk")),
        ("3 · Bullet — higher-better (via zones_from_threshold)",
         bullet(72, 90,
                zones_from_threshold({"target": 90, "warn": 75, "critical": 60},
                                     "higher-better"),
                direction="higher-better", unit="%", axis_max=100)),
        ("3 · Bullet — lower-better (via zones_from_threshold)",
         bullet(9, 5,
                zones_from_threshold({"target": 5, "warn": 8, "critical": 12},
                                     "lower-better"),
                direction="lower-better", unit="%", axis_max=15)),
        ("4 · Progress Bar",
         progress_bar(65, 100, label="Sprint completion", sev="medium")),
        ("5 · Fuel Tank",
         fuel_tank(73, 100, label="Budget")),
        ("6 · Radial Gauge — zones= branch, needle + target tick",
         radial_gauge(68, 0, 100,
                      zones=zones_from_threshold(
                          {"target": 90, "warn": 75, "critical": 60},
                          "higher-better"),
                      direction="higher-better", target=90, unit="%")),
        ("7 · Sparkline",
         sparkline([12, 15, 11, 18, 14, 20, 17], unit="%", sev="good")),
        ("7 · Sparkline — under 4 readings",
         sparkline([12, 15, 11])),
        ("8 · Slope",
         slope([42, 67], labels=["Q3", "Q4"], unit="%")),
        ("9 · Line Chart",
         line_chart([10, 15, 12, 18, 16, 22, 19, 25],
                    labels=["Jan", "Feb", "Mar", "Apr",
                            "May", "Jun", "Jul", "Aug"],
                    sev="good")),
        ("10 · Column Trend",
         column_trend([8, 12, 10, 15, 13, 18],
                      labels=["Jan", "Feb", "Mar", "Apr", "May", "Jun"])),
        ("11 · Bar Chart — risk bands (sev → RAG)",
         bar_chart([("Cloud", 45, "good"), ("On-Prem", 72, "high"),
                    ("SaaS", 31, "good")])),
        ("11 · Bar Chart — categories (categorical=True → ramp)",
         bar_chart([("Phishing", 45), ("Web app", 72), ("Insider", 31),
                    ("Supply chain", 18)], categorical=True)),
        ("12 · Heat Matrix — intensity (no sev → ramp, darkest = highest)",
         heat_matrix(
             [[{"value": 12, "label": "12"}, {"value": 8, "label": "8"},
               {"value": 3, "label": "3"}],
              [{"value": 7, "label": "7"}, {"value": 1, "label": "1"},
               {"value": 5, "label": "5"}]],
             row_labels=["Access", "Config"],
             col_labels=["Q1", "Q2", "Q3"]
         )),
        ("12 · Heat Matrix — risk bands (sev → RAG)",
         heat_matrix(
             [[{"sev": "good", "label": "2"}, {"sev": "medium", "label": "5"},
               {"sev": "high", "label": "9"}],
              [{"sev": "critical", "label": "3"}, {"sev": "good", "label": "1"},
               None]],
             row_labels=["Infra", "Apps"],
             col_labels=["Confidentiality", "Integrity", "Availability"]
         )),
        ("13 · Stacked Bar — categorical (no sev → MEASURE ramp)",
         stacked_bar([
             {"label": "Q1",
              "segments": [{"label": "Phishing", "value": 12},
                           {"label": "Web", "value": 7},
                           {"label": "Insider", "value": 4},
                           {"label": "Supply chain", "value": 2}]},
             {"label": "Q2",
              "segments": [{"label": "Phishing", "value": 9},
                           {"label": "Web", "value": 9},
                           {"label": "Insider", "value": 3},
                           {"label": "Supply chain", "value": 5}]},
             {"label": "Q3",
              "segments": [{"label": "Phishing", "value": 7},
                           {"label": "Web", "value": 11},
                           {"label": "Insider", "value": 2},
                           {"label": "Supply chain", "value": 6}]},
         ])),
        ("13 · Stacked Bar — risk bands (sev → RAG)",
         stacked_bar([
             {"label": "Q1",
              "segments": [{"sev": "good", "value": 8},
                           {"sev": "medium", "value": 5},
                           {"sev": "high", "value": 4},
                           {"sev": "critical", "value": 3}]},
             {"label": "Q2",
              "segments": [{"sev": "good", "value": 11},
                           {"sev": "medium", "value": 6},
                           {"sev": "high", "value": 3},
                           {"sev": "critical", "value": 2}]},
             {"label": "Q3",
              "segments": [{"sev": "good", "value": 14},
                           {"sev": "medium", "value": 4},
                           {"sev": "high", "value": 3},
                           {"sev": "critical", "value": 1}]},
         ])),
        ("14 · Small Multiples — shared axis_max keeps the wall comparable",
         small_multiples(
             [{"value": 72, "target": 90, "label": "Patch"},
              {"value": 94, "target": 90, "label": "MFA"},
              {"value": 61, "target": 90, "label": "EDR"}],
             lambda m: bullet(
                 m["value"], m["target"],
                 zones_from_threshold({"target": 90, "warn": 75, "critical": 60},
                                      "higher-better"),
                 direction="higher-better", unit="%",
                 axis_max=m.get("axis_max")),
             axis_max=100
         )),
        ("15 · Milestone Timeline",
         milestone_timeline([
             {"label": "Detected", "date": "2026-03-02"},
             {"label": "Determined", "date": "2026-03-05", "sev": "high"},
             {"label": "Filed", "date": "2026-03-08", "sev": "good"},
             {"label": "DORA final report", "date": "2026-04-06", "sev": "medium"},
         ], today="2026-03-14")),
        ("16 · Gantt (with milestones + chip vocabulary)",
         gantt([
             {"label": "Discovery", "start": "2026-01", "end": "2026-02",
              "pct": 1.0, "sev": "good"},
             {"label": "Build", "start": "2026-02", "end": "2026-05",
              "pct": 0.6, "sev": "medium"},
             {"label": "Launch", "start": "2026-05", "end": "2026-07",
              "pct": 0.0, "sev": "high"},
         ], today="2026-04",
         milestones=[{"label": "Beta", "date": "2026-04"}])),
    ]

    items_html = ""
    for title, svg in marks:
        items_html += (
            '<div style="background:#FFFFFF;border:1px solid #DCD7C9;'
            'border-radius:8px;padding:16px;margin-bottom:16px;">'
            f'<p style="font-size:12px;color:#7F8C8D;'
            f'font-family:system-ui,sans-serif;margin:0 0 8px;">'
            f'{_esc(title)}</p>'
            f'{svg}'
            '</div>'
        )

    page = (
        "<!doctype html><html><head><meta charset=utf-8>"
        "<title>CAC Graphics Gallery</title>"
        '<meta name="color-scheme" content="light">'
        "<style>:root{color-scheme:light}"
        "body{background:#F6F4EE;color:#14171C;max-width:760px;margin:40px auto;"
        "font-family:system-ui,sans-serif;padding:20px;}</style>"
        "</head><body>"
        "<h1 style='font-size:20px;color:#2C3E50;margin-bottom:24px;'>"
        "CAC Graphics Library — Mark Gallery</h1>"
        + items_html
        + "</body></html>"
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"gallery written → {out_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(_sys.argv) < 2:
        print(__doc__)
        _sys.exit(0)
    cmd = _sys.argv[1]
    if cmd == "self-test":
        _self_test()
    elif cmd == "gallery":
        if len(_sys.argv) < 3:
            print("usage: cac_graphics.py gallery /path/to/out.html")
            _sys.exit(1)
        _gallery(_sys.argv[2])
    else:
        print(f"unknown command: {cmd!r}  (self-test | gallery)")
        _sys.exit(1)
