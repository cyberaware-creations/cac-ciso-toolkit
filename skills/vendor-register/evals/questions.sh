#!/usr/bin/env bash
# The subtraction, from the CLI — and the claim that makes this skill worth using.
#
# THE check is the T1/T3 pair. The same three requirements covered by an audited report shrink
# the question set; covered by a trust page they do not. Checking only the first would pass a
# tool that subtracted on any evidence at all, which is precisely the failure the tier model
# exists to prevent — and that failure looks like success, because the set gets smaller.
#
# Also asserted here rather than only in the engine: every shipped question asks for evidence
# with a date rather than an attestation, and an empty result prints a sentence.
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

V="$skill/scripts/vendor_register.py"
echo "questions: $($PY -V 2>&1)"

# Two identical registers, differing only in the TIER of the artifact that covers three
# questions. Everything else — criticality, batteries, dates — is the same, so any difference
# in the counts is attributable to the tier and to nothing else.
build() {  # build <store> <tier>
  "$PY" "$V" init "$1" --org "Q Ltd" >/dev/null 2>&1
  "$PY" "$V" add-vendor "$1" --name "Contoso Cloud" >/dev/null 2>&1
  "$PY" "$V" add-arrangement "$1" --vendor V-001 --services hosting --owner CTO \
     --supports "CRM (Salesforce)" >/dev/null 2>&1
  "$PY" "$V" classify "$1" --arrangement VA-001 --context "$work/ctx.json" \
     --confirm high --by "R. Calder" >/dev/null 2>&1
  if [ "$2" = "T1" ]; then
    "$PY" "$V" ingest "$1" --arrangement VA-001 --kind soc2-type2 --tier T1 \
       --source "auditor PDF" --scope "the hosting platform" \
       --period-start 2026-01-01 --period-end 2026-12-31 >/dev/null 2>&1
  else
    "$PY" "$V" ingest "$1" --arrangement VA-001 --kind trust-page --tier T3 \
       --source "their trust centre" >/dev/null 2>&1
  fi
}

"$PY" "$skill/../business-context/scripts/business_context.py" export \
   "$skill/../business-context/examples/example-org.biz" --out "$work/ctx.json" >/dev/null 2>&1

open_count() {  # open_count <store>
  "$PY" "$V" ask "$1" --arrangement VA-001 --context "$work/ctx.json" --today 2026-06-01 \
     --format json 2>/dev/null | "$PY" -c 'import json,sys;print(json.load(sys.stdin)["open"])'
}

"$PY" "$V" init "$work/base.vnd" --org "Q Ltd" >/dev/null 2>&1
"$PY" "$V" add-vendor "$work/base.vnd" --name "Contoso Cloud" >/dev/null 2>&1
"$PY" "$V" add-arrangement "$work/base.vnd" --vendor V-001 --services hosting --owner CTO \
   --supports "CRM (Salesforce)" >/dev/null 2>&1
"$PY" "$V" classify "$work/base.vnd" --arrangement VA-001 --context "$work/ctx.json" \
   --confirm high --by "R. Calder" >/dev/null 2>&1
baseline=$(open_count "$work/base.vnd")
if [ "${baseline:-0}" -ge 4 ]; then
  ok "a register with no evidence asks its full applicable set ($baseline questions)"
else
  bad "the baseline set is non-trivial" \
      "only ${baseline:-0} questions — every comparison below would be meaningless"
fi

THREE="contract-terms.incident-notice assurance.latest-report subprocessors.current-list"

# --- T1: proposed, assessed, subtracted ---------------------------------------
build "$work/t1.vnd" T1
n=1
for key in $THREE; do
  "$PY" "$V" propose "$work/t1.vnd" --arrangement VA-001 --requirement "$key" \
     --evidence EV-001 --citation "SOC 2 section IV, control for $key" >/dev/null 2>&1
  n=$((n + 1))
done
"$PY" "$V" assess "$work/t1.vnd" --arrangement VA-001 --by "R. Calder" \
   --confirm PR-001 --confirm PR-002 --confirm PR-003 >/dev/null 2>&1
