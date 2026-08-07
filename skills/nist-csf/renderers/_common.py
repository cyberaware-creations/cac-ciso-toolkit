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

# Vendored alongside this file, for the same reason this file is vendored: a
# shipped script must run from its own skill directory with no path surgery.
# tools/check-versions.py fails if this copy drifts from tools/cac_graphics.py.
import cac_graphics as G

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

# Crosswalk band fills. A THIRD ramp, and deliberately so: this skill already has
# two measures that must not be confused, and a crosswalk band is a third one.
# COVERAGE_RAMP encodes coverage against a Target; the register's RAG ramp encodes
# risk severity; a crosswalk band encodes a derived share of the Profile's own
# rating scale. Sharing a ramp across two of those would assert an equivalence
# none of them have. Single-hue slate blue, so it also cannot be mistaken for
# patina, which never encodes a measurement.
#
# Validated with the dataviz skill's validate_palette.js --ordinal against the
# workbench surface: monotone lightness, adjacent ΔL >= 0.06, light end 2.09:1,
# hue spread 8°. ALL CHECKS PASS. Re-run it if any step moves.
CROSSWALK_BAND_FILL = {
    "minimal": "#98AEBE",
    "weak": "#7595A8",
    "moderate": "#4E768B",
    "strong": "#2D4C5E",
}
# "unknown" is not a low value on the ramp — it is the absence of one, so it sits
# off the ramp entirely and is hatched in CSS. Same discipline as UNTARGETED_FILL:
# nothing rated must never be confusable with rated-and-weak.
CROSSWALK_UNKNOWN_FILL = WB_LINE
# "insufficient" is off the ramp for the same reason as "unknown", and is a
# separate state from it: unknown means nothing behind this control is rated,
# insufficient means too little of it is to band honestly. Both are hatched, and
# neither may look like a low measurement.
CROSSWALK_BAND_ORDER = ["strong", "moderate", "weak", "minimal",
                        "insufficient", "unknown"]
CROSSWALK_BAND_LABEL = {
    "strong": "strong", "moderate": "moderate", "weak": "weak",
    "minimal": "minimal", "insufficient": "too little rated",
    "unknown": "not yet rated",
}
CROSSWALK_OFF_RAMP = ("unknown", "insufficient")


def crosswalk_fill(band: str) -> str:
    return CROSSWALK_BAND_FILL.get(band, CROSSWALK_UNKNOWN_FILL)

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

# --- Confirmation age: the four graded bands ----------------------------------
#
# Ordered ascending by age, tracking AGE_BANDS in ../scripts/profile_analysis.py. The
# engine owns this vocabulary and emits the counts; this module only names and draws
# them. Both renderers read from here, so the operational and board views cannot put
# opposite words on one number — which they did: the board page called `beyond`
# "within 360 days" while the working view called it "beyond cadence".
#
# The LABELS are this skill's own and must NOT be merged with the near-identical
# AGE_BAND_LABEL coming to skills/risk-register/renderers/render_dashboard.py. Only the
# KEY SET is shared, and only because both track AGE_BANDS. The wording is meant to
# diverge — these read as a trailing clause after a date ("confirmed 2026-01-10, beyond
# cadence"), which is not the sentence shape over there — so "keep the two in step"
# applies to the keys and to nothing else. Do not converge the values.
#
# What holds the keys and the rendered ranges honest is `_cmd_self_test` in
# profile_analysis.py: it asserts these key sets against AGE_BANDS and pins
# age_band_ranges(180) to fixed strings. That is the only thing standing between a
# relabelling and a quietly flattering board page, so it is not optional.
AGE_BAND_ORDER = ["within", "approaching", "beyond", "wellBeyond"]
AGE_BAND_LABEL = {"within": "within cadence", "approaching": "approaching cadence",
                  "beyond": "beyond cadence", "wellBeyond": "well beyond cadence"}
# A single-hue sequential ramp, light to dark: never the coverage ramp and never a RAG
# scale. Age is a distance from a cadence the reader chose — not a severity, not a
# confidence — and a governance outcome and an asset inventory go stale at completely
# different rates. Colouring `wellBeyond` red would make that judgement for the reader,
# on the one page where it would carry the most weight. Lightness carries the ordering
# instead, which is what an ordinal measure asks for.
#
# Warm neutrals off the workbench, deliberately NOT the cool greys in EVIDENCE_FILL: on
# the executive page this strip sits directly beneath the evidence strip, and a shared
# grey would have read as one continuous scale across two unrelated questions.
# Luminance is strictly descending, and every fill clears AA against text_on(fill) —
# lowest is `beyond` at 5.16:1. Retune one and re-check both properties.
AGE_BAND_FILL = {"within": "#E4DFD2", "approaching": "#C0B49B",
                 "beyond": "#786C54", "wellBeyond": "#4A4335"}

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


