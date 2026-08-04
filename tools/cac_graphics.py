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
_PATINA        = "#2FA98C"   # chrome only — never a data mark
_INK           = "#14171C"   # brand ink (dark chrome / body text)
_MUTED         = "#4A4F58"   # brand muted (secondary text)
_BG            = "#F6F4EE"   # brand workbench

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


def zones_from_threshold(threshold, direction):
    """
    Convert engine threshold dict to zones list for bullet().

    threshold = {"target": x, "warn": y, "critical": z}
    direction = "higher-better" | "lower-better" (or without -better suffix)
    Returns [(threshold_value, sev), ...] suitable for bullet() and _zone_sev().
    """
    direction = _normalize_direction(direction)
    zones = []
    t = threshold.get("target")
    w = threshold.get("warn")
    c = threshold.get("critical")
    if direction == "higher":
        if c is not None:
            zones.append((c, "critical"))
        if w is not None:
            zones.append((w, "high"))
        if t is not None:
            zones.append((t, "medium"))
    else:
        if t is not None:
            zones.append((t, "medium"))
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
    delta_svg = ""
    if delta:
        delta_col = _sev_colour(delta_sev, "text") if delta_sev and delta_sev in _RAG else _MUTED
        delta_svg = (
            f'<text x="{w // 2}" y="82" text-anchor="middle" '
            f'font-size="13" fill="{delta_col}">{_esc(str(delta))}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">'
        f'<rect width="{w}" height="{h}" rx="6" fill="{_BG}" '
        f'stroke="#E0E0E0" stroke-width="1"/>'
        f'<rect x="0" y="0" width="4" height="{h}" rx="2" fill="{fill}"/>'
        f'<text x="{w // 2}" y="55" text-anchor="middle" font-size="32" '
        f'font-family="{_FONT_DISPLAY}" font-weight="700" '
        f'fill="{_INK}">{vtext}</text>'
        f'{delta_svg}'
        f'<text x="{w // 2}" y="100" text-anchor="middle" font-size="12" '
        f'font-family="{_FONT_BODY}" fill="{_MUTED}">{_esc(label)}</text>'
        f'</svg>'
    )


# ── Mark 2: RAG Chip ───────────────────────────────────────────────────────────