t1_open=$(open_count "$work/t1.vnd")
if [ "${t1_open:-0}" -eq $((baseline - 3)) ]; then
  ok "an audited report covering three questions removes exactly three ($baseline -> $t1_open)"
else
  bad "a T1 removes exactly the three it covers" "expected $((baseline - 3)), got ${t1_open:-0}"
fi

# --- T3: cannot even be proposed against, and subtracts nothing ----------------
build "$work/t3.vnd" T3
if "$PY" "$V" propose "$work/t3.vnd" --arrangement VA-001 \
     --requirement contract-terms.incident-notice --evidence EV-001 \
     --citation "their trust page" >/dev/null 2>&1; then
  bad "a trust page cannot be proposed against" "it was accepted"
else
  ok "a trust page cannot be proposed against at all"
fi
t3_open=$(open_count "$work/t3.vnd")
if [ "${t3_open:-0}" -eq "${baseline:-0}" ]; then
  ok "...and the question set is UNCHANGED by it ($t3_open, same as with no evidence at all)"
else
  bad "a T3 subtracts nothing" "expected $baseline, got ${t3_open:-0}"
fi
# THE claim, stated as a comparison rather than as two separate facts.
if [ "${t1_open:-0}" -lt "${t3_open:-99}" ]; then
  ok "reading a real report shrinks the set; reading marketing copy does not ($t1_open < $t3_open)"
else
  bad "an audited report shrinks the set more than a trust page" \
      "T1 left $t1_open open, T3 left $t3_open — the tier model is not doing anything"
fi

# --- every question asks for evidence, not an attestation ---------------------
if "$PY" -c '
import importlib.util, re, sys
spec = importlib.util.spec_from_file_location("vr", sys.argv[1])
vr = importlib.util.module_from_spec(spec); spec.loader.exec_module(vr)
bad = [q["ask"] for b in vr.BATTERIES for q in b["questions"]
       if re.match(r"^(do|are|is|does|have|has|can|will) ", q["ask"], re.I)]
n = sum(len(b["questions"]) for b in vr.BATTERIES)
if n < 5:
    print("only %d shipped questions — this is not the core" % n, file=sys.stderr); sys.exit(2)
print(n)
sys.exit(1 if bad else 0)' "$V" > "$work/n.txt" 2>"$work/att.err"; then
  ok "all $(cat "$work/n.txt") shipped questions ask for evidence, never an attestation"
else
  bad "no shipped question is an attestation" "$(cat "$work/att.err")"
fi

# --- the empty case says so, in words -----------------------------------------
for key in $THREE contract-terms.audit-right assurance.open-findings \
           exit.last-exercised exit.deletion-evidence; do
  "$PY" "$V" propose "$work/t1.vnd" --arrangement VA-001 --requirement "$key" \
     --evidence EV-001 --citation "SOC 2 coverage for $key" >/dev/null 2>&1
done
ids=$("$PY" -c 'import json,sys
s = json.load(open(sys.argv[1]))
print(" ".join("--confirm %s" % p["id"] for p in s["arrangements"][0]["proposals"]
               if p["status"] == "proposed"))' "$work/t1.vnd")
# shellcheck disable=SC2086
"$PY" "$V" assess "$work/t1.vnd" --arrangement VA-001 --by "R. Calder" $ids >/dev/null 2>&1
out=$("$PY" "$V" ask "$work/t1.vnd" --arrangement VA-001 --context "$work/ctx.json" \
        --today 2026-06-01 2>/dev/null)
left=$(open_count "$work/t1.vnd")
if [ "${left:-1}" -eq 0 ]; then
  ok "with every applicable question covered, none is left open"
else
  bad "the fixture can reach zero open questions" \
      "${left} still open — the empty-case check below would prove nothing"
fi
if printf '%s' "$out" | grep -qF "Nothing is open for this arrangement"; then
  ok "...and the result SAYS so, rather than printing an empty page"
else
  bad "an empty result prints a sentence" \
      "got: $(printf '%s' "$out" | tail -2 | tr '\n' ' ')"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'questions: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'questions: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'questions: all %s checks passed\n' "$checks"
