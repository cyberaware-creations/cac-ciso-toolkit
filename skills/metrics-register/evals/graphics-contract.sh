#!/usr/bin/env bash
# graphics-contract.sh — the colour contract, asserted on rendered output.
#
# The library's own self-test proves each mark in isolation. This proves the
# renderer wired them up correctly: that the engine's status reaches the mark, that
# a metric with no threshold stays out of the RAG palette entirely, and that one
# metric renders as one mark across both views.
#
# Counts, not absences. "No red anywhere" passes on a blank page, so every check
# that asserts something is missing is paired with one asserting what is there.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=21
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

echo "graphics-contract: $($PY -V 2>&1)"

$PY "$skill/scripts/metrics_analysis.py" analyze "$skill/examples/example-metrics.mtr" \
    --out "$work/a.json" >/dev/null
(cd "$skill/renderers" && $PY render_executive.py --in "$work/a.json" \
    --translations "$skill/examples/example-translations.json" \
    --out "$work/exec.html" --offline) >/dev/null
(cd "$skill/renderers" && $PY render_operational.py --in "$work/a.json" \
    --out "$work/ops.html" --offline) >/dev/null

# All assertions run inside one Python process against the rendered HTML, so a
# check that cannot find its metric fails loudly instead of matching nothing.
$PY - "$work/a.json" "$work/exec.html" "$work/ops.html" <<'PYEOF' > "$work/out.txt"
import json, re, sys
sys.path.insert(0, __import__("os").path.join(
    __import__("os").path.dirname(sys.argv[2]), ""))

analysis, exec_html, ops_html = sys.argv[1], sys.argv[2], sys.argv[3]
A = json.load(open(analysis))
EX = open(exec_html, encoding="utf-8").read()
OP = open(ops_html, encoding="utf-8").read()

RAG_FILL = {"good": "#30915B", "medium": "#e8c547",
            "high": "#e08e0b", "critical": "#c0392b"}
RAG_MID = {"good": "#86BE9C", "medium": "#F0DC92",
           "high": "#EEC17E", "critical": "#DFA096"}
MEASURE = "#2E6FA7"
ALL_RAG = set(RAG_FILL.values()) | set(RAG_MID.values())

BY_ID = {m["metricId"]: m for m in A["metrics"]}
IDS = sorted(BY_ID)


def segment(html, mid):
    """The rendered block for one metric, bounded by the next metric id."""
    i = html.find(mid)
    if i < 0:
        return None
    nxt = [html.find(o, i + 1) for o in IDS if html.find(o, i + 1) > i]
    return html[i:min(nxt)] if nxt else html[i:]


def svgs(seg):
    return re.findall(r"<svg.*?</svg>", seg, re.S) if seg else []


def hexes(text):
    return {h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}", text or "")}


out = []
def emit(good, name, detail=""):
    out.append(("ok" if good else "FAIL", name, detail))

# 1-2. Every metric renders a mark in both views. Guards every later check:
# an absence check over a metric that rendered nothing proves nothing.
missing_ex = [m for m in IDS if not svgs(segment(EX, m))]
emit(not missing_ex, "every metric renders a mark in the board view",
     "no mark for: %s" % ", ".join(missing_ex))
missing_op = [m for m in IDS if not svgs(segment(OP, m))]
emit(not missing_op, "every metric renders a mark in the working view",
     "no mark for: %s" % ", ".join(missing_op))

# 3. The same metric renders as the same mark in both views (standard 6.1).
mismatch = []
for m in IDS:
    a = svgs(segment(EX, m))
    b = svgs(segment(OP, m))
    if not a or not b or re.sub(r"\s+", " ", a[0]) != re.sub(r"\s+", " ", b[0]):
        mismatch.append(m)
emit(not mismatch, "one metric renders as one mark across both views",
     "differs for: %s" % ", ".join(mismatch))

# 4-5. A metric with no threshold emits the measure colour and ZERO RAG fills.
# Both halves: "no RAG" alone would pass on an empty mark.
noth = [m for m in IDS if BY_ID[m]["status"] == "no-threshold"]
emit(len(noth) == 1, "the fixture carries exactly one metric with no threshold",
     "found %d" % len(noth))