def rag_chip(sev, label):
    """Status chip: tint background + coloured dot + accessible dark text."""
    if sev not in _RAG:
        return ""
    tint = _RAG[sev]["tint"]
    dot_fill = _RAG[sev]["fill"]
    text_col = _RAG[sev]["text"]
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
    zone_rects = ""
    prev_x = 20.0
    for thresh, s in sorted_z:
        tx = to_x(thresh)
        mid = _RAG[s]["mid"] if s in _RAG else _MUTED
        zone_rects += (
            f'<rect x="{prev_x:.1f}" y="{bar_y}" '
            f'width="{tx - prev_x:.1f}" height="{bar_h}" '
            f'fill="{mid}"/>'
        )
        prev_x = tx
    end_x = to_x(scale_max)
    zone_rects += (
        f'<rect x="{prev_x:.1f}" y="{bar_y}" '
        f'width="{end_x - prev_x:.1f}" height="{bar_h}" '
        f'fill="{_RAG["good"]["mid"]}"/>'
    )

    bar_sev = _zone_sev(value, zones, direction)
    bar_fill = _RAG[bar_sev]["fill"] if bar_sev in _RAG else _MEASURE
    bar_text = _RAG[bar_sev]["text"] if bar_sev in _RAG else _MUTED
    val_x = to_x(value)

    # White measure lane punches through zone colours so the bar edge stays crisp
    lane = (
        f'<rect x="20" y="{bar_y + 7}" width="{end_x - 20:.1f}" '
        f'height="{bar_h - 14}" fill="#FFFFFF"/>'
    )
    val_bar = (
        f'<rect x="20" y="{bar_y + 7}" width="{val_x - 20:.1f}" '
        f'height="{bar_h - 14}" rx="2" fill="{bar_fill}"/>'
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
        label_svg = (
            f'<text x="20" y="{bar_y + bar_h + 14}" font-size="10" '
            f'font-family="{_FONT_BODY}" fill="{_MUTED}">0{_esc(unit)}</text>'
        )
        # Suppress axis max when target is near the end (would collide)
        if target / scale_max < 0.88:
            label_svg += (
                f'<text x="{end_x:.1f}" y="{bar_y + bar_h + 14}" '
                f'text-anchor="end" font-size="10" '
                f'font-family="{_FONT_BODY}" fill="{_MUTED}">'
                f'{_fmt(scale_max)}{_esc(unit)}</text>'
            )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">'
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
        f'viewBox="0 0 {w} {h}">'
        f'<rect x="20" y="14" width="{w - 40}" height="16" rx="8" '
        f'fill="{_MEASURE_TRACK}"/>'
        f'<rect x="20" y="14" width="{bar_w:.1f}" height="16" rx="8" fill="{fill}"/>'
        f'<text x="{w - 18}" y="26" text-anchor="end" font-size="11" '
        f'font-family="{_FONT_BODY}" fill="{_INK}">{pct_label}</text>'
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
        f'viewBox="0 0 {w} {h}">'
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

def radial_gauge(value, min_v, max_v, zones=None, sev=""):
    """Half-circle gauge 180°. large-arc-flag is always 0."""
    w, h = 200, 120
    cx, cy, r = 100, 100, 75
    rng = max_v - min_v if max_v != min_v else 1
    pct = _clamp((value - min_v) / rng, 0, 1)

    # Sweep from left (π) towards right (0); counter-clockwise in math, but
    # SVG y-axis is flipped so sweep-flag=1 is visually clockwise (upward arc).
    start_a = _math.pi
    end_a = start_a - _math.pi * pct

    def polar(angle, radius=r):
        return cx + radius * _math.cos(angle), cy - radius * _math.sin(angle)

    sx, sy = polar(start_a)
    ex, ey = polar(end_a)
    bg_ex, bg_ey = polar(0)

    if zones:
        fill = _RAG.get(_zone_sev(value, zones), _MEASURE)
    elif sev:
        fill = _sev_colour(sev)
    else:
        fill = _MEASURE

    # Background track: M left A r r rotation=0 large-arc=0 sweep=1 right
    track = (
        f'<path d="M {sx:.2f} {sy:.2f} A {r} {r} 0 0 1 {bg_ex:.2f} {bg_ey:.2f}" '
        f'fill="none" stroke="{_MEASURE_TRACK}" stroke-width="14" '
        f'stroke-linecap="round"/>'
    )

    val_arc = ""
    if pct > 0.005:
        # large-arc-flag MUST be 0 (arc always < 180°)
        val_arc = (
            f'<path d="M {sx:.2f} {sy:.2f} A {r} {r} 0 0 1 {ex:.2f} {ey:.2f}" '
            f'fill="none" stroke="{fill}" stroke-width="14" stroke-linecap="round"/>'
        )

    val_label = (
        f'<text x="{cx}" y="{cy - 8}" text-anchor="middle" '
        f'font-size="24" font-weight="700" '
        f'font-family="{_FONT_BODY}" fill="{_INK}">'
        f'{_esc(str(value))}</text>'
    )
    range_labels = (
        f'<text x="{sx:.1f}" y="{sy + 16:.1f}" text-anchor="middle" font-size="10" '
        f'font-family="{_FONT_BODY}" fill="{_MUTED}">{_esc(str(min_v))}</text>'
        f'<text x="{bg_ex:.1f}" y="{bg_ey + 16:.1f}" text-anchor="middle" '
        f'font-size="10" font-family="{_FONT_BODY}" fill="{_MUTED}">'
        f'{_esc(str(max_v))}</text>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">'
        f'{track}{val_arc}{val_label}{range_labels}'
        f'</svg>'
    )


# ── Mark 7: Sparkline ─────────────────────────────────────────────────────────

def sparkline(readings, unit="", sev=""):
    """Returns a note SVG if fewer than 4 readings — never a bare empty string."""
    if len(readings) < 4:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="160" height="20" '
            f'viewBox="0 0 160 20">'
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
        f'viewBox="0 0 {w} {h}">'
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
    lbl = labels or ["", ""]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">'
        f'<line x1="{x0}" y1="{y0:.1f}" x2="{x1}" y2="{y1:.1f}" '
        f'stroke="{fill}" stroke-width="2.5" stroke-linecap="round"/>'
        f'<circle cx="{x0}" cy="{y0:.1f}" r="4" fill="{fill}"/>'
        f'<circle cx="{x1}" cy="{y1:.1f}" r="4" fill="{fill}"/>'
        f'<text x="{x0}" y="{y0 - 6:.1f}" text-anchor="middle" font-size="11" '
        f'font-family="{_FONT_BODY}" fill="{_INK}">'
        f'{_esc(str(readings[0]))}{_esc(unit)}</text>'
        f'<text x="{x1}" y="{y1 - 6:.1f}" text-anchor="middle" font-size="11" '
        f'font-family="{_FONT_BODY}" fill="{_INK}">'
        f'{_esc(str(readings[1]))}{_esc(unit)}</text>'
        f'<text x="{x0}" y="{h - 2}" text-anchor="middle" font-size="10" '
        f'font-family="{_FONT_BODY}" fill="{_MUTED}">{_esc(str(lbl[0]))}</text>'
        f'<text x="{x1}" y="{h - 2}" text-anchor="middle" font-size="10" '
        f'font-family="{_FONT_BODY}" fill="{_MUTED}">{_esc(str(lbl[1]))}</text>'
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
        f'viewBox="0 0 {w} {h}">'
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
        f'viewBox="0 0 {w} {h}">'
        f'<line x1="{pad_x}" y1="{pad_y + chart_h}" '
        f'x2="{w - pad_x}" y2="{pad_y + chart_h}" '
        f'stroke="#E0E0E0" stroke-width="1"/>'
        f'{cols}'
        f'</svg>'
    )


