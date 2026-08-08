#!/usr/bin/env bash
# Every question asks for evidence with a date, and subtraction works only for tiers that can.
#
# The shape of the question is the product. "Do you test for prompt injection?" is worthless —
# everybody answers yes, and the answer is unfalsifiable. "What is the most recent dated
# adversarial test of THIS deployment, and what did it find?" has a discoverable answer, a
# date, and degrades honestly when the answer is "none". The difference is the whole reason
# this is not a questionnaire product, and it is enforced here rather than remembered.
#
# The second half is the subtraction rule, checked in the only form that matters: the same
# requirement covered by a T1 shrinks the open set, and covered by a T3 does not. A model card
# is the artifact an AI provider is most likely to hand over, and a register that let one close
# questions would go quiet exactly where it should be loudest.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=12
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

A="$skill/scripts/ai_register.py"
S="$work/q.air"
echo "questions: $($PY -V 2>&1)"

# --- 1-5. the shape of every shipped question ---------------------------------
out=$("$PY" "$here/_questionscan.py" "$A" 2>"$work/scan.err")
rc=$?
if [ "$rc" -eq 0 ]; then
  ok "every shipped question asks for evidence with a date, not an attestation ($out)"
elif [ "$rc" -eq 2 ]; then
  bad "there are questions to inspect" "$(cat "$work/scan.err")"
else
  bad "no question is an attestation" "$(cat "$work/scan.err")"
fi
# The scanner's own teeth, on a battery built to be wrong. A guard never seen to fail is a
# guard nobody has tested.
if "$PY" "$here/_questionscan.py" "$A" --mutant >/dev/null 2>&1; then
  bad "the scanner fails a planted attestation question" \
      "it passed 'Do you test for prompt injection?'"
else
  ok "and the scanner fails a planted 'Do you ...?' question"
fi
if "$PY" -c '
import importlib.util, sys
spec = importlib.util.spec_from_file_location("ar", sys.argv[1])
ar = importlib.util.module_from_spec(spec); spec.loader.exec_module(ar)
keys = [ar.question_key(b, q) for b, q in ar.all_questions()]
if len(keys) != len(set(keys)):
    print("duplicate question ids", file=sys.stderr); sys.exit(1)
if len(keys) < 8:
    print("only %d questions ship" % len(keys), file=sys.stderr); sys.exit(1)
' "$A" 2>"$work/keys.err"; then
  ok "question ids are unique, and there are enough of them to be a battery"
else
  bad "question ids are unique" "$(cat "$work/keys.err")"
fi
if "$PY" -c '
import importlib.util, sys
spec = importlib.util.spec_from_file_location("ar", sys.argv[1])
ar = importlib.util.module_from_spec(spec); spec.loader.exec_module(ar)
missing = [b["id"] for b in ar.BATTERIES if not b.get("gvsc")]
if missing:
    print("no CSF reference on: %s" % ", ".join(missing), file=sys.stderr); sys.exit(1)
' "$A" 2>"$work/csf.err"; then
  ok "every battery names the CSF Subcategories it bears on"
else
  bad "every battery names its CSF Subcategories" "$(cat "$work/csf.err")"
fi
if "$PY" -c '
import importlib.util, sys
spec = importlib.util.spec_from_file_location("ar", sys.argv[1])
ar = importlib.util.module_from_spec(spec); spec.loader.exec_module(ar)
bad = [b["id"] for b in ar.BATTERIES
       if any(c not in ar.NISTAML for c in (b.get("nistaml") or []))]
if bad:
    print("unknown NISTAML class on: %s" % ", ".join(bad), file=sys.stderr); sys.exit(1)
' "$A" 2>"$work/aml.err"; then
  ok "and every NISTAML class a battery cites is one the engine actually derives"
else
  bad "battery NISTAML references resolve" "$(cat "$work/aml.err")"
fi

# --- 6-12. the subtraction rule, end to end -----------------------------------
"$PY" "$A" init "$S" --org "Question Ltd" >/dev/null 2>&1
"$PY" "$A" add-system "$S" --name "Contoso Assist" --provider Contoso --version 2026.4 \
   >/dev/null 2>&1
