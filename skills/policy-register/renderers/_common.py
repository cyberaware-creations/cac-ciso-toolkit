#!/usr/bin/env python3
"""Shared rendering pieces for the policy-register reports.

Each skill carries its own `_common.py` rather than importing a shared one: every shipped
script must run standalone, so a cross-skill import needs sys.path surgery and breaks the
moment a single skill directory is used on its own. Documented the same way in the siblings.

THE COLOUR DECISION IS THE INTERESTING ONE HERE, so it is at the top rather than buried.

Every other register in this suite maps its states onto the RAG palette. This one deliberately
does not, and the reason is the rule the whole skill exists to hold: a requirement with an
approved policy is NOT known to be in good shape, and a requirement with no policy is NOT a
finding. Painting the first green and the second red would make the coverage claim in colour
that `no-coverage-claim.sh` forbids in words — and colour is the part a board reads first.

So:

  * `approved-policy` and `not-declared` take NEUTRAL chips. One says a document exists, the
    other says nothing has been mapped here yet. Neither is a verdict.
  * `draft-only` and `superseded-only` take the attention palette, because both describe a
    document problem this register genuinely can see: nobody has approved the thing, or the
    thing that was approved has been withdrawn and not replaced.

The legend says this in words on every page, because a reader who works it out from the
colours has already been misled once.
"""
#
# BRAND TOKENS ARE A DECLARED NINE-WAY TWIN (CAC-TW-1, BL-213). `FONTS`, `INK`, `LIME`,
# `PATINA`, `SLATE`, `WB`, `WB_SURF` and `WB_LINE` are duplicated across all nine
# `renderers/_common.py` copies and must agree character for character — one palette, one
# brand, whatever surface a reader is on. The family is listed in
# skills/risk-register/renderers/_common.py; `tools/check-twins.py` compares all nine on every
# run and fails if any token moves alone.
#
# Nothing else in these modules is claimed to agree. Each carries its own derivation layer and
# its own CLI surface, deliberately.
from __future__ import annotations

import argparse
import html
import json
import re
from datetime import date

# Vendored alongside this file, for the same reason this file is vendored: a shipped
# script must run from its own skill directory with no path surgery.
# tools/check-versions.py fails if this copy drifts from tools/cac_graphics.py.
import cac_graphics as G

INK = "#14171C"
LIME = "#EAE7DF"
PATINA = "#2FA98C"
SLATE = "#666D7C"
WB = "#F6F4EE"
WB_SURF = "#FFFFFF"
WB_LINE = "#D8D3C6"
MUTED = "#4A4F58"

# Requirement-state chips. See the module docstring for why two of the four are neutral.
# The banded pair comes from the library so a chip and any mark beside it cannot draw one
# meaning in two colours.
STATE_FILL = {}
STATE_LABEL = {
    "not-declared": "not declared",
    "draft-only": "draft only",
    "superseded-only": "superseded, not replaced",
    "approved-policy": "approved policy recorded",
}
# Policy lifecycle chips, on the record itself.
POLICY_STATE_LABEL = {"draft": "draft", "approved": "approved", "superseded": "superseded"}
POLICY_STATE_FILL = {}
REVIEW_LABEL = {
    "review-current": "review scheduled",
    "review-due": "review due",
    "review-overdue": "review overdue",
    "no-review-date": "no review date",
}
REVIEW_FILL = {}


def _rebuild_derived() -> None:
    """Recompute every palette that depends on a rebindable colour name.

    Called at import and again after `apply_brand`, so a client brand reaches the chips and
    not only the charts. A brand that reached the charts and left the chips in CAC colours
    is a worse result than no override at all, because only one half looks deliberate.
    """
    STATE_FILL.clear()
    STATE_FILL.update({
        # Neutral, and deliberately so.
        "not-declared": ("#EFEDE7", MUTED),
        "approved-policy": ("#E6EEF6", "#204A6E"),
        # Attention, because these are document problems this register can actually see.
        "draft-only": G.chip("high"),
        "superseded-only": G.chip("critical"),
    })
    POLICY_STATE_FILL.clear()
    POLICY_STATE_FILL.update({
        "draft": ("#EFEDE7", MUTED),
        "approved": ("#E6EEF6", "#204A6E"),
        "superseded": ("#EDE0EA", "#5E3660"),
    })
    REVIEW_FILL.clear()
    REVIEW_FILL.update({
        "review-current": ("#EFEDE7", MUTED),
        "review-due": G.chip("high"),
        "review-overdue": G.chip("critical"),
        "no-review-date": G.chip("high"),
    })