# ── Mark 11: Bar Chart ────────────────────────────────────────────────────────

def bar_chart(items):
    """Horizontal bar chart. items = [(label, value) or (label, value, sev)]."""
    if not items:
        return ""
    pad_x, pad_y = 90, 10
    row_h = 28
    h = pad_y * 2 + len(items) * row_h
    w = 300
    chart_w = w - pad_x - 20
    mx = max((item[1] for item in items), default=1)
    if mx == 0:
        mx = 1

    bars = ""
    for i, item in enumerate(items):
        lbl = item[0]
        val = item[1]
        sev = item[2] if len(item) > 2 else None
        fill = _sev_colour(sev) if sev else _MEASURE
        bw = val / mx * chart_w
        y = pad_y + i * row_h
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
        f'viewBox="0 0 {w} {h}">{bars}</svg>'
    )


# ── Mark 12: Heat Matrix ──────────────────────────────────────────────────────

def heat_matrix(cells, row_labels=None, col_labels=None):
    """Heat matrix. cells[i][j] = {sev, label} or None."""
    if not cells:
        return ""
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
            if cell is None:
                fill = "#F0F0F0"
                txt = ""
                sev = ""
            else:
                sev = cell.get("sev", "")
                fill = _RAG[sev]["fill"] if sev and sev in _RAG else _MEASURE
                txt = cell.get("label", "")
            out += (
                f'<rect x="{x + 1}" y="{y + 1}" '
                f'width="{cell_sz - 2}" height="{cell_sz - 2}" '
                f'rx="3" fill="{fill}" opacity="0.85"/>'
            )
            if txt:
                # good/critical fills are dark enough for white; amber/yellow need ink
                txt_col = "#FFFFFF" if sev in ("good", "critical") else _INK
                out += (
                    f'<text x="{x + cell_sz // 2}" '
                    f'y="{y + cell_sz // 2 + 4}" '
                    f'text-anchor="middle" font-size="11" '
                    f'font-family="{_FONT_BODY}" '
                    f'fill="{txt_col}">{_esc(str(txt))}</text>'
                )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">{out}</svg>'
    )


# ── Mark 13: Stacked Bar ──────────────────────────────────────────────────────

