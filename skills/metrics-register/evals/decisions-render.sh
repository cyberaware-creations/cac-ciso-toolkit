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

EXPECTED_CHECKS=4
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
hastext() {  # hastext <label> <file> <needle>
  # Silent on a missing page, for the same reason as norepr below: `wrote` owns that failure.
  # Without this, the `crash` mutation defeats the text check too — and then the anti-vacuity
  # property is proved only by a page that never rendered, which is one property standing in
  # for another. That substitution IS BL-209, so leaving it here would reintroduce the defect
  # inside its own fix (D-3).
  if [ ! -s "$2" ]; then return; fi
  if grep -qF -- "$3" "$2"; then ok "$1"; else bad "$1" "expected decision text not found"; fi
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


echo "decisions-render (metrics): $($PY -V 2>&1)"

$PY "$skill/scripts/metrics_analysis.py" analyze "$skill/examples/example-metrics.mtr" \
    --today 2026-07-31 --out "$work/a.json" >/dev/null
(cd "$skill/renderers" && $PY render_executive.py --in "$work/a.json" \
    --translations "$skill/examples/example-translations.json" \
    --out "$work/board.html" --offline) >/dev/null

# 1. No raw dict repr — the P1 defect that this eval guards against.
wrote "the renderer wrote a page at all" "$work/board.html"
norepr "no raw dict repr in rendered decisions" "$work/board.html" "$RE_TEXT"

# 2. No 'altitude' key — a dict repr or JSON leak of the object form.
norepr "no 'altitude' key in rendered output" "$work/board.html" "$RE_ALT"

# 3. The board decision text is present (anti-vacuity: a filter that matches nothing is not green).
hastext "board decision text renders as prose" "$work/board.html" "Fund the patching backlog"

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'decisions-render (metrics): ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'decisions-render (metrics): %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'decisions-render (metrics): all %s checks passed\n' "$checks"
