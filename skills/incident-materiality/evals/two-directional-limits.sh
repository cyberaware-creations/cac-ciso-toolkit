#!/usr/bin/env bash
# Every regulatory limit in the shipped prose runs in both directions, not just outward.
#
# BL-188 found three NYDFS receipts that scoped only outward — at who the rule does not reach —
# and said nothing about which covered entities inside the perimeter are exempt. `§500.19` was
# absent from `skills/` entirely. The sweep that followed asked the same question of all 31
# outward-scoping sentences in the repo and left three unanswered, because answering them meant
# reading two more regulations rather than pattern-matching. This guard is what those reads
# produced, frozen.
#
# THE READS, and what each established:
#
#   DORA — Art. 2(3) takes SIX categories out of the Regulation from inside the financial-entity
#     list: AIFMs under Art. 3(2) of 2011/61/EU, insurers under Art. 4 of 2009/138/EC, IORPs with
#     no more than 15 members, persons exempted under Arts. 2-3 of 2014/65/EU, SME insurance
#     intermediaries, and post office giro institutions. Art. 2(4) lets a Member State exclude
#     more. THAT is the inward limit on reporting.
#
#   DORA Art. 16 — and this is the reason for the second half. The simplified ICT risk
#     management framework disapplies "Articles 5 to 15" and nothing else. Incident reporting is
#     Chapter III, Arts. 17-23, with major-incident reporting at Art. 19 — untouched. The only
#     mention of microenterprises anywhere in Chapter III is a mandate to the ESAs to bear their
#     capacity in mind when setting the Art. 18 classification criteria, which is not an
#     exemption. So Art. 16 belongs to the residual-risk receipts under RTS 2024/1774, where it
#     already correctly sits, and NOT to the reporting receipt under RTS 2025/301.
#
#     The tempting edit was one line: two shipped files already name the Art. 16 limit, so
#     copying it into the third looks like consistency. It would have been a fabricated
#     exemption in a disclosure record. This half freezes the correction.
#
#   SEC Item 106 — 17 CFR 229.106 carries NO exemption. Read in full it is definitions, risk
#     management and strategy, governance and a structured-data requirement. Its one inward
#     variation is Instruction 1 to Item 106(c), a two-tier-board accommodation for a foreign
#     private issuer, which relieves nobody of the disclosure. "Who is let off this?" has an
#     answer, and the answer is nobody — which is worth stating rather than leaving blank.
#
# TWO halves:
#   1. INWARD-STATED — each (file, regime) pair in the registry carries its verified inward
#      limit. Fails when a receipt goes back to scoping outward only.
#   2. NO-BORROWED-LIMIT — a file naming Art. 16 beside reporting says what Art. 16 actually
#      disapplies. Fails when the correction is dropped and the wrong reading becomes available
#      again.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=9
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

echo "two-directional-limits: $($PY -V 2>&1)"

run() { "$PY" "$here/_limitcheck.py" "$1" "$2"; }

# 1-2. The shipped tree, both halves.
for half in inward-stated no-borrowed-limit; do
  res="$(run "$repo" "$half")"
  case "$res" in
    "clean "*) ok "the shipped prose passes the $half half" ;;
    *) bad "the shipped prose passes the $half half" "$res" ;;
  esac
done

# 3. GP-1.7 — the registry asserts what it read. Six pairs, and a registry that quietly shrank
# to four would still print `clean`.
n="$(run "$repo" count)"
if [ "$n" = "6" ]; then
  ok "all 6 registered (file, regime) pairs were opened and read"
else
  bad "all 6 registered (file, regime) pairs were opened and read" "it read '$n'"
fi

# 4. A missing file fails rather than passing vacuously.
mkdir -p "$work/empty"
case "$(run "$work/empty" inward-stated)" in
  "clean "*) bad "a missing location fails rather than passing vacuously" \
                 "an empty tree passed" ;;
  *) ok "a missing location fails rather than passing vacuously" ;;
