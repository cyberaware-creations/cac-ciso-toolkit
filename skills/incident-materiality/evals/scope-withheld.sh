#!/usr/bin/env bash
# A statutory deadline is never computed for a perimeter nobody declared — and never quietly.
#
# This is decision AP-2 made into a check. Both halves of it are load-bearing and each fails
# in the opposite direction, which is why neither on its own would do.
#
#   1. NO MANUFACTURED DATE. An incident tracked against SEC Item 1.05, on a profile that has
#      never declared `secItem105Scope`, gets NO 8-K deadline. This is the London-listed
#      non-registrant every release test from v0.48.0 to v0.63.0 reproduced: it was handed a
#      four-business-day clock it does not owe, in a compliance product, with a real date on
#      it. A manufactured legal date is worse than a missing one, because it gets acted on.
#
#   2. NO SILENT WITHHOLDING. The same incident still escalates, and the withheld window is
#      still a visible row naming the flag. Withholding alone would trade a false date for a
#      blank one, and a genuine registrant who simply had not filled in the profile would see
#      an empty deadline column with nothing to say why — the s.15(d) suppression arriving
#      through the other door.
#
# The third thing this asserts is that the two states READ DIFFERENTLY. *No window because
# nobody said* and *no window because counsel said no* are different facts, and AP-2 is
# explicit that a reader must never have to guess which one is in front of them.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=21
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }
eq()  { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "expected '$2', got '$3'"; fi; }
has() { if grep -qF -- "$2" "$3"; then ok "$1"; else bad "$1" "'$2' is not in $3"; fi; }

echo "scope-withheld: $($PY -V 2>&1)"

E="$skill/scripts/incident_analysis.py"
S="$work/t.inc"
UNSCOPED="$work/unscoped.json"
DECLARED="$work/declared.json"
DENIED="$work/denied.json"

# Three payloads that differ in ONE fact, so every difference below is attributable to it.
"$PY" - "$UNSCOPED" "$DECLARED" "$DENIED" <<'PYEOF'
import json, sys

LABEL = "SEC Item 1.05 disclosure window"


def payload(ask, skipped, undeclared):
    return {"contractVersion": "CAC-AP-1", "schemaVersion": 1,
            "orgName": "Thameside plc", "profileVersion": "FY26 close",
            "profileReviewedOn": "2026-08-07", "profile": {}, "revenue": None,
            "crownJewels": [],
            "applicability": {"incident": {"ask": ask, "skipped": skipped,
                                           "undeclared": undeclared}}}


# 1. Nobody has declared SEC scope. Shares trade in London; that is not the same fact, and
#    the profile says nothing about the Exchange Act at all.
json.dump(payload(["sec-item-105"], [], [{
    "battery": "sec-item-105", "label": LABEL, "flag": "secItem105Scope",
    "source": "absent", "declaredBy": "", "declaredOn": "", "basis": "",
    "sentence": (LABEL + " — asked in full. Organisation profile: `secItem105Scope` is not "
                 "declared. Nobody has said whether this applies.")}]),
          open(sys.argv[1], "w"), indent=2)

# 2. Counsel declared it TRUE. Same store, same incident, one declared fact.
json.dump(payload(["sec-item-105"], [], []), open(sys.argv[2], "w"), indent=2)

# 3. Counsel declared it FALSE. The skip, which must not read like case 1.
json.dump(payload([], [{
    "battery": "sec-item-105", "label": LABEL, "flag": "secItem105Scope",
    "source": "profile", "declaredBy": "General Counsel", "declaredOn": "2026-03-02",
    "basis": "No registered class and no s.15(d) obligation.",
    "sentence": (LABEL + " — not assessed. Organisation profile: `secItem105Scope: false`, "
                 "declared 2026-03-02 by General Counsel — no registered class and no "
                 "s.15(d) obligation.")}], []), open(sys.argv[3], "w"), indent=2)
PYEOF

# One incident, tracked against sec-1.05, with a determination — so a deadline EXISTS to be
# computed. Without the determination the clock reports `not-started` and every check below
# would pass on an engine that had never withheld anything.
"$PY" "$E" init "$S" --client "Thameside plc" --actor eval >/dev/null
"$PY" "$E" open "$S" --title "Payroll portal breach" --discovered 2026-07-06 \
  --regime sec-1.05 --actor eval >/dev/null
