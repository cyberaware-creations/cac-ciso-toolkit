#!/usr/bin/env python3
"""A top-banded metric must render a readable bullet. Used by graphics-contract.sh.

Driven through metrics-register's own `mark_for`, so it checks the decision the
renderer actually makes rather than the capability the library merely has.

The shapes below are the ordinary ones in this domain — patch coverage, MFA
enrolment, backup success. All three band inside the top 15 percent of a 0-100
axis, which is exactly where the shared-ceiling rule used to produce a bar that
was 85 percent one colour with its thresholds crushed into the right edge.
"""
import math
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "skills" / "metrics-register" / "renderers"))
import _common as C  # noqa: E402

CASES = [
    ("patch coverage", {"target": 95.0, "warn": 90.0, "critical": 85.0}, 88.0),
    ("MFA enrolment",  {"target": 99.0, "warn": 95.0, "critical": 90.0}, 96.0),
    ("backup success", {"target": 99.0, "warn": 98.0, "critical": 95.0}, 97.0),
    # Thresholds that do not divide evenly, so the floor has to be rounded down to
    # a step rather than left on whatever the arithmetic produced. Without this
    # case the rounding is untested: every shape above lands on a multiple of 5 by
    # accident, and dropping the rounding entirely changes nothing.
    ("odd thresholds", {"target": 96.0, "warn": 92.0, "critical": 87.0}, 93.0),
]
# A band thinner than this share of the bar cannot be read as a band at all.
MIN_BAND_SHARE = 0.10

problems, checked, checked_gauge, checked_low, checked_tgt = [], 0, 0, 0, 0
for name, thr, value in CASES:
    row = {"id": "M-001", "value": value, "unit": "percent", "threshold": thr,
           "direction": "higher-better", "viz": "bullet", "status": "ok",
           "readings": []}
    svg = C.mark_for(row)
    if not svg:
        problems.append("%s produced no mark" % name)
        continue
    widths = [float(w) for w in
              re.findall(r'<rect x="[\d.]+" y="26" width="([\d.]+)"', svg)]
    if len(widths) != 3:
        problems.append("%s drew %d bands, expected 3" % (name, len(widths)))
        continue
    checked += 1
    share = min(widths) / sum(widths)
    if share < MIN_BAND_SHARE:
        problems.append("%s: narrowest band is %.1f%% of the bar" % (name, share * 100))
    # The numbers the bands are drawn from have to survive on the axis.
    labels = {l for l in re.findall(r'>([\d.]+)%<', svg)}
    missing = [t for t in (thr["warn"], thr["critical"])
               if not any(abs(float(l) - t) < 1e-9 for l in labels)]
    if len(missing) > 1:
        problems.append("%s: %d of its 2 thresholds are unlabelled" % (name, len(missing)))
    # A raised floor must announce itself, or bar length reads against a baseline
    # the reader has no reason to doubt.
    left = re.search(r'text-anchor="start"[^>]*>([\d.]+)', svg)
    if left and float(left.group(1)) > 0 and 'stroke-width="3.5"' not in svg:
        problems.append("%s: axis starts at %s with no break glyph"
                        % (name, left.group(1)))

    # A floor is an axis number a reader has to hold in their head. It lands on a
    # step; 74% is arithmetic showing through.
    if left and float(left.group(1)) > 0 and float(left.group(1)) % 5 != 0:
        problems.append("%s: axis floor %s is not on a step"
                        % (name, left.group(1)))

# The dial compresses exactly as the bar does — it just hides it better, because
# an arc squeezed into 8 degrees still looks like an arc. Measured as the angular
# span of each band, around the hub the library draws it at.
def _arc_spans(svg):
    spans = []
    for x0, y0, x1, y1 in re.findall(
            r'<path d="M ([\d.]+) ([\d.]+) A \d+ \d+ 0 0 1 ([\d.]+) ([\d.]+)"'
            r'[^>]*stroke-width="13"', svg):
        a0 = math.atan2(96 - float(y0), float(x0) - 100)
        a1 = math.atan2(96 - float(y1), float(x1) - 100)
        spans.append(abs(a0 - a1))
    return spans