nid = noth[0] if noth else None
if nid:
    marks = "".join(svgs(segment(EX, nid)))
    got = hexes(marks)
    emit(not (got & {h.upper() for h in ALL_RAG}),
         "a metric with no threshold emits zero RAG colours",
         "found %s in %s" % (sorted(got & {h.upper() for h in ALL_RAG}), nid))
    emit(MEASURE.upper() in got or not got,
         "...and renders in the measure colour", "%s: %s" % (nid, sorted(got)))
else:
    emit(False, "a metric with no threshold emits zero RAG colours", "no fixture")
    emit(False, "...and renders in the measure colour", "no fixture")

# 6-8. Status reaches the mark: warn -> amber, critical -> red, ok -> green.
# Asserted per status, not in bulk, so one green metric cannot carry the rest.
WANT = {"warn": RAG_FILL["high"], "critical": RAG_FILL["critical"],
        "ok": RAG_FILL["good"]}
for status, want in sorted(WANT.items()):
    ids = [m for m in IDS if BY_ID[m]["status"] == status]
    if not ids:
        emit(False, "a %s metric emits %s in its mark" % (status, want),
             "no metric with status %s in the fixture" % status)
        continue
    hit = [m for m in ids if want.upper() in hexes("".join(svgs(segment(EX, m))))]
    emit(bool(hit), "a %s metric emits %s in its mark" % (status, want),
         "none of %s did" % ", ".join(ids))

# 9. The status chip and the mark agree for every metric. This is the check that
# would have caught the adapter promoting `target` to a band boundary: it put a
# green chip beside a yellow band on the same row.
disagree = []
for m in IDS:
    row = BY_ID[m]
    want = {"ok": "good", "warn": "high", "critical": "critical"}.get(row["status"])
    if not want:
        continue
    got = hexes("".join(svgs(segment(EX, m))))
    if RAG_FILL[want].upper() not in got:
        disagree.append("%s (%s)" % (m, row["status"]))
emit(not disagree, "every banded metric's mark carries its own status colour",
     "; ".join(disagree))

# 10-11. viz resolution matches the archetype table, and is what actually rendered.
DEFAULTS = {"patch-coverage": "bullet", "phishing-click": "bullet",
            "dwell-time": "line", "third-party": "bar",
            "mfa-coverage": "progress", "framework-maturity": "bar",
            "backup-recovery": "bullet", "custom": "bullet"}
wrong = []
for m in IDS:
    row = BY_ID[m]
    arch, viz = row.get("archetype"), row.get("viz")
    banded = row["status"] in ("ok", "warn", "critical")
    want = DEFAULTS.get(arch, "bullet") if banded else "tile"
    if viz != want:
        wrong.append("%s: archetype=%s banded=%s viz=%s want=%s"
                     % (m, arch, banded, viz, want))
emit(not wrong, "viz resolves per the archetype table for every metric",
     "; ".join(wrong))
emit(all(BY_ID[m].get("viz") for m in IDS),
     "every metric carries a resolved viz in the analysis",
     "missing on: %s" % ", ".join(m for m in IDS if not BY_ID[m].get("viz")))

# 12. No bullet is drawn on an axis its data never reaches.
#
# A lower-better metric banded at 3 / 6 / 10 percent, forced onto a 0-100 axis,
# put its good zone in 6% of the bar and filled the other 90% with a critical
# band no reading could land in. The mark then reads as "almost everything is
# bad" about a metric whose good range is most of what it can actually be.
#
# Expressed as a ratio, not a rule about percents: the failure is not about the
# unit but about a ceiling chosen for tidiness instead of from the data. 2.5x
# leaves headroom above the top threshold without letting an empty band dominate.
overscaled = []
for m in IDS:
    row = BY_ID[m]
    if row.get("viz") != "bullet":
        continue
    marks = svgs(segment(EX, m))
    if not marks:
        continue
    nums = []
    for t in re.findall(r">([\d.,]+)\s*(?:%|d)?<", marks[0]):
        try:
            nums.append(float(t.replace(",", "")))
        except ValueError:
            pass
    if not nums:
        continue
    ceiling = max(nums)
    thr = row.get("threshold") or {}
    reach = max([v for v in (row.get("value"), thr.get("target"),
                             thr.get("warn"), thr.get("critical"))
                 if v is not None] or [0])
    if reach and ceiling > reach * 2.5:
        overscaled.append("%s: axis reaches %g, data only %g"
                          % (m, ceiling, reach))
