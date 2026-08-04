#!/usr/bin/env python3
"""Shared rendering pieces for the metrics-register reports.

Each skill in this toolkit carries its own `_common.py` rather than importing a shared
one. That duplication is deliberate and is documented in the siblings: every shipped
script must run standalone, so a cross-skill import needs sys.path surgery and breaks the
moment a single skill directory is used on its own.

Two reports are built on this: an operational view for the team and an executive view for
the board. The executive view never writes board language — it composes the sidecar that
`ciso-board-translation` produces, and renders a marked placeholder where a slot is unfilled.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys

# Vendored alongside this file, for the same reason this file is vendored: a
# shipped script must run from its own skill directory with no path surgery.
# tools/check-versions.py fails if this copy drifts from tools/cac_graphics.py.
import cac_graphics as G

# --- Brand tokens (assets/brand.md) ------------------------------------------
# Patina is the brand/action accent and never encodes a measurement.
INK = "#14171C"
LIME = "#EAE7DF"
PATINA = "#2FA98C"
SLATE = "#666D7C"
WB = "#F6F4EE"
WB_SURF = "#FFFFFF"
WB_LINE = "#D8D3C6"
MUTED = "#4A4F58"

# Threshold status is a STATUS palette, not a sequential ramp: the four values are named
# states, not points on a scale. Kept distinct from nist-csf's coverage ramp and the
# crosswalk band ramp for the reason those two are distinct from each other — sharing a
# ramp across two measures asserts an equivalence they do not have.
#
# Light fill with dark ink, so every chip clears AA against its own background by a wide
# margin rather than sitting near the line. Colour never carries the meaning alone: the
# status word is always rendered inside the chip.
STATUS_FILL = {
    "ok":           ("#E3EDE4", "#2F5D3A"),
    "warn":         ("#F7EBD9", "#7A5218"),
    "critical":     ("#F6E0DC", "#7C3A32"),
    "no-threshold": ("#EFEDE7", MUTED),
    "no-reading":   ("#EFEDE7", MUTED),
}
STATUS_LABEL = {
    "ok": "within threshold",
    "warn": "past warn",
    "critical": "past critical",
    "no-threshold": "no threshold set",
    "no-reading": "no reading yet",
}

# Trend is shown as a word plus a mark. The mark is never the only carrier — a reader who
# cannot resolve the glyph still gets the word, and a reader in monochrome gets both.
TREND_MARK = {"gaining": "▲", "slipping": "▼", "holding": "▬", "no-prior": "·"}
TREND_LABEL = {
    "gaining": "gaining",
    "slipping": "slipping",
    "holding": "holding",
    "no-prior": "first reading",
}

AGE_LABEL = {
    "within": "within cadence",
    "approaching": "approaching cadence",
    "beyond": "past cadence",
    "wellBeyond": "well past cadence",
}

# --- Engine status -> the graphics library's RAG band -------------------------
# One mapping, used by every mark on the page, so the chip, the graphic and the
# count cannot disagree about the same metric.
#
# `warn` maps to `high`, not `medium`. The engine bands on critical and warn only,
# and cac_graphics.zones_from_threshold mirrors exactly that: below critical is
# `critical`, below warn is `high`, anything past warn is `good`. Mapping warn to
# `medium` would put a yellow chip beside an amber bullet band for one value.
#
# The statusless states map to None rather than to a band. A metric with no agreed
# limit is not a status, so it renders in the measure colour -- returning a band
# here would invent the threshold the engine declined to assert.
STATUS_SEV = {
    "ok": "good",
    "warn": "high",
    "critical": "critical",
    "no-threshold": None,
    "no-reading": None,
}


def sev_for(row: dict):
    """The RAG band for a metric row, or None when it has no status."""
    return STATUS_SEV.get(row.get("status"))


# A percent bullet uses the full 0-100 axis so that a wall of coverage metrics is
# comparable at a glance. But that only helps when the metric actually lives on
# that scale. A phishing click rate banded at 2 / 5 / 10 percent has its entire
# meaningful range inside the first tenth of the bar: every threshold collapses
# into the left edge, the labels collide, and the mark stops answering the one
# question it exists for. Comparability is worth having; it is not worth an
# unreadable bar.
#
# So the shared ceiling applies only when the metric reaches a reasonable part of
# it. Below that the bullet scales to its own data, which is what the library
# does when axis_max is omitted.
AXIS_FULL_SCALE_FLOOR = 0.4


def _axis_max(row: dict, thr: dict, unit: str):
    """100 for a percent metric that uses the scale; None (auto) otherwise."""
    if unit != "percent":
        return None
    reach = max([v for v in (row.get("value"), thr.get("target"), thr.get("warn"),
                             thr.get("critical")) if v is not None] or [0])
    return 100 if reach >= 100 * AXIS_FULL_SCALE_FLOOR else None


def mark_for(row: dict) -> str:
    """The SVG mark for one metric, dispatched on the engine's resolved `viz`.

    `viz` is resolved once in metrics_analysis.resolve_viz and travels in the
    analysis JSON; nothing is re-decided here. That is what keeps one metric
    rendering as the same mark in the operational view, the executive view and
    the board pack.

    Every branch passes the engine's own value, threshold, direction and status
    straight through -- no renderer arithmetic on top of the numbers it was
    handed.
    """
    viz = row.get("viz") or "tile"
    sev = sev_for(row)
    value = row.get("value")
    unit = row.get("unit") or ""
    if value is None:
        return ""

    thr = row.get("threshold") or {}
    direction = row.get("direction") or "higher-better"
    target = thr.get("target")
    zones = G.zones_from_threshold(thr, direction) if sev else []
    # The mark's own numbers carry the unit. Without it a dwell-time slope reads
    # "11 -> 8" and the reader has to go looking for what the figures are in.
    # `currency` is deliberately absent: a prefix is not a suffix, and a mark that
    # rendered "1200$" would be worse than one that rendered nothing.
    suffix = {"percent": "%", "days": " d", "ratio": "x"}.get(unit, "")
    readings = row.get("readings") or []

    if viz == "bullet" and zones:
        return G.bullet(value, target if target is not None else value, zones,
                        direction=direction, unit=suffix,
                        axis_max=_axis_max(row, thr, unit))
    if viz == "progress" and target:
        return G.progress_bar(value, target, label="", sev=sev or "")
    if viz == "tank" and target:
        return G.fuel_tank(value, target, label="")
    if viz == "gauge" and zones:
        return G.radial_gauge(value, 0, max(100, value), zones=zones,
                              direction=direction, target=target, unit=suffix)
    if viz == "sparkline":
        # The library suppresses below 4 readings itself, returning a visible
        # note rather than an empty string.
        return G.sparkline(readings, unit=suffix, sev=sev or "")
    # A slope's two ends are periods, not just positions. The engine knows only
    # the latest period, so the earlier end is labelled "prior" rather than
    # invented -- naming a quarter the store never recorded would be a fabrication
    # in the one place a reader is most likely to trust it.
    slope_labels = ["prior", row.get("period") or "latest"]
    if viz == "slope" and len(readings) == 2:
        return G.slope(readings, labels=slope_labels, unit=suffix, sev=sev or "")
    if viz == "line" and len(readings) >= 4:
        return G.line_chart(readings, unit=suffix, sev=sev or "")
    if viz == "line" and len(readings) == 2:
        # The standard's own fallback: two points are a slope, never a line.
        return G.slope(readings, labels=slope_labels, unit=suffix, sev=sev or "")
    if viz == "column" and readings:
        return G.column_trend(readings, unit=suffix)

    # `tile` and every unsatisfied branch above land here: a bare number, in the
    # measure colour when the metric has no band -- no gauge, no RAG.
    return G.kpi_tile(fmt_value(value, unit), "", sev=sev or "")

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700'
         '&family=Space+Grotesk:wght@500;600&display=swap" rel="stylesheet">')

DISCLAIMER = "A Cyber Aware Creation · Not affiliated with NIST"
PLACEHOLDER = ("Board narrative not supplied. Run the ciso-board-translation skill over this "
               "register and pass its output with --translations to replace this block.")


def esc(s) -> str:
    return html.escape("" if s is None else str(s))


def fmt_value(value, unit: str) -> str:
    """A reading in its own unit. No rounding that would change what was recorded."""
    if value is None:
        return "—"
    if float(value).is_integer():
        text = f"{int(value):,}"
    else:
        text = f"{value:,.2f}".rstrip("0").rstrip(".")
    return {"percent": text + "%", "days": text + " d", "currency": "$" + text}.get(unit, text)


def fmt_delta(delta, unit: str) -> str:
    """The signed difference, sign always shown. It is not flipped to match the verdict.

    A lower-better metric that worsened from 8 to 14 reads `slipping` and `+6`. Hiding the
    sign to agree with the verdict would make the arithmetic irreproducible, and the two
    fields answer different questions.
    """
    if delta is None:
        return "—"
    return ("+" if delta > 0 else "") + fmt_value(delta, unit)


class Translations:
    """The ciso-board-translation sidecar. Never fabricates: absent means absent.

    Conforms to skills/board-pack/references/section-contract.md. The item key for this
    section is `metrics`, keyed by metric id.
    """

    SECTION = "metrics"
    CONTRACT_VERSION = 1

    def __init__(self, raw: dict | None):
        self.absent = raw is None
        raw = raw or {}
        self.executive_summary = raw.get("executiveSummary") or None
        self.metrics = raw.get("metrics") or {}
        self.decisions = raw.get("decisions") or []
        self.as_of = raw.get("asOf") or None
        self.contract_version = raw.get("contractVersion", self.CONTRACT_VERSION)
        self.section = raw.get("section") or None

    def metric(self, mid: str):
        return self.metrics.get(mid) or None

    @staticmethod
    def load(path: str | None) -> "Translations":
        if not path:
            return Translations(None)
        try:
            with open(path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except FileNotFoundError:
            raise SystemExit(f"error: --translations file not found: {path}")
        except json.JSONDecodeError as exc:
            raise SystemExit(f"error: --translations file {path} is not valid JSON "
                             f"(line {exc.lineno}, column {exc.colno}): {exc.msg}")
        if not isinstance(raw, dict):
            raise SystemExit(f"error: --translations file {path} must contain a JSON object, "
                             f"got {type(raw).__name__}.")
        tr = Translations(raw)
        # A sidecar that parses but maps nothing is the dangerous case: the render
        # "succeeds", every narrative falls back to a placeholder, and the deck looks
        # finished. The flat {id: sentence} shape is the usual cause.
        if not (tr.metrics or tr.executive_summary or tr.decisions):
            hint = ""
            if raw and all(isinstance(v, str) for v in raw.values()):
                hint = ('\n  It looks like a flat {"M-001": "sentence"} map. '
                        'Wrap it: {"metrics": { ... }}.')
            raise SystemExit(f"error: --translations file {path} contains no usable keys "
                             f'(expected "metrics", "executiveSummary" or "decisions").{hint}')
        if tr.contract_version != Translations.CONTRACT_VERSION:
            raise SystemExit(
                f"error: --translations file {path} declares contractVersion "
                f"{tr.contract_version!r}; this renderer implements version "
                f"{Translations.CONTRACT_VERSION}. See "
                f"skills/board-pack/references/section-contract.md.")
        if tr.section is not None and tr.section != Translations.SECTION:
            raise SystemExit(
                f"error: --translations file {path} is a {tr.section!r} section; "
                f"this renderer produces the {Translations.SECTION!r} section. "
                f"Pass the sidecar written for this skill.")
        return tr


class Context:
    """The analyze JSON plus an optional sidecar. A pass-through, not a derivation layer.

    Every figure shown by either renderer comes out of the engine. Nothing is recomputed
    here, so a report cannot disagree with the analysis it was built from.
    """

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.offline = bool(getattr(args, "offline", False))
        self.out_path = args.out
        try:
            with open(args.infile, encoding="utf-8") as fh:
                self.a = json.load(fh)
        except FileNotFoundError:
            raise SystemExit(f"error: --in file not found: {args.infile}")
        except json.JSONDecodeError as exc:
            raise SystemExit(f"error: --in file {args.infile} is not valid JSON: {exc.msg}")
        for key in ("metrics", "attention", "counts"):
            if key not in self.a:
                raise SystemExit(
                    f"error: {args.infile} is not a metrics-register analysis "
                    f"(no {key!r} key). Produce it with "
                    f"`metrics_analysis.py analyze <store.mtr> --out {args.infile}`.")
        self.metrics = self.a["metrics"]
        self.attention = self.a["attention"]
        self.counts = self.a["counts"]
        self.rollups = self.a.get("rollups") or {}
        self.meta = self.a.get("meta") or {}
        self.today = self.a.get("today") or ""
        self.cadence = self.a.get("cadenceDays")
        self.tr = Translations.load(getattr(args, "translations", None))

    def footer(self) -> str:
        bits = [DISCLAIMER, f"generated {esc(self.today)}"]
        if self.meta.get("clientName"):
            bits.insert(0, esc(self.meta["clientName"]))
        return '<footer>' + ' · '.join(bits) + '</footer>'


def base_css() -> str:
    return f"""
