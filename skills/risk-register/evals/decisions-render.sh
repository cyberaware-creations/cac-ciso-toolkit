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

EXPECTED_CHECKS=8
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

# --- what this suite got wrong for as long as it has existed ------------------
#
# A rendered page must carry no Python repr IN EITHER FORM, and must exist at all. Both halves
# of that sentence were missing here, and each on its own made the checks below unable to fail.
#
#   THE ESCAPED FORM. `C.esc()` calls `str()` and then `html.escape()`, so a decision object
#   reaches the page as `{&#x27;text&#x27;: ...}`. A grep for the literal `{'text'` finds
#   nothing on a page made entirely of them. Five suites reported clean while
#   `risk-register/renderers/render_report.py` shipped exactly that to a reader (BL-199).
#
#   THE MISSING FILE. `grep` over a file the renderer never wrote also finds nothing, and also
#   reports clean. That is BL-121's crashed probe, and this guard's own proof file named it in
#   writing — then chose a mutation that stepped around it rather than closing it.
wrote() {  # wrote <label> <file>
  if [ -s "$2" ]; then ok "$1"; else bad "$1" "the renderer wrote no page, so every grep below would have read nothing and reported clean"; fi
}
norepr() {  # norepr <label> <file> <extended-regex>
  # Silent, not `bad`, when there is no page — `wrote` above already owns that and has already
  # failed the suite. Reporting the same absence three times would make a missing page defeat
  # every check here, and a half whose mutation defeats everything proves nothing about any one
  # of them (GP-1.9). The EXPECTED_CHECKS floor catches the missing calls, so nothing goes
  # quiet: the suite still exits non-zero, naming the shortfall.
  if [ ! -s "$2" ]; then return; fi
  hit="$(grep -oE "$3" "$2" | sort -u | tr '\n' ' ')"
  if [ -n "$hit" ]; then bad "$1" "found repr marker(s): $hit"; else ok "$1"; fi
}
RE_TEXT="\{&#x27;text&#x27;|\{'text'|\{&quot;text&quot;"
RE_ALT="&#x27;altitude&#x27;|'altitude'|&quot;altitude&quot;"


echo "decisions-render (risk): $($PY -V 2>&1)"

(cd "$skill/renderers" && $PY render_board.py \
    "$skill/examples/example-register-v2.rr" "$work/board.html" \
    --translations "$skill/references/example-translations.json" --offline) >/dev/null

# 1. No raw dict repr — the P1 defect that this eval guards against.
# BOTH renderers that emit decisions, and the second one is the whole point.
#
# This suite rendered `render_board.py` only. `render_report.py` also prints the decisions
# list, was covered by nothing, and was shipping `{&#x27;text&#x27;: ...}` to a reader on every
# operational report — a live instance of the exact P1 this file was written to prevent, with
# this file green over it. A guard that covers one of the two renderers that can commit the
# defect is a guard over half the surface (BL-209).
(cd "$skill/renderers" && $PY render_report.py \
    "$skill/examples/example-register-v2.rr" "$work/report.html" \
    --translations "$skill/references/example-translations.json" --offline) >/dev/null 2>&1

wrote "the renderer wrote a page at all" "$work/board.html"
norepr "no raw dict repr in rendered decisions" "$work/board.html" "$RE_TEXT"

# 2. No 'altitude' key — a dict repr or JSON leak of the object form.
norepr "no 'altitude' key in rendered output" "$work/board.html" "$RE_ALT"

# 3. The board decision text is present (anti-vacuity).
wrote "the operational report wrote a page at all" "$work/report.html"
norepr "no raw dict repr in the operational report" "$work/report.html" "$RE_TEXT"
norepr "no 'altitude' key in the operational report" "$work/report.html" "$RE_ALT"
if grep -qF "Fund DMARC enforcement" "$work/report.html"; then
  ok "the report's decision text renders as prose"
else
  bad "the report's decision text renders as prose" "expected decision text not found"
fi

if grep -qF "Fund DMARC enforcement" "$work/board.html"; then
  ok "board decision text renders as prose"
else
  bad "board decision text renders as prose" \
      "expected 'Fund DMARC enforcement' not found in board HTML"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'decisions-render (risk): ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'decisions-render (risk): %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'decisions-render (risk): all %s checks passed\n' "$checks"
