#!/usr/bin/env python3
"""Shared rendering pieces for the business-context framing output.

Each skill carries its own `_common.py` rather than importing a shared one: every shipped
script must run standalone, so a cross-skill import needs sys.path surgery and breaks the
moment a single skill directory is used on its own. Documented the same way in the siblings.

This skill draws no charts. It vendors `cac_graphics` anyway, and not as a formality: the
attribution line has exactly one sanctioned source, `G.footer()`, which is what drops the
maker's name on a white-labelled page while keeping the NIST disclaimer. Hardcoding that
line here is refused by `tools/check-versions.py::check_maker_name`, so importing the
library is the only correct way to produce it — which settles whether the vendored copy
belongs in a chartless skill.
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

# Vendored alongside this file, for the same reason this file is vendored: a shipped
# script must run from its own skill directory with no path surgery.
# tools/check-versions.py fails if this copy drifts from tools/cac_graphics.py.
import cac_graphics as G

INK = "#14171C"
INK_RAISED = "#1C2026"
LIME = "#EAE7DF"
LIME_DIM = "#9AA0A6"
PATINA = "#2FA98C"
SLATE = "#666D7C"
MUTED = "#4A4F58"
WB = "#F6F4EE"
WB_SURF = "#FFFFFF"
WB_LINE = "#D8D3C6"

# ⚠️ ALIGNED WITH THE OTHER EIGHT IN v0.85.0, and it was wrong here (BL-213).
#
# This module requested `Manrope:wght@400;600;800` and `Space+Grotesk:wght@500;700` while the
# other eight `_common.py` copies requested `400;600;700` and `500;600`. Its own stylesheet
# uses `font-weight: 700` three times and 800 nowhere — so every bold heading on a
# business-context page fell back to a synthesised bold off the 600 face, while the same
# heading on a risk-register or nist-csf page rendered in the real 700. Two weights were
# downloaded and never used; the one actually used was never fetched.
#
# Invisible in every test: the page renders, the CSS is valid, and the difference is a font
# the browser quietly approximates. Found by enumerating the brand tokens across all nine
# copies for the CAC-TW-1 registration below, which is the registration's whole point.
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700'
         '&family=Space+Grotesk:wght@500;600&display=swap" rel="stylesheet">')
FONTS_OFFLINE = ""


def fonts(offline: bool) -> str:
    """The <head> font links, or nothing at all when rendering offline."""
    return FONTS_OFFLINE if offline else FONTS


# --- Client brand override ----------------------------------------------------
#
# The chart marks followed a client brand long before the page around them did: the graphics
# library floors what it can see, and this shell — a dark band, light text on it, a lifted
# sub-header — lived here as literals. A brand that reached the charts and left the page in
# CAC colours is a worse result than no override at all, because only one half of it looks
# deliberate.
#
# `G.chrome()` now owns the shell and floors the pairings the library cannot see. This binds
# what that returns onto the names the CSS below already interpolates.
_BRAND_BINDINGS = {
    "INK": "ink", "INK_RAISED": "inkRaised", "INK_LINE": "inkLine",
    "LIME": "lime", "LIME_DIM": "limeDim",
    "PATINA": "patina", "PATINA_H": "patinaHover", "PATINA_TEXT": "patinaText",
    "SLATE": "slate", "WB": "bg", "WB_SURF": "surface", "WB_LINE": "line",
    "MUTED": "muted",
}
# Snapshotted at import, and restored verbatim when no brand is supplied. Not recomputed from
# `G.chrome()`, deliberately: a couple of these values were tuned in this file and differ
# slightly from the library's, and rebuilding the default from the library would change what
# an unbranded page renders. Restoring the literal shipped values makes "no --brand renders
# exactly what it always did" true by construction rather than by inspection.
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
    # No `_rebuild_derived()` here, unlike the siblings: this skill builds no fill maps or
    # chip-text maps from the palette, so there is nothing downstream to recompute. Copying
    # the call across without the function is what broke the first render.

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


def base_css() -> str:
    """The page stylesheet, built when it is asked for.

    A function and not a module constant: this is an f-string over the palette, and the
    palette is rebound by `apply_brand()` at render time. Bound at import it would freeze
    the CAC colours and a `--brand` override would reach nothing.
    """
    return f"""
*{{box-sizing:border-box}}
body{{margin:0;font-family:'Manrope',system-ui,sans-serif;background:{WB};color:{INK};
  line-height:1.55}}
.wrap{{max-width:900px;margin:0 auto;padding:0 24px 48px}}
header{{background:{INK};color:{LIME};padding:28px 0;margin-bottom:28px}}
header .wrap{{padding-bottom:0}}
header .eyebrow{{color:{PATINA};font-size:11px;letter-spacing:.16em;
  text-transform:uppercase;font-weight:700}}
header h1{{font-family:'Space Grotesk','Manrope',system-ui,sans-serif;
  font-size:30px;margin:8px 0 0}}
header .sub{{color:{LIME_DIM};font-size:13px;margin-top:10px}}
h2{{font-family:'Space Grotesk','Manrope',system-ui,sans-serif;font-size:17px;
  margin:28px 0 10px}}
.lead{{font-size:15.5px}}
.card{{background:{WB_SURF};border:1px solid {WB_LINE};border-radius:10px;
  padding:16px 18px;margin:12px 0}}
.k{{color:{MUTED};font-size:12px;text-transform:uppercase;letter-spacing:.08em;
  font-weight:700}}
.jewel{{margin:10px 0;padding-left:12px;border-left:3px solid {PATINA}}}
.jewel .sys{{font-weight:700}}
.jewel .stake{{color:{MUTED};font-size:13.5px}}
.jewel .mark{{font-size:13px;margin-top:2px}}
.jewel .mark .basis{{color:{MUTED}}}
blockquote{{margin:10px 0;padding:12px 16px;background:{WB_SURF};
  border-left:3px solid {SLATE};font-size:14.5px}}
blockquote .who{{display:block;color:{MUTED};font-size:12px;margin-top:8px}}
.prov{{margin-top:28px;padding-top:14px;border-top:1px solid {WB_LINE};
  color:{MUTED};font-size:12px}}
footer{{color:{MUTED};font-size:12px;margin-top:18px}}
@media print{{header{{background:{INK} !important;-webkit-print-color-adjust:exact}}}}
"""
