#!/usr/bin/env bash
# decisions-render.sh — the board renderer emits decision TEXT, never a raw dict repr.
#
# The shipped-P1 guard every producer in this suite carries. `ciso-board-translation` emits
# decisions as {"text": ..., "altitude": ...} objects; a renderer that stringifies one prints
# `{'text': ...}` where a board decision should be. It shipped across this suite once, which is
# why every producer now carries this eval rather than trusting the renderer.
#
# It caught the same defect here, on its first run, before this skill had ever been released.
#
# Both directions are asserted. Checking only for the absence of `{'text'` would pass a
# renderer that emitted nothing at all, so the decision prose must also be PRESENT — and the
# board/management split must survive, because a management action rendered into the board list
# is an ask nobody in the room was meant to vote on.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
repo="$(cd "$skill/../.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=6
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

T="$skill/examples/example-translations.json"
echo "decisions-render (vendor): $($PY -V 2>&1)"

# The fixture has to carry the OBJECT form, or this whole suite passes over the one shape the
# defect lives in. Asserted rather than assumed.
if "$PY" -c '
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))["decisions"]
objs = [x for x in d if isinstance(x, dict) and "text" in x]
mgmt = [x for x in objs if x.get("altitude") == "management"]
sys.exit(0 if objs and mgmt else 1)' "$T"; then
  ok "the example sidecar carries object-form decisions, including a management one"
else
  bad "the example sidecar carries object-form decisions" \
      "all strings, or no management action — the suite would pass over the shape that breaks"
fi

"$PY" "$repo/skills/business-context/scripts/business_context.py" export \
   "$repo/skills/business-context/examples/example-org.biz" --out "$work/ctx.json" >/dev/null 2>&1
"$PY" "$skill/scripts/vendor_register.py" analyze "$skill/examples/example-vendors.vnd" \
   --context "$work/ctx.json" --today 2026-08-07 --out "$work/a.json" >/dev/null 2>&1
( cd "$skill/renderers" && "$PY" render_board.py --in "$work/a.json" \
    --translations "$T" --out "$work/board.html" --offline ) >/dev/null 2>&1

if [ ! -s "$work/board.html" ]; then
  bad "the board page rendered at all" "nothing was written, so nothing below proves anything"
else
  ok "the board page rendered"
fi

# 1. No raw dict repr — the defect itself, in both raw and HTML-escaped form. The renderer
# escapes its output, so grepping only for `{'text'` would miss `{&#x27;text&#x27;`.
if grep -qF "{'text'" "$work/board.html" || grep -qF "{&#x27;text&#x27;" "$work/board.html"; then
  bad "no raw dict repr in rendered decisions" "found a stringified decision object"
else
  ok "no raw dict repr in rendered decisions, escaped or otherwise"
fi

# 2. No leaked `altitude` key — the other half of a dict repr, and a separate failure if the
# renderer ever serialises the object rather than reading it.
if grep -qF "altitude" "$work/board.html"; then
  bad "no 'altitude' key in rendered output" "found 'altitude' in the board HTML"
else
  ok "no 'altitude' key leaks into rendered output"
fi

# 3. Anti-vacuity: the prose is actually there.
if grep -qF "Fund a tested failover for the plant historian" "$work/board.html"; then
  ok "board decision text renders as prose"
else
  bad "board decision text renders as prose" "the expected sentence is not on the page"
fi

# 4. The split survives. A management action in the board list is an ask nobody was meant to
# vote on — the same reasoning behind board-pack's crowded-agenda warning.
if grep -qF "Management actions — not for board decision" "$work/board.html" \
   && grep -qF "Name an owner for the two untraced arrangements" "$work/board.html"; then
  ok "management actions render under their own heading, not in the board's list"
else
  bad "management actions are separated from board decisions" \
      "no management heading, or its action is missing"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'decisions-render (vendor): ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"
  exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'decisions-render (vendor): %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'decisions-render (vendor): all %s checks passed\n' "$checks"