"$PY" "$E" determine "$S" --id I-001 --state material \
  --rationale "Export of employee records confirmed." --decider "General Counsel" \
  --on 2026-07-14 --actor eval >/dev/null

for tag in unscoped declared denied; do
  "$PY" "$E" analyze "$S" --today 2026-07-22 --context "$work/$tag.json" \
    --out "$work/$tag.out.json" >/dev/null || {
      printf 'scope-withheld: analyze --context %s failed outright\n' "$tag"; exit 1; }
done

row() { "$PY" -c 'import json,sys
a = json.load(open(sys.argv[1]))
r = [x for x in a["incidents"] if x["id"] == "I-001"][0]
print(eval(sys.argv[2]))' "$1" "$2"; }
top() { "$PY" -c 'import json,sys
a = json.load(open(sys.argv[1]))
print(eval(sys.argv[2]))' "$1" "$2"; }

SEC='[c for c in r["clocks"] if c["regime"] == "sec-1.05"]'

# --- the baseline, without which nothing below discriminates -------------------
eq "with a DECLARED perimeter the 8-K deadline is computed, as it always was" \
   "2026-07-20" "$(row "$work/declared.out.json" "$SEC[0][\"deadline\"]")"
eq "...and it is overdue on this date, so there is a real clock to withhold" \
   "overdue" "$(row "$work/declared.out.json" "$SEC[0][\"state\"]")"

# --- 1. NO MANUFACTURED DATE ---------------------------------------------------
eq "an undeclared perimeter computes no deadline at all" \
   "None" "$(row "$work/unscoped.out.json" "$SEC[0][\"deadline\"]")"
eq "...and says so in its own state rather than borrowing another" \
   "scope-not-declared" "$(row "$work/unscoped.out.json" "$SEC[0][\"state\"]")"
eq "...naming the flag that would settle it" \
   "secItem105Scope" "$(row "$work/unscoped.out.json" "$SEC[0][\"scopeFlag\"]")"
eq "the battery is still ASKED — a silence narrows nothing (CAC-AP-1 §2.2)" \
   "True" "$(row "$work/unscoped.out.json" '"sec-item-105" in r["context"]["asked"]')"

# --- 2. NO SILENT WITHHOLDING --------------------------------------------------
eq "the withheld window is a visible row, not an absent one" \
   "1" "$(row "$work/unscoped.out.json" "len($SEC)")"
eq "...and it escalates, so the attention survives the withholding" \
   "scope-undeclared" "$(top "$work/unscoped.out.json" '[e["trigger"] for e in a["escalations"]][0]')"
eq "...at high, not critical: a fact nobody recorded is not a deadline that passed" \
   "high" "$(top "$work/unscoped.out.json" '[e["severity"] for e in a["escalations"]][0]')"

# --- 2b. THE CONDITIONAL DATE (BL-207) -----------------------------------------
#
# The decision was NEITHER of the two options as framed: withhold the clock, AND carry the
# date in the escalation. Computing the clock would assert that Item 1.05 APPLIES, inferred
# from an assessor's tag - a legal conclusion, and `record and refuse, never judge` forbids
# it. Withholding in silence leaves a real registrant with no date at all on an obligation
# running four business days from the determination. "If X applies, the date is Y" asserts
# nothing whatever about whether X applies.
#
# WARNING: the four withholding assertions above are UNCHANGED and must stay green. This
# section ADDS to them; it replaces nothing. If anything above goes red, the change is wrong.
DETAIL='[e["evidence"]["detail"] for e in a["escalations"] if e["trigger"] == "scope-undeclared"][0]'
top "$work/unscoped.out.json" "$DETAIL" > "$work/detail.txt"
has "the withheld escalation carries a date after all" \
    "2026-07-20" "$work/detail.txt"
# THE assertion. Not "a date" - the SAME date the declared path computes on the same facts. A
# conditional that disagreed with the clock it is conditional on would be worse than silence.
eq "...and it is the same date the DECLARED path computes, to the day" \
   "2026-07-20" "$(row "$work/declared.out.json" "$SEC[0][\"deadline\"]")"
# The conditional clause is load-bearing and belongs in the EMITTED text. "Window closes 20
# July" is wrong. "If sec-1.05 applies, the window closes 20 July" is right.
has "...stated as a CONDITIONAL, naming the regime it is conditional on" \
    "If \`sec-1.05\` applies" "$work/detail.txt"
has "...and saying in the same breath that it is not a finding that it applies" \
    "not a finding that it applies" "$work/detail.txt"
# The NEGATIVE form of the same rule, here for a structural reason rather than for
# thoroughness. Every check above reads the scope-undeclared escalation, so deleting that
# escalation defeats all of them - which made this half indistinguishable from
# `no-silent-withholding` under CAC-GP-1.9, and an indistinguishable half is an unproved one.
# This one PASSES when the escalation is absent (nothing states anything) and FAILS only when
# a date is stated WITHOUT its conditional clause. That is the failure the conditional exists
# to prevent, and the only one no other half can reach.
BARE='sum(1 for e in a["escalations"] if "window closes on" in e["evidence"]["detail"] and "applies, the four-business-day" not in e["evidence"]["detail"])'
eq "no escalation ever states the window closes WITHOUT the conditional clause" \
   "0" "$(top "$work/unscoped.out.json" "$BARE")"
# THE TRAP. `ESCALATION_KEYS` is not defined in this skill; the contract lives in the
# consumers, and `attention_surface.py` projects an escalation down to exactly six keys. A
# seventh would NOT fail loudly - it would be silently dropped before reaching any surface,
# and the field would ship having never once appeared. So the shape is pinned here, at the
# producer, which is where adding the key would happen.
KEYS='",".join(sorted([e for e in a["escalations"] if e["trigger"] == "scope-undeclared"][0]))'
eq "the escalation still carries exactly the six contract keys, so nothing is silently dropped" \
   "evidence,severity,since,subjectKind,subjectRef,trigger" \
   "$(top "$work/unscoped.out.json" "$KEYS")"
# Constraint 4: a declared-FALSE profile already has a real clock and a reported conflict. A
# conditional there would put two dates on one incident.
eq "a declared-FALSE profile raises no scope-undeclared escalation, so it gets no second date" \
   "0" "$(top "$work/denied.out.json" 'len([e for e in a["escalations"] if e["trigger"] == "scope-undeclared"])')"

# --- 3. declared-out and undeclared do not behave alike, on the SAME incident --
#
# Both leave the profile disagreeing with a tracked regime, and the engine answers them
# differently on purpose. A declared NO is an answer, so the assessor who opened the clock is
# contradicting one: the window is computed and the disagreement is reported. A silence is not
# an answer, so there is nothing to contradict and nothing to compute a date from.
eq "a DECLARED-OUT perimeter still computes the window — the tool does not overrule the assessor" \
   "2026-07-20" "$(row "$work/denied.out.json" "$SEC[0][\"deadline\"]")"
eq "...and reports the disagreement instead" \
   "sec-item-105" "$(row "$work/denied.out.json" '[c["battery"] for c in r["context"]["conflicts"]][0]')"
eq "while an UNDECLARED one raises no conflict — a silence is not a disagreement" \
   "0" "$(row "$work/unscoped.out.json" 'len(r["context"]["conflicts"])')"
row "$work/unscoped.out.json" "$SEC[0][\"note\"]" > "$work/note.txt"
has "the withheld note says the regime may yet apply" "not a finding" "$work/note.txt"
(cd "$skill/renderers" && "$PY" render_worksheet.py --in "$work/unscoped.out.json" \
  --out "$work/w.html" >/dev/null)
has "and the worksheet gives it its own heading, apart from the profile's skips" \
    "Questions asked with nothing declared" "$work/w.html"

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'scope-withheld: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"
  exit 1
fi
if [ "$fails" -ne 0 ]; then
  printf 'scope-withheld: %s of %s checks FAILED\n' "$fails" "$checks"
  exit 1
fi
printf 'scope-withheld: all %s checks passed\n' "$checks"
