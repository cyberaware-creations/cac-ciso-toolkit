#!/usr/bin/env bash
# Does the deck hold what the pack put in it?
#
# `deck-contrast.sh` answers whether the text can be READ. This answers whether it is all
# THERE. The deck is drawn with fixed EMU geometry, so a box holds what it was given
# whether or not it fits, and every textBody carries normAutofit with no computed
# fontScale — a viewer that recomputes shrinks the text and one that does not clips it.
#
# The defect this was written for: pagination counted ITEMS. Eight figures a slide, three
# mixes, and `add()` took a whole list into one fixed box regardless of length. Eight short
# decisions fit. Eight decisions written the way a real risk committee writes them did not,
# and the last ones were simply below the bottom of the slide with nothing reporting it.
# The shipped specimen never showed it, because the specimen is written tightly — which is
# exactly the shape of a fixture that agrees with its own code.
#
# The load-bearing case is #5. It is BEHAVIOURAL: a pack with much longer prose must
# produce MORE slides than the same pack with short prose. Item-count pagination gives the
# same number for both. No shared constant between the writer's estimate and this suite's
# can fake that, which matters because the two do estimate the same thing — see
# _deckfit.py on why its constants deliberately differ from the writer's.
#
# What this does NOT do is claim to be PowerPoint. Real line breaking needs the font. It
# catches a box asked to hold substantially more than it can, which is the failure that
# ships; it says nothing about one word tipping onto a second line.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=16
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }
eq()  { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "expected '$2', got '$3'"; fi; }

echo "deck-fit: $($PY -V 2>&1)"

"$PY" "$skill/scripts/assemble_pack.py" assemble "$skill/examples/pack.manifest.json" \
  --out "$work/pack.json" >/dev/null 2>&1 || {
    printf 'deck-fit: FIXTURE FAILED — assemble errored\n'; exit 1; }
(cd "$skill/renderers" && "$PY" render_pack.py --in "$work/pack.json" \
  --html "$work/p.html" --pptx "$work/p.pptx") >/dev/null 2>&1 || {
    printf 'deck-fit: FIXTURE FAILED — render_pack errored\n'; exit 1; }

# The same pack with every title, headline and body sentence replaced by prose of the
# length a real committee writes. Not invented content — the same structure, said longer.
"$PY" - "$work/pack.json" "$work/long.json" <<'PY'
import json, sys
LONG = ("Reduce third-party concentration exposure across the payments value chain by "
        "migrating the authorisation gateway off the single incumbent provider, "
        "commissioning an independent resilience assessment of the replacement, and "
        "reporting quarterly to the risk committee until the transition completes")
