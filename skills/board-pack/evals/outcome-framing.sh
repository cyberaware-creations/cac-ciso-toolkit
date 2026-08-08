#!/usr/bin/env bash
# C-1: the translation contract's existing requirements, turned into a test.
#
# `ciso-board-translation` has always required four things of a board sentence — what is
# exposed, what it means for us, the trend, and a decision. Two of those were guidance that
# nothing checked. Every `board-safety.sh` in the suite tests for ABSENCE: no confidence
# vocabulary, no reworded score, no derived materiality. None tested for PRESENCE, so a sidecar
# reading
#
#     "Patch compliance fell to 88%."
#
# passed every test in the repository. It names a thing, gives no consequence, and asks nothing.
#
# The shipped examples are strong because an author was careful, not because the toolkit
# insists — which is exactly the class of property this repo elsewhere converts into a test.
#
# What this is NOT: a style checker. It tests that a required element is present, never that
# the prose is good. The vocabulary is data, in
# `ciso-board-translation/references/consequence-vocabulary.json`, and extending it is the
# intended response to a false negative — which is why every rejection names its sentence.
#
# Three rules, and they are not equally strict on purpose:
#
#   HARD   every `decisions[]` entry ends on a decision. Unambiguous, no floor.
#   HARD   no opportunity vocabulary inside a risk-carrying item sentence. An optimistic tail
#          welded onto a loss statement reads as softening it, which is worse than either
#          element alone and teaches a board to discount the section (C-2, GV.RM-07).
#   FLOOR  item sentences clear a share — 80%, with at least one miss always tolerated,
#          because a linguistic check with acknowledged false negatives must not be a perfect
#          gate on a four-item section. Individual misses print as warnings.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# One per shipped sidecar, plus the vocabulary check, the two mutation halves and the
# anti-vacuity count. Asserted, so a sidecar that stopped being discovered fails loudly.
EXPECTED_CHECKS=15
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

SCAN="$here/_outcomescan.py"
VOCAB="$repo/skills/ciso-board-translation/references/consequence-vocabulary.json"
echo "outcome-framing: $($PY -V 2>&1)"

# --- the checker's own tests, first -------------------------------------------
# Running the guard before the thing it guards is the only order in which a green tick below
# means anything — the same reasoning the crosswalk validator's self-test is sequenced by.
if "$PY" "$SCAN" --self-test >"$work/st.out" 2>&1; then
  ok "the checker's own tests pass ($(tail -1 "$work/st.out"))"
else
  bad "the checker's own tests pass" "$(tail -3 "$work/st.out" | tr '\n' ' ')"
fi

# --- the vocabulary is real data ----------------------------------------------
if "$PY" -c '
import json, sys
v = json.load(open(sys.argv[1], encoding="utf-8"))
small = [k for k in ("connectives", "consequenceNouns", "decisionVerbs")
         if len(v.get(k) or []) < 10]
if small:
    print("these lists are too short to be doing any work: %s" % small, file=sys.stderr)
    sys.exit(1)
if len((v.get("opportunityVocabulary") or {}).get("words") or []) < 5:
    print("the opportunity list is too short to catch a blend", file=sys.stderr); sys.exit(1)
for key in ("connectives", "consequenceNouns", "decisionVerbs"):
    if len(v[key]) != len(set(v[key])):
        print("%s has duplicates" % key, file=sys.stderr); sys.exit(1)
' "$VOCAB" 2>"$work/v.err"; then
  ok "the vocabulary carries enough of each list to be doing work, with no duplicates"
else
  bad "the vocabulary is substantial" "$(cat "$work/v.err")"
fi

# --- every shipped sidecar, discovered rather than listed ---------------------
#
# Discovered by glob so a producer that ships a sidecar is checked without editing this file —
# the same convention prove-guards.sh uses, and for the same reason. The count is asserted
# below, so a glob that stopped matching fails instead of reporting a clean run over nothing.
seen=0
while IFS= read -r sidecar; do
  [ -n "$sidecar" ] || continue
  seen=$((seen + 1))
  name="$(basename "$(dirname "$(dirname "$sidecar")")")"
  if "$PY" "$SCAN" "$sidecar" >"$work/out.txt" 2>"$work/err.txt"; then
    warned=$(grep -c "^  warn" "$work/err.txt" || true)
    note=""
    [ "${warned:-0}" -gt 0 ] && note=" ($warned warned)"
    ok "$name: $(cat "$work/out.txt")$note"
  else
    bad "$name carries a consequence in its sentences and a decision in its decisions" \
        "$(grep '^  FAIL' "$work/err.txt" | head -3 | tr '\n' ' ')"
  fi