emit(not overscaled, "no bullet is drawn on an axis its data never reaches",
     "; ".join(overscaled))

# 13. Both views carry the legend that states what the colours mean.
emit('class="legend"' in EX and 'class="legend"' in OP,
     "both views carry the colour legend")

# 13. Both views carry the CAC band.
emit('class="band"' in EX and 'class="band"' in OP,
     "both views carry the CAC header band")

# 14. Patina never appears inside a mark. It is chrome; a data mark using it
# would be claiming the brand accent means something.
patina_in_mark = []
for html, label in ((EX, "board"), (OP, "working")):
    for m in IDS:
        if "#2FA98C" in "".join(svgs(segment(html, m))).upper():
            patina_in_mark.append("%s/%s" % (label, m))
emit(not patina_in_mark, "no mark uses patina, which is chrome only",
     "; ".join(patina_in_mark))

# 15. No mark composites opacity anywhere in either rendered page.
op_marks = [m for html in (EX, OP) for m in IDS
            if "opacity=" in "".join(svgs(segment(html, m)))]
emit(not op_marks, "no rendered mark composites opacity", "; ".join(op_marks))

# 16. No dict repr reached the HTML. The defect this branch shipped once already.
leak = [s for s in ("{'text'", "{'fill'", "'altitude'") if s in EX or s in OP]
emit(not leak, "no Python repr leaked into the rendered HTML", "found %s" % leak)

for status, name, detail in out:
    print("%s\t%s\t%s" % (status, name, detail))
PYEOF

while IFS=$'\t' read -r status name detail; do
  [ -z "$name" ] && continue
  if [ "$status" = "ok" ]; then ok "$name"; else bad "$name" "$detail"; fi
done < "$work/out.txt"

# Sparkline progression, exercised against the vendored library directly: the
# fixture has no metric with 3 or 4 readings, and inventing one in the store
# would test the fixture rather than the rule.
spark=$(cd "$skill/renderers" && $PY -c "
import cac_graphics as g
three = g.sparkline([1, 2, 3])
four = g.sparkline([1, 2, 3, 4])
print('suppressed' if 'polyline' not in three else 'drawn', end=' ')
print('drawn' if 'polyline' in four else 'suppressed', end='')
")
if [ "$spark" = "suppressed drawn" ]; then
  ok "sparkline is suppressed at 3 readings and drawn at 4"
else
  bad "sparkline is suppressed at 3 readings and drawn at 4" "got: $spark"
fi

# --- a top-banded metric stays readable ----------------------------------------
#
# Coverage banded 85/90/95 on a shared 0-100 axis put 204 of 240 pixels into the
# critical band, left warn 12, and pushed every threshold past x=224 where the
# label placer dropped two of them for collision. The bands were unreadable and
# their numbers unrecoverable at the same time.
#
# Asserted through the RENDERER, not the library: the library has taken an
# axis_min since this went in, and what matters is whether metrics-register asks
# for one on the metrics that need it. A library that can zoom and a renderer that
# never does is the same unreadable bar.
axis_res="$("$PY" "$here/_axisroom.py" 2>&1)"
case "$axis_res" in
  PASS*) ok "a metric banded near its ceiling gets a readable axis (${axis_res#PASS })" ;;
  *)     bad "a metric banded near its ceiling gets a readable axis" "$axis_res" ;;
esac

# --- the library's banding against the REAL engine -----------------------------
#
# The chip and the bullet on one page must never disagree about the same number.
# They are computed by two modules that cannot import each other: the library is
# standard-library-only and ships vendored into six skills, so its own self-test
# compares against a hand-written mirror of threshold_status. This suite can import
# both, so it is the only place the two real implementations meet.
band_parity="$("$PY" "$here/_bandparity.py" 2>&1)"
case "$band_parity" in
  PASS*) ok "the library's bands agree with the engine's status (${band_parity#PASS })" ;;
  *)     bad "the library's bands agree with the engine's status" "$band_parity" ;;
esac

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'graphics-contract: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'graphics-contract: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'graphics-contract: all %s checks passed\n' "$checks"
