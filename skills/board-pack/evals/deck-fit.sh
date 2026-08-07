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

EXPECTED_CHECKS=9
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

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

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'deck-fit: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'deck-fit: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'deck-fit: all %s checks passed\n' "$checks"
