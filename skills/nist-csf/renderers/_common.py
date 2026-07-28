#!/usr/bin/env python3
"""
_common.py — shared presentation layer for the nist-csf renderers.

Ported from `skills/risk-register/renderers/_common.py`. Skills are self-contained, so
this is a deliberate copy rather than an import: change the brand tokens in one and you
must change them in the other. The twin lives at
`skills/risk-register/renderers/_common.py`.

ONE IMPORTANT DIFFERENCE FROM THE TWIN. The register's `_common.py` carries a derivation
layer, because `score_register.py` emits scored risks rather than a finished view model.
Here, `profile_analysis.py analyze` already emits every number a dashboard shows. So this
module deliberately contains **no derivation at all** — it parses input, holds brand
tokens, formats values, and writes files. If a renderer needs a number that is not in the
analyze JSON, add it to `analyze`, never compute it here. Two views of one Profile must
never be able to disagree.

Board *language* is never derived — it is supplied by the `ciso-board-translation` skill
through an optional --translations sidecar, or clearly marked as absent.

Standard library only.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

# --- Brand tokens (assets/brand.md) ------------------------------------------
# Patina is the brand/action accent and never encodes a measurement.
INK = "#14171C"; INK_RAISED = "#1C2026"; INK_LINE = "#2A2F36"
LIME = "#EAE7DF"; LIME_DIM = "#9AA0A6"
PATINA = "#2FA98C"; PATINA_H = "#279884"
# 4.45:1 on the workbench — just under AA, and it carries every hint, footer and
# table header in the suite. One step darker clears them all at once.
SLATE = "#666D7C"; WB = "#F6F4EE"; WB_SURF = "#FFFFFF"; WB_LINE = "#D8D3C6"

# Coverage uses a sequential ramp, deliberately distinct from the register's risk-severity
# RAG ramp: low coverage is not "critical", it may be a low Target that is fully met.
COVERAGE_RAMP = [(25, "#7C3A32"), (50, "#A6603A"), (75, "#C08A3E"), (100, "#8A9A4B")]
COVERAGE_FULL = "#4A7C59"
UNTARGETED_FILL = WB_LINE          # hatched in CSS; must never read as 0% or 100%
NA_FILL = WB

PRIORITY_COLOR = {"low": "#6A7180", "medium": "#5F7A8A", "high": "#A6603A", "critical": "#7C3A32"}

# Evidence states are STATES, not measurements, so they must not sit on the coverage
# ramp and must not use patina. Text on any of them comes from text_on(fill) — never
# hand-picked. See assets/brand.md, "Text on a coverage swatch — do not hand-pick it".
EVIDENCE_FILL = {
    "confirmed":        INK,        # 17.96:1 with white
    "evidence-pending": "#526A78",  #  5.69:1 with white
    "unrated":          WB_LINE,    # 12.02:1 with ink
    "not-applicable":   WB,         # 16.33:1 with ink, plus a WB_LINE border
}
EVIDENCE_LABEL = {
    "confirmed": "confirmed", "evidence-pending": "material, not yet confirmed",
    "unrated": "not looked at", "not-applicable": "not applicable",
}
EVIDENCE_ORDER = ["confirmed", "evidence-pending", "unrated", "not-applicable"]
EVIDENCE_KEY = {"confirmed": "confirmed", "evidence-pending": "evidencePending",
                "unrated": "unrated", "not-applicable": "notApplicable"}

# Two font modes. The brand faces come from Google Fonts, which means opening a report
# makes an outbound request — for a document full of a client's risk data, that is a real
# (if small) disclosure, and the dashboards were documented as making "no external calls".
#
# `--offline` is the honest escape hatch: no request, system stack, layout unchanged
# because the CSS already names fallbacks. Default stays branded.
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700'
         '&family=Space+Grotesk:wght@500;600&display=swap" rel="stylesheet">')
FONTS_OFFLINE = ""


def fonts(offline: bool = False) -> str:
    """The <head> font links, or nothing at all when rendering offline."""
    return FONTS_OFFLINE if offline else FONTS


DISCLAIMER = "A Cyber Aware Creation · Not affiliated with NIST"

PLACEHOLDER = ("Board narrative not supplied. Run the ciso-board-translation skill over this "
               "Profile and pass its output with --translations to replace this block.")


def esc(s) -> str:
    return html.escape("" if s is None else str(s))


# --- Coverage formatting -----------------------------------------------------
# The engine's contract: percent is None when nothing is targeted. Every helper here
# keeps that state visually distinct from both 0% and 100%.

def cov_color(cov: dict) -> str:
    pct = cov.get("percent")
    if pct is None:
        return UNTARGETED_FILL
    if pct >= 100:
        return COVERAGE_FULL
    for ceiling, colour in COVERAGE_RAMP:
        if pct < ceiling:
            return colour
    return COVERAGE_FULL


# --- Contrast ----------------------------------------------------------------
# Deliberately duplicated from the risk-register renderer rather than shared: a
# skill has to stand alone. Keep the two in step.

def _luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    chans = []
    for i in (0, 2, 4):
        v = int(h[i:i + 2], 16) / 255.0
        chans.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * chans[0] + 0.7152 * chans[1] + 0.0722 * chans[2]


def contrast_ratio(a: str, b: str) -> float:
    """WCAG 2.x contrast ratio between two opaque colours. 1.0 … 21.0."""
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def text_on(fill: str) -> str:
    """The brand text colour with the most contrast on `fill`."""
    return max((INK, LIME, "#FFFFFF"), key=lambda fg: contrast_ratio(fg, fill))


def cov_text_color(cov: dict) -> str:
    """Text colour for a coverage tile — measured against the tile's own fill.

    This used to be `LIME if pct < 50 else INK`, a threshold guess that put
    limestone on #A6603A at 3.90:1 and ink on the full-coverage green at 3.69:1,
    both under AA. Deriving it from the fill fixes every ramp value at once and
    cannot drift when a ramp colour is retuned.
    """
    if cov.get("percent") is None:
        return SLATE
    return text_on(cov_color(cov))


def cov_pct(cov: dict) -> str:
    """The percentage alone — for places where the fraction is shown separately."""
    pct = cov.get("percent")
    return "—" if pct is None else f"{pct:.0f}%"


def cov_label(cov: dict) -> str:
    """Never a bare percentage: the fraction always travels with it."""
    pct = cov.get("percent")
    if pct is None:
        return "not yet targeted"
    return f"{pct:.0f}% ({cov.get('n', 0)}/{cov.get('d', 0)})"


def cov_is_untargeted(cov: dict) -> bool:
    return cov.get("percent") is None


def completeness_line(comp: dict) -> str:
    """'8 of 106 assessed · 8 targeted · 1 n/a' — the honesty line beside any coverage."""
    bits = [f"{comp.get('assessed', 0)} of {comp.get('inScope', 0)} assessed",
            f"{comp.get('targeted', 0)} targeted"]
    if comp.get("notApplicable"):
        bits.append(f"{comp['notApplicable']} n/a")
    return " · ".join(bits)


def rating(v, scale_max: int = 3) -> str:
    """Ratings render as numbers; null renders as 'unassessed', never as 0."""
    return "unassessed" if v is None else f"{v}"


def trunc(text: str, n: int) -> str:
    """Shorten on a word boundary with an ellipsis.

    CSF outcome text is long and uniformly phrased, so a hard character cut lands
    mid-word and mid-clause ("...are analyzed to better underst"), which reads as a
    rendering fault rather than an abbreviation.
    """
    text = (text or "").strip()
    if len(text) <= n:
        return text
    cut = text[:n]
    space = cut.rfind(" ")
    if space > n * 0.6:          # only back up to a word break if one is reasonably near
        cut = cut[:space]
    return cut.rstrip(" ,;:.") + "…"


# --- CLI ---------------------------------------------------------------------

def parse_args(argv: list[str], description: str, default_out: str) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--in", dest="infile", metavar="FILE",
                   help="analyze JSON (default: stdin, so `analyze ... | this` works)")
    p.add_argument("--out", default=default_out, metavar="FILE",
                   help=f"output HTML path (default: ./{default_out})")
    p.add_argument("--translations", metavar="FILE",
                   help="board-language sidecar from the ciso-board-translation skill; "
                        "omitted means board narrative is shown as a labelled placeholder")
    p.add_argument("--offline", action="store_true",
                   help="omit the Google Fonts links so the file makes no external request; "
                        "falls back to the system font stack")
    return p.parse_args(argv)


class Translations:
    """The ciso-board-translation sidecar. Never fabricates: absent means absent."""

    def __init__(self, raw: dict | None):
        self.absent = raw is None
        raw = raw or {}
        self.executive_summary = raw.get("executiveSummary") or None
        self.gaps = raw.get("gaps") or raw.get("subcategories") or {}
        self.decisions = raw.get("decisions") or []
        self.as_of = raw.get("asOf") or None

    def gap(self, sid: str) -> str | None:
        return self.gaps.get(sid) or None

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
        # "succeeds", every narrative silently falls back to a placeholder, and the board
        # deck looks finished. The most likely cause is the flat {id: sentence} shape,
        # which reads as correct and is not.
        if not (tr.gaps or tr.executive_summary or tr.decisions):
            hint = ""
            if raw and all(isinstance(v, str) for v in raw.values()):
                hint = ('\n  It looks like a flat {"SUBCATEGORY-ID": "sentence"} map. '
                        'Wrap it: {"gaps": { ... }}.')
            raise SystemExit(f"error: --translations file {path} contains no usable keys "
                             f'(expected "gaps", "executiveSummary" or "decisions").{hint}')
        return tr


class Context:
    """The analyze JSON plus an optional sidecar. A pass-through, not a derivation layer."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.offline = bool(getattr(args, "offline", False))
        self.out_path = args.out
        if args.infile:
            try:
                with open(args.infile, encoding="utf-8") as fh:
                    self.a = json.load(fh)
            except FileNotFoundError:
                raise SystemExit(f"error: no such file: {args.infile}") from None
            except json.JSONDecodeError as exc:
                raise SystemExit(f"error: {args.infile} is not valid JSON ({exc}). Expected the "
                                 f"output of `profile_analysis.py analyze <store.csfp>`.") from None
        else:
            if sys.stdin.isatty():
                raise SystemExit("error: no input. Pipe `profile_analysis.py analyze <store>` "
                                 "into this renderer, or pass --in FILE.")
            raw = sys.stdin.read()
            if not raw.strip():
                raise SystemExit("error: empty input. Pipe `profile_analysis.py analyze <store>` "
                                 "into this renderer, or pass --in FILE.")
            try:
                self.a = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"error: input is not valid JSON ({exc}). Expected the output of "
                                 f"`profile_analysis.py analyze <store.csfp>`.") from None

        for key in ("profile", "coverage", "completeness", "gaps"):
            if key not in self.a:
                raise SystemExit(f"error: input is not analyze output (missing {key!r}). "
                                 f"Generate it with `profile_analysis.py analyze <store.csfp>`.")

        self.profile = self.a["profile"]
        self.framework = self.a.get("framework", {})
        self.coverage = self.a["coverage"]
        self.completeness = self.a["completeness"]
        self.gaps = self.a["gaps"]
        self.attention = self.a.get("attention", {})
        self.actions = self.a.get("actionItems", {"items": [], "summary": {}})
        self.tiers = self.a.get("tiers", {})
        self.diff = self.a.get("diff")
        # Absent on analyze output from a v1 engine — every consumer must degrade,
        # not crash, so a dashboard built from an older JSON still renders.
        self.evidence = self.a.get("evidence") or {}
        self.intake = self.a.get("intake") or {"records": [], "bySource": []}
        self.queue = self.a.get("queue") or []
        # Absent unless a Profile has opted into an overlay. Empty dict means
        # "no overlay", which every consumer must render as nothing at all —
        # not as a disabled badge, which would advertise a feature to someone
        # who never asked for it.
        self.overlay = self.a.get("overlay") or {}
        self.today = self.a.get("generated", {}).get("today", "")
        self.scale_max = self.profile.get("settings", {}).get("scale", {}).get("max", 3)
        self.tr = Translations.load(args.translations)

    def function_meta(self) -> list[dict]:
        """Functions in framework order, each with its categories. Never hardcoded."""
        return self.framework.get("functions", [])

    def as_of_line(self) -> str:
        if self.diff:
            return f'As of {self.today} · compared against {self.diff["against"].get("label", "the last snapshot")}'
        return f"As of {self.today} · no snapshot yet, so no trend is available"

    def footer(self, extra: str = "") -> str:
        bits = [DISCLAIMER,
                f'{self.framework.get("name", "framework")} {self.framework.get("version", "")}'.strip(),
                f"generated {self.today}"]
        if extra:
            bits.append(extra)
        if self.tr.absent:
            bits.append("board narrative not supplied")
        return " · ".join(bits)


