#!/usr/bin/env bash
# What a board is asked to decide renders as a sentence, and only board asks are in the list.
#
# This suite exists because of a defect that actually shipped in a sibling skill. The
# `ciso-board-translation` sidecar carries a decision as `{"text": ..., "altitude": ...}`, an
# older one carries a bare string, and a renderer that stringified the object printed a raw
# Python dict — `{'text': 'Fund a tested...', 'altitude': 'board'}` — in the place where a
# board decision should have been. It was caught by the equivalent of this file on its first
# run, and nowhere else: the JSON was correct, the page was not, and the page is the artifact.
#
# Three properties, each in both directions:
#
#   1. Neither form leaks its representation. Object and bare string both render as prose.
#   2. Management actions are SEPARATED from board asks. A board votes on the first list;
#      mixing the second in pads the agenda with things nobody in the room is deciding.
#   3. A missing narrative renders a visible placeholder, never an invented sentence. A page
#      that fills a hole with plausible prose is worse than one that shows the hole, because
#      only one of them gets noticed.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=11
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

find "$skill/renderers" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

A="$skill/scripts/ai_register.py"
echo "decisions-render: $($PY -V 2>&1)"

"$PY" "$A" analyze "$skill/examples/example-ai.air" \
   --context "$skill/examples/example-context.json" --today 2026-08-07 \
   --out "$work/a.json" >/dev/null 2>&1

render() {  # render <translations-or-empty> <out>
  ( cd "$skill/renderers" \
    && if [ -n "$1" ]; then
         "$PY" render_board.py --in "$work/a.json" --translations "$1" --out "$2" --offline
       else
         "$PY" render_board.py --in "$work/a.json" --out "$2" --offline
       fi ) >/dev/null 2>&1
}

# --- 1-4. the object form, which is what the sidecar emits today --------------
render "$skill/examples/example-translations.json" "$work/full.html"
if [ -s "$work/full.html" ]; then
  ok "no decision renders as a raw dict"
else
  bad "the board view rendered" "empty — every check below would pass over nothing"
fi
# THE check. A raw dict repr, in any of the forms an escaped page can carry it.
if grep -qE "\{&#x27;text&#x27;|\{'text'|&#39;altitude&#39;|'altitude':" "$work/full.html"; then
  bad "no decision renders as a raw dict" \
      "$(grep -oE ".{0,40}(\{&#x27;text&#x27;|\{'text').{0,40}" "$work/full.html" | head -1)"
else
  ok "no decision renders as a raw Python dict — the defect this suite exists for"
fi
if grep -qF "Decide whether a provider may change the model underneath" "$work/full.html"; then
  ok "and the object form's text renders as a sentence"
else
  bad "the object form renders its text" "the board ask is not on the page"
fi
if grep -qF "Management actions — not for board decision" "$work/full.html"; then
  ok "management actions are separated under their own heading"
else
  bad "management actions are separated" "no heading — they are mixed into the board asks"
fi

# --- 5-7. the split is real, not just a heading -------------------------------
if "$PY" -c '
import re, sys
html = open(sys.argv[1], encoding="utf-8").read()
head = "Management actions — not for board decision"
i = html.find(head)
if i < 0:
    print("no management heading", file=sys.stderr); sys.exit(1)
board, mgmt = html[:i], html[i:]
# A board ask must be above the split, a management action below it.
if "Decide whether a provider may change" not in board:
    print("a board ask fell below the management heading", file=sys.stderr); sys.exit(1)
if "declare what it supports" not in mgmt:
    print("a management action is in the board list", file=sys.stderr); sys.exit(1)
if "declare what it supports" in board:
    print("a management action ALSO appears in the board list", file=sys.stderr); sys.exit(1)
' "$work/full.html" 2>"$work/split.err"; then
  ok "board asks sit above the split and management actions below it"
else
  bad "the board / management split holds" "$(cat "$work/split.err")"
fi

# The bare-string form still works. Every sidecar written before the object form existed is
# still a valid document, and refusing one would be a breaking change dressed as a fix.
cat > "$work/old.json" <<'JSON'
{"section": "ai", "contractVersion": 1,
 "executiveSummary": "One deployment decides about people.",
 "deployments": {"D-001": "Screens applicants."},
 "decisions": ["Fund an adversarial test of the screening deployment."]}
JSON
render "$work/old.json" "$work/old.html"
if grep -qF "Fund an adversarial test of the screening deployment." "$work/old.html"; then
  ok "a bare-string decision from an older sidecar still renders"
else
  bad "the bare-string form still renders" "the decision is not on the page"
fi
if grep -qE "\{&#x27;text&#x27;|\{'text'" "$work/old.html"; then
  bad "the bare-string form renders no dict" "found one"
else
  ok "...and renders no dict either"
fi

# --- 8-11. the placeholder pair, both directions ------------------------------
render "" "$work/none.html"
if grep -q 'class="ph"' "$work/none.html"; then
  ok "with no sidecar, the narrative slots render a visible placeholder"
else
  bad "a missing narrative renders a placeholder" \
      "nothing — the page either invented prose or silently dropped the section"
fi
if grep -qF "ciso-board-translation" "$work/none.html"; then
  ok "...and the placeholder names the skill that fills it"
else
  bad "the placeholder says how to fill it" "it does not name ciso-board-translation"
fi
if grep -q 'class="ph"' "$work/full.html"; then
  bad "a fully-translated page renders NO placeholder" \
      "found one — a slot is unfilled or the sidecar is not being read"
else
  ok "and a fully-translated page renders none"
fi
# A sidecar for another section must be refused rather than rendered under this heading.
cat > "$work/wrong.json" <<'JSON'
{"section": "vendor", "contractVersion": 1,
 "arrangements": {"VA-001": "Hosting."},
 "decisions": ["Fund a second region."]}
JSON
if ( cd "$skill/renderers" && "$PY" render_board.py --in "$work/a.json" \
       --translations "$work/wrong.json" --out "$work/wrong.html" --offline ) >/dev/null 2>&1; then
  bad "a sidecar for another section is refused" "it rendered"
else
  ok "a sidecar written for another section is refused, not rendered under this heading"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'decisions-render: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'decisions-render: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'decisions-render: all %s checks passed\n' "$checks"
