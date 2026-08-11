#!/usr/bin/env bash
# DORA's conditional date, where the anchor exists — and NO date where it does not (BL-237).
#
# `sec-1.05` carries a conditional date on a withheld clock because its anchor, the materiality
# determination, exists by the time the question arises. DORA stacks TWO unknowns: scope may be
# undeclared AND the anchor absent, because its windows run in clock hours from `awareAt` or
# `classifiedAt` and neither may ever have been recorded.
#
# So the rule is NOT a flat copy of the SEC one:
#
#   PATH A — anchor present, scope undeclared. Identical to `sec-1.05`: if DORA applies, the
#            initial report window closes at DATETIME. A conditional asserts nothing whatever
#            about whether the regime applies, and says so in the same breath.
#
#   PATH B — anchor absent. NO date. Not a placeholder, not an empty string dressed as a
#            value. Name the missing anchor instead. Path B's message is the MORE USEFUL of
#            the two: it names something the reader can go and supply, and it is true whether
#            or not DORA applies, so it needs no scope hypothesis at all.
#
# ⚠️ HALF 2 IS THE ONE A CARELESS IMPLEMENTATION FAILS, and it fails in the direction that
# looks like success. An empty-or-None date still RENDERS — the sentence is there, the field is
# there, it simply has nothing in it — so a check asserting "a date is present" goes green on a
# lie. The mutation registered against this half emits an empty-but-present date for exactly
# that reason. "If DORA applies, the window closes at ." is worse than silence: it looks like a
# computation and is none.
#
# WHAT THIS SUITE DOES NOT TOUCH: the `sec-1.05` path. `scope-withheld.sh` is the canary for
# that and must stay green at 21 checks throughout — if it goes red, this change reached
# somewhere it should not have. NYDFS is not a regime in this engine and does not become one by
# implication.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=14
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }
eq()  { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "expected '$2', got '$3'"; fi; }

echo "dora-conditional: $($PY -V 2>&1)"

E="$skill/scripts/incident_analysis.py"
LABEL="DORA major-incident reporting windows"

# Two context payloads differing in ONE fact: whether anyone declared DORA scope.
"$PY" - "$work/unscoped.json" "$work/declared.json" <<'PYEOF'
import json, sys

LABEL = "DORA major-incident reporting windows"


def payload(ask, undeclared):
    return {"contractVersion": "CAC-AP-1", "schemaVersion": 1,
            "orgName": "Thameside plc", "profileVersion": "FY26 close",
            "profileReviewedOn": "2026-08-07", "profile": {}, "revenue": None,
            "crownJewels": [],
            "applicability": {"incident": {"ask": ask, "skipped": [],
                                           "undeclared": undeclared}}}


json.dump(payload(["dora-windows"], [{
    "battery": "dora-windows", "label": LABEL, "flag": "doraScope",
    "source": "absent", "declaredBy": "", "declaredOn": "", "basis": "",
    "sentence": (LABEL + " — asked in full. Organisation profile: `doraScope` is not "
                 "declared. Nobody has said whether this applies.")}]),
          open(sys.argv[1], "w"), indent=2)
json.dump(payload(["dora-windows"], []), open(sys.argv[2], "w"), indent=2)
PYEOF

# Two stores differing in ONE fact: whether an anchor was ever recorded.
for tag in anchored bare; do
  "$PY" "$E" init "$work/$tag.inc" --client "Thameside plc" --actor eval >/dev/null
  "$PY" "$E" open "$work/$tag.inc" --title "Payment rail outage" --discovered 2026-07-06 \
    --regime dora --actor eval >/dev/null
done
"$PY" "$E" set-anchor "$work/anchored.inc" --id I-001 --aware 2026-07-06T09:00 \
  --actor eval >/dev/null

for tag in anchored bare; do
  "$PY" "$E" analyze "$work/$tag.inc" --today 2026-07-22 --context "$work/unscoped.json" \
    --out "$work/$tag.out.json" >/dev/null || {
      printf 'dora-conditional: FIXTURE FAILED — analyze %s errored\n' "$tag"; exit 1; }
done
"$PY" "$E" analyze "$work/anchored.inc" --today 2026-07-22 --context "$work/declared.json" \
  --out "$work/declared.out.json" >/dev/null || {
    printf 'dora-conditional: FIXTURE FAILED — analyze declared errored\n'; exit 1; }

