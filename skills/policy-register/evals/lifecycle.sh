#!/usr/bin/env bash
# What the policy register DOES, through the real CLI. Not a guard — see
# tools/guard-registry.json, where this is classified `not-a-guard` on purpose: these are
# assertions about behaviour, not properties whose violation must be impossible.
#
# The engine self-test covers the same ground in-process and much faster. This exists because
# in-process is not where the product is used: argparse, the store file on disk, and the
# refusal path a shell actually sees are all outside it, and every one of them has broken in
# this repository before while a self-test stayed green.
#
# Four things it pins:
#
#   R-3  `approve` refuses without a named approver AND a date, and the refused command
#        leaves the file BYTE-IDENTICAL. A refusal that half-wrote is worse than no refusal.
#        The converse too: a file already carrying the bad state still loads and analyses.
#
#   R-5  a requirement with no policy reads NOT DECLARED, and the words on the page say that
#        this is not a finding that no policy exists.
#
#   R-6  an overdue review flags and never blocks — the record stays in every view.
#
#   BL-169 D-1/D-2/D-4  the skill runs from a standing start with no other skill's store, an
#        empty register is a legitimate state rather than an error, and stopping half way
#        through leaves a file that loads.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
. "$here/../../../tools/eval-probe.sh"   # `probe` — a crashed check is not a clean one (BL-121)
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=16
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

A="$skill/scripts/policy_register.py"
S="$work/s.pol"
echo "lifecycle: $($PY -V 2>&1)"

sha() { "$PY" -c '
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())
' "$1"; }

# --- D-1/D-2/D-4: entry anywhere, and an empty register is normal ---------------------
if "$PY" "$A" init "$S" --org "Standing Start Ltd" >/dev/null 2>&1; then
  ok "a register is created with no other skill's store present"
else
  bad "a register is created from a standing start" "init failed"
fi

out=$("$PY" "$A" analyze "$S" --today 2026-08-09 2>&1)
rc=$?
if [ "$rc" -eq 0 ] && printf '%s' "$out" | grep -q "22 not-declared"; then
  ok "an empty register analyses cleanly and reports 22 not-declared"
else
  bad "an empty register analyses cleanly" "exit $rc: $(printf '%s' "$out" | head -2)"
fi
if printf '%s' "$out" | grep -q "no escalations"; then
  ok "and raises nothing — an empty programme is not nagged at"
else
  bad "an empty register raises no escalation" \
      "$(printf '%s' "$out" | grep -i escal | head -2)"
fi

"$PY" "$A" requirements "$S" --today 2026-08-09 --out "$work/empty.txt" >/dev/null 2>&1
if [ -s "$work/empty.txt" ] && grep -q "not-declared" "$work/empty.txt"; then
  ok "the requirement view renders on an empty register rather than erroring"
else
  bad "the requirement view renders on an empty register" "empty or missing output"
fi

# --- R-3: the approve refusal, and that it writes nothing ------------------------------
"$PY" "$A" add "$S" --title "Access Control Policy" --owner "IT Director" \
   --map AC-1 >/dev/null 2>&1
before=$(sha "$S")

err=$("$PY" "$A" approve "$S" --id P-001 --on 2026-01-05 2>&1 >/dev/null)
rc=$?
if [ "$rc" -ne 0 ] && printf '%s' "$err" | grep -q -- "--by"; then
  ok "approve without an approver is refused, and the refusal names --by"
else
  bad "approve without an approver is refused" "exit $rc: $(printf '%s' "$err" | head -2)"
fi

err=$("$PY" "$A" approve "$S" --id P-001 --by "The Board" 2>&1 >/dev/null)
rc=$?
if [ "$rc" -ne 0 ] && printf '%s' "$err" | grep -q -- "--on"; then
  ok "approve without a date is refused, and the refusal names --on"
else
  bad "approve without a date is refused" "exit $rc: $(printf '%s' "$err" | head -2)"
fi

err=$("$PY" "$A" approve "$S" --id P-001 2>&1 >/dev/null)
if printf '%s' "$err" | grep -q -- "--by" && printf '%s' "$err" | grep -q -- "--on"; then
  ok "and a command missing both names both, in one refusal"
else
  bad "a command missing both fields names both" "$(printf '%s' "$err" | head -3)"
fi
if printf '%s' "$err" | grep -qi "senior management"; then
  ok "the refusal says WHY, citing what GV.PO-01 asks for"
else
  bad "the refusal explains itself" "no reason given: $(printf '%s' "$err" | head -3)"
fi

if [ "$(sha "$S")" = "$before" ]; then
  ok "three refused approvals left the store byte-identical"
else
  bad "a refused command leaves the store byte-identical" "the file changed"
fi

# --- R-3 is write-time only: a bad file still loads --------------------------------------
"$PY" -c '
import json, sys
store = json.load(open(sys.argv[1], encoding="utf-8"))
store["policies"][0]["state"] = "approved"     # approved, with approval still null
json.dump(store, open(sys.argv[2], "w", encoding="utf-8"), indent=2)
' "$S" "$work/legacy.pol"
"$PY" "$A" analyze "$work/legacy.pol" --today 2026-08-09 --out "$work/legacy.json" \
   >/dev/null 2>&1
