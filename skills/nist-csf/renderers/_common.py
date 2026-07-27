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
SLATE = "#6A7180"; WB = "#F6F4EE"; WB_SURF = "#FFFFFF"; WB_LINE = "#D8D3C6"

# Coverage uses a sequential ramp, deliberately distinct from the register's risk-severity
# RAG ramp: low coverage is not "critical", it may be a low Target that is fully met.
COVERAGE_RAMP = [(25, "#7C3A32"), (50, "#A6603A"), (75, "#C08A3E"), (100, "#8A9A4B")]
COVERAGE_FULL = "#4A7C59"
UNTARGETED_FILL = WB_LINE          # hatched in CSS; must never read as 0% or 100%
NA_FILL = WB

PRIORITY_COLOR = {"low": "#6A7180", "medium": "#5F7A8A", "high": "#A6603A", "critical": "#7C3A32"}

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700'
         '&family=Space+Grotesk:wght@500;600&display=swap" rel="stylesheet">')
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


def cov_text_color(cov: dict) -> str:
    pct = cov.get("percent")
    if pct is None:
        return SLATE
    return LIME if pct < 50 else INK


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
        with open(path, encoding="utf-8") as fh:
            return Translations(json.load(fh))


class Context:
    """The analyze JSON plus an optional sidecar. A pass-through, not a derivation layer."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
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
header{{background:{INK};color:{LIME};padding:22px 28px}}
header h1{{font-size:21px;letter-spacing:-.01em}}
header .sub{{color:{LIME_DIM};font-size:13px;margin-top:6px}}
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


def page(title: str, head_extra: str, body: str) -> str:
    return (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{esc(title)}</title>{FONTS}"
            f"<style>{BASE_CSS}{head_extra}</style></head><body>{body}</body></html>")
