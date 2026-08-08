#!/usr/bin/env bash
# An attack class has no closed state — proved, not asserted.
#
# This is the rule in this skill most likely to be relaxed later, and the reason is that its
# absence looks like a gap rather than a decision. Somebody will open the register, see a class
# with four controls recorded against it, and reach for the obvious next feature: a way to say
# it is handled. It is a one-line change, nothing in the codebase would object, and the result
# would be a register asserting exactly what NIST's adversarial ML work declines to — that a
# defence holds. Published defences have repeatedly been broken by adaptive attacks; the
# mitigations are empirical rather than guaranteed; the problem is open.
#
# So both halves run, because either alone is escapable:
#
#   BEHAVIOURAL — nothing inside a real store's exposure block, at any depth, in a key or a
#   value, describes a class as mitigated, resolved, closed, accepted, remediated or handled.
#
#   STATIC — no shipped .py assigns such a field, writes one through `setdefault`, or defines
#   a function named for closing a class that does not refuse. Catches the field computed and
#   rendered but never persisted, which the behavioural half cannot see.
#
# Anti-vacuity: EXPECTED_CHECKS is asserted; the probe store is proved to carry classes AND
# recorded controls before anything is checked against it (a class with no controls is not the
# situation this guard is about); the static scan reports how many files it read.
#
# Mutation-tested. `exposure["mitigated"] = True` fails the static half; writing the same key
# into the store fails the behavioural half. A guard never seen to fail is not known to work.
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

A="$skill/scripts/ai_register.py"
S="$work/s.air"
echo "no-closed-state: $($PY -V 2>&1)"

# A register with real content. An empty one has no class to be wrong about and would pass
# every check below while proving nothing — which is why the probe asserts both counts.
"$PY" "$A" init "$S" --org "Probe Ltd" >/dev/null 2>&1
"$PY" "$A" add-system "$S" --name "Contoso Assist" --provider "Contoso" --version "2026.4" \
   --retrieval-augmented >/dev/null 2>&1
"$PY" "$A" deploy "$S" --system S-001 --purpose "screening job applicants" \
   --owner "HR Director" --autonomy decides --data-class "applicant personal data" \
   --consequential >/dev/null 2>&1
for n in 1 2 3; do
  "$PY" "$A" record-control "$S" --deployment D-001 --class NISTAML.02 \
     --control "input filtering pass $n" --evidence "config export $n, dated" \
     --on 2026-06-0$n --by "Head of Security" >/dev/null 2>&1
done

# --- behavioural --------------------------------------------------------------
out=$("$PY" "$here/_closedstate.py" --store "$S" 2>"$work/b.err")
rc=$?
if [ "$rc" -eq 0 ]; then
  ok "nothing in the store's exposure describes a class as handled ($out)"
elif [ "$rc" -eq 2 ]; then
  bad "the probe store carries classes and controls to inspect" "$(cat "$work/b.err")"
else
  bad "no key or value describes a class as handled" "$(cat "$work/b.err")"
fi

# The class is still exposed after three controls. This is the property in one assertion:
# recording a control is not a step towards closing anything.
if "$PY" -c '
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("ar", sys.argv[1])
ar = importlib.util.module_from_spec(spec); spec.loader.exec_module(ar)
store = json.load(open(sys.argv[2], encoding="utf-8"))
entry = store["deployments"][0]["exposure"]["NISTAML.02"]
assert len(entry["controls"]) == 3, "expected three controls, got %d" % len(entry["controls"])
state = ar.exposure_state(entry)
if state not in ar.EXPOSURE_STATES:
    print("state %r is not one of the declared states" % state, file=sys.stderr); sys.exit(1)
if len(ar.EXPOSURE_STATES) != 2:
    print("there are now %d exposure states" % len(ar.EXPOSURE_STATES), file=sys.stderr)
    sys.exit(1)
' "$A" "$S" 2>"$work/state.err"; then
  ok "a class with three controls still reads as exposed, in one of exactly two states"
else
  bad "a class with three controls is still exposed" "$(cat "$work/state.err")"
