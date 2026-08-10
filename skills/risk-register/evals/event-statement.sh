#!/usr/bin/env bash
# A scored risk carries an event statement. Both ways in.
#
# `SKILL.md`'s first named precondition — *risks are written as events, not topics* — was a
# documented discipline the engine did not enforce for nine releases. `add --title "Phishing"`
# with four numbers wrote `"description": ""`, and that one-word noun was scored, banded,
# counted in the band mix and eligible for board views. The only trace was a muted
# *"No event statement recorded."* on the rendered page, produced long after the number existed.
#
# It is worse than an omission, and the asymmetry is the reason this is a guard rather than a
# validation. The two IMPORT paths mark their rows `provisionalTitle` precisely so raw CSF
# wording stays out of board views until a person rewords it. `add` sets no such flag. So the
# register held an imported control objective back and let a hand-typed noun straight through
# (BL-81).
#
# TWO HALVES, one per way in, because closing either alone leaves the defect reachable:
#
#   1. ADD — a new risk with no description is refused, and nothing is written.
#   2. RESCORE — a risk that already has no description refuses on `set-score`. Registers
#      written before v0.78.0 hold these, and refusals guard WRITES, never loads: the file
#      still opens. A new number attached to a topic is the same defect arriving a release
#      later, through the one command whose entire purpose is to revise the number.
#
# ⚠️ THE THIRD CHECK IS THE ONE THAT KEEPS THIS HONEST. Half 2 is gated on `provisionalTitle`,
# and it has to be: an imported CSF gap has NO description by design, and the sanctioned order
# is `set-score` to assess, then `set-text` to reword. An unconditional refusal would deadlock
# that flow at its first step. So this suite proves the import path still works — otherwise a
# guard that refused everything would pass both halves while breaking the register's main
# intake.
#
# THE SHAPE IS NEVER VALIDATED. No regex, no `startswith("If")`, no minimum length. Requiring
# the field is a record requirement; pattern-matching a human's sentence for whether it is a
# good risk statement is the tool judging, which is the wrong side of `record and refuse,
# never judge`. This suite asserts a wilfully bad-but-present statement is ACCEPTED, so that
# rule is checked rather than remembered.
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

echo "event-statement: $($PY -V 2>&1)"

"$PY" - "$skill/scripts/score_register.py" "$work" >"$work/out" 2>"$work/err" <<'PYEOF'
import importlib.util, os, sys

spec = importlib.util.spec_from_file_location("sr", sys.argv[1])
sr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sr)
work = sys.argv[2]


def run(argv):
    """(refused, message). Stdout is swallowed; only the refusal matters here."""
    import contextlib, io
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            sr.COMMANDS[argv[0]](argv[1:])
        return (False, "")
    except ValueError as exc:
        return (True, str(exc))


reg = os.path.join(work, "g.rr")
run(["init", reg, "--client", "Guard Co", "--assessor", "Tester"])

# --- half 1: ADD ------------------------------------------------------------------
topic = ["add", reg, "--title", "Phishing", "--il", "4", "--ii", "4", "--rl", "3", "--ri", "3"]
before = open(reg, "rb").read()
refused, msg = run(topic)
print("ADD %s" % ("refused" if refused else "ACCEPTED A TOPIC"))
print("BYTES %s" % ("ok" if open(reg, "rb").read() == before else "the register changed"))
# A refusal a reader cannot act on is a refusal they work around.
want = ("--description", "topic", "no likelihood", "If <event>, then <consequence>")
missing = [w for w in want if w not in msg]
print("WHY %s" % ("ok" if not missing else "the refusal omits %s" % ", ".join(missing)))

# ...and it accepts one. A guard that only proves the refusal cannot tell "refuses correctly"
# from "refuses everything" — and the wording here is deliberately NOT if-then, because the
# shape is never validated and that rule is checked rather than remembered.
refused, _ = run(topic + ["--description", "phishing gets in and things go wrong"])
print("ACCEPTS %s" % ("ok" if not refused else "a present-but-unshaped statement was refused"))

# --- half 2: RESCORE, on a register written before the rule existed ----------------
legacy = os.path.join(work, "legacy.rr")
run(["init", legacy, "--client", "Legacy Co", "--assessor", "Tester"])
store = sr.load_register(legacy)
risk = sr.empty_risk("R-001")
risk.update({"title": "Phishing", "description": "",
             "inherent": {"likelihood": 4, "impact": 4},
             "residual": {"likelihood": 3, "impact": 3}})
store["risks"].append(risk)
sr.save_register(store, legacy)

# It LOADS. Refusals guard writes, never loads — an old register still opens and renders.
try:
    sr.load_register(legacy)
    print("LOADS ok")
except Exception as exc:                                # noqa: BLE001 — any escape is a fail
    print("LOADS a pre-v0.78.0 register no longer opens: %s" % exc)

rescore = ["set-score", legacy, "R-001", "--residual", "4", "4", "--why", "revised"]
refused, msg = run(rescore)
print("RESCORE %s" % ("refused" if refused else "RE-SCORED A TOPIC"))
print("RESCORE-WHY %s" % ("ok" if "set-text" in msg else "the refusal does not name the way through"))

# ⚠️ And the import path still works. An imported CSF gap has no description BY DESIGN.
store = sr.load_register(legacy)
store["risks"][0]["provisionalTitle"] = True
sr.save_register(store, legacy)
refused, _ = run(rescore)
print("IMPORT %s" % ("ok" if not refused
                     else "an imported provisional risk can no longer be scored — the "
                          "sanctioned intake flow is broken at its first step"))
PYEOF

if [ ! -s "$work/out" ]; then
  bad "the probe ran at all" "$(tail -3 "$work/err")"
  checks=$EXPECTED_CHECKS
else
  for want in "ADD refused:a new risk with no description is refused" \
              "BYTES ok:...and the register is byte-identical afterwards" \
              "WHY ok:...and the refusal names the flag, the reason and the house format" \
              "ACCEPTS ok:a present statement is accepted, whatever its shape" \
              "LOADS ok:a pre-v0.78.0 register holding one still LOADS" \
              "RESCORE refused:...and re-scoring that risk is refused" \
              "RESCORE-WHY ok:...naming set-text as the way through" \
              "IMPORT ok:while an IMPORTED provisional risk with no description still scores"; do
    line="${want%%:*}"; label="${want#*:}"
    if grep -qx "$line" "$work/out"; then ok "$label"
    else bad "$label" "$(grep "^${line%% *} " "$work/out" || echo 'the check printed nothing')"
    fi
  done
fi

if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'event-statement: ran %d checks, expected %d — a case stopped executing\n' \
         "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'event-statement: %d of %d checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'event-statement: all %d checks passed\n' "$checks"
