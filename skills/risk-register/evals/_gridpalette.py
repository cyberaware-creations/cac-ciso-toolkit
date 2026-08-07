#!/usr/bin/env python3
"""One grid, one palette. Used by board-safety.sh.

Its own file rather than a heredoc inside a command substitution: that nesting is how a
shell suite acquires a parse error, and this suite hit exactly that on the first attempt —
the check did not run at all, which a suite reporting PASS elsewhere makes easy to miss.
"""
import pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(sys.argv[2]) / "tools"))
import cac_graphics as G
MID  = {G._RAG[s]["mid"] for s in ("good", "medium", "high", "critical")}
FILL = {G._RAG[s]["fill"] for s in ("good", "medium", "high", "critical")}
work = pathlib.Path(sys.argv[1])
problems, checked = [], 0

# 1. the library, called directly with a RAG grid
svg = G.heat_matrix([[{"sev": "good", "label": "1"}, {"sev": "medium", "label": "2"}],
                     [{"sev": "high", "label": "3"}, {"sev": "critical", "label": "4"}]])
lib = set(re.findall(r'fill="(#[0-9A-Fa-f]{6})"', svg)) & (MID | FILL)
if not lib:
    problems.append("heat_matrix emitted no band-coloured cell; this check saw nothing")
else:
    checked += 1
    if not lib <= MID:
        problems.append("heat_matrix draws cells in %s" % sorted(lib - MID))

# 2. the report's HTML table
f = work / "render_report.html"
cells = set(re.findall(r'<td style="background:(#[0-9A-Fa-f]{6})', f.read_text())) if f.exists() else set()
if not cells:
    problems.append("render_report drew no matrix cells; this check saw nothing")
else:
    checked += 1
    if not cells <= MID:
        problems.append("render_report draws cells in %s" % sorted(cells - MID))

# 3. the dashboard's injected constant, which its JS builds every cell from
f = work / "render_dashboard.html"
m = re.search(r"const BAND_MID=(\{[^;]*\})", f.read_text()) if f.exists() else None
if not m:
    problems.append("render_dashboard injects no BAND_MID, so its grid is not zone-toned")
else:
    checked += 1
    tones = set(re.findall(r"#[0-9A-Fa-f]{6}", m.group(1)))
    if tones != MID:
        problems.append("render_dashboard injects %s, not the zone tones" % sorted(tones))
    # Scoped to the GRID cell, not to every use of BAND. Chips elsewhere on the page are
    # meant to be saturated — a chip IS a status mark, where a cell is a region — and the
    # first version of this line matched them and failed for the wrong reason.
    if re.search(r'<td class="cell\$\{s\}" style="background:\$\{BAND\[', f.read_text()):
        problems.append("render_dashboard still paints a grid cell from the status fill")

if checked < 3:
    problems.append("only %d of 3 sites were checked" % checked)
print("PASS" if not problems else "FAIL " + "; ".join(problems[:3]))
