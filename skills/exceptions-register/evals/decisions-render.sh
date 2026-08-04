#!/usr/bin/env bash
# decisions-render.sh — board renderer must emit decision text, not raw Python dict repr.
#
# Phase 0 regression guard: the sidecar carries decisions as {"text":..., "altitude":...}
# objects. Before the fix, the renderer stringified them and the board saw {'text':...}.
# This eval renders with the example-translations.json (which uses object form) and asserts
# the defect is absent and the board decision text is present.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=3
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

echo "decisions-render (exceptions): $($PY -V 2>&1)"

$PY "$skill/scripts/exceptions_register.py" analyze "$skill/examples/example.exc" \
    --out "$work/a.json" >/dev/null 2>&1
(cd "$skill/renderers" && $PY render_board.py --in "$work/a.json" \
    --translations "$skill/examples/example-translations.json" \
    --out "$work/board.html" --offline) >/dev/null

# 1. No raw dict repr — the P1 defect that this eval guards against.
if grep -qF "{'text'" "$work/board.html"; then
  bad "no raw dict repr in rendered decisions" "found {'text' in board HTML"
else
  ok "no raw dict repr in rendered decisions"
fi

# 2. No 'altitude' key — a dict repr or JSON leak of the object form.
if grep -qF "'altitude'" "$work/board.html"; then
  bad "no 'altitude' key in rendered output" "found 'altitude' in board HTML"
else
  ok "no 'altitude' key in rendered output"
fi

# 3. The board decision text is present (anti-vacuity).
if grep -qF "Re-validate the CRM vendor" "$work/board.html"; then
  ok "board decision text renders as prose"
else
  bad "board decision text renders as prose" \
      "expected 'Re-validate the CRM vendor' not found in board HTML"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'decisions-render (exceptions): ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'decisions-render (exceptions): %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'decisions-render (exceptions): all %s checks passed\n' "$checks"