def overlay_note(ctx: "Context", reordered: bool) -> str:
    """The overlay disclosure, rendered next to the rows it describes.

    This has to sit adjacent to the affected table, not in the footer. A reader
    who is not told assumes a prioritized gap table is ordered by gap severity,
    because that is what it means everywhere else in this tool, and a footnote
    two screens away does not undo that assumption.

    `reordered` says whether THIS table is the one the overlay resequenced.
    Both answers need saying. A table that was reordered must say so; a table
    that was not, on a Profile where the overlay is active, must say that too —
    otherwise a reader who knows the overlay is on assumes every list reflects
    it. Two views of one Profile ordering by different rules is fine; two views
    ordering by different rules without saying which is not.
    """
    ov = ctx.overlay
    if not ov:
        return ""
    areas = ", ".join(ov.get("focusAreas") or []) or "none selected"
    lead = (ov.get("orderingNote", "") if reordered else
            "Ordered by gap size, not by AI priority — the AI-prioritized order is on "
            "the operational dashboard's gap table.")
    return (f'<div class="hint">{esc(lead)} '
            f'Cyber AI Profile overlay · focus areas: {esc(areas)} · mode '
            f'{esc(ov.get("mode", ""))} · dataset {esc(ov.get("datasetVersion", ""))} '
            f'({esc(ov.get("sourceStatus", ""))}). Proposed priority indicates '
            f'sequencing, not required maturity.</div>')