def walk(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("title", "headline") and isinstance(v, str) and len(v) > 8:
                node[k] = LONG
            elif k == "text" and isinstance(v, str) and len(v) > 8:
                node[k] = LONG + ". " + LONG
            else:
                walk(v)
    elif isinstance(node, list):
        for v in node:
            walk(v)
doc = json.load(open(sys.argv[1]))
walk(doc)
json.dump(doc, open(sys.argv[2], "w"))
PY
(cd "$skill/renderers" && "$PY" render_pack.py --in "$work/long.json" \
  --html "$work/l.html" --pptx "$work/l.pptx") >/dev/null 2>&1 || {
    printf 'deck-fit: FIXTURE FAILED — long render_pack errored\n'; exit 1; }

# 1. The shipped specimen.
if out="$("$PY" "$here/_deckfit.py" "$work/p.pptx" 2>&1)"; then
  ok "every text box in the specimen deck holds what it was given"
else
  bad "every text box in the specimen deck holds what it was given" \
      "$(echo "$out" | head -5)"
fi

# 2. ...and it measured something. Zero boxes reports zero problems.
boxes="$("$PY" "$here/_deckfit.py" "$work/p.pptx" --count)"
if [ "$boxes" -gt 100 ]; then
  ok "and it measured $boxes text boxes, so that is not a silent empty walk"
else
  bad "the scan measured a plausible number of boxes" "only $boxes"
fi

# 3. The long pack fits too — which is the writer adapting, not the content being short.
if out="$("$PY" "$here/_deckfit.py" "$work/l.pptx" 2>&1)"; then
  ok "and so does the same pack written at committee length"
else
  bad "the same pack written at committee length also fits" "$(echo "$out" | head -5)"
fi

# 4-5. THE BEHAVIOURAL CASE. Longer prose must cost more slides. Under item-count
# pagination both decks have the same slide count and the surplus text is off the page.
short_n="$("$PY" "$here/_deckfit.py" "$work/p.pptx" --slides)"
long_n="$("$PY" "$here/_deckfit.py" "$work/l.pptx" --slides)"
if [ "$long_n" -gt "$short_n" ]; then
  ok "longer prose costs more slides ($short_n → $long_n), so pagination reads length"
else
  bad "longer prose costs more slides" \
      "both decks are $short_n slides — pagination is counting items, not measuring content"
fi
if "$PY" - "$work/l.pptx" <<'PY'
import re, sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
titles = []
for n in z.namelist():
    if re.match(r"ppt/slides/slide\d+\.xml$", n):
        runs = re.findall(r"<a:t>(.*?)</a:t>", z.read(n).decode())
        titles += runs[:3]
sys.exit(0 if any(re.search(r"\(\d+\)$", t.strip()) for t in titles) else 1)
PY
then
  ok "...and a continued slide says so in its title, so no two slides share one"
else
  bad "a continued slide is titled as a continuation" "no '(n)' suffix anywhere"
fi

# 6-7. THE GUARD, SEEN TO FAIL. A run in the shipped deck is replaced with prose far past
# what its box can hold. If this passes, the check cannot see the thing it exists for.
"$PY" - "$work/p.pptx" "$work/poisoned.pptx" <<'PY'
import re, sys, zipfile
LONG = ("This sentence is deliberately far longer than the box it has been put into, so "
        "that a check which measures whether text fits has something it must catch, and "
        "a check which does not measure anything has something it will miss entirely, "
        "which is the whole difference between a guard and a decoration on a slide.")
zin = zipfile.ZipFile(sys.argv[1])
zout = zipfile.ZipFile(sys.argv[2], "w", zipfile.ZIP_DEFLATED)
done = False
for item in zin.infolist():
    data = zin.read(item.filename)
    if not done and re.match(r"ppt/slides/slide\d+\.xml$", item.filename):
        text = data.decode()
        # The eyebrow: a one-line box near the top of every content slide.
        new, n = re.subn(r"(<p:cNvPr id=\"2\" name=\"Eyebrow\"/>.*?<a:t>)(.*?)(</a:t>)",
                         lambda m: m.group(1) + LONG + m.group(3), text, count=1,
                         flags=re.S)
        if n:
            data = new.encode()
            done = True
    zout.writestr(item, data)
zout.close()
sys.exit(0 if done else 1)
PY
poison_rc=$?
[ "$poison_rc" -eq 0 ] || {
  printf 'deck-fit: FIXTURE FAILED — could not poison a deck\n'; exit 1; }
if "$PY" "$here/_deckfit.py" "$work/poisoned.pptx" >"$work/poison.txt" 2>&1; then
  bad "a box given far more than it can hold is caught" \
      "the poisoned deck passed — this check cannot see the defect it exists for"
else
  ok "a box given far more than it can hold is caught"
fi
if grep -q "Eyebrow" "$work/poison.txt"; then
  ok "...naming the shape, the height it needed and the height it had"
else
  bad "the failure names the offending shape" "$(head -3 "$work/poison.txt")"
fi

# 8-9. The vacuity hole in the scanner itself.
"$PY" - "$work/empty.pptx" <<'PY'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1], "w")
z.writestr("ppt/slides/slide1.xml", "<p:sld/>")
z.close()
PY
if "$PY" "$here/_deckfit.py" "$work/empty.pptx" >"$work/empty.txt" 2>&1; then
  bad "a deck with no text boxes is refused, not reported sound" "it passed"