fi

# The refusal has somewhere to go. A refusal with no destination just gets worked around.
if "$PY" -c '
import importlib.util, sys
spec = importlib.util.spec_from_file_location("ar", sys.argv[1])
ar = importlib.util.module_from_spec(spec); spec.loader.exec_module(ar)
try:
    ar.accept_exposure()
except ar.Refusal as exc:
    sys.exit(0 if "exceptions-register" in str(exc) else 1)
sys.exit(1)
' "$A" 2>/dev/null; then
  ok "and accepting an exposure is refused, naming exceptions-register as where it belongs"
else
  bad "the acceptance refusal names exceptions-register" \
      "it either did not refuse, or refused without saying where the act belongs"
fi

# --- static -------------------------------------------------------------------
scanned=$("$PY" "$here/_closedstate.py" --static "$skill" 2>"$work/s.err")
rc=$?
if [ "$rc" -eq 0 ]; then
  ok "no shipped .py assigns a closed-state field on an exposure class"
else
  bad "no shipped .py assigns a closed-state field" "$(cat "$work/s.err")"
fi
count=${scanned#scanned }
if [ "${count:-0}" -ge 1 ] 2>/dev/null; then
  ok "and the static scan actually read $count shipped file(s), not zero"
else
  bad "the static scan read at least one file" "it read none, so it proved nothing"
fi

# --- the guard's own teeth ----------------------------------------------------
#
# Both halves are run against a deliberately broken copy. A guard that has never been seen to
# fail is a guard nobody has tested, and this is the one rule where that matters most.
#
# TWO mutants, because the static half has two distinct ways of catching this and one of them
# masked a real bug in the other. The first draft planted a `def mark_mitigated()` that ALSO
# assigned the field; it went red on the function name, and the assignment scan — which read
# the subscript key wrongly on every interpreter after 3.8 — passed a genuine
# `exposure[cls]["mitigated"] = True` for as long as that mutant was the only test of it.
mkdir -p "$work/mutant-assign/scripts" "$work/mutant-name/scripts"

# 1. The assignment, under a name that gives nothing away.
cp "$A" "$work/mutant-assign/scripts/ai_register.py"
cat >> "$work/mutant-assign/scripts/ai_register.py" <<'PYEOF'


def _apply(store, did, cls):
    rec = find_deployment(store, did)
    rec["exposure"][cls]["mitigated"] = True
PYEOF
if "$PY" "$here/_closedstate.py" --static "$work/mutant-assign" >/dev/null 2>&1; then
  bad "the static half fails on a planted closed-state ASSIGNMENT" \
      "it passed a file that assigns exposure[cls]['mitigated'] under an innocent name"
else
  ok "the static half fails on a planted closed-state assignment"
fi

# 2. The command named for closing a class, which must refuse or not exist.
cp "$A" "$work/mutant-name/scripts/ai_register.py"
cat >> "$work/mutant-name/scripts/ai_register.py" <<'PYEOF'


def mark_resolved(entry):
    entry["state"] = "done"
    return entry
PYEOF
if "$PY" "$here/_closedstate.py" --static "$work/mutant-name" >/dev/null 2>&1; then
  bad "the static half fails on a function named for closing a class" \
      "it passed a mark_resolved() that does not refuse"
else
  ok "and on a function named for closing a class that does not refuse"
fi

"$PY" -c '
import json, sys
store = json.load(open(sys.argv[1], encoding="utf-8"))
store["deployments"][0]["exposure"]["NISTAML.02"]["mitigated"] = True
json.dump(store, open(sys.argv[2], "w", encoding="utf-8"), indent=2)
' "$S" "$work/mutant.air"
if "$PY" "$here/_closedstate.py" --store "$work/mutant.air" >/dev/null 2>&1; then
  bad "the behavioural half fails on a planted closed-state field" \
      "it passed a store whose class carries mitigated: true"
else
  ok "and the behavioural half fails on one written into the store"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'no-closed-state: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'no-closed-state: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'no-closed-state: all %s checks passed\n' "$checks"