_rebuild_derived()

# The sentence this page exists to stop a reader assuming. It is a caveat block on the page,
# not a footnote, for the same reason the exceptions register puts discoverability up top:
# a reader who does not see it has not been told the thing that most affects how they should
# read everything below.
CAVEAT = ("A policy mapped to a requirement records that a document exists, that a named "
          "person approved it on a date, and what it is aimed at. It is not evidence that "
          "the requirement is met. This register has no way to determine whether it is, and "
          "does not try — a policy nobody follows maps exactly as well as one everybody "
          "does.")

SPINE_NOTE = ("The requirements listed here are the NIST policy spine: the Policy and "
              "Procedures control in each SP 800-53 Rev. 5 family, plus CSF 2.0 GV.PO-01 "
              "and GV.PO-02. They are not this organisation's obligations, so this page "
              "reports counts and never a proportion.")


# --- Client brand override ----------------------------------------------------

_BRAND_BINDINGS = {
    "INK": "ink", "LIME": "lime", "PATINA": "patina", "SLATE": "slate",
    "WB": "bg", "WB_SURF": "surface", "WB_LINE": "line", "MUTED": "muted",
}
# Snapshotted at import and restored verbatim when no brand is supplied, so "no --brand
# renders exactly what it always did" is true by construction rather than by inspection.
_BRAND_DEFAULTS = {n: globals()[n] for n in _BRAND_BINDINGS if n in globals()}


def apply_brand(path: str = "") -> None:
    """Rebind this module's shell from a client brand file, or restore the CAC one.

    Raises `SystemExit` with the reason on a bad file or a refused palette. A renderer that
    fell back to CAC colours after a failed override would hand a client a document that
    looks finished and is not the one they asked for.
    """
    if not path:
        globals().update(_BRAND_DEFAULTS)
        G.set_brand()
        _rebuild_derived()
        return
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except OSError as exc:
        raise SystemExit("--brand %s: %s" % (path, exc))
    except ValueError as exc:
        raise SystemExit("--brand %s is not valid JSON: %s" % (path, exc))
    if not isinstance(raw, dict):
        raise SystemExit("--brand %s must contain a JSON object, got %s"
                         % (path, type(raw).__name__))
    try:
        shell = G.apply_chrome(raw)
    except G.BrandError as exc:
        raise SystemExit("--brand %s was refused:\n%s" % (path, exc))
    g = globals()
    for name, key in _BRAND_BINDINGS.items():
        if name in g:
            g[name] = shell[key]
    _rebuild_derived()


# --- Small helpers ------------------------------------------------------------

def esc(s) -> str:
    """HTML-escape a scalar for a text slot, and REFUSE a container.

    `str()` on a dict produces a Python repr; `html.escape` then turns its quotes into
    `&#x27;`, and a board reads `{'text': ...}` off the page. That is a shipped P1, and the
    escaping is also why it survived: the guard greps for the RAW repr, which escaping has
    already destroyed, so five suites reported clean over a live defect (BL-209 / BL-199).

    Scalars are unaffected and deliberately so. A runtime census over every eval suite in the
    repo found 21,213 strings, 595 ints and four dicts — the ints are legitimate (`esc(42)` is
    "42") and all four dicts were the defect. So the rule is not "strings only", which would
    break 595 real call sites; it is that a container never belongs in a text slot.

    It raises rather than rendering, at the call site holding the object rather than three
    layers later in a page nobody diffed."""
    if isinstance(s, (dict, list, tuple, set)):
        raise TypeError(
            "esc() was passed a %s. It would render on the page as a Python repr: %.140r\n"
            "  Pass the field a reader should see. For a decision object that is d['text'].\n"
            "  Escaping does not save you here, it hides the problem: html.escape rewrites\n"
            "  the repr's quotes as &#x27;, so the output slips a grep for {'text'."
            % (type(s).__name__, s))
    return html.escape("" if s is None else str(s))


def chip(fills: dict, labels: dict, key: str) -> str:
    bg, fg = fills.get(key, ("#EFEDE7", MUTED))
    return ('<span class="chip" style="background:%s;color:%s">%s</span>'
            % (bg, fg, esc(labels.get(key, key))))


def state_chip(state: str) -> str:
    return chip(STATE_FILL, STATE_LABEL, state)


def policy_chip(state: str) -> str:
    return chip(POLICY_STATE_FILL, POLICY_STATE_LABEL, state)


def review_chip(state: str) -> str:
    return chip(REVIEW_FILL, REVIEW_LABEL, state) if state else ""


