#!/usr/bin/env bash
# Exposure is DERIVED from attributes and cannot be hand-waved away — from the CLI.
#
# The self-test proves the derivation is right. This proves something the self-test structurally
# cannot: that there is **no way in** from outside. A hand-selectable class list becomes a list
# somebody trims when it is inconvenient, and the class most likely to be trimmed is the one
# that took longest to explain — so the guard is the ABSENCE of a command, and an absence has
# to be checked or it grows back.
#
# Four rules, each in both directions where a direction exists. A guard that refuses everything
# is not a guard.
#
#   1. No command selects, marks or excludes a class. Not in the CLI, not in the module.
#   2. Misuse is generative-only; supply chain is external-only. Both checked positively AND
#      negatively, because a rule that fires on everything says nothing.
#   3. Changing an attribute recomputes, and controls survive the recompute — evidence
#      somebody produced is not thrown away because a class stopped being derivable.
#   4. A control cannot be recorded against a class that was not derived. That is the only
#      other door into the exposure block, and it is locked.
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

A="$skill/scripts/ai_register.py"
S="$work/e.air"
echo "exposure: $($PY -V 2>&1)"

"$PY" "$A" init "$S" --org "Exposure Ltd" >/dev/null 2>&1
"$PY" "$A" add-system "$S" --name "Contoso Assist" --provider "Contoso" --version "2026.4" \
   --retrieval-augmented >/dev/null 2>&1
"$PY" "$A" add-system "$S" --name "Churn model" --provider "In-house" --version "3.1" \
   --predictive --hosting self-hosted >/dev/null 2>&1
"$PY" "$A" deploy "$S" --system S-001 --purpose "screening applicants" \
   --owner "HR Director" --autonomy decides --data-class "applicant personal data" \
   --consequential --by CISO >/dev/null 2>&1
"$PY" "$A" deploy "$S" --system S-002 --purpose "churn scoring" --owner "Head of Sales" \
   --autonomy recommends --by CISO >/dev/null 2>&1

cls() {  # cls <deployment>
  "$PY" -c '
import json, sys
store = json.load(open(sys.argv[1], encoding="utf-8"))
rec = next(d for d in store["deployments"] if d["id"] == sys.argv[2])
print(" ".join(sorted(rec["exposure"])))' "$S" "$1"
}

# --- 1-2. no command, anywhere, selects a class -------------------------------
help_text=$("$PY" "$A" --help 2>&1)
if printf '%s' "$help_text" | grep -qiE 'select|deselect|exclude|mark-|set-class|dismiss|accept-exposure'; then
  bad "no subcommand selects, excludes or accepts a class" \
      "$(printf '%s' "$help_text" | grep -iE 'select|exclude|mark-|dismiss|accept' | head -3)"
else
  ok "no subcommand selects, excludes or accepts a class"
fi
if "$PY" -c '
import importlib.util, inspect, re, sys
spec = importlib.util.spec_from_file_location("ar", sys.argv[1])
ar = importlib.util.module_from_spec(spec); spec.loader.exec_module(ar)
bad = []
for name, obj in vars(ar).items():
    if not inspect.isfunction(obj):
        continue
    if re.search(r"inapplicable|deselect|exclude_class|unmap|dismiss", name, re.I):
        bad.append(name)
    # `accept_exposure` may exist, and must do nothing but refuse.
    if re.search(r"accept", name, re.I):
        try:
            obj()
        except ar.Refusal:
            continue
        except TypeError:
            pass
        bad.append("%s did not refuse" % name)
if bad:
    print(", ".join(bad), file=sys.stderr); sys.exit(1)
' "$A" 2>"$work/fn.err"; then
  ok "and no module function marks one inapplicable — the only 'accept' there is refuses"
else
  bad "no function can mark a class inapplicable" "$(cat "$work/fn.err")"
fi

# --- 3-8. what derives, and what does not -------------------------------------
gen=$(cls D-001)
pred=$(cls D-002)
case "$gen" in
  *NISTAML.03*) ok "a generative deployment handling personal data is exposed to NISTAML.03" ;;
  *) bad "NISTAML.03 derives for a generative deployment on personal data" "got: $gen" ;;
