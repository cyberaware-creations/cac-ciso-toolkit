#!/usr/bin/env bash
# The guard on the Layer A / Layer B boundary — the safety property of the assessment layer.
#
# A model reading a trust page and ticking requirements produces a register full of green
# derived from marketing copy. That is worse than an empty register, because it LOOKS FINISHED
# and nobody re-checks a page of ticks.
#
# The self-test proves the two shipped acts behave. This suite proves something the self-test
# structurally cannot: that no THIRD path exists. The realistic failure is not `assess` going
# wrong — it is a convenience helper added next year that writes `met: True` without going
# through it, or an inlined `("T1", "T2")` that drifts from the constant.
#
# Behavioural checks run against a real store; static checks read the AST. Anti-vacuity: the
# static scans report how many functions they walked, and the fixture is proved to have
# produced a proposal before anything is asserted about one.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=10
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

V="$skill/scripts/vendor_register.py"
S="$work/b.vnd"
echo "proposal-boundary: $($PY -V 2>&1)"

"$PY" "$V" init "$S" --org "Boundary Ltd" >/dev/null 2>&1
"$PY" "$V" add-vendor "$S" --name "Contoso Cloud" >/dev/null 2>&1
"$PY" "$V" add-arrangement "$S" --vendor V-001 --services hosting --owner CTO >/dev/null 2>&1
"$PY" "$V" ingest "$S" --arrangement VA-001 --kind soc2-type2 --tier T1 \
   --source "auditor PDF" --scope "the hosting platform" \
   --period-start 2025-01-01 --period-end 2025-12-31 >/dev/null 2>&1
"$PY" "$V" ingest "$S" --arrangement VA-001 --kind trust-page --tier T3 \
   --source "their trust centre" >/dev/null 2>&1

q() { "$PY" -c 'import json,sys
a = json.load(open(sys.argv[1]))
print(eval(sys.argv[2]))' "$work/a.json" "$1"; }

# --- 1-2. a T3 can never propose, and a proposal needs a receipt --------------
if "$PY" "$V" propose "$S" --arrangement VA-001 --requirement "encryption at rest" \
     --evidence EV-002 --citation "their trust page says AES-256" >/dev/null 2>"$work/t3.err"; then
  bad "a T3 evidence item cannot be proposed against" "it was accepted"
else
  if grep -qF "never satisfy a requirement" "$work/t3.err"; then
    ok "a T3 evidence item cannot be proposed against, and the refusal says why"
  else
    bad "the T3 refusal names the tier rule" "$(head -1 "$work/t3.err")"
  fi
fi
if "$PY" "$V" propose "$S" --arrangement VA-001 --requirement "encryption at rest" \
     --evidence EV-001 --citation "" >/dev/null 2>&1; then
  bad "a proposal with no citation is refused" "it was accepted"
else
  ok "a proposal with no citation is refused"
fi

# --- 3-5. Layer A writes, and closes nothing ----------------------------------
"$PY" "$V" propose "$S" --arrangement VA-001 --requirement "encryption at rest" \
   --evidence EV-001 --citation "SOC 2 section IV, control CC6.7" --by "reading layer" \
   >/dev/null 2>&1
"$PY" "$V" analyze "$S" --out "$work/a.json" >/dev/null 2>&1
made=$("$PY" -c 'import json,sys
s = json.load(open(sys.argv[1]))
print(len(s["arrangements"][0].get("proposals") or []))' "$S")
if [ "${made:-0}" -ge 1 ]; then
  ok "the fixture produced a proposal ($made) to assert against"
else
  bad "the fixture produced a proposal" "none — every check below would pass over nothing"
fi
met=$("$PY" -c 'import json,sys
s = json.load(open(sys.argv[1]))
print(len([r for r in (s["arrangements"][0].get("requirements") or []) if r.get("met")]))' "$S")
if [ "${met:-1}" -eq 0 ]; then
  ok "...and NOTHING is satisfied by it — the reading layer cannot close anything"
else
  bad "a proposal satisfies nothing on its own" "$met requirement(s) are already met"
fi
if "$PY" "$V" assess "$S" --arrangement VA-001 --confirm PR-001 >/dev/null 2>&1; then
  bad "an unattributed assessment is refused" "it was accepted"
else
  ok "an unattributed assessment is refused — only a named person confirms"
fi

# --- 6-7. and a named person closes it, with the trail --------------------------
"$PY" "$V" assess "$S" --arrangement VA-001 --by "D. Galleyne" --on 2026-06-30 \
   --confirm PR-001 >/dev/null 2>&1
if "$PY" -c '
import json, sys
s = json.load(open(sys.argv[1]))
met = [r for r in (s["arrangements"][0].get("requirements") or []) if r.get("met")]
need = ("evidenceRef", "citation", "checkedBy", "checkedOn")
sys.exit(0 if len(met) == 1 and all(str(met[0].get(k) or "") for k in need) else 1)' "$S"; then
  ok "a confirmed proposal satisfies its requirement, naming evidence, citation, who and when"
else
  bad "a satisfied requirement carries its full trail" \
      "a bare met:true is what this register exists not to produce"
fi
if "$PY" -c '
import json, sys
s = json.load(open(sys.argv[1]))
a = s["arrangements"][0].get("assessments") or []
sys.exit(0 if a and a[-1].get("by") and a[-1].get("on") else 1)' "$S"; then
  ok "...and the assessment clock has an act that resets it"
else
  bad "assess writes the assessments list" "the clock Plan 1 built still has no act"
fi

# --- the OTHER act that can close a requirement -------------------------------
#
# `review-requirements` records a provision checked directly against the signed agreement. It
# is a legitimate Layer B act and is exempt from the static scan below for that reason — so it
# has to be held to the same bar behaviourally, or the exemption is just a quieter hole. It
# shipped in v0.39.0 without requiring a name at all, which is what that scan found.
if "$PY" "$V" review-requirements "$S" --arrangement VA-001 \
     --requirement "breach notification within 24h" \
     --evidence "MSA schedule 3, clause 11.2" >/dev/null 2>&1; then
  bad "review-requirements refuses without a named person" \
      "it marked a requirement met with nobody's name against it"
else
  ok "review-requirements refuses without a named person, like assess"
fi

# --- static: no third path, and no second copy of the rule --------------------
for mode in met tiers; do
  out=$("$PY" "$here/_boundaryscan.py" "$V" "--$mode" 2>"$work/$mode.err")
  rc=$?
  scanned=$(printf '%s' "$out" | sed -n 's/^scanned \([0-9]*\).*/\1/p')
  if [ "$rc" -eq 0 ] && [ "${scanned:-0}" -ge 10 ]; then
    case "$mode" in
      met)   ok "no code path outside assess() marks a requirement met (${scanned} functions read)" ;;
      tiers) ok "no inlined tier list — SATISFYING_TIERS is the only definition (${scanned} read)" ;;
    esac
  else
    bad "static scan --$mode" "$(cat "$work/$mode.err")"
  fi
done

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'proposal-boundary: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'proposal-boundary: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'proposal-boundary: all %s checks passed\n' "$checks"
