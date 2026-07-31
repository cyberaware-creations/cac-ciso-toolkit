#!/usr/bin/env bash
# The acceptance/exception lifecycle, over a register built by the real CLI.
#
# Anti-vacuity, mirrored from confirmation-age.sh: the store is built by commands rather
# than hand-written, so a schema change breaks this suite instead of sliding past it; every
# banding expectation is worked by hand and written here as a literal; and EXPECTED_CHECKS
# is asserted at the end so a case that stops executing fails loudly.
#
# Two properties this exists to protect:
#   1. A refused command leaves the store byte-identical. The refusal discipline IS the
#      product, and a refusal that half-wrote would be worse than no refusal at all.
#   2. A lapsed clock surfaces an item and never removes it. An overdue acceptance is still
#      an acceptance; the organisation is still carrying that risk.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
repo="$(cd "$skill/../.." && pwd)"
E="$skill/scripts/exceptions_register.py"
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
S="$work/t.exc"

EXPECTED_CHECKS=29
checks=0; fails=0
ok()  { checks=$((checks+1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks+1)); fails=$((fails+1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }
is()  { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "expected '$3', got '$2'"; fi; }
sha() { $PY -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$1"; }

echo "revalidation-lifecycle: $($PY -V 2>&1)"

q() { $PY -c "
import json,sys
d=json.load(open(sys.argv[1]))
r={x['id']:x for x in d['records']}
print($1)" "$work/a.json"; }
refresh() { $PY "$E" analyze "$S" --today "${1:-2026-07-31}" --out "$work/a.json" >/dev/null; }

$PY "$E" init "$S" --client "Eval Corp" --due-window-days 30 --actor eval >/dev/null
$PY "$E" accept-add "$S" --title "Accepted residual" --approver CISO \
  --justification "documented basis" --accepted 2026-01-01 --revalidation 2026-09-30 \
  --expiry 2027-01-01 --risk R-001 --actor eval >/dev/null
$PY "$E" except-add "$S" --title "Deviation with an offset" --deviation-from "CIS-4.1" \
  --compensating "segmentation and flow capture" --approver COO \
  --justification "agent unsupported on the controller OS" --accepted 2026-01-01 \
  --revalidation 2026-08-20 --actor eval >/dev/null
[ -s "$S" ] && ok "the CLI built a register" || bad "the CLI built a register" "no store"
refresh

# --- banding, hand-worked against a 30-day window from 2026-07-31 -------------------
#   A-001 revalidation 2026-09-30 -> 61 days out -> current
#   X-001 revalidation 2026-08-20 -> 20 days out -> due
is "61 days out is current"        "$(q "r['A-001']['band']")" "current"
is "20 days out is due"            "$(q "r['X-001']['band']")" "revalidation-due"
is "days to re-validation is a plain distance" "$(q "r['X-001']['daysToRevalidation']")" "20"
is "the acceptance is an acceptance" "$(q "r['A-001']['kind']")" "acceptance"
is "the exception is an exception"   "$(q "r['X-001']['kind']")" "exception"

refresh 2026-08-31
is "past the re-validation date is overdue" "$(q "r['X-001']['band']")" "revalidation-overdue"
is "and the overdue list names it"          "$(q "d['attention']['overdue']")" "['X-001']"
# The property that matters: an overdue item stays in the inventory.
$PY "$E" export-inventory "$S" --today 2026-08-31 --format json --out "$work/inv.json" >/dev/null
is "an overdue record STAYS in the inventory" \
   "$($PY -c "import json;print(any(r['id']=='X-001' for r in json.load(open('$work/inv.json'))))")" "True"

refresh 2027-06-01
is "past the expiry date is expired"        "$(q "r['A-001']['band']")" "expired"
is "expiry outranks an overdue re-validation" "$(q "d['attention']['expired']")" "['A-001']"

# --- re-validation is an act -------------------------------------------------------
before="$(sha "$S")"
$PY "$E" revalidate "$S" --id X-001 --on 2026-08-31 --next 2027-08-31 --actor eval \
   >/dev/null 2>"$work/e1.txt"; r1=$?
after="$(sha "$S")"
[ "$r1" -ne 0 ] && ok "re-validating without --why is refused" || bad "re-validating without --why is refused" "exit 0"
grep -q "not a timer reset" "$work/e1.txt" \
  && ok "and the refusal says why a rationale is required" \
  || bad "and the refusal says why a rationale is required" "$(tail -1 "$work/e1.txt")"
is "the refusal left the store byte-identical" "$after" "$before"

$PY "$E" revalidate "$S" --id X-001 --on 2026-08-31 --next 2027-08-31 \
   --why "reviewed with the COO; replacement still on the 2027 plan" --actor eval >/dev/null
refresh 2026-08-31
is "a re-validated record returns to current" "$(q "r['X-001']['band']")" "current"
is "and the new date is the one recorded"     "$(q "r['X-001']['revalidationDate']")" "2027-08-31"
is "the rationale is in the change log" \
   "$($PY -c "
import json;d=json.load(open('$S'))
print(any(h['event']=='exception-revalidated' and h.get('why') for h in d['history']))")" "True"

# --- refusals, each leaving the file byte-identical ---------------------------------
before="$(sha "$S")"
$PY "$E" accept-add "$S" --title "No approver" --justification x --accepted 2026-01-01 \
   --revalidation 2027-01-01 --actor eval >/dev/null 2>"$work/e2.txt"; a=$?
$PY "$E" except-add "$S" --title "No compensating control" --deviation-from CIS-1.1 \
   --approver CISO --justification x --accepted 2026-01-01 --revalidation 2027-01-01 \
   --actor eval >/dev/null 2>"$work/e3.txt"; b=$?
$PY "$E" accept-add "$S" --title "Bad date" --approver CISO --justification x \
   --accepted 2026-1-1 --revalidation 2027-01-01 --actor eval >/dev/null 2>"$work/e4.txt"; c=$?
$PY "$E" close "$S" --id A-001 --actor eval >/dev/null 2>"$work/e5.txt"; d=$?
after="$(sha "$S")"
[ "$a" -ne 0 ] && ok "an acceptance with no approver is refused" || bad "an acceptance with no approver is refused" "exit 0"
[ "$b" -ne 0 ] && ok "an exception with no compensating control is refused" || bad "an exception with no compensating control is refused" "exit 0"
grep -q "launders it" "$work/e3.txt" && ok "and the refusal says what it would be instead" || bad "and the refusal says what it would be instead" "$(tail -1 "$work/e3.txt")"
[ "$c" -ne 0 ] && ok "an unpadded date is refused" || bad "an unpadded date is refused" "exit 0"
[ "$d" -ne 0 ] && ok "closing without a reason is refused" || bad "closing without a reason is refused" "exit 0"
is "all four refusals left the store byte-identical" "$after" "$before"

# --- close removes from the inventory, not from the store ---------------------------
$PY "$E" close "$S" --id A-001 --why "risk treated; acceptance withdrawn" --actor eval >/dev/null
$PY "$E" export-inventory "$S" --today 2027-06-01 --format json --out "$work/inv2.json" >/dev/null
is "a closed record leaves the active inventory" \
   "$($PY -c "import json;print(any(r['id']=='A-001' for r in json.load(open('$work/inv2.json'))))")" "False"
is "but stays in the store" \
   "$($PY -c "import json;print(any(a['id']=='A-001' for a in json.load(open('$S'))['acceptances']))")" "True"

# --- the risk-register bridge round-trips, and is idempotent ------------------------
$PY "$repo/skills/risk-register/scripts/score_register.py" export-acceptances \
   "$repo/skills/risk-register/examples/example-register-v2.rr" --out "$work/acc.json" >/dev/null 2>&1
$PY "$E" init "$work/b.exc" --client Bridge --actor eval >/dev/null
n1="$($PY "$E" import-acceptances "$work/b.exc" --from "$work/acc.json" --actor eval | head -1)"
n2="$($PY "$E" import-acceptances "$work/b.exc" --from "$work/acc.json" --actor eval | head -1)"
count="$($PY -c "import json;print(len(json.load(open('$work/b.exc'))['acceptances']))")"
case "$n1" in added\ 3*) ok "the bridge imports the register's accepted risks";; *) bad "the bridge imports the register's accepted risks" "$n1";; esac
case "$n2" in added\ 0*) ok "re-running the import adds nothing";; *) bad "re-running the import adds nothing" "$n2";; esac
is "so the inventory is not doubled" "$count" "3"
is "and every imported record carries its source risk" \
   "$($PY -c "
import json;d=json.load(open('$work/b.exc'))
print(all(a.get('sourceRiskRef') for a in d['acceptances']))")" "True"

echo
[ "$checks" -ne "$EXPECTED_CHECKS" ] && { printf 'revalidation-lifecycle: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; }
[ "$fails" -ne 0 ] && { printf 'revalidation-lifecycle: %s of %s FAILED\n' "$fails" "$checks"; exit 1; }
printf 'revalidation-lifecycle: all %s checks passed\n' "$checks"