done < <(ls "$repo"/skills/*/references/example-translations.json \
            "$repo"/skills/*/examples/example-translations.json \
            "$repo"/skills/board-pack/examples/pack.board.json 2>/dev/null | sort)

if [ "$seen" -ge 7 ]; then
  ok "...across $seen shipped sidecar(s), which is every producer plus the through-line"
else
  bad "every shipped sidecar was checked" \
      "found only $seen — the glob stopped matching and this proved nothing"
fi

# --- the teeth, both halves ---------------------------------------------------
#
# T4/CAC-GP-1: seen to fail, then seen to pass. A guard that only ever passes is
# indistinguishable from a guard that stopped working, and this one is a floor rather than an
# equality, so it is exactly the kind that can rot silently.
#
# HALF ONE — strip the consequence clause from real sentences until the floor breaks.
"$PY" - "$repo/skills/risk-register/references/example-translations.json" \
       "$work/stripped.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
# Three of the seven risk sentences reduced to a bare fact — the "Patch compliance fell to
# 88%" shape this whole suite exists for. Three misses out of seven is past any floor and
# past the one tolerated miss.
for i, key in enumerate(sorted(d["risks"])[:3]):
    d["risks"][key] = "Exposure moved to %d this quarter." % (11 + i)
json.dump(d, open(sys.argv[2], "w", encoding="utf-8"), indent=2)
PYEOF
if "$PY" "$SCAN" "$work/stripped.json" >/dev/null 2>"$work/m1.err"; then
  bad "the floor fails when consequence clauses are stripped" \
      "it passed with three bare-fact sentences out of seven"
else
  named=$(grep -c "carries no consequence" "$work/m1.err" || true)
  if [ "${named:-0}" -ge 3 ]; then
    ok "the floor fails on three stripped sentences, and NAMES all $named of them"
  else
    bad "the floor names what it rejected" "only $named sentence(s) named — a rejection a "\
"reader cannot act on is a rejection they will disable"
  fi
fi

# HALF TWO — a decision that is not a decision. Hard rule, so one is enough.
"$PY" - "$repo/skills/risk-register/references/example-translations.json" \
       "$work/wishful.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
d["decisions"][0] = dict(d["decisions"][0], text="We should look at this.")
json.dump(d, open(sys.argv[2], "w", encoding="utf-8"), indent=2)
PYEOF
if "$PY" "$SCAN" "$work/wishful.json" >/dev/null 2>&1; then
  bad "a decisions entry that decides nothing fails" \
      "'We should look at this.' passed as a board decision"
else
  ok "...and a decisions entry that decides nothing fails, with no floor to hide behind"
fi

# HALF THREE — the blend. C-2's guardrail, checked here because it is the same scan.
"$PY" - "$repo/skills/risk-register/references/example-translations.json" \
       "$work/blended.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
key = sorted(d["risks"])[0]
d["risks"][key] = d["risks"][key].rstrip(".") + ", and this also unlocks faster onboarding."
json.dump(d, open(sys.argv[2], "w", encoding="utf-8"), indent=2)
PYEOF
if "$PY" "$SCAN" "$work/blended.json" >/dev/null 2>"$work/m3.err"; then
  bad "an optimistic tail on a risk sentence fails" \
      "'...and this also unlocks faster onboarding' passed inside a risk sentence"
else
  if grep -q "blends opportunity" "$work/m3.err"; then
    ok "an optimistic tail on a risk sentence fails, and is named as a blend"
  else
    bad "the blend is named as a blend" "$(tail -2 "$work/m3.err" | tr '\n' ' ')"
  fi
fi

# ...and the clean article still passes, which is the direction a failure-only test misses.
if "$PY" "$SCAN" "$repo/skills/risk-register/references/example-translations.json" \
     >/dev/null 2>&1; then
  ok "while the unmutated sidecar still passes — both directions, in that order"
else
  bad "the unmutated sidecar passes" "the guard is broken, not the sidecar"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'outcome-framing: ran %s checks, expected %s — a case stopped executing\n' \
         "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'outcome-framing: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'outcome-framing: all %s checks passed\n' "$checks"