det() { "$PY" -c 'import json,sys
a = json.load(open(sys.argv[1]))
e = [x for x in a["escalations"] if x["trigger"] == "scope-undeclared"]
print(e[0]["evidence"]["detail"] if e else "<no scope-undeclared escalation>")' "$1"; }
top() { "$PY" -c 'import json,sys
a = json.load(open(sys.argv[1]))
print(eval(sys.argv[2]))' "$1" "$2"; }

# --- the baseline, without which nothing below discriminates ---------------------------
DORA='[c for c in [x for x in a["incidents"] if x["id"]=="I-001"][0]["clocks"] if c["regime"]=="dora" and c["window"]=="initial"]'
eq "with a DECLARED perimeter the initial window is computed, as it always was" \
   "2026-07-07T09:00:00+00:00" "$(top "$work/declared.out.json" "$DORA[0][\"deadline\"]")"
eq "...and with the perimeter undeclared no deadline is computed at all" \
   "None" "$(top "$work/anchored.out.json" "$DORA[0][\"deadline\"]")"
eq "...saying so in its own state rather than borrowing another" \
   "scope-not-declared" "$(top "$work/anchored.out.json" "$DORA[0][\"state\"]")"

# --- HALF 1: THE CONDITIONAL APPEARS WHEN THE ANCHOR EXISTS ----------------------------
det "$work/anchored.out.json" > "$work/anchored.txt"
if grep -qF "2026-07-07T09:00:00+00:00" "$work/anchored.txt"; then
  ok "with an anchor, the withheld escalation carries a date after all"
else
  bad "with an anchor, the withheld escalation carries a date after all" "$(cat "$work/anchored.txt")"; fi
# THE assertion — not "a date", the SAME date the declared path computes on the same facts. A
# conditional disagreeing with the clock it is conditional on would be worse than silence.
eq "...and it is the SAME datetime the declared path computes, to the second" \
   "2026-07-07T09:00:00+00:00" "$(top "$work/declared.out.json" "$DORA[0][\"deadline\"]")"
if grep -qF 'If `dora` applies' "$work/anchored.txt"; then
  ok "...stated as a CONDITIONAL, naming the regime it is conditional on"
else
  bad "...stated as a CONDITIONAL, naming the regime it is conditional on" "$(cat "$work/anchored.txt")"; fi
if grep -qF "not a finding that it applies" "$work/anchored.txt"; then
  ok "...and saying in the same breath that it is not a finding that it applies"
else
  bad "...and saying in the same breath that it is not a finding that it applies" "$(cat "$work/anchored.txt")"; fi

# --- HALF 2: NO DATE WHEN THE ANCHOR DOES NOT EXIST ------------------------------------
det "$work/bare.out.json" > "$work/bare.txt"
# The negative, written so it CANNOT pass on an empty-but-present date. It counts the
# conditional CLAUSE, not the date: `If \`dora\` applies` must be wholly absent, so a mutation
# emitting "…closes at ." fails here rather than sliding through a "a date is present" check.
eq "with NO anchor, the conditional clause is wholly absent — not emitted empty" \
   "0" "$(top "$work/bare.out.json" 'sum(1 for e in a["escalations"] if "If `dora` applies" in e["evidence"]["detail"])')"
# ...and nothing that LOOKS like a datetime is emitted either. Belt and braces, because the
# clause could be reworded while still shipping a bare date.
eq "...and no datetime-shaped string is emitted anywhere in the escalation" \
   "0" "$(top "$work/bare.out.json" 'sum(1 for e in a["escalations"] if __import__("re").search(r"\d{4}-\d{2}-\d{2}T\d{2}:", e["evidence"]["detail"]))')"
# Path B earns its place by being USEFUL, not merely silent: it names the anchor to supply.
if grep -qF "awareAt" "$work/bare.txt" && grep -qF "classifiedAt" "$work/bare.txt"; then
  ok "...and the missing anchors are NAMED, so the reader knows what to supply"
else
  bad "...and the missing anchors are NAMED, so the reader knows what to supply" "$(cat "$work/bare.txt")"; fi
if grep -qF "whether or not DORA applies" "$work/bare.txt"; then
  ok "...stated as true regardless of scope, so it needs no scope hypothesis"
else
  bad "...stated as true regardless of scope, so it needs no scope hypothesis" "$(cat "$work/bare.txt")"; fi

# --- the constraints carried across from sec-1.05, unchanged ---------------------------
# `ESCALATION_KEYS` is not defined in this skill; the contract lives in the consumers, and
# `attention_surface.py` projects an escalation down to exactly six keys. A seventh would NOT
# fail loudly — it would be silently dropped before reaching any surface, and the field would
# ship having never once appeared. Pinned at the producer, which is where adding it happens.
eq "the escalation still carries exactly the six contract keys, so nothing is silently dropped" \
   "evidence,severity,since,subjectKind,subjectRef,trigger" \
   "$(top "$work/anchored.out.json" '",".join(sorted([e for e in a["escalations"] if e["trigger"] == "scope-undeclared"][0]))')"
eq "severity is unchanged by any of this" "high" \
   "$(top "$work/anchored.out.json" '[e for e in a["escalations"] if e["trigger"] == "scope-undeclared"][0]["severity"]')"
# A DECLARED profile has a real clock; a conditional there would put two dates on one incident.
eq "a declared profile raises no scope-undeclared escalation, so it gets no second date" \
   "0" "$(top "$work/declared.out.json" 'len([e for e in a["escalations"] if e["trigger"] == "scope-undeclared"])')"

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'dora-conditional: ran %d checks, expected %d — a case stopped executing\n' \
         "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'dora-conditional: %d of %d checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'dora-conditional: all %d checks passed\n' "$checks"