def stacked_bar(periods):
    """Stacked bar chart. periods = [{label, segments:[{sev, value}]}]."""
    if not periods:
        return ""
    pad_x, pad_y, pad_b = 20, 10, 24
    w = max(280, len(periods) * 60 + 40)
    h = 140
    chart_h = h - pad_y - pad_b

    totals = [sum(s.get("value", 0) for s in p.get("segments", [])) for p in periods]
    mx = max(totals) if totals else 1
    if mx == 0:
        mx = 1

    n = len(periods)
    gap = (w - 2 * pad_x) / n
    bar_w = gap * 0.6

    out = ""
    for i, period in enumerate(periods):
        x = pad_x + i * gap + (gap - bar_w) / 2
        y_cur = pad_y + chart_h
        for seg in period.get("segments", []):
            sev = seg.get("sev", "")
            val = seg.get("value", 0)
            # segment fills use RAG or MEASURE; _PATINA is never a segment fill
            fill = _RAG[sev]["fill"] if sev and sev in _RAG else _MEASURE
            seg_h = val / mx * chart_h
            y_cur -= seg_h
            out += (
                f'<rect x="{x:.1f}" y="{y_cur:.1f}" '
                f'width="{bar_w:.1f}" height="{seg_h:.1f}" fill="{fill}"/>'
            )
            # Mandatory label — ΔE 13.3 between medium and high means colour
            # alone cannot distinguish them; label when the segment is tall enough
            if seg_h >= 14 and val:
                txt_col = "#FFFFFF" if sev in ("good", "critical") else _INK
                out += (
                    f'<text x="{x + bar_w / 2:.1f}" '
                    f'y="{y_cur + seg_h / 2 + 4:.1f}" '
                    f'text-anchor="middle" font-size="9" '
                    f'font-family="{_FONT_BODY}" fill="{txt_col}">'
                    f'{_esc(_fmt(val))}</text>'
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
        f'viewBox="0 0 {w} {h}">'
        f'<line x1="{pad_x}" y1="{pad_y + chart_h}" '
        f'x2="{w - pad_x}" y2="{pad_y + chart_h}" '
        f'stroke="#E0E0E0" stroke-width="1"/>'
        f'{out}'
        f'</svg>'
    )


# ── Mark 14: Small Multiples ──────────────────────────────────────────────────

def small_multiples(metrics, mark_fn):
    """Grid of same mark. mark_fn(metric) -> SVG string."""
    if not metrics:
        return ""
    cols = min(3, len(metrics))
    rows = (len(metrics) + cols - 1) // cols
    cell_w, cell_h = 220, 130
    w = cols * cell_w
    h = rows * cell_h
    out = ""
    for idx, m in enumerate(metrics):
        col = idx % cols
        row = idx // cols
        inner = mark_fn(m)
        out += (
            f'<g transform="translate({col * cell_w},{row * cell_h})">'
            f'{inner}'
            f'</g>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">{out}</svg>'
    )


# ── Mark 15: Milestone Timeline ───────────────────────────────────────────────