*{{box-sizing:border-box}}
body{{margin:0;padding:24px;background:{WB};color:{INK};
  font-family:Manrope,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  font-size:15px;line-height:1.55}}
.wrap{{max-width:1100px;margin:0 auto}}
h1,h2,h3{{font-family:'Space Grotesk',Manrope,sans-serif;margin:0 0 8px;line-height:1.25}}
h1{{font-size:26px}} h2{{font-size:19px;margin-top:28px}} h3{{font-size:16px}}
.sub{{color:{MUTED};margin:0 0 20px}}
.card{{background:{WB_SURF};border:1px solid {WB_LINE};border-radius:10px;
  padding:16px 18px;margin:14px 0}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}
.tile{{background:{WB_SURF};border:1px solid {WB_LINE};border-radius:10px;padding:14px}}
.tile .n{{font-family:'Space Grotesk',sans-serif;font-size:28px;font-weight:600;
  display:block;line-height:1.1}}
.tile .l{{color:{MUTED};font-size:13px}}
.scroll{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
table{{border-collapse:collapse;width:100%;min-width:640px}}
th,td{{text-align:left;padding:9px 10px;border-bottom:1px solid {WB_LINE};
  vertical-align:top}}
th{{color:{MUTED};font-size:13px;font-weight:600;white-space:nowrap}}
td.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
.chip{{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12.5px;
  font-weight:600;white-space:nowrap}}
.muted{{color:{MUTED}}}
.list{{margin:6px 0 0;padding-left:20px}}
.list li{{margin:3px 0}}
.ph{{background:{LIME};border:1px dashed {SLATE};border-radius:8px;padding:12px 14px;
  color:{MUTED}}}
.rule{{border:0;border-top:1px solid {WB_LINE};margin:22px 0}}
footer{{color:{MUTED};font-size:12.5px;margin-top:28px;padding-top:14px;
  border-top:1px solid {WB_LINE}}}
/* CAC chrome. A compact band, not a cover: these are working views, and a
   full-page cover on a section a reader opens twenty times is furniture. */
.band{{background:{INK};color:{LIME};border-radius:10px;padding:14px 18px;
  margin:0 0 18px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
.band .lockup{{font-family:'Space Grotesk',Manrope,sans-serif;font-weight:600;
  font-size:13px;letter-spacing:.02em}}
.band .spark{{width:9px;height:9px;border-radius:2px;background:{PATINA};
  flex:0 0 auto}}
.band .kicker{{margin-left:auto;color:{PATINA};font-size:11px;font-weight:700;
  letter-spacing:.12em;text-transform:uppercase}}

/* Marks size to their column and never push the page sideways. */
.mark{{margin:10px 0 2px}}
.mark svg{{display:block;max-width:100%;height:auto}}
.mrow{{display:flex;gap:18px;align-items:flex-start;flex-wrap:wrap}}
.mrow .mcol{{flex:1 1 280px;min-width:0}}

/* The legend states what the colours mean, once per page. Without it a reader
   has to infer the contract from the marks. */
.legend{{display:flex;gap:14px;flex-wrap:wrap;color:{MUTED};font-size:12px;
  margin:6px 0 0}}
.legend span{{display:flex;align-items:center;gap:6px}}
.legend i{{width:14px;height:10px;border-radius:2px;display:block;flex:0 0 auto}}

@media (max-width:560px){{body{{padding:14px}} h1{{font-size:22px}}
  .tile .n{{font-size:24px}}}}
@media print{{body{{background:#fff;padding:0}} .card,.tile{{break-inside:avoid}}
  .band{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
"""


def band(title: str, kicker: str = "") -> str:
    """The CAC header band: ink ground, patina spark, lockup, optional kicker."""
    k = f'<span class="kicker">{esc(kicker)}</span>' if kicker else ""
    return (f'<div class="band"><span class="spark"></span>'
            f'<span class="lockup">{esc(title)}</span>{k}</div>')


def legend() -> str:
    """What the colours mean. Measure first: it is the default, not the exception."""
    items = [(G._MEASURE, "no threshold set"),
             (G._RAG["good"]["fill"], "within threshold"),
             (G._RAG["high"]["fill"], "past warn"),
             (G._RAG["critical"]["fill"], "past critical")]
    inner = "".join(f'<span><i style="background:{c}"></i>{esc(t)}</span>'
                    for c, t in items)
    return f'<div class="legend">{inner}</div>'


def mark_block(row: dict) -> str:
    """One metric's mark, wrapped so it scales inside its column."""
    svg = mark_for(row)
    return f'<div class="mark">{svg}</div>' if svg else ""


def page(title: str, body: str, offline: bool = False) -> str:
    head_fonts = "" if offline else FONTS
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)}</title>{head_fonts}'
            f'<style>{base_css()}</style></head><body><div class="wrap">'
            f'{body}</div></body></html>')


def status_chip(status: str) -> str:
    bg, fg = STATUS_FILL.get(status, STATUS_FILL["no-reading"])
    return (f'<span class="chip" style="background:{bg};color:{fg}">'
            f'{esc(STATUS_LABEL.get(status, status))}</span>')


def trend_cell(trend: str) -> str:
    return (f'<span aria-hidden="true">{TREND_MARK.get(trend, "·")}</span> '
            f'{esc(TREND_LABEL.get(trend, trend))}')


def build_parser(description: str, default_out: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--in", dest="infile", required=True,
                   help="metrics_analysis.py analyze --out JSON")
    p.add_argument("--out", default=default_out, help="output HTML path")
    p.add_argument("--translations", metavar="FILE",
                   help="ciso-board-translation sidecar; omitted means the board "
                        "narrative renders as a labelled placeholder")
    p.add_argument("--offline", action="store_true",
                   help="omit the webfont link so the file makes no outbound request")
    return p


def write(ctx: Context, doc: str, note: str) -> int:
    with open(ctx.out_path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"wrote {ctx.out_path} ({len(doc):,} bytes) — {note}")
    return 0