# A crosswalk view names ISO and CIS controls, so the non-affiliation line has to
# cover them too. Selected by Context.footer() from the content actually rendered
# rather than passed in by each renderer: a report that shows ISO or CIS material
# must not be able to ship the NIST-only wording by omission.
#
# Both lines come from the graphics library, at render time. They were constants here,
# spelling the maker's name out by hand — and `G.footer()` is what drops that name when a
# client white-labels while keeping the disclaimer, so a hardcoded copy is a white-label
# leak waiting for the day this renderer gains a brand flag. Called rather than bound at
# import for the same reason: the brand is process-global and can be rebound after this
# module loads, and a constant captured at import would keep printing the old name.
UNAFFILIATED_CROSSWALK = ("NIST", "ISO", "CIS")

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
    # The risk-register renderers are positional (`render_board.py reg.rr out.html`) and
    # these are flag-based over the derived JSON. Both are documented, but someone moving
    # between the two skills in one session will type the other form, and argparse's bare
    # "unrecognized arguments" does not tell them which two files it wanted or why.
    args, extra = p.parse_known_args(argv)
    if extra:
        looks_like_io = [a for a in extra if not a.startswith("-")]
        hint = ""
        if len(looks_like_io) == 2:
            hint = (f"\n  Did you mean:  --in {looks_like_io[0]} --out {looks_like_io[1]}")
        elif len(looks_like_io) == 1:
            hint = f"\n  Did you mean:  --in {looks_like_io[0]}"
        raise SystemExit(
            f"error: unexpected argument(s): {' '.join(extra)}\n"
            f"  These renderers take flags over the JSON that `profile_analysis.py analyze`\n"
            f"  emits, not positional paths -- the risk-register renderers are the "
            f"positional ones.{hint}")
    return args


