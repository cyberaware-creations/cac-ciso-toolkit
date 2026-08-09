#!/usr/bin/env bash
# Wherever this suite states a NYDFS obligation, it states who inside the perimeter is exempt.
#
# BL-188. Three shipped locations told a covered entity that §500.12 (MFA) and §500.15
# (encryption) bind it. §500.19 exempts qualifying covered entities from exactly those
# sections, and §500.19 appeared nowhere in `skills/` at all — `grep -rn "500\.19"` returned
# nothing across five releases of reports.
#
# What makes it worth a guard rather than a fix is the PATTERN the three shared. Every one of
# them carried a careful limit, and every limit scoped in one direction:
#
#     "it binds covered entities in New York financial services and nobody else"
#     "NYDFS §500.12 binds covered entities in New York and nobody else"
#     "it applies only to covered financial entities"          <- annotated "HONEST LIMIT"
#
# They are written to stop the claim reaching firms OUTSIDE the perimeter, and they are silent
# on which firms inside it are exempt. The discipline that produced them guards against
# over-claiming outward and had no equivalent habit for over-claiming inward. So an exempt firm
# is told its lawful gap is a compliance failure, and — following this suite's own guidance —
# logs a controlled exception with a remediation timeline for an obligation it does not have.
# That is the toolkit manufacturing the finding.
#
# THE D-4 SWEEP, recorded here because a result nobody wrote down is a result nobody has.
# Every `*.md` under `skills/` was scanned for an outward-scoping sentence ("nobody else",
# "applies only to", "HONEST LIMIT", "**Limit:**") and each hit read against one question:
# DOES THIS REGULATION EXEMPT ANYONE INSIDE THE PERIMETER IT NAMES? 31 candidates, and the
# regulatory ones fall into three groups:
#
#   ALREADY TWO-DIRECTIONAL — DORA RTS Art. 3(d) in `regulatory-receipts.md` and in
#     `exceptions.md`, both of which name the Art. 16 simplified framework (and the receipt
#     even warns against the word "exempt" for it); SEC Item 1.05 in `disclosure-clocks.md`,
#     which carries the 1.05(c) and 1.05(d) delay mechanisms and the Form 8-K boundary.
#   FIXED HERE — the three NYDFS locations this guard now holds.
#   OUTWARD-ONLY AND UNVERIFIED — `materiality-factors.md` on DORA and on SEC Item 106, and
#     `incident-materiality/SKILL.md` on Item 1.05. The inward limit for the first exists in
#     two other shipped files and is missing from this one; whether Art. 16 reaches incident
#     REPORTING under RTS 2025/301 the way it reaches the residual-risk inventory under RTS
#     2024/1774 is a different question, and it has not been read against the primary source.
#     Filed rather than guessed — copying a limit between regimes is how the next BL-188 gets
#     written.
#
# This guard deliberately covers the NYDFS three and no more. Widening the file list before
# the reading is done would turn a real check into a green light over unverified prose.
#
# TWO halves, and they fail on different things:
#
#   1. STATED — each location names §500.19 and distinguishes its limbs. Not "an exemption
#      exists": (a) reaches §500.15 and NOT §500.12, (c) and (d) reach both, and a receipt
#      that collapses them is wrong in a way a reader cannot detect.
#   2. NOT COMPUTED — wherever a qualification THRESHOLD appears, the sentence saying it is a
#      legal determination appears in the same file. The tests read like arithmetic (a
#      headcount, a revenue figure, an asset total) and that is exactly the trap: affiliate
#      aggregation and "otherwise qualifies as a covered entity" are not arithmetic. A file
#      that prints the numbers and drops the caveat invites the reader to self-assess.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=10
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

echo "nydfs-exemptions: $($PY -V 2>&1)"

run() { "$PY" "$here/_exemptioncheck.py" "$1" "$2"; }

# 1-2. The shipped tree, both halves.
for half in stated not-computed; do
  res="$(run "$repo" "$half")"
  case "$res" in
    "clean "*) ok "the shipped locations pass the $half half" ;;
    *) bad "the shipped locations pass the $half half" "$res" ;;
  esac
done

# 3. GP-1.7 — the scan asserts what it read. A checker whose file list has drifted finds
# nothing to check and reports success forever, which is the defect this repo named in
# BL-204 and then committed again inside the fix for it.
n="$(run "$repo" count)"
if [ "$n" = "3" ]; then
  ok "all 3 shipped locations were opened and read"
else
  bad "all 3 shipped locations were opened and read" "it read '$n' of them"
fi

# 4. ...and a missing file is a FAILURE, not a skip. A renamed reference would otherwise
# silently shrink the guard to whatever survived.
mkdir -p "$work/empty"
case "$(run "$work/empty" stated)" in
  "clean "*) bad "a missing location fails rather than passing vacuously" \
                 "an empty tree passed the stated half" ;;
  *) ok "a missing location fails rather than passing vacuously" ;;