def milestone_timeline(events, today=""):
    """
    Vertical milestone list. events = [{label, date, sev}].
    today dashed line = PATINA. Dots: RAG if sev else INK.
    """
    if not events:
        return ""
    row_h = 36
    h = len(events) * row_h + 20
    w = 400
    dot_x = 100

    out = (
        f'<line x1="{dot_x}" y1="10" x2="{dot_x}" y2="{h - 10}" '
        f'stroke="#C0C0C0" stroke-width="1.5"/>'
    )

    today_y = None
    for i, ev in enumerate(events):
        sev = ev.get("sev", "")
        fill = _RAG.get(sev) if sev else None
        if fill is None:
            fill = _INK
        cy = 10 + i * row_h + row_h // 2
        out += (
            f'<circle cx="{dot_x}" cy="{cy}" r="7" fill="{fill}"/>'
            f'<text x="{dot_x + 14}" y="{cy + 4}" font-size="12" '
            f'font-family="{_FONT_BODY}" fill="{_INK}">'
            f'{_esc(ev.get("label", ""))}</text>'
        )
        if ev.get("date"):
            out += (
                f'<text x="{dot_x - 14}" y="{cy + 4}" text-anchor="end" '
                f'font-size="10" font-family="{_FONT_BODY}" '
                f'fill="{_MUTED}">{_esc(str(ev["date"]))}</text>'
            )
        if today and str(ev.get("date", "")) == today:
            today_y = cy

    if today:
        ty = today_y if today_y is not None else h // 2
        out += (
            f'<line x1="10" y1="{ty}" x2="{w - 10}" y2="{ty}" '
            f'stroke="{_PATINA}" stroke-width="1.5" stroke-dasharray="5,3"/>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">{out}</svg>'
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
    unique = sorted(set(all_dates))
    n = len(unique)
    chart_w = w - lbl_w - pct_col_w - chip_col_w - 8
    date_pos = {d: i / max(n - 1, 1) for i, d in enumerate(unique)}
    h = pad_y + len(phases) * row_h + 20

    def to_x(d):
        return lbl_w + date_pos.get(str(d), 0) * chart_w

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
            chip_tint = _RAG[sev]["tint"]
            chip_dot  = _RAG[sev]["fill"]
            chip_txt  = _RAG[sev]["text"]
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

    # Today line
    if today and today in date_pos:
        tx = to_x(today)
        out += (
            f'<line x1="{tx:.1f}" y1="{pad_y - 10}" '
            f'x2="{tx:.1f}" y2="{h - 10}" '
            f'stroke="{_PATINA}" stroke-width="1.5" stroke-dasharray="5,3"/>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" style="max-width:100%;height:auto">{out}</svg>'
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
        present=["#c0392b"])

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
        progress_bar(50, 100, sev="critical"), present=["#c0392b"])

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
        sparkline([1, 2, 3, 4], sev="medium"), present=["#e8c547"])

    # 13. slope sev=medium → #e8c547 (not coloured by direction of change)
    chk("slope sev=medium → #e8c547 (declining ok)",
        slope([10, 5], sev="medium"), present=["#e8c547"])

    # 14. bullet value in high zone → #e08e0b
    chk("bullet value in high zone → #e08e0b",
        bullet(65, 90, [(50, "critical"), (80, "high"), (100, "medium")]),
        present=["#e08e0b"])

    # 15. bullet value in crit zone → #c0392b
    chk("bullet value in crit zone → #c0392b",
        bullet(30, 90, [(50, "critical"), (80, "high"), (100, "medium")]),
        present=["#c0392b"])

    # 16. bullet lower-better high value → crit fill
    chk("bullet lower-better high value → crit",
        bullet(95, 70, [(80, "high"), (90, "critical")], direction="lower"),
        present=["#c0392b"])

    # 17. heat_matrix sev=critical → #c0392b
    chk("heat_matrix sev=critical → #c0392b",
        heat_matrix([[{"sev": "critical", "label": "H"}]]),
        present=["#c0392b"])

    # 18. heat_matrix no sev → MEASURE
    chk("heat_matrix no sev → MEASURE",
        heat_matrix([[{"label": "X"}]]),
        present=[_MEASURE])

    # 19. stacked_bar critical segment → #c0392b
    chk("stacked_bar critical segment → #c0392b",
        stacked_bar([{"label": "Q1",
                      "segments": [{"sev": "critical", "value": 5}]}]),
        present=["#c0392b"])

    # 20. stacked_bar → no PATINA in segment fills
    chk("stacked_bar → no patina",
        stacked_bar([{"label": "Q1",
                      "segments": [{"sev": "good", "value": 3},
                                   {"sev": "high", "value": 2}]}]),
        absent=[_PATINA])

    # 21. milestone_timeline event no sev → no RAG hex
    chk("milestone no-sev event → no RAG",
        milestone_timeline([{"label": "Kick-off", "date": "2026-01"}]),
        absent=rag_vals)

    # 22. milestone_timeline event with sev=high → #e08e0b
    chk("milestone sev=high → #e08e0b",
        milestone_timeline([{"label": "Deadline", "date": "2026-06",
                             "sev": "high"}]),
        present=["#e08e0b"])

    # 23. milestone_timeline today → PATINA
    chk("milestone today → patina",
        milestone_timeline([{"label": "Now", "date": "2026-03"}],
                           today="2026-03"),
        present=[_PATINA])

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
        present=["#30915B", "ON TRACK"])

    # 27. gantt today → PATINA
    chk("gantt today → patina",
        gantt([{"label": "Ph1", "start": "2026-01", "end": "2026-06"}],
              today="2026-03"),
        present=[_PATINA])

    # 28. rag_chip "good" → #30915B
    chk("rag_chip good → #30915B", rag_chip("good", "On Track"),
        present=["#30915B"])

    # 29. rag_chip "critical" → #c0392b
    chk("rag_chip critical → #c0392b", rag_chip("critical", "At Risk"),
        present=["#c0392b"])

    # 30. column_trend → no PATINA
    chk("column_trend → no patina", column_trend([5, 10, 8, 12]),
        absent=[_PATINA])

    # 31. bar_chart no sev → MEASURE
    chk("bar_chart no sev → MEASURE",
        bar_chart([("Item A", 10), ("Item B", 20)]),
        present=[_MEASURE])

    # 32. bar_chart sev=critical → #c0392b
    chk("bar_chart sev=critical → #c0392b",
        bar_chart([("Item A", 10, "critical")]),
        present=["#c0392b"])

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
    chk("line_chart sev=high → #e08e0b",
        line_chart([10, 20, 15, 25, 18], sev="high"),
        present=["#e08e0b"])

    # ── Contrast / accessibility checks (P1) ─────────────────────────────────

    # 35. rag_chip medium → no white text (amber fill; white = 1.64:1, fails WCAG)
    chk("rag_chip medium → no #FFFFFF text",
        rag_chip("medium", "Watch"), absent=["#FFFFFF"])

    # 36. rag_chip high → no white text (orange fill; white = 2.54:1, fails WCAG)
    chk("rag_chip high → no #FFFFFF text",
        rag_chip("high", "At Risk"), absent=["#FFFFFF"])

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
        absent=["#FFFFFF"])

    # 40. heat_matrix medium cell → ink text, not white (amber fill)
    chk("heat_matrix medium cell → ink text",
        heat_matrix([[{"sev": "medium", "label": "M"}]]),
        present=[f'fill="{_INK}">M'])

    # 41. stacked_bar high segment → ink text, not white (amber fill)
    chk("stacked_bar high segment → ink label",
        stacked_bar([{"label": "Q1", "segments": [{"sev": "high", "value": 10}]}]),
        present=[f'fill="{_INK}">10'])

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

    print()
    if checks != 44:
        print(f"self-test: ran {checks} checks, expected 44")
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
        ("3 · Bullet Graph",
         bullet(72, 85, [(60, "critical"), (75, "high"), (85, "medium")],
                unit="%")),
        ("4 · Progress Bar",
         progress_bar(65, 100, label="Sprint completion", sev="medium")),
        ("5 · Fuel Tank",
         fuel_tank(73, 100, label="Budget")),
        ("6 · Radial Gauge",
         radial_gauge(68, 0, 100, sev="medium")),
        ("7 · Sparkline",
         sparkline([12, 15, 11, 18, 14, 20, 17], unit="%", sev="good")),
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
        ("11 · Bar Chart",
         bar_chart([("Cloud", 45, "good"), ("On-Prem", 72, "high"),
                    ("SaaS", 31, "good")])),
        ("12 · Heat Matrix",
         heat_matrix(
             [[{"sev": "good", "label": "L"}, {"sev": "high", "label": "H"},
               None],
              [{"sev": "critical", "label": "C"}, {"sev": "medium", "label": "M"},
               {"label": "?"}]],
             row_labels=["Infra", "Apps"],
             col_labels=["Confidentiality", "Integrity", "Availability"]
         )),
        ("13 · Stacked Bar",
         stacked_bar([
             {"label": "Q1",
              "segments": [{"sev": "good", "value": 8},
                           {"sev": "high", "value": 3}]},
             {"label": "Q2",
              "segments": [{"sev": "good", "value": 10},
                           {"sev": "medium", "value": 4}]},
             {"label": "Q3",
              "segments": [{"sev": "good", "value": 12},
                           {"sev": "critical", "value": 2}]},
         ])),
        ("14 · Small Multiples",
         small_multiples(
             [{"v": 98, "l": "Coverage"}, {"v": 4, "l": "Open P1s"},
              {"v": 14, "l": "Avg Days"}],
             lambda m: kpi_tile(m["v"], m["l"])
         )),
        ("15 · Milestone Timeline",
         milestone_timeline([
             {"label": "Design complete", "date": "2026-02"},
             {"label": "Build", "date": "2026-04", "sev": "high"},
             {"label": "Release", "date": "2026-07", "sev": "good"},
         ], today="2026-04")),
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
            '<div style="background:#fff;border:1px solid #e0e0e0;'
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
        "<style>body{background:#F8F9FA;max-width:700px;margin:40px auto;"
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
