#!/usr/bin/env bash
# A profile flag states ONE fact, and a battery is gated on the flag that names its regime.
#
# BL-175 is the whole reason this exists, and it is worth stating precisely because the defect
# survived twelve releases of review by people looking straight at it.
#
# `listedEntity` was documented as:
#
#     "shares admitted to trading — the SEC Item 1.05 perimeter"
#
# Two facts, joined by an em dash. The first is a listing fact, true of any exchange anywhere.
# The second is a US securities-law fact about who must file current reports on Form 8-K. The
# definition asserted they were the same thing, and `QUESTION_SETS["incident"]["sec-item-105"]`
# then computed a four-business-day statutory deadline off it. A London-listed plc with no
# Exchange Act obligation got a clock it does not owe; an unlisted US issuer reporting under
# s.15(d) was denied one it does.
#
# Nothing in that is an inference the engine performs. The arithmetic is correct, the skip
# sentences carry a declarer and a date, and every review passed — because the wrong fact was
# selected one layer up, in a dictionary of English sentences that nobody tests.
#
# So this guard tests them, in both directions:
#
#   1. STATIC — no flag definition joins two facts. The em dash is the join that did it, and
#      it is the join a definition reaches for when somebody wants to explain what a flag is
#      "really for". Catches the conflation as it is being written.
#   2. MAPPING — every gated battery whose regime is named in this table is gated on a flag
#      whose own definition names that regime. Catches the conflation arriving the other way:
#      a definition kept clean while the mapping quietly points somewhere else.
#
# Either alone is weak. A clean definition string on a battery gated by the wrong flag is
# exactly the state this repo shipped for twelve releases.
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

echo "one-fact-per-flag: $($PY -V 2>&1)"

B="$skill/scripts/business_context.py"

# `_flagcheck.py` is run three times: against the shipped module, and against two poisoned
# copies, one per direction. A guard never seen to fail is not known to work.
run() { "$PY" "$here/_flagcheck.py" "$1" "$2"; }

# 1-2. The shipped module, both halves. The labels carry no count: a label that interpolates
# what the scan found changes when the module changes, and a check whose NAME moves cannot be
# registered as a mutation target.
for half in conflation mapping; do
  res="$(run "$B" "$half")"
  case "$res" in
    "clean "*) ok "the shipped flags pass the $half half" ;;
    *) bad "the shipped flags pass the $half half" "$res" ;;
  esac
done

# 3. The scan asserted what it read (GP-1.7). A checker that found no flags at all would
# report `clean` forever, and this repo has shipped exactly that mistake twice.
count="$(run "$B" count)"
if [ "$count" -ge 15 ] 2>/dev/null; then
  ok "the scan read $count flag definitions, so 'clean' above means something"
else
  bad "the scan read enough to be meaningful" "it read '$count' flag definitions"
fi

# 4. ...and it read the mapping too, not only the definitions.
gated="$(run "$B" count-gated)"
if [ "$gated" -ge 3 ] 2>/dev/null; then
  ok "and $gated regime-bearing batteries were checked against their gate"
else
  bad "the mapping half read something" "it checked '$gated' gated batteries"
fi

# 5-8. THE GUARD, SEEN TO FAIL, on three standalone fixture modules.
#
# Deliberately NOT copies of the shipped module with a line swapped. The proofs registered
# under CAC-GP-1 mutate that module, and a poison built by patching it would fail to find its
# target the moment a proof was running — so the checker would look broken exactly when the
# harness needed it to work. These fixtures depend on nothing.
fixture() { # fixture <path> <listedEntity definition> <sec gate>
  cat > "$1" <<EOF
KNOWN_FLAGS = {
    "listedEntity": "$2",
    "secItem105Scope": "required to file current reports on Form 8-K under the Exchange Act",
    "doraScope": "in scope for DORA as a financial entity or critical ICT provider",
}
QUESTION_SETS = {
    "incident": {"sec-item-105": "$3", "dora-windows": "doraScope"},
}
EOF
}

# The control. If this does not come back clean, the two poisons below prove nothing —
# a checker that fails on everything "catches" every defect ever written.
fixture "$work/clean.py" "shares admitted to trading on a public exchange" "secItem105Scope"
if [ "$(run "$work/clean.py" conflation)" = "clean 3" ] \
   && [ "$(run "$work/clean.py" mapping)" = "clean 2" ]; then
  ok "the checker passes a clean fixture, so a red below is the poison and not the checker"
else
  bad "the checker passes a clean fixture" \
      "conflation=$(run "$work/clean.py" conflation) mapping=$(run "$work/clean.py" mapping)"
fi

# DIRECTION ONE: the em dash goes back into the definition, verbatim from the shipped v0.48.0
# source. The gate stays correct.
fixture "$work/conflated.py" "shares admitted to trading — the SEC Item 1.05 perimeter" \
        "secItem105Scope"
case "$(run "$work/conflated.py" conflation)" in
  "clean "*) bad "the static half catches a definition that joins two facts" \
                 "the exact BL-175 string passed — this guard cannot see what it exists for" ;;
  *) ok "the static half catches a definition that joins two facts" ;;
esac

# DIRECTION TWO: every definition stays clean and the gate is repointed at the listing flag.
# This is the state the repo actually shipped, and no static scan of the definitions can see
# it — which is why the halves are not one check wearing two names.
fixture "$work/repointed.py" "shares admitted to trading on a public exchange" "listedEntity"
case "$(run "$work/repointed.py" mapping)" in
  "clean "*) bad "the mapping half catches a battery gated on the wrong flag" \
                 "sec-item-105 gated on listedEntity passed — that is BL-175, unchanged" ;;
  *) ok "the mapping half catches a battery gated on the wrong flag" ;;
esac
if [ "$(run "$work/conflated.py" mapping)" = "clean 2" ] \
   && [ "$(run "$work/repointed.py" conflation)" = "clean 3" ]; then
  ok "and neither half sees the other's defect, so removing either loses real coverage"
else
  bad "the two halves are distinct" \
      "one half flagged the other's fixture: conflated/mapping=$(run "$work/conflated.py" mapping) repointed/conflation=$(run "$work/repointed.py" conflation)"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'one-fact-per-flag: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"
  exit 1
fi
if [ "$fails" -ne 0 ]; then
  printf 'one-fact-per-flag: %s of %s checks FAILED\n' "$fails" "$checks"
  exit 1
fi
printf 'one-fact-per-flag: all %s checks passed\n' "$checks"