esac

# 5-9. THE GUARD, SEEN TO FAIL, on synthetic fixture trees.
#
# NOT copies of the shipped tree with a property removed. `one-fact-per-flag.sh` learned this
# the hard way and this suite walked into it anyway: the CAC-GP-1 proofs mutate the very files
# a copy would be made from, so under a live mutation the "poisoned" copy carries the harness's
# defect as well as its own and the distinctness checks flip. A fixture depends on nothing.
fixture() { # fixture <dir> <limbs?> <sections?> <caveat?> <thresholds?>
  local d="$1"
  mkdir -p "$d/skills/exceptions-register/references" \
           "$d/skills/ciso-board-translation/references"
  local limbs="" sections="" caveat="" thresholds=""
  [ "$2" = yes ] && limbs="Limbs: 500.19(a) and 500.19(c) and 500.19(d)."
  [ "$3" = yes ] && sections="It reaches 500.15 but not 500.12 under (a)."
  [ "$4" = yes ] && caveat="Qualifying is a legal determination and counsel makes it."
  [ "$5" = yes ] && thresholds="Under 20 employees, or \$7,500,000, or \$15,000,000."
  for f in "$d/skills/exceptions-register/references/exceptions.md" \
           "$d/skills/exceptions-register/SKILL.md" \
           "$d/skills/ciso-board-translation/references/regulatory-receipts.md"; do
    printf 'NYDFS 500.19 exempts some covered entities.\n%s\n%s\n%s\n%s\n' \
      "$limbs" "$sections" "$caveat" "$thresholds" > "$f"
  done
}

# The control. Without it, a checker that failed on everything would "catch" every defect.
fixture "$work/clean" yes yes yes yes
if [ "$(run "$work/clean" stated)" = "clean 3" ] \
   && [ "$(run "$work/clean" not-computed)" = "clean 3" ]; then
  ok "the checker passes a complete fixture, so a red below is the fixture not the checker"
else
  bad "the checker passes a complete fixture" \
      "stated=$(run "$work/clean" stated) not-computed=$(run "$work/clean" not-computed)"
fi

# A — the limbs collapsed to a bare section number. Everything else intact.
fixture "$work/collapsed" no yes yes yes
case "$(run "$work/collapsed" stated)" in
  "clean "*) bad "the stated half catches limbs collapsed to a bare section number" \
                 "a receipt naming §500.19 without its limbs passed, and (a) reaches §500.15 "\
"while (c) and (d) reach §500.12 too" ;;
  *) ok "the stated half catches limbs collapsed to a bare section number" ;;
esac
case "$(run "$work/collapsed" not-computed)" in
  "clean "*) ok "...and the not-computed half does not fire on a limb defect" ;;
  *) bad "the not-computed half ignores a limb defect" \
         "it flagged the collapsed fixture, so the two halves overlap" ;;
esac

# B — no §500.19 anywhere. This is the state the repo shipped for five releases.
mkdir -p "$work/none/skills/exceptions-register/references" \
         "$work/none/skills/ciso-board-translation/references"
for f in "$work/none/skills/exceptions-register/references/exceptions.md" \
         "$work/none/skills/exceptions-register/SKILL.md" \
         "$work/none/skills/ciso-board-translation/references/regulatory-receipts.md"; do
  printf 'NYDFS 500.12 and 500.15 bind covered entities and nobody else.\n' > "$f"
done
case "$(run "$work/none" stated)" in
  "clean "*) bad "the stated half catches a location that names no exemption at all" \
                 "the pre-BL-188 state passed — this guard cannot see what it exists for" ;;
  *) ok "the stated half catches a location that names no exemption at all" ;;
esac

# C — the thresholds kept, the determination caveat gone. Everything still reads correct.
fixture "$work/uncaveated" yes yes no yes
case "$(run "$work/uncaveated" not-computed)" in
  "clean "*) bad "the not-computed half catches thresholds printed without the caveat" \
                 "a file inviting a reader to self-assess off three numbers passed" ;;
  *) ok "the not-computed half catches thresholds printed without the caveat" ;;
esac
case "$(run "$work/uncaveated" stated)" in
  "clean "*) ok "...and the stated half does not fire on a missing caveat" ;;
  *) bad "the stated half ignores a caveat defect" \
         "it flagged the uncaveated fixture, so the two halves overlap" ;;
esac

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'nydfs-exemptions: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"
  exit 1
fi
if [ "$fails" -ne 0 ]; then
  printf 'nydfs-exemptions: %s of %s checks FAILED\n' "$fails" "$checks"
  exit 1
fi
printf 'nydfs-exemptions: all %s checks passed\n' "$checks"