def build(argv: list[str], description: str, default_out: str) -> Context:
    return Context(parse_args(argv, description, default_out))


def write(ctx: Context, doc: str) -> None:
    out = Path(ctx.out_path)
    if out.parent != Path(""):
        out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    cov = ctx.coverage["overall"]
    print(f"wrote {out} ({len(doc):,} bytes) — coverage {cov_label(cov)}, "
          f"{len(ctx.gaps)} gaps")


# --- Shared chrome -----------------------------------------------------------

BASE_CSS = f"""
*,*::before,*::after{{box-sizing:border-box}}
body{{margin:0;background:{WB};color:{INK};
  font-family:'Manrope',system-ui,-apple-system,sans-serif;font-size:15px;line-height:1.5}}
h1,h2,h3{{font-family:'Space Grotesk',system-ui,sans-serif;font-weight:600;margin:0}}
header{{background:{INK};color:{LIME};padding:20px 28px}}
header .hwrap{{display:flex;align-items:center;justify-content:space-between;
  gap:16px;flex-wrap:wrap}}
.brand{{display:flex;align-items:center;gap:12px}}
.mark{{width:30px;height:30px;border-radius:7px;
  background:linear-gradient(135deg,{PATINA},{PATINA_H});position:relative;flex:0 0 auto}}
.mark::after{{content:"";position:absolute;inset:9px 8px;background:{INK};
  clip-path:polygon(0 40%,100% 0,100% 60%,0 100%)}}
.eyebrow{{color:{PATINA};font-size:11px;letter-spacing:.14em;text-transform:uppercase;
  font-weight:700}}
header h1{{font-size:19px;line-height:1.1;letter-spacing:-.01em}}
.hmeta{{text-align:right;font-size:12.5px;color:{LIME_DIM};line-height:1.5}}
.hmeta b{{color:{LIME}}}
.hmeta .tag{{display:inline-block;background:{PATINA};color:{INK};font-weight:700;
  border-radius:999px;padding:2px 10px;font-size:12px}}
header .sub{{color:{LIME_DIM};font-size:13px;margin-top:10px}}
@media (max-width:760px){{.hmeta{{text-align:left}}}}
main{{padding:24px 28px 40px;max-width:1280px;margin:0 auto}}
section{{margin-bottom:32px}}
section>h2{{font-size:16px;margin-bottom:4px}}
section>.hint{{color:{SLATE};font-size:13px;margin-bottom:12px}}
.card{{background:{WB_SURF};border:1px solid {WB_LINE};border-radius:10px;padding:16px}}
table{{width:100%;border-collapse:collapse;background:{WB_SURF};
  border:1px solid {WB_LINE};border-radius:10px;overflow:hidden}}
th,td{{text-align:left;padding:9px 12px;border-bottom:1px solid {WB_LINE};
  font-size:13px;vertical-align:top}}
th{{background:{WB};font-weight:600;font-size:12px;text-transform:uppercase;
  letter-spacing:.04em;color:{SLATE};white-space:nowrap}}
tr:last-child td{{border-bottom:none}}
.mono{{font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:12px}}
.muted{{color:{SLATE}}}
.chip{{display:inline-block;padding:2px 8px;border-radius:999px;
  font-size:11px;font-weight:600;white-space:nowrap}}
.untargeted{{background:repeating-linear-gradient(45deg,{WB_LINE},{WB_LINE} 4px,
  {WB} 4px,{WB} 8px);color:{SLATE}}}
footer{{background:{INK};color:{LIME_DIM};padding:16px 28px;font-size:12px}}
.scroll{{overflow-x:auto}}
@media print{{body{{background:#fff}} header,footer{{-webkit-print-color-adjust:exact;
  print-color-adjust:exact}}}}
"""