esac

# 5-9. SEEN TO FAIL, on synthetic fixtures. Not copies of the tree: the CAC-GP-1 proofs mutate
# the files a copy would be made from, so a poisoned copy carries the harness's defect too and
# the distinctness checks flip. `nydfs-exemptions.sh` records the same lesson.
fixture() { # fixture <dir> <inward?> <art16-correction?>
  local d="$1" inward="" art16=""
  mkdir -p "$d/skills/incident-materiality/references" \
           "$d/skills/ciso-board-translation/references"
  [ "$2" = yes ] && inward="Art. 2(3) excludes six categories. Instruction 1 to Item 106(c) \
accommodates a two-tier board. Item 1.05(c) and Item 1.05(d) delay. secItem105Scope is declared."
  [ "$3" = yes ] && art16="Art. 16 disapplies Articles 5 to 15 only."
  for f in "$d/skills/incident-materiality/references/materiality-factors.md" \
           "$d/skills/incident-materiality/SKILL.md" \
           "$d/skills/incident-materiality/references/disclosure-clocks.md" \
           "$d/skills/ciso-board-translation/references/regulatory-receipts.md"; do
    printf 'Outward: it binds registrants and nobody else.\n%s\n%s\n' "$inward" "$art16" > "$f"
  done
}

# The control.
fixture "$work/clean" yes yes
if [ "$(run "$work/clean" inward-stated)" = "clean 6" ] \
   && [ "$(run "$work/clean" no-borrowed-limit)" = "clean 2" ]; then
  ok "the checker passes a complete fixture, so a red below is the fixture not the checker"
else
  bad "the checker passes a complete fixture" \
      "inward=$(run "$work/clean" inward-stated) borrowed=$(run "$work/clean" no-borrowed-limit)"
fi

# A — outward only. This is the pre-BL-188 shape, in a different regime.
fixture "$work/outward" no yes
case "$(run "$work/outward" inward-stated)" in
  "clean "*) bad "the inward-stated half catches a receipt that scopes outward only" \
                 "a perimeter with nobody excluded from inside it passed" ;;
  *) ok "the inward-stated half catches a receipt that scopes outward only" ;;
esac
case "$(run "$work/outward" no-borrowed-limit)" in
  "clean "*) ok "...and the no-borrowed-limit half does not fire on it" ;;
  *) bad "the halves are distinct" "no-borrowed-limit flagged a missing inward limit" ;;
esac

# B — Art. 16 named beside reporting with no statement of what it disapplies. One line from
# somebody "helpfully" reading it as an exemption from the reporting obligation.
mkdir -p "$work/borrowed/skills/incident-materiality/references" \
         "$work/borrowed/skills/ciso-board-translation/references"
fixture "$work/borrowed" yes no
for f in "$work/borrowed/skills/incident-materiality/references/materiality-factors.md" \
         "$work/borrowed/skills/incident-materiality/SKILL.md"; do
  printf 'Art. 16 entities use a simplified framework.\n' >> "$f"
done
case "$(run "$work/borrowed" no-borrowed-limit)" in
  "clean "*) bad "the no-borrowed-limit half catches Art. 16 named with no correction" \
                 "a reporting receipt naming Art. 16 without 'Articles 5 to 15' passed, which "\
"is the fabricated exemption this guard exists for" ;;
  *) ok "the no-borrowed-limit half catches Art. 16 named with no correction" ;;
esac
case "$(run "$work/borrowed" inward-stated)" in
  "clean "*) ok "...and the inward-stated half does not fire on it" ;;
  *) bad "the halves are distinct" "inward-stated flagged a missing Art. 16 correction" ;;
esac

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'two-directional-limits: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"
  exit 1
fi
if [ "$fails" -ne 0 ]; then
  printf 'two-directional-limits: %s of %s checks FAILED\n' "$fails" "$checks"
  exit 1
fi
printf 'two-directional-limits: all %s checks passed\n' "$checks"