# Escalation severities come from the engine as `high` / `medium` / `low`. They describe the
# ATTENTION an item needs, not a judgment about the requirement, and they are the one place
# on this page where the RAG palette is the right vocabulary.
_SEV_TO_BAND = {"high": "critical", "medium": "high", "low": "good"}


def severity_chip(severity: str, label: str) -> str:
    bg, fg = G.chip(_SEV_TO_BAND.get(severity, "high"))
    return ('<span class="chip" style="background:%s;color:%s">%s</span>'
            % (bg, fg, esc(label)))


_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def iso_or_none(value):
    return value if isinstance(value, str) and _ISO.match(value) else None


def days_phrase(days, noun: str) -> str:
    if days is None:
        return ""
    if days < 0:
        return "%d %s overdue" % (-days, noun)
    return "in %d day%s" % (days, "" if days == 1 else "s")


# --- Page shell ---------------------------------------------------------------

# The gstatic preconnect is where the font FILES come from; the googleapis one only
# reaches the stylesheet. Eight of the nine copies had only the second until v0.85.0,
# so the nine `FONTS` values were not identical and the CAC-TW-1 brand-token twin below
# could not be registered without either converging them or exempting a real difference.
# Converged on the fuller form rather than the majority one: matching eight files by
# deleting a correct resource hint from the ninth would be the checker dictating the
# product (BL-213).
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700'
         '&family=Space+Grotesk:wght@500;600&display=swap" rel="stylesheet">')


def base_css() -> str:
    return """
*{box-sizing:border-box}
body{margin:0;padding:24px;background:%(WB)s;color:%(INK)s;
  font-family:Manrope,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  font-size:15px;line-height:1.55}
.wrap{max-width:1100px;margin:0 auto}
h1,h2,h3{font-family:'Space Grotesk',Manrope,sans-serif;margin:0 0 8px;line-height:1.25}
h1{font-size:26px} h2{font-size:19px;margin-top:28px} h3{font-size:16px}
p{margin:0 0 10px}
.sub{color:%(MUTED)s;margin:0 0 18px}
.band{background:%(INK)s;color:%(LIME)s;border-radius:10px;padding:12px 16px;
  display:flex;align-items:center;gap:10px;margin-bottom:18px;flex-wrap:wrap}
.band .spark{width:10px;height:10px;border-radius:3px;background:%(PATINA)s;flex:none}
.band .lockup{font-family:'Space Grotesk',Manrope,sans-serif;font-weight:600}
.band .kicker{color:%(LIME)s;opacity:.75;margin-left:auto;font-size:13px}
.caveat{border:1px solid %(WB_LINE)s;border-left:4px solid %(PATINA)s;background:%(WB_SURF)s;
  border-radius:8px;padding:12px 14px;margin:0 0 18px}
.caveat strong{display:block;font-family:'Space Grotesk',Manrope,sans-serif;margin-bottom:4px}
.tiles{display:flex;flex-wrap:wrap;gap:12px;margin:0 0 18px}
.tile{background:%(WB_SURF)s;border:1px solid %(WB_LINE)s;border-radius:8px;padding:12px 14px;
  min-width:150px;flex:1 1 150px}
.tile .n{display:block;font-family:'Space Grotesk',Manrope,sans-serif;font-size:26px;
  font-weight:600;font-variant-numeric:tabular-nums}
.tile .l{display:block;color:%(MUTED)s;font-size:13px}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;width:100%%;background:%(WB_SURF)s;border:1px solid %(WB_LINE)s;
  border-radius:8px}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid %(WB_LINE)s;
  vertical-align:top;font-size:14px}
th{font-family:'Space Grotesk',Manrope,sans-serif;font-weight:600;font-size:13px;
  color:%(MUTED)s;white-space:nowrap}
tr:last-child td{border-bottom:none}
td.id{white-space:nowrap;font-variant-numeric:tabular-nums}
.chip{display:inline-block;border-radius:999px;padding:2px 9px;font-size:12px;
  font-weight:600;white-space:nowrap}
.muted{color:%(MUTED)s;font-size:13px}
.famrow td{background:%(LIME)s;font-family:'Space Grotesk',Manrope,sans-serif;font-weight:600}
.legend{display:flex;flex-wrap:wrap;gap:14px;margin:10px 0 0;font-size:13px;color:%(MUTED)s}
.legend span{display:flex;align-items:center;gap:6px}
.legend i{width:12px;height:12px;border-radius:3px;display:inline-block}
.esc{background:%(WB_SURF)s;border:1px solid %(WB_LINE)s;border-radius:8px;padding:12px 14px;
  margin:0 0 10px}
.esc .what{font-weight:600}
footer{margin-top:28px;padding-top:12px;border-top:1px solid %(WB_LINE)s;color:%(MUTED)s;
  font-size:12px}
@media print{body{padding:0;background:#fff}.scroll{overflow:visible}}
""" % globals()