else
  ok "a deck with no text boxes is refused, not reported sound"
fi
if grep -q "walk is broken" "$work/empty.txt"; then
  ok "...saying the walk is broken rather than the deck sound"
else
  bad "the empty-deck message blames the walk" "$(head -2 "$work/empty.txt")"
fi

# --- 10-13. THE TYPE FLOORS ARE DECLARED (BL-168 T1/T2) ------------------------
#
# ⚠️ DECLARED, NOT YET ENFORCED. Raising the emitted sizes to meet these floors forces real
# editorial cuts — BL-126 measured 0.24" of headroom on the mix slide — and deciding what
# gets dropped per slide is Darren's, not a machine's. T1 and T2 establish the vocabulary;
# T3 onward applies it. These checks pin the vocabulary so it cannot drift before then, and
# they pin the CURRENT sub-floor inventory so nothing new slips under it in the meantime.
#
# The fit assertions above are UNCHANGED and stay. Fit is a document property and it is
# already correct for the narrative half; legibility is a second property beside it, not a
# replacement for it.
flr="$("$PY" - "$skill/scripts" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import pptx_writer as P
print("%d %d %d %d %s" % (
    P.NARRATIVE_TYPE_FLOOR, P.DECISIONS_TYPE_FLOOR,
    P.TYPE_FLOOR_GOVERNS["narrative"], P.TYPE_FLOOR_GOVERNS["decisions"],
    "yes" if P.CHROME_EXEMPT else "no"))
PY
)"
set -- $flr
# Two floors, not one. A single number would have to serve a desk read and a ten-foot read,
# which means being wrong for one of them.
if [ "$1" -lt "$2" ] && [ "$1" -gt 0 ]; then
  ok "two type floors are declared and ordered — narrative ${1}, decisions ${2} centipoints"
else
  bad "two type floors are declared and ordered" "narrative=$1 decisions=$2"
fi
# The map names the classes rather than leaving a reader to infer them from constant names,
# and it must hold the SAME values — a copied number is a number that drifts.
if [ "$3" = "$1" ] && [ "$4" = "$2" ]; then
  ok "...and TYPE_FLOOR_GOVERNS names which slide class each governs, without copying it"
else
  bad "TYPE_FLOOR_GOVERNS agrees with the constants" "got $3/$4, want $1/$2"
fi
if [ "$5" = "yes" ]; then
  ok "the deck's own chrome is named as exempt from BOTH floors, not pattern-matched"
else
  bad "chrome exemptions are declared" "CHROME_EXEMPT is empty"
fi
# THE INVENTORY, and it is the only one of these four that can catch a regression today.
# It pins exactly which sub-floor sizes the shipped deck emits, so T3 starts from a known
# list and nothing new can slip under the floor while the floors are unenforced.
under="$("$PY" - "$work/p.pptx" "$skill/scripts" <<'PY'
import re, sys, zipfile
sys.path.insert(0, sys.argv[2])
import pptx_writer as P
SZ = re.compile(r'sz="(\d+)"')
sizes = set()
with zipfile.ZipFile(sys.argv[1]) as z:
    for n in z.namelist():
        if n.startswith("ppt/slides/slide") and n.endswith(".xml"):
            sizes |= {int(v) for v in SZ.findall(z.read(n).decode("utf-8"))}
print(",".join(str(v) for v in sorted(v for v in sizes if v < P.NARRATIVE_TYPE_FLOOR)))
PY
)"
# 1050 is in this list and is NOT on the item page, which names only 900 and 950. The
# inventory found it: `pptx_writer.py:590` (chart labels) and `render_pack.py:745`/`:832`
# (escalation evidence lines). 1000 likewise, at `pptx_writer.py:585`/`:595` and
# `render_pack.py:880`/`:898`. Recorded as a finding rather than quietly folded in — T3 has
# more sites to raise than the plan anticipated, and pinning the true set is the point of
# having an inventory at all.
eq "the sizes below the narrative floor are exactly the known ones, awaiting T3" \
   "900,950,1000,1050" "$under"

