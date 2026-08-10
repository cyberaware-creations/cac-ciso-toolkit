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
. "$here/../../../tools/eval-probe.sh"   # `probe` — a crashed check is not a clean one (BL-121)
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=22
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

# --- 11-13. our own SOURCE — every shipped .py, scripts included -------------------
#
# GP-1.7, reaching the two suites BL-211 scoped out (BL-221). This scanned
# `renderers/render_*.py` and `renderers/_common.py` through a shell glob until v0.77.0 —
# every renderer and NO engine script — while `scripts/ai_register.py` writes most of the strings
# the renderers print. Three checks, because the scan and the population it read are separate
# claims and a clean scan over the wrong population is the failure being fixed.
#
# Docstrings, comments and any `self_test` function are exempt: the refusal has to be
# explainable, and an assertion that a word is ABSENT has to name the word.
tree=$("$PY" "$here/_vocab.py" "$skill" --tree)
hits=$(printf '%s\n' "$tree" | grep '^SCAN: ' || true)
listp=$(printf '%s\n' "$tree" | grep '^LIST: ' || true)
orph=$(printf '%s\n' "$tree" | grep '^UNDECIDED-ORPHAN: ' || true)
pop=$(printf '%s\n' "$tree" | sed -n 's/^POPULATION: //p')

if [ -z "$hits" ]; then
  ok "no banned vocabulary in the executable source of any shipped file"
else
  bad "no banned vocabulary in the executable source of any shipped file" \
      "$(printf '%s' "$hits" | tr '\n' ' ')"
fi

# The population, ASSERTED rather than counted. `scanned == len(files)` is true of any list,
# including one with no engine script in it — which is precisely the state this suite was in.
case ",$pop," in
  *",scripts/ai_register.py,"*) popok=1 ;;
  *) popok="" ;;
esac
if [ -n "$popok" ] && [ -z "$listp" ]; then
  ok "the file list is recomputed from the tree and includes the engine ($pop)"
else
  bad "the file list is recomputed from the tree and includes the engine" \
      "${listp:-the engine script is not in the population: $pop}"
fi

# BL-221 D-3. Hits that ship, are not defects, and whose disposition is NOT YET DECIDED are
# allowed AND ANNOUNCED — printed on every run, and required to still match a real hit. An
# allowance that outlives its hit fails here, so this cannot decay into a silent exemption.
if [ -z "$orph" ]; then
  printf '%s\n' "$tree" | grep '^UNDECIDED: ' | sed 's/^/        /' || true
  ok "every undecided hit is still present and still named (BL-221 D-3, open)"
else
  bad "every undecided hit is still present and still named" \
      "$(printf '%s' "$orph" | tr '\n' ' ')"
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


# --- C-1: the sentences carry a consequence, the decisions decide -------------
#
# Appended rather than woven in, so every check above is untouched. This suite has always
# tested for ABSENCE — no confidence vocabulary, no reworded score. Nothing tested for
# PRESENCE, and "Patch compliance fell to 88%." passed all of it: a named thing, no
# consequence, no ask.
#
# The scan lives once, under board-pack, because nine copies of a linguistic rule would drift
# into nine slightly different rules. See board-pack/evals/outcome-framing.sh for the full
# argument and the mutation proofs; this is the per-producer call.
_scan="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../board-pack/evals" && pwd)/_outcomescan.py"
_sidecar=""
for _cand in "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"/references/example-translations.json \
             "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"/examples/example-translations.json \
             "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"/examples/pack.board.json; do
  [ -f "$_cand" ] && _sidecar="$_cand" && break
done
if [ -z "$_sidecar" ]; then
  # business-context is framing rather than a section, so it ships no translations sidecar.
  # Asserted rather than skipped: the day it gains one, this fails and somebody wires it in.
  ok "no board sidecar in this skill, so there is no board prose here to check"
elif "$PY" "$_scan" "$_sidecar" >/dev/null 2>"${TMPDIR:-/tmp}/cac-outcome.$$.err"; then
  ok "every board sentence carries a consequence and every decision decides (C-1)"
else
  bad "every board sentence carries a consequence and every decision decides (C-1)" \
      "$("$PY" "$_scan" "$_sidecar" 2>&1 >/dev/null | grep '^  FAIL' | head -3 | tr '\n' ' ')"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'board-safety (ai-register): ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"
  exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'board-safety (ai-register): %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'board-safety (ai-register): all %s checks passed\n' "$checks"
