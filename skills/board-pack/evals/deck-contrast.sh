#!/usr/bin/env bash
# WCAG AA contrast for the written `.pptx` — the one output format nothing measured.
#
# The HTML artifacts go through a real headless Chrome in risk-register/evals/responsive.sh,
# because a resolved layout is the only place a colour pairing exists. The deck had no
# equivalent, and it is the artifact that actually reaches a board. That gap is how a band
# label at 2.62:1 shipped in both outputs for four releases: nothing was looking at the
# deck at all, and the HTML checker resolved SVG text against the page ground rather than
# the mark painted behind it, so both outputs agreed and both were wrong.
#
# This needs no rendering engine, and that is a property of how `pptx_writer.py` writes
# rather than a corner cut. It emits explicit EMU geometry and an explicit srgbClr on every
# run and every fill — no cascade, no inheritance, no theme indirection — so the pairing a
# viewer will see is already written down. What `_deckcontrast.py` walks is the emitted XML,
# not anybody's intention about it.
#
# It does NOT check overflow. Font metrics, autofit and line breaking belong to PowerPoint,
# and a check that guessed at them would be worse than the absence of one.
#
# Anti-vacuity: EXPECTED_CHECKS pins the count; the scanner refuses to report a clean deck
# when it measured no runs at all; and the last two cases poison a deck and require the
# guard to fail on it, because a guard never seen to fail is not known to work.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=7
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

echo "deck-contrast: $($PY -V 2>&1)"

"$PY" "$skill/scripts/assemble_pack.py" assemble "$skill/examples/pack.manifest.json" \
  --out "$work/pack.json" >/dev/null 2>&1 || {
    printf 'deck-contrast: FIXTURE FAILED — assemble errored\n'; exit 1; }
(cd "$skill/renderers" && "$PY" render_pack.py --in "$work/pack.json" \
  --html "$work/p.html" --pptx "$work/p.pptx") >/dev/null 2>&1 || {
    printf 'deck-contrast: FIXTURE FAILED — render_pack errored\n'; exit 1; }

# 1. The shipped specimen deck.
if out="$("$PY" "$here/_deckcontrast.py" "$work/p.pptx" 2>&1)"; then
  ok "every text run in the specimen deck meets WCAG AA"
else
  bad "every text run in the specimen deck meets WCAG AA" "$(echo "$out" | head -6)"
fi

# 2. ...and it measured something. A scan of zero runs reports no failures, which reads
# identically to a clean deck on the line above.
runs="$("$PY" "$here/_deckcontrast.py" "$work/p.pptx" --count)"
if [ "$runs" -gt 100 ]; then
  ok "and it measured $runs text runs, so that result is not a silent empty walk"
else
  bad "the scan measured a plausible number of runs" "only $runs"
fi

# 3. The band labels specifically, which is where the defect was. A deck whose charts
# stopped emitting labels would pass check 1 by having nothing left to fail.
seg="$("$PY" - "$work/p.pptx" <<'PY'
import re, sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
n = 0
for name in z.namelist():
    if re.match(r"ppt/slides/slide\d+\.xml$", name):
        n += len(re.findall(r'name="Segment value \d+"', z.read(name).decode()))
print(n)
PY
)"
if [ "$seg" -gt 0 ]; then
  ok "the deck still draws $seg band-segment values for that check to measure"
else
  bad "the deck draws band-segment values" "none found — the charts stopped labelling"
fi

# 4-5. THE GUARD, SEEN TO FAIL. The exact defect is reintroduced into a copy of the deck:
# a band value painted in its band's text colour, which is measured against white and was
# 2.62:1 on the mark it actually sits on.
"$PY" - "$work/p.pptx" "$work/poisoned.pptx" <<'PY'
import re, shutil, sys, zipfile
src, dst = sys.argv[1], sys.argv[2]
zin = zipfile.ZipFile(src)
zout = zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED)
for item in zin.infolist():
    data = zin.read(item.filename)
    if re.match(r"ppt/slides/slide\d+\.xml$", item.filename):
        # The good band: SEV_TEXT 25764A back onto SEV_MID 86BE9C.
        data = data.decode().replace('<a:srgbClr val="14171C"/></a:solidFill>'
                                     '<a:latin typeface="Helvetica Neue"/></a:rPr>'
                                     '<a:t>2</a:t>',
                                     '<a:srgbClr val="25764A"/></a:solidFill>'
                                     '<a:latin typeface="Helvetica Neue"/></a:rPr>'
                                     '<a:t>2</a:t>').encode()
    zout.writestr(item, data)
zout.close()
PY
if "$PY" "$here/_deckcontrast.py" "$work/poisoned.pptx" >"$work/poison.txt" 2>&1; then
  bad "a band label repainted in its band's text colour is caught" \
      "the poisoned deck passed — this guard cannot see the defect it exists for"
else
  ok "a band label repainted in its band's text colour is caught"
fi
if grep -q "25764A on #86BE9C" "$work/poison.txt"; then
  ok "...naming the pairing and the measured ratio"
else
  bad "the failure names the pairing" "$(head -3 "$work/poison.txt")"
fi

# 6-7. The vacuity holes in the scanner itself.
"$PY" - "$work/empty.pptx" <<'PY'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1], "w")
z.writestr("ppt/slides/slide1.xml", "<p:sld/>")
z.close()
PY
if "$PY" "$here/_deckcontrast.py" "$work/empty.pptx" >"$work/empty.txt" 2>&1; then
  bad "a deck with no text runs is refused, not reported clean" "it passed"
else
  ok "a deck with no text runs is refused, not reported clean"
fi
if grep -q "walk is broken" "$work/empty.txt"; then
  ok "...saying the walk is broken rather than the deck clean"
else
  bad "the empty-deck message blames the walk" "$(head -2 "$work/empty.txt")"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'deck-contrast: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'deck-contrast: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'deck-contrast: all %s checks passed\n' "$checks"