def section(heading: str, body: str) -> str:
    """A heading only where there is something under it. An empty section reads as a bug."""
    return '<h2>%s</h2>%s' % (esc(heading), body) if body else ""


def band(title: str, kicker: str = "") -> str:
    """The CAC header band: ink ground, patina spark, lockup, optional kicker."""
    k = '<span class="kicker">%s</span>' % esc(kicker) if kicker else ""
    return ('<div class="band"><span class="spark"></span>'
            '<span class="lockup">%s</span>%s</div>' % (esc(title), k))


def legend() -> str:
    """What the colours mean, in words, including what they deliberately do NOT mean."""
    items = [(STATE_FILL["approved-policy"][0],
              "approved policy recorded — a document exists, not a verdict"),
             (STATE_FILL["not-declared"][0],
              "not declared — nothing mapped here yet, which is not a finding"),
             (STATE_FILL["draft-only"][0], "draft only — nobody has approved it"),
             (STATE_FILL["superseded-only"][0],
              "superseded and not replaced — nothing in force")]
    out = ['<span><i style="background:%s"></i>%s</span>' % (c, esc(t)) for c, t in items]
    return '<div class="legend">%s</div>' % "".join(out)


def page(title: str, body: str, offline: bool = False) -> str:
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>%s</title>%s<style>%s</style></head><body><div class="wrap">'
            '%s</div></body></html>'
            % (esc(title), "" if offline else FONTS, base_css(), body))


def build_parser(description: str, default_out: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description,
                                epilog="This report is not legal advice.",
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--in", dest="infile", required=True,
                   help="policy_register.py analyze --out JSON")
    p.add_argument("--out", default=default_out)
    p.add_argument("--brand", metavar="FILE",
                   help="client brand JSON — ink, patina, bg, measure, wordmark, "
                        "whiteLabel. Refused rather than approximated if any pairing "
                        "falls below its contrast floor")
    p.add_argument("--offline", action="store_true",
                   help="emit no external request — the artifact opens in a room, "
                        "on a laptop, with no network")
    return p


class Context:
    """The analysis, loaded once, with the accessors both surfaces need."""

    def __init__(self, args):
        apply_brand(getattr(args, "brand", "") or "")
        with open(args.infile, encoding="utf-8") as fh:
            self.data = json.load(fh)
        fam = self.data.get("family")
        if fam != "policy-register":
            raise SystemExit("--in %s is a %r analysis, not a policy-register one"
                             % (args.infile, fam))
        self.out_path = args.out
        self.offline = bool(getattr(args, "offline", False))
        self.meta = self.data.get("meta") or {}
        self.today = self.data.get("today") or date.today().isoformat()
        self.requirements = self.data.get("requirements") or []
        self.policies = self.data.get("policies") or []
        self.counts = self.data.get("stateCounts") or {}
        self.escalations = self.data.get("escalations") or []
        # The review agenda, beside the escalations rather than inside them (v0.70.0). An
        # analysis written by an older engine carries no `attention` key, and an empty dict
        # is the honest reading of that: this renderer cannot re-derive the lists, because
        # the engine computed them against a review window it does not hold.
        self.attention = self.data.get("attention") or {}
        self.limits = self.data.get("limits") or []

    def in_catalogue(self) -> list:
        return [r for r in self.requirements if r.get("inCatalogue")]

    def outside_catalogue(self) -> list:
        return [r for r in self.requirements if not r.get("inCatalogue")]

    def caveat_block(self) -> str:
        return ('<div class="caveat"><strong>What a mapping does and does not say</strong>'
                '<p>%s</p></div>' % esc(CAVEAT))

    def footer(self) -> str:
        bits = [b for b in (esc(self.meta.get("orgName") or ""),
                            "as at %s" % esc(self.today),
                            "Not legal advice.") if b]
        return "<footer>" + " · ".join(bits) + "</footer>"


def write(ctx: Context, doc: str, note: str) -> int:
    with open(ctx.out_path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print("wrote %s (%s bytes) — %s" % (ctx.out_path, format(len(doc), ","), note))
    return 0