for name, thr, value in CASES:
    row = {"id": "M-002", "value": value, "unit": "percent", "threshold": thr,
           "direction": "higher-better", "viz": "gauge", "status": "ok",
           "readings": []}
    svg = C.mark_for(row)
    spans = _arc_spans(svg)
    if len(spans) != 3:
        problems.append("%s gauge drew %d band arcs, expected 3" % (name, len(spans)))
        continue
    checked_gauge += 1
    share = min(spans) / sum(spans)
    if share < MIN_BAND_SHARE:
        problems.append("%s gauge: narrowest arc is %.1f%% of the dial"
                        % (name, share * 100))

# A reading far BELOW the bands must not be zoomed away, and this is the case the
# renderer's own guard exists for rather than the library's. bullet() abandons a
# floor that sits above the data; radial_gauge has no such fallback — hand it a
# min_v above the value and `pct` clamps to 0, pinning the needle hard left where
# it reads as "zero" instead of "well short". So the renderer must not ASK.
low_thr = {"target": 95.0, "warn": 90.0, "critical": 85.0}
low_row = {"id": "M-003", "value": 55.0, "unit": "percent", "threshold": low_thr,
           "direction": "higher-better", "viz": "gauge", "status": "critical",
           "readings": []}
if C._axis_min(low_row, low_thr, 100) is not None:
    problems.append("a reading below the bands still got a raised floor")
else:
    checked_low += 1
    gsvg = C.mark_for(low_row)
    # The needle is a tapered polygon; its first point is the tip.
    needle = re.search(r'<polygon points="([\d.]+),([\d.]+) ', gsvg)
    if not needle:
        problems.append("the low-reading gauge drew no needle")
    else:
        ang = math.atan2(96 - float(needle.group(2)), float(needle.group(1)) - 100)
        frac = 1.0 - ang / math.pi
        if not 0.45 < frac < 0.65:
            problems.append("the low-reading needle sits at %.2f of the dial, not "
                            "near its 0.55 value" % frac)
    lsvg = C.mark_for(dict(low_row, viz="bullet"))
    left = re.search(r'text-anchor="start"[^>]*>([\d.]+)', lsvg)
    if not left or float(left.group(1)) != 0:
        problems.append("the low-reading bullet did not fall back to a zero axis")

# The same trap on the TARGET rather than the value, which only a lower-better
# metric reaches: bands high on the axis, target far below them. bullet() protects
# itself — target is in the set the floor is checked against — but the gauge draws
# its target tick straight from min_v, so a floor above the target slides the tick
# to the far left and points it at the wrong number.
tgt_thr = {"target": 30.0, "warn": 70.0, "critical": 80.0}
tgt_row = {"id": "M-004", "value": 65.0, "unit": "percent", "threshold": tgt_thr,
           "direction": "lower-better", "viz": "gauge", "status": "ok",
           "readings": []}
if C._axis_min(tgt_row, tgt_thr, 100) is not None:
    problems.append("a target below the floor still got a raised floor")
else:
    checked_tgt += 1
    tsvg = C.mark_for(tgt_row)
    tick = re.search(r'<line x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)"', tsvg)
    if not tick:
        problems.append("the low-target gauge drew no target tick")
    else:
        ta = math.atan2(96 - float(tick.group(2)), float(tick.group(1)) - 100)
        tfrac = 1.0 - ta / math.pi
        if not 0.2 < tfrac < 0.4:
            problems.append("the target tick sits at %.2f of the dial, not near "
                            "its 0.30 value" % tfrac)

if checked_tgt != 1:
    problems.append("the low-target case did not run")
if checked_low != 1:
    problems.append("the below-the-bands case did not run")
if checked != len(CASES) or checked_gauge != len(CASES):
    problems.append("only %d bullets and %d gauges were checked, of %d shapes"
                    % (checked, checked_gauge, len(CASES)))

print("PASS %d shapes as bullet and gauge, narrowest band >= %d%%"
      % (checked, MIN_BAND_SHARE * 100) if not problems
      else "FAIL " + "; ".join(problems[:3]))