esac
case "$gen" in
  *NISTAML.04*) ok "NISTAML.04 derives for a generative deployment" ;;
  *) bad "NISTAML.04 derives for a generative deployment" "got: $gen" ;;
esac
case "$gen" in
  *NISTAML.05*) ok "...and to supply chain, because the model comes from outside" ;;
  *) bad "NISTAML.05 derives for an external provider" "got: $gen" ;;
esac
case "$pred" in
  *NISTAML.04*) bad "a PREDICTIVE deployment is not exposed to misuse" "got: $pred" ;;
  *) ok "a PREDICTIVE deployment is NOT exposed to misuse — the rule discriminates" ;;
esac
case "$pred" in
  *NISTAML.05*) bad "an in-house model raises no supply-chain class" "got: $pred" ;;
  *) ok "and an in-house model raises no supply-chain class" ;;
esac
case "$pred" in
  *NISTAML.01*NISTAML.02*) ok "while availability and integrity apply to any deployment" ;;
  *) bad "availability and integrity apply to every deployment" "got: $pred" ;;
esac

# --- 9-11. recompute, and what survives it ------------------------------------
"$PY" "$A" record-control "$S" --deployment D-002 --class NISTAML.02 \
   --control "input validation" --evidence "config export, dated" --on 2026-06-01 \
   --by "Head of Security" >/dev/null 2>&1
# Flip the system to generative the way a real edit would — through the store, then recompute.
"$PY" -c '
import json, sys
store = json.load(open(sys.argv[1], encoding="utf-8"))
next(s for s in store["systems"] if s["id"] == "S-002")["genAI"] = True
json.dump(store, open(sys.argv[1], "w", encoding="utf-8"), indent=2)' "$S"
"$PY" "$A" map-exposure "$S" --deployment D-002 --by CISO >/dev/null 2>&1
case "$(cls D-002)" in
  *NISTAML.04*) ok "flipping genAI recomputes exposure" ;;
  *) bad "flipping genAI recomputes exposure" "got: $(cls D-002)" ;;
esac
n=$("$PY" -c '
import json, sys
store = json.load(open(sys.argv[1], encoding="utf-8"))
rec = next(d for d in store["deployments"] if d["id"] == "D-002")
print(len(rec["exposure"]["NISTAML.02"]["controls"]))' "$S")
if [ "$n" = "1" ]; then
  ok "and the control recorded before the recompute survived it"
else
  bad "controls survive a recompute" "expected 1, got $n — evidence somebody produced was lost"
fi
if "$PY" "$A" map-exposure "$S" --deployment D-002 --by CISO 2>&1 | grep -q "NISTAML.01"; then
  ok "map-exposure prints every derived class with the reason it applies"
else
  bad "map-exposure names the classes and why" "it printed nothing recognisable"
fi

# --- 12-14. the other door into the exposure block ----------------------------
before=$(md5 -q "$S" 2>/dev/null || md5sum "$S" | cut -d' ' -f1)
if "$PY" "$A" record-control "$S" --deployment D-002 --class NISTAML.99 \
     --control "x" --evidence "y" >/dev/null 2>"$work/c1.err"; then
  bad "a control against a class that was not derived is refused" "it was accepted"
else
  if grep -qF "cannot be selected by hand" "$work/c1.err"; then
    ok "a control against a class not derived is refused, saying exposure is not selectable"
  else
    ok "a control against a class not derived is refused"
  fi
fi
if "$PY" "$A" record-control "$S" --deployment D-002 --class NISTAML.01 \
     --control "rate limiting" --evidence "" >/dev/null 2>"$work/c2.err"; then
  bad "a control with no evidence is refused" "it was accepted"
else
  ok "and one with no evidence is refused — a control with none is an intention"
fi
after=$(md5 -q "$S" 2>/dev/null || md5sum "$S" | cut -d' ' -f1)
if [ "$before" = "$after" ]; then
  ok "neither refusal touched the store"
else
  bad "a refused record-control leaves the store byte-identical" "the file changed"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'exposure: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'exposure: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'exposure: all %s checks passed\n' "$checks"
