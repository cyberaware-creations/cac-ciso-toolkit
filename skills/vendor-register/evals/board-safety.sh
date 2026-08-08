#!/usr/bin/env bash
# Board-safety for the third-party views: no claim this register cannot support reaches a page.
#
# Inherits the confidence and catastrophizing checks every producer here carries, and adds one
# this skill needs that its siblings do not: **no scoring vocabulary**. `no-vendor-score.sh`
# proves nothing computes a score; this proves nothing SAYS one. A page calling a provider
# "rated" or printing a "scorecard" has delivered the number the design refuses, whether or not
# any code produced it — and it is the page, not the JSON, that a board reads.
#
# Both surfaces are checked, because the operational view is the one people forget: it is read
# by fewer people and it is where a convenient word gets added first.
#
# Anti-vacuity throughout: EXPECTED_CHECKS is asserted, the pages are proved non-empty before
# anything greps them, and the `--offline` guarantee is verified by looking for an external
# reference rather than trusting the flag.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
repo="$(cd "$skill/../.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=14
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

echo "board-safety (vendor-register): $($PY -V 2>&1)"

"$PY" "$repo/skills/business-context/scripts/business_context.py" export \
   "$repo/skills/business-context/examples/example-org.biz" --out "$work/ctx.json" >/dev/null 2>&1
"$PY" "$skill/scripts/vendor_register.py" analyze "$skill/examples/example-vendors.vnd" \
   --context "$work/ctx.json" --today 2026-08-07 --out "$work/a.json" >/dev/null 2>&1
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

# --- 3-8. vocabulary, on both rendered pages ----------------------------------
for page in board op; do
  for list in confidence catastrophizing scoring; do
    hit=$("$PY" "$here/_vocab.py" "$work/$page.html" "$list")
    if [ -z "$hit" ]; then
      ok "no $list vocabulary in the rendered $page view"
    else
      bad "no $list vocabulary in the rendered $page view" "found: $hit"
    fi
  done
done

# --- 9-10. our own source, docstrings and comments exempt ---------------------
#
# The refusal has to be explainable: every file here carries a paragraph naming the claim it
# declines to make, and those paragraphs necessarily use the words. What must stay clean is the
# code that can reach a page.
res=""
for f in "$skill"/renderers/render_*.py "$skill"/renderers/_common.py; do
  for list in confidence scoring; do
    hit=$("$PY" "$here/_vocab.py" "$f" "$list" --source)
    [ -n "$hit" ] && res="$res $(basename "$f"):$hit"
  done
done
if [ -z "$res" ]; then
  ok "no confidence or scoring vocabulary in the executable source of any view"
else
  bad "no confidence or scoring vocabulary in the source of any view" "$res"
fi
# And the stripper actually works, proved on a file built for the purpose rather than on a
# shipped one. The first version of this check probed render_board.py and passed only because
# its docstring happened to contain a banned word; when the word became legitimately exempt the
# check started failing for a reason that had nothing to do with the stripper. A purpose-built
# probe cannot rot that way.
cat > "$work/probe.py" <<'PROBE'
"""This docstring mentions a scorecard, which is exactly what a page must never print."""


def f():
    return 1
PROBE
in_prose=$("$PY" "$here/_vocab.py" "$work/probe.py" scoring)
in_code=$("$PY" "$here/_vocab.py" "$work/probe.py" scoring --source)
if [ -n "$in_prose" ] && [ -z "$in_code" ]; then
  ok "the stripper exempts prose and still reads code — banned word seen in the docstring, not after"
else
  bad "the stripper exempts prose and still reads code" \
      "with docstring: '${in_prose:-nothing}', stripped: '${in_code:-nothing}'"
fi

# --- 11-12. the page says what it will not do ---------------------------------
for page in board op; do
  if grep -qF "no vendor score" "$work/$page.html"; then
    ok "the $page view states that it produces no vendor score"
  else
    bad "the $page view states that it produces no vendor score" \
        "the caveat is absent, so a reader expecting one is not told why there isn't one"
  fi
done

# --- 13. not legal advice -----------------------------------------------------
if grep -qiF "not legal advice" "$work/board.html"; then
  ok "the board view says it is not legal advice"
else
  bad "the board view says it is not legal advice" "absent"
fi

# --- 14. --offline actually means offline -------------------------------------
ext=$(grep -oE 'https?://[^"'"'"' )]+' "$work/board.html" | grep -v 'w3\.org' | head -3 || true)
if [ -z "$ext" ]; then
  ok "--offline emits no external request from the board view"
else
  bad "--offline emits no external request" "found: $(printf '%s' "$ext" | tr '\n' ' ')"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'board-safety (vendor-register): ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"
  exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'board-safety (vendor-register): %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'board-safety (vendor-register): all %s checks passed\n' "$checks"