def header(artifact: str, ctx, sub_lines: list[str]) -> str:
    """The shared header for every nist-csf artifact.

    Built here rather than in each renderer so the two views cannot drift apart — which
    is exactly how these dashboards ended up looking like a different product from the
    risk register's, despite both skills declaring the same brand tokens.

    The `h1` is the **artifact type**, not the client. A board member holding two reports
    needs to know which one this is at a glance; whose it is belongs in the meta block,
    the way a letterhead works.
    """
    p = ctx.profile
    scope = p.get("scope") or {}
    owner = (scope.get("owner") or "").strip()
    fw = f'{ctx.framework.get("name", "")} {ctx.framework.get("version", "")}'.strip()
    meta_bits = [f'<b>{esc(p.get("name") or "(unnamed Profile)")}</b>']
    if owner:
        meta_bits.append(esc(owner))
    if fw:
        meta_bits.append(f'<span class="tag">{esc(fw)}</span>')
    subs = "".join(f'<div class="sub">{s}</div>' for s in sub_lines if s)
    return (f'<header><div class="hwrap">'
            f'<div class="brand"><div class="mark"></div><div>'
            f'<div class="eyebrow">Cyber Aware Creations · NIST CSF</div>'
            f'<h1>{esc(artifact)}</h1></div></div>'
            f'<div class="hmeta">{"<br>".join(meta_bits)}</div>'
            f'</div>{subs}</header>')