rc=$?
res=$(probe "$work/legacy.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
rec = data["policies"][0]
problems = []
if rec.get("state") != "approved":
    problems.append("the state was rewritten on load to %r" % rec.get("state"))
if rec.get("approval") is not None:
    problems.append("an approval block was invented for a record that has none")
if "no-review-date" not in [e["kind"] for e in data["escalations"]]:
    problems.append("the state is loaded but never surfaced: %s"
                    % [e["kind"] for e in data["escalations"]])
print("; ".join(problems))
PY
)
if [ "$rc" -eq 0 ] && [ -z "$res" ]; then
  ok "a file already carrying approved-with-no-approver loads, and the state is reported"
else
  bad "a file carrying the refused state still loads and is reported" \
      "exit $rc; $res — refusing to READ it would strand the person who has to fix it"
fi

# --- R-5: not declared, in those words ----------------------------------------------------
"$PY" "$A" approve "$S" --id P-001 --by "The Board" --on 2026-01-05 >/dev/null 2>&1
"$PY" "$A" analyze "$S" --today 2026-08-09 --out "$work/a.json" >/dev/null 2>&1
res=$(probe "$work/a.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
rows = {r["id"]: r for r in data["requirements"]}
problems = []
row = rows.get("PE-1", {})
if row.get("state") != "not-declared":
    problems.append("PE-1 reads %r" % row.get("state"))
if "not a finding that no policy exists" not in (row.get("means") or ""):
    problems.append("the not-declared meaning no longer disclaims 'no policy exists'")
if "omnibus" not in (row.get("means") or ""):
    problems.append("the meaning no longer explains why one policy may cover several families")
print("; ".join(problems))
PY
)
if [ -z "$res" ]; then
  ok "an unmapped requirement reads not-declared and says that is not a finding"
else
  bad "an unmapped requirement reads not-declared, in those words" "$res"
fi

# An id outside the shipped spine is SHOWN, not dropped.
"$PY" "$A" map "$S" --id P-001 --requirement "PCI DSS 12.5.1" >/dev/null 2>&1
"$PY" "$A" analyze "$S" --today 2026-08-09 --out "$work/a.json" >/dev/null 2>&1
res=$(probe "$work/a.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
outside = [r for r in data["requirements"] if not r["inCatalogue"]]
problems = []
if [r["id"] for r in outside] != ["PCI DSS 12.5.1"]:
    problems.append("outside-catalogue rows are %s" % [r["id"] for r in outside])
if data["requirementCount"] != 22:
    problems.append("the catalogue count moved to %d" % data["requirementCount"])
print("; ".join(problems))
PY
)
if [ -z "$res" ]; then
  ok "a requirement id outside the shipped spine gets its own row and is not silently dropped"
else
  bad "an id outside the spine is shown rather than dropped" "$res"
fi

# --- R-6: an overdue review flags and never blocks ------------------------------------------
"$PY" "$A" analyze "$S" --today 2028-06-01 --out "$work/late.json" >/dev/null 2>&1
res=$(probe "$work/late.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
kinds = [e["kind"] for e in data["escalations"]]
rows = {r["id"]: r for r in data["requirements"]}
problems = []
if "review-overdue" not in kinds:
    problems.append("no review-overdue escalation two years past the review date: %s" % kinds)
if len(data["policies"]) != 1:
    problems.append("the overdue policy was dropped from the analysis")
if rows["AC-1"]["policyCount"] != 1:
    problems.append("the overdue policy no longer appears against AC-1")
if rows["AC-1"]["state"] != "approved-policy":
    problems.append("being overdue changed the requirement state to %r" % rows["AC-1"]["state"])
print("; ".join(problems))
PY
)
if [ -z "$res" ]; then
  ok "an overdue review flags, and the policy stays in every view"
else
  bad "an overdue review flags and never blocks" "$res"
fi

if "$PY" "$A" review "$S" --id P-001 --on 2028-06-01 --next 2029-06-01 \
     --why "Reviewed late; no change to the control set." >/dev/null 2>&1; then
  ok "and being overdue does not stop the review being recorded"
else
  bad "an overdue policy can still be reviewed" "the command failed"
fi
out=$("$PY" "$A" analyze "$S" --today 2028-06-02 2>&1)
if printf '%s' "$out" | grep -q "no escalations"; then
  ok "recording the review clears the flag, because the flag was derived and never stored"
else
  bad "the overdue flag clears once the condition clears" \
      "$(printf '%s' "$out" | grep -i 'escal\|overdue' | head -2)"
fi

# --- D-2: stopping half way leaves a file that loads -------------------------------------
"$PY" "$A" add "$S" --title "Half-finished Standard" --owner "Nobody yet" >/dev/null 2>&1
if "$PY" "$A" analyze "$S" --today 2028-06-02 >/dev/null 2>&1; then
  ok "a draft with no mappings and no approval leaves a register that still analyses"
else
  bad "a half-entered record leaves a loadable register" "analyze failed after a bare add"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'lifecycle: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'lifecycle: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'lifecycle: all %s checks passed\n' "$checks"