"$PY" "$A" deploy "$S" --system S-001 --purpose "drafting" --owner CMO --autonomy informs \
   --by CISO >/dev/null 2>&1

open_count() {
  "$PY" "$A" ask "$S" --deployment D-001 --today "$1" --json \
    | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["open"])'
}

base=$(open_count 2026-06-15)
if [ "$base" -gt 0 ]; then
  ok "an unevidenced deployment has $base open questions"
else
  bad "an unevidenced deployment has questions open" "it has none, so subtraction proves nothing"
fi

# A model card. The artifact a provider is most likely to hand over, and it closes nothing.
"$PY" "$A" ingest "$S" --deployment D-001 --kind model-card --tier T3 \
   --source "their published card" >/dev/null 2>&1
"$PY" -c '
import json, sys
store = json.load(open(sys.argv[1], encoding="utf-8"))
rec = store["deployments"][0]
rec["requirements"].append({"requirement": "inventory.provenance", "met": True,
                            "evidenceRef": "EV-001", "checkedOn": "2026-06-01",
                            "checkedBy": "CISO"})
json.dump(store, open(sys.argv[1], "w", encoding="utf-8"), indent=2)' "$S"
with_t3=$(open_count 2026-06-15)
if [ "$with_t3" = "$base" ]; then
  ok "a requirement covered by a T3 model card subtracts NOTHING — the product claim"
else
  bad "a T3 subtracts nothing" "open went from $base to $with_t3"
fi

# The same requirement, covered by an audited artifact.
"$PY" "$A" ingest "$S" --deployment D-001 --kind third-party-evaluation --tier T1 \
   --source "an independent lab" --scope "the deployment as configured" \
   --period-start 2026-01-01 --period-end 2026-08-31 >/dev/null 2>&1
"$PY" -c '
import json, sys
store = json.load(open(sys.argv[1], encoding="utf-8"))
rec = store["deployments"][0]
rec["requirements"] = [{"requirement": "inventory.provenance", "met": True,
                        "evidenceRef": "EV-002", "checkedOn": "2026-06-01",
                        "checkedBy": "CISO"}]
json.dump(store, open(sys.argv[1], "w", encoding="utf-8"), indent=2)' "$S"
with_t1=$(open_count 2026-06-15)
if [ "$with_t1" -lt "$base" ]; then
  ok "the same requirement covered by a T1 DOES subtract ($base to $with_t1)"
else
  bad "a T1 subtracts a question" "open stayed at $with_t1 — the guard refuses everything"
fi
if [ "$((base - with_t1))" = "1" ]; then
  ok "...by exactly one, the question it answers"
else
  bad "a T1 subtracts exactly the question it answers" "it subtracted $((base - with_t1))"
fi

# Ageing is not gone, and gone is not ageing.
grace=$("$PY" "$A" ask "$S" --deployment D-001 --today 2027-01-01 --json \
  | "$PY" -c 'import json,sys; d=json.load(sys.stdin); print(d["reConfirm"])')
if [ "$grace" -ge 1 ]; then
  ok "past its period, the same question returns marked re-confirm rather than open"
else
  bad "evidence in grace re-asks as re-confirm" "reConfirm was $grace"
fi
expired=$(open_count 2028-01-01)
if [ "$expired" = "$base" ]; then
  ok "and once expired it is fully open again — a lapsed answer covers nothing"
else
  bad "expired evidence reopens the question" "open is $expired, was $base unevidenced"
fi

# The empty result must never be an empty page.
if "$PY" "$A" ask "$S" --deployment D-001 --today 2026-06-15 --json \
   | grep -q '"skipped"'; then
  ok "and the output carries the skipped batteries, so a narrowing is visible rather than silent"
else
  bad "ask reports what was skipped" "no skipped key — a narrowing would be invisible"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'questions: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'questions: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'questions: all %s checks passed\n' "$checks"