def page(title: str, head_extra: str, body: str, offline: bool = False) -> str:
    return (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{esc(title)}</title>{fonts(offline)}"
            f"<style>{BASE_CSS}{head_extra}</style></head><body>{body}</body></html>")


# --- Evidence: four-way coverage bar ------------------------------------------
# Shared by both renderers so the two views cannot render this differently.

def evidence_bar(split: dict) -> str:
    """The four-way coverage strip. 'Material on 41, confirmed on 24' is what makes a
    partial profile read as progress rather than abandonment."""
    total = split.get("total") or 0
    if not total:
        return ""
    segs, legend = [], []
    for state in EVIDENCE_ORDER:
        n = split.get(EVIDENCE_KEY[state], 0)
        if not n:
            continue
        fill = EVIDENCE_FILL[state]
        fg = text_on(fill)
        border = f";border:1px solid {WB_LINE}" if state == "not-applicable" else ""
        segs.append(f'<div class="eseg" style="flex:{n};background:{fill};color:{fg}{border}" '
                    f'title="{esc(EVIDENCE_LABEL[state])}: {n}">{n}</div>')
        legend.append(f'<span class="eleg"><i style="background:{fill}{border}"></i>'
                      f'{esc(EVIDENCE_LABEL[state])} {n}</span>')
    unatt = split.get("unattributed", 0)
    note = ("" if not unatt else
            f'<div class="muted" style="margin-top:6px">{unatt} of '
            f'{split.get("confirmed", 0)} confirmed ratings carry no source or confirmer. '
            f'They still count toward coverage — they simply cannot answer how they '
            f'were arrived at.</div>')
    return (f'<div class="ebar">{"".join(segs)}</div>'
            f'<div class="elegend">{"".join(legend)}</div>{note}')


EVIDENCE_CSS = f"""
.ebar{{display:flex;height:34px;border-radius:6px;overflow:hidden;margin-top:10px}}
.eseg{{display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;
      min-width:0;overflow:hidden}}
.elegend{{display:flex;flex-wrap:wrap;gap:14px;margin-top:10px;font-size:13px;color:{SLATE}}}
.eleg{{display:inline-flex;align-items:center;gap:6px}}
.eleg i{{width:12px;height:12px;border-radius:3px;display:inline-block;flex:none}}
.guard{{border-left:4px solid {EVIDENCE_FILL["evidence-pending"]};padding:14px 16px}}
.guard .gh{{font-family:'Space Grotesk',sans-serif;font-size:20px;font-weight:600}}
.agegrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;
         margin-top:10px;min-width:0}}
.agecell{{border:1px solid {WB_LINE};border-radius:6px;padding:10px;min-width:0}}
.agecell .an{{font-size:20px;font-weight:700;font-family:'Space Grotesk',sans-serif}}
"""