class Translations:
    """The ciso-board-translation sidecar. Never fabricates: absent means absent."""

    # The section this renderer's sidecar describes, per
    # board-pack/references/section-contract.md. `gaps` is the canonical item key;
    # `subcategories` stays readable so no sidecar written before the contract stops
    # rendering, but it is deprecated and not extended to other sections.
    SECTION = "posture"
    CONTRACT_VERSION = 1

    def __init__(self, raw: dict | None):
        self.absent = raw is None
        raw = raw or {}
        self.executive_summary = raw.get("executiveSummary") or None
        self.gaps = raw.get("gaps") or raw.get("subcategories") or {}
        self.decisions = raw.get("decisions") or []
        self.as_of = raw.get("asOf") or None
        # Absent means 1: every sidecar written before the contract existed is a
        # valid v1 document. Stated here so the default is one line, not a guess
        # spread across call sites.
        self.contract_version = raw.get("contractVersion", self.CONTRACT_VERSION)
        self.section = raw.get("section") or None

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
        # Two contract checks, both refusing rather than rendering on a best-effort
        # basis. A section that half-renders is worse than one that does not render,
        # because only one of those gets noticed before it reaches a board.
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
        # Absent unless `analyze --crosswalk <id>` was asked for. Crosswalks are a
        # report-time choice, never stored, so an analysis JSON without them is
        # the normal case and every consumer renders nothing at all.
        self.crosswalks = self.a.get("crosswalks") or {}
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
        bits = [G.footer(unaffiliated=UNAFFILIATED_CROSSWALK) if self.crosswalks
                else G.footer(),
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
    # The scope guard binds this line too. Suppressing the headline figure inside the
    # HTML and then printing it to the terminal defeats the guard's whole stated reason
    # — that the number must not reappear one document over. An agent reads stdout and
    # repeats it to the user, which is the outcome the guard exists to prevent.
    # Phrased here rather than imported from profile_analysis: the renderers consume the
    # analyze JSON and nothing else, which is the whole reason they cannot drift from the
    # engine's numbers. The guard's own fields are in that JSON, so the rule travels with
    # the data — see coverage_stdout() in the engine for the same decision on its side.
    guard = ctx.evidence.get("scopeGuard") or {}
    head = (f'withheld ({guard.get("assessed", 0)} of {guard.get("inScope", 0)} assessed, '
            f'below the {guard.get("thresholdPct", 60)}% threshold)'
            if guard.get("suppressed") else cov_label(ctx.coverage["overall"]))
    print(f"wrote {out} ({len(doc):,} bytes) — coverage {head}, {len(ctx.gaps)} gaps")


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

/* CAC chrome. A compact band, not a cover: these are working views, and a
   full-page cover on a section a reader opens twenty times is furniture.

   Ported from skills/metrics-register/renderers/_common.py base_css(), with two
   selectors RENAMED because this skill had already taken both names:
     .band  -> .cacband   render_crosswalk.py styles `.cell .band`, the crosswalk
                          band WORD on every heatmap cell. A global `.band` with an
                          ink ground would have repainted every one of them.
     .mark  -> .gmark     BASE_CSS above already uses `.mark` for the AnvilMark
                          logo in the header lockup.
   The rules themselves are unchanged; only the hooks differ. */
.cacband{{background:{INK};color:{LIME};border-radius:10px;padding:14px 18px;
  margin:0 0 18px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
.cacband .lockup{{font-family:'Space Grotesk',Manrope,sans-serif;font-weight:600;
  font-size:13px;letter-spacing:.02em}}
.cacband .spark{{width:9px;height:9px;border-radius:2px;background:{PATINA};
  flex:0 0 auto}}
.cacband .kicker{{margin-left:auto;color:{PATINA};font-size:11px;font-weight:700;
  letter-spacing:.12em;text-transform:uppercase}}

/* Marks size to their column and never push the page sideways. */
.gmark{{margin:10px 0 2px}}
.gmark svg{{display:block;max-width:100%;height:auto}}
.mrow{{display:flex;gap:18px;align-items:flex-start;flex-wrap:wrap}}
.mrow .mcol{{flex:1 1 280px;min-width:0}}

/* The legend states what the colours mean, once per page. Without it a reader
   has to infer the contract from the marks. */
.legend{{display:flex;gap:14px;flex-wrap:wrap;color:{SLATE};font-size:12px;
  margin:6px 0 0}}
.legend span{{display:flex;align-items:center;gap:6px}}
.legend i{{width:14px;height:10px;border-radius:2px;display:block;flex:0 0 auto}}
/* flex-basis:100% so the sentence always takes its own line rather than sitting
   in the swatch row until it happens to be long enough to wrap. */
.legend .note{{display:block;flex:0 0 100%;margin-top:2px}}

@media print{{body{{background:#fff}} header,footer{{-webkit-print-color-adjust:exact;
  print-color-adjust:exact}}
  .cacband{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
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


def band(title: str, kicker: str = "") -> str:
    """The CAC header band: ink ground, patina spark, lockup, optional kicker."""
    k = f'<span class="kicker">{esc(kicker)}</span>' if kicker else ""
    return (f'<div class="cacband"><span class="spark"></span>'
            f'<span class="lockup">{esc(title)}</span>{k}</div>')


# --- Graphics marks -----------------------------------------------------------
#
# THE ONE RULE THAT GOVERNS EVERY MARK IN THIS FILE: coverage is not severity, so
# no mark here is ever handed a `sev`. cac_graphics chooses its palette from what
# it is given -- any `sev` on any item turns bar_chart and heat_matrix into RAG
# charts -- so withholding it is not an omission, it is the encoding decision.
# See assets/brand.md, "Encoding coverage (this skill)": a Category at 20% may be a
# deliberately low Target that is fully met, and a red cell would assert a danger
# the data never claimed.
#
# The library cannot be handed this skill's own COVERAGE_RAMP (the warm five-step
# ramp the HTML tiles and cells use); heat_matrix shades from its own sequential
# MEASURE ramp and bar_chart from the single MEASURE blue, and neither takes a
# palette argument. That is the documented fallback -- the library's sequential
# ramp in preference to RAG -- and NOT a licence to reach for RAG instead. Editing
# cac_graphics.py is not an option either: it is a vendored copy and
# tools/check-versions.py fails the build on drift.

# The ground heat_matrix draws under a `None` cell. Mirrored here so the legend can
# name it; it is the library's constant, not a colour this skill picked. It is off
# every step of the MEASURE ramp, which is exactly the property "not yet targeted"
# needs: nothing targeted must never be confusable with fully covered.
HEAT_EMPTY_FILL = "#ECEAE3"


def mark_block(svg: str) -> str:
    """One mark, wrapped so it scales inside its column."""
    return f'<div class="gmark">{svg}</div>' if svg else ""


def legend(sequential: bool = False) -> str:
    """What the colours in the marks mean. Adapted to what THIS skill encodes.

    The sibling skills' legend reads good / past warn / past critical off the RAG
    ramp. There is no equivalent line here and there must not be one: none of these
    fills is a status, so the legend says what the scale IS rather than translating
    it into a verdict the engine never issued.

    `sequential` adds the two ends of the intensity ramp and the ground that sits
    off it, and is passed only by a page that actually draws the matrix -- a swatch
    for a mark that is not on the page teaches the reader a contract nothing on it
    obeys. The board view's bar chart has no blank state to explain, because a
    Function with nothing targeted is left off it and named in words instead.
    """
    items = [(G._MEASURE, "coverage of Target")]
    if sequential:
        items += [(G._MEASURE_RAMP[0], "more of Target achieved"),
                  (G._MEASURE_RAMP[4], "less of Target achieved"),
                  (HEAT_EMPTY_FILL, "not yet targeted, or not tracked")]
    inner = "".join(f'<span><i style="background:{c}"></i>{esc(t)}</span>'
                    for c, t in items)
    note = ("A sequential scale, not a traffic light. Low coverage is not a red "
            "flag on its own: it may be a low Target that is fully met, and the "
            "figure on every cell says which.")
    return f'<div class="legend">{inner}<span class="note">{esc(note)}</span></div>'


def coverage_bar(ctx: "Context") -> str:
    """Coverage by Function, as one bar chart. Never handed a `sev`.

    Two things this deliberately does not do:

    - It does not draw a Function with nothing targeted at zero. `percent: null` is
      not 0%, and a zero-length bar is a claim of 0% that the engine refused to
      make. Those Functions are left off and named beside the chart instead, which
      is the same discipline the hatched cells apply in the HTML grid.
    - It does not print a bare percentage. Every row label carries the achieved /
      targeted fraction the percentage came from, so the mark obeys cov_label's
      rule rather than quietly exempting itself from it.

    Returns "" when no Function has a coverage figure, so a Profile with nothing
    targeted renders no mark at all rather than an empty axis.
    """
    items, untargeted = [], []
    for fn in ctx.function_meta():
        fid = fn["id"]
        cov = ctx.coverage["byFunction"].get(fid)
        if cov is None or cov.get("percent") is None:
            untargeted.append(fid)
            continue
        # Formatting, not arithmetic: the same rounding cov_pct() already renders
        # beside this mark. Nothing is derived here that the engine did not emit.
        items.append((f'{fid} {cov.get("n", 0)}/{cov.get("d", 0)}',
                      round(cov["percent"])))
    if not items:
        return ""
    # The library scales bars to the largest value shown, not to 100, and takes no
    # axis argument. Saying so is the honest fix: the alternative -- padding the
    # item list with a phantom 100 to force the axis -- would put a row on the chart
    # that no Function stands behind.
    note = ("The figure at each bar's tip is the percentage of Target achieved, and "
            "the fraction it came from is on the row label. Bar length is relative "
            "to the highest figure here, not to 100%.")
    if untargeted:
        note += (" Not on the chart, because nothing in them is targeted yet: "
                 + ", ".join(untargeted) + ".")
    return (mark_block(G.bar_chart(items))
            + f'<div class="hint">{esc(note)}</div>')


def coverage_matrix(ctx: "Context") -> str:
    """Function x Category coverage, as one intensity matrix. Never handed a `sev`.

    With no cell carrying a `sev`, heat_matrix shades by `value` along its own
    sequential MEASURE ramp -- the branch its docstring describes as the INTENSITY
    matrix, and the branch that exists precisely so that a count of findings per
    control family is not painted as a severity.

    That ramp is normalized across the cells drawn, so the darkest cell is the
    highest coverage ON THIS PAGE and not necessarily 100%. The caption says so,
    and every cell carries its own percentage, so the ranking is never the only
    thing a reader has to go on.

    A Category with nothing targeted, and a Category the framework defines that
    this Profile does not track, are both passed as `None`. heat_matrix draws those
    on a neutral ground that is off the ramp entirely -- which is the treatment
    assets/brand.md requires for exactly these two states. The Category names and
    the words that go with them ("not yet targeted", "not tracked") are on the
    worded grid this mark sits above; the mark is the overview, never the record.

    ONE MEASURED CAVEAT, recorded here rather than left to be rediscovered. That
    neutral ground is HEAT_EMPTY_FILL, which the library picks and this skill
    cannot override without editing a vendored file. Against the ramp steps this
    mark actually uses it measures 7.22:1 at the dark end and 1.19:1 at the light
    end. The rule that matters most -- nothing targeted must never look like fully
    covered -- holds by a wide margin. Separation from the LIGHTEST step is thin,
    so colour is not left carrying it: every measured cell prints its percentage
    and a blank cell prints nothing at all, which is the same "never by colour
    alone" discipline the band words enforce elsewhere. The other candidate is
    worse, not better -- a cell with a `label` and no `value` takes _MEASURE_TRACK,
    which is nearer the light end still.

    Rows are ragged -- Functions do not all have the same number of Categories --
    which heat_matrix tolerates, and short rows simply end.
    """
    cells, row_labels = [], []
    drawn = 0
    for fn in ctx.function_meta():
        row = []
        for cat in fn.get("categories", []):
            cov = ctx.coverage["byCategory"].get(cat["id"])
            if cov is None or cov.get("percent") is None:
                row.append(None)
                continue
            row.append({"value": cov["percent"], "label": f'{cov["percent"]:.0f}%'})
            drawn += 1
        if not row:
            continue
        cells.append(row)
        row_labels.append(fn["id"])
    if not drawn:
        return ""
    note = ("One cell per Category, in framework order, ranked against the other "
            "cells here rather than against a fixed scale — the darkest cell is "
            "the highest coverage on this page, not 100%. Blank cells are not yet "
            "targeted or not tracked; they are named with their Categories in the "
            "grid below.")
    return (mark_block(G.heat_matrix(cells, row_labels=row_labels))
            + f'<div class="hint">{esc(note)}</div>')


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


# --- Confirmation age: the band distribution ----------------------------------
# Shared by both renderers for the same reason evidence_bar is.

def age_band_ranges(threshold_days: int) -> dict:
    """The day range each band covers, as a qualifier on its label.

    EXCLUSIVE ranges, and that is the entire point of this function. The counts these
    annotate partition the dated population, so a cumulative phrase over one of them is
    simply false. The board grid briefly read "confirmed within 90 days / within 180 days
    / within 360 days / over 360 days" against four exclusive counts: three of the four
    were wrong, and `beyond` — ratings PAST the cadence — was labelled "within 360 days",
    which reads as meeting a deadline.

    Every boundary is derived from `threshold_days`; none is hardcoded. They mirror
    age_band() in ../scripts/profile_analysis.py exactly: each band is inclusive of its
    upper bound, and `within` runs to T//2.
    """
    half = threshold_days // 2
    return {"within": f"0–{half}d",
            "approaching": f"{half + 1}–{threshold_days}d",
            "beyond": f"{threshold_days + 1}–{threshold_days * 2}d",
            "wellBeyond": f"over {threshold_days * 2}d"}


def age_band_bar(age: dict, threshold_days: int) -> str:
    """The band distribution as one proportional strip, with its denominator in view.

    Four bare counts as peer tiles beside the `older than T days` cell gave a reader five
    numbers, one of them the sum of two others, and a denominator for none of them. Same
    shape and same markup as evidence_bar: mutually-exclusive counts partitioning a
    stated total, drawn as one bar rather than as competing tiles, so the bands read as a
    grading OF the population that cell counts rather than as a rival to it.

    A band absent from the payload is dropped, never defaulted to 0: analyze output from
    an engine that predates banding does not carry these counts, and a rendered 0 would
    be a claim it never made. A band present and genuinely 0 has no width to draw either,
    so the caption states outright that an unlisted band is zero — the reader is never
    left inferring it.
    """
    bands = age.get("bands") or {}
    segs, legend = [], []
    ranges = age_band_ranges(threshold_days)
    for band in AGE_BAND_ORDER:
        if band not in bands:
            continue
        n = bands[band] or 0
        if not n:
            continue
        fill = AGE_BAND_FILL[band]
        fg = text_on(fill)
        label = f"{AGE_BAND_LABEL[band]} ({ranges[band]})"
        segs.append(f'<div class="eseg" style="flex:{n};background:{fill};color:{fg}" '
                    f'title="{esc(label)}: {n}">{n}</div>')
        legend.append(f'<span class="eleg"><i style="background:{fill}"></i>'
                      f'{esc(label)} {n}</span>')
    if not segs:
        return ""
    dated = age.get("dated") or 0
    return (f'<div class="ebar">{"".join(segs)}</div>'
            f'<div class="elegend">{"".join(legend)}</div>'
            f'<div class="muted" style="margin-top:6px">Graded across the {dated} dated '
            f'confirmation{"" if dated == 1 else "s"} counted above, against the '
            f'{threshold_days}-day cadence this Profile set for itself. A band not listed '
            f'here is zero. This is distance from that cadence — ratings do not expire, '
            f'and none of this says how much to trust a rating.</div>')


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
