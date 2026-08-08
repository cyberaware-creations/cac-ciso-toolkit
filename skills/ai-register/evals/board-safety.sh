#!/usr/bin/env bash
# Board-safety for the AI views: no claim this register cannot support reaches a page.
#
# Inherits the confidence, catastrophizing and scoring checks the sibling registers carry, and
# adds the one this skill needs that none of them does: **no closure vocabulary**.
# `no-closed-state.sh` proves nothing STORES a closed state; this proves nothing SAYS one. A
# page reading "mitigated" or "fully covered" beside an attack class has asserted exactly what
# the store refuses to hold — and it is the page, not the JSON, that a board reads.
#
# It also checks the visual half of the same rule: no exposure class renders with a green or
# complete affordance. A tick beside NISTAML.02 says "done" to every reader in the room, and
# no word anywhere else on the page undoes it.
#
# Both surfaces, because the operational view is the one people forget: fewer people read it,
# and it is where a convenient word gets added first.
#
# Anti-vacuity throughout: EXPECTED_CHECKS is asserted, the pages are proved non-empty before
# anything greps them, the exposure check is proved to have found classes to inspect, and the
# `--offline` guarantee is verified by looking for an external reference rather than trusting
# the flag.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=19
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

# A stale __pycache__ in the renderers directory will serve a previously-imported _common
# for the rest of the run. That bit once, during this suite's own mutation testing: a reverted
# file kept rendering the mutated colours and the guard looked broken when it was working.
find "$skill/renderers" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

echo "board-safety (ai-register): $($PY -V 2>&1)"

"$PY" "$skill/scripts/ai_register.py" analyze "$skill/examples/example-ai.air" \
   --context "$skill/examples/example-context.json" --today 2026-08-07 \
   --out "$work/a.json" >/dev/null 2>&1
( cd "$skill/renderers" \
  && "$PY" render_board.py --in "$work/a.json" --out "$work/board.html" \
       --translations "$skill/examples/example-translations.json" --offline \
  && "$PY" render_operational.py --in "$work/a.json" --out "$work/op.html" --offline \
) >/dev/null 2>&1

# Non-empty first. Every grep below "passes" against a file that was never written.
for page in board op; do
  if [ -s "$work/$page.html" ]; then
    ok "the $page view rendered and is non-empty"
  else
    bad "the $page view rendered" "empty or missing — every check below would pass over nothing"
  fi
done

# --- 3-10. vocabulary, on both rendered pages ---------------------------------
for page in board op; do
  for list in confidence catastrophizing scoring closure; do
    hit=$("$PY" "$here/_vocab.py" "$work/$page.html" "$list")
    if [ -z "$hit" ]; then
      ok "no $list vocabulary in the rendered $page view"
    else
      bad "no $list vocabulary in the rendered $page view" "found: $hit"
    fi
  done
done

# --- 11. our own source, docstrings and comments exempt -----------------------
#
# The refusal has to be explainable: every file here carries a paragraph naming the claim it
# declines to make, and those paragraphs necessarily use the words. What must stay clean is
# the code that can reach a page.
res=""
for f in "$skill"/renderers/render_*.py "$skill"/renderers/_common.py; do
  for list in confidence scoring closure; do
    hit=$("$PY" "$here/_vocab.py" "$f" "$list" --source)
    [ -n "$hit" ] && res="$res $(basename "$f"):$hit"
  done
done
if [ -z "$res" ]; then
  ok "no confidence, scoring or closure vocabulary in the executable source of any view"
else
  bad "no banned vocabulary in the source of any view" "$res"
fi

# --- 12. and the stripper actually works, on a probe built for the purpose ----
cat > "$work/probe.py" <<'PROBE'
"""This docstring says a class was fully mitigated, which a page must never print."""


def f():
    return 1
PROBE
in_prose=$("$PY" "$here/_vocab.py" "$work/probe.py" closure)
in_code=$("$PY" "$here/_vocab.py" "$work/probe.py" closure --source)
if [ -n "$in_prose" ] && [ -z "$in_code" ]; then
  ok "the stripper exempts prose and still reads code"
else
  bad "the stripper exempts prose and still reads code" \
      "with docstring: '${in_prose:-nothing}', stripped: '${in_code:-nothing}'"
fi

# --- 13-14. THE visual half of the no-closed-state rule -----------------------
#
# A word check cannot see a green tick. This reads the chips the renderers actually emitted
# and asserts that no exposure-class chip carries a "good" fill or a completion glyph — and
# proves it found chips to inspect, because a selector that stopped matching would pass.
for page in board op; do
  out=$("$PY" "$here/_exposurescan.py" "$work/$page.html" 2>"$work/$page.err")
  rc=$?
  if [ "$rc" -eq 0 ]; then
    ok "no exposure class renders green or complete in the $page view ($out)"
  elif [ "$rc" -eq 2 ]; then
    bad "the $page view has exposure classes to inspect" "$(cat "$work/$page.err")"
  else
    bad "no exposure class renders as done in the $page view" "$(cat "$work/$page.err")"
  fi
done

# --- 15-16. the page says what it will not do ---------------------------------
for page in board op; do
  if grep -qF "no AI risk score" "$work/$page.html" \
     && grep -qF "never as closed" "$work/$page.html"; then
    ok "the $page view states that it produces no score and closes no class"
  else
    bad "the $page view states both refusals" \
        "the caveat is absent or partial, so a reader expecting either is not told why"
  fi
done

# --- 17. autonomy is never coloured as a severity -----------------------------
#
# `acts` is not worse than `informs`. Colouring the ladder would turn it into a risk scale on
# the surface where that misreading is hardest to undo, so every autonomy chip takes the
# neutral measure fill on both pages.
if "$PY" -c '
import re, sys
bad = []
for path in sys.argv[1:]:
    html = open(path, encoding="utf-8").read()
    for m in re.finditer(r"<span class=\"chip auto\" style=\"background:([^;]+);", html):
        if m.group(1).strip().upper() != "#EFEDE7":
            bad.append("%s: %s" % (path.split("/")[-1], m.group(1)))
if bad:
    print("; ".join(bad), file=sys.stderr); sys.exit(1)
' "$work/board.html" "$work/op.html" 2>"$work/auto.err"; then
  ok "every autonomy chip takes the neutral fill — the ladder is not a severity scale"
else
  bad "autonomy is never coloured as a severity" "$(cat "$work/auto.err")"
fi

# --- 18. not legal advice -----------------------------------------------------
if grep -qiF "not legal advice" "$work/board.html"; then
  ok "the board view says it is not legal advice"
else
  bad "the board view says it is not legal advice" "absent"
fi

# --- 19. --offline actually means offline -------------------------------------
ext=$(grep -oE 'https?://[^"'"'"' )]+' "$work/board.html" | grep -v 'w3\.org' | head -3 || true)
if [ -z "$ext" ]; then
  ok "--offline emits no external request from the board view"
else
  bad "--offline emits no external request" "found: $(printf '%s' "$ext" | tr '\n' ' ')"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'board-safety (ai-register): ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"
  exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'board-safety (ai-register): %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'board-safety (ai-register): all %s checks passed\n' "$checks"