# --- BL-124 T1. EVERY CHART IS DRAWN OR NAMED -----------------------------------------
#
# The defect: eleven charts reach the pack, the HTML draws eleven, the writer draws the
# three band mixes, and the other eight left NO trace on the deck at all — not a title, not
# a pointer. Nothing failed, because nothing was looking: the deck is a valid file with or
# without them, and a reader working from the deck could not learn that a chart existed to
# go and look for. The writer's own comment claimed the deck "says where the rest are",
# which had been aspirational since it was written.
#
# What is asserted is the INVARIANT, not the current count. A chart is accounted for if its
# title appears anywhere in the deck's text — as a drawn "Mix title", or on the pointer
# slide. That holds whatever the pack contains and whatever the writer later learns to
# draw: teach it bullets tomorrow and this stays green without an edit, because a drawn
# chart carries its title too. Pinning "8 undrawn" instead would need editing the day the
# writer improved, which is how a check ends up asserting the fixture.
missing="$("$PY" - "$work/pack.json" "$work/p.pptx" <<'PY'
import json, re, sys, zipfile
charts = json.load(open(sys.argv[1])).get("charts") or []
text = ""
with zipfile.ZipFile(sys.argv[2]) as z:
    for n in z.namelist():
        if re.match(r"ppt/slides/slide\d+\.xml$", n):
            text += " ".join(re.findall(r"<a:t>([^<]*)</a:t>", z.read(n).decode("utf-8")))
print("|".join(c["title"] for c in charts if c.get("title") and c["title"] not in text))
PY
)"
eq "every chart in the pack is either drawn on the deck or named on it" "" "$missing"

# The negative half, and it is the one that catches the lazy fix. Listing ALL eleven on the
# pointer slide would satisfy the check above while telling the reader that the three charts
# they can see in front of them are somewhere else. So the slide must name the undrawn ones
# and ONLY those — the count comes from the writer's own MIX_PER_SLIDE, never from a
# constant repeated here.
named="$("$PY" - "$work/pack.json" "$work/p.pptx" "$skill/scripts" <<'PY'
import json, re, sys, zipfile
sys.path.insert(0, sys.argv[3])
import pptx_writer as P
charts = json.load(open(sys.argv[1])).get("charts") or []
drawn = [c for c in charts if c.get("kind") == "band-mix"][:P.Deck.MIX_PER_SLIDE]
want = [c["title"] for c in charts if c not in drawn]
page = ""
with zipfile.ZipFile(sys.argv[2]) as z:
    for n in z.namelist():
        if re.match(r"ppt/slides/slide\d+\.xml$", n):
            x = z.read(n).decode("utf-8")
            if "Charts in the document" in x:
                page += " ".join(re.findall(r"<a:t>([^<]*)</a:t>", x))
absent = [t for t in want if t not in page]
extra = [c["title"] for c in drawn if c["title"] in page]
print("absent=%s extra=%s" % (len(absent), len(extra)))
PY
)"
eq "...and the pointer slide names the undrawn charts, and only those" \
   "absent=0 extra=0" "$named"

# A pointer that lands in the appendix of a board deck is a pointer the board does not see.
# `--deck-mode board` moves item detail behind the divider; this slide is navigation, not
# detail, and belongs in front of it.
core_has="$("$PY" - "$work/p.pptx" <<'PY'
import re, sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    names = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                   key=lambda n: int(re.search(r"(\d+)", n).group(1)))
    hit = [i for i, n in enumerate(names)
           if "Charts in the document" in z.read(n).decode("utf-8")]
print("once" if len(hit) == 1 else "%d slides" % len(hit))
PY
)"
eq "...on exactly one slide, so it is a pointer and not a refrain" "once" "$core_has"

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'deck-fit: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'deck-fit: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'deck-fit: all %s checks passed\n' "$checks"
