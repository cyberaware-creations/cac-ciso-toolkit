#!/usr/bin/env bash
# The register records HOW a risk was analysed, and refuses to overclaim about it.
#
# Two registers scored by wholly different methods were byte-indistinguishable until v0.87.0.
# NIST ties defensibility to the method, so the register kept the conclusion and discarded the
# warrant. `set-method` records it; this suite guards the two rules that make the record worth
# trusting rather than merely present.
#
# TWO HALVES, and they fail in opposite directions — one guards against claiming too much, the
# other against reporting something we cannot see:
#
#   1. PARTIAL — `conformance: partial` with no `deviations` is refused ON WRITE (BL-92 A6).
#      Partial conformance with no stated deviation is the claim without the caveat: a reader
#      is told the method was followed loosely and not in what respect. The refusal also
#      carries the naming rule, because the reader who reached for a coined "FAIR-lite" is
#      exactly the reader about to hit it.
#
#   2. EXTERNAL — a method the catalogue marks `external` emits NO `method-prerequisite-unmet`
#      under any input (BL-93 B3, D-4.2). Monte Carlo's real prerequisites are the analyst's
#      input distributions; Bayesian's are their priors; event tree's are their branch
#      probabilities. This toolkit cannot see any of them, and flagging their absence would
#      assert a fact about work done outside it.
#
# ⚠️ HALF 2 IS THE ONE THAT WILL BE ARGUED AWAY. The pressure to "just flag it anyway" on an
# external method will be real, because an escalation looks like value and the code to emit one
# is already there — the boundary is a single early return. So this suite asserts both that the
# external method stays silent AND that a checkable one still fires: a guard that suppressed
# everything would pass half 2 while quietly disabling the trigger the item exists to add.
#
# REFUSALS GUARD WRITES, NEVER LOADS. A register that already carries `partial` with an empty
# `deviations` — hand-edited, or written by another tool — still LOADS, scores and renders. It
# refuses on the next write that touches the method. Asserted here, because validating at load
# is the reflex implementation and it would make an existing register unopenable over a field
# whose entire purpose is honest disclosure.
#
# THE MIXED-METHOD DISCLOSURE (B6) is checked here too, in all three states: mixed declared
# types produce the sentence, a single declared type does not, and an all-undeclared register
# does not. The third is the one worth pinning — absent means NOT DECLARED (CAC-AP-1 s 2.2),
# never "no method was used", so an all-undeclared register is not a single-method register and
# must not read as one.
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

echo "analysis-method: $($PY -V 2>&1)"

"$PY" - "$skill/scripts/score_register.py" "$work" "$skill" >"$work/out" 2>"$work/err" <<'PYEOF'
import contextlib, importlib.util, io, json, os, sys

spec = importlib.util.spec_from_file_location("sr", sys.argv[1])
sr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sr)
work, skill = sys.argv[2], sys.argv[3]
sys.path.insert(0, os.path.join(skill, "renderers"))
sys.path.insert(0, os.path.join(skill, "scripts"))


def run(argv):
    """(refused, message). Stdout is swallowed; only the refusal matters here."""
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            sr.COMMANDS[argv[0]](argv[1:])
        return (False, "")
    except ValueError as exc:
        return (True, str(exc))


def seed(name):
    path = os.path.join(work, name)
    run(["init", path, "--client", "Guard Co", "--assessor", "Tester"])
    run(["add", path, "--title", "Ransomware",
         "--description", "If ransomware reaches the file estate, then production stops",
         "--il", "4", "--ii", "4", "--rl", "3", "--ri", "3", "--why", "fixture"])
    return path

# --- half 1: PARTIAL --------------------------------------------------------------
reg = seed("partial.rr")
bad_write = ["set-method", reg, "R-001", "--name", "OPEN FAIR", "--type", "quantitative",
             "--conformance", "partial", "--why", "modelled"]
before = open(reg, "rb").read()
refused, msg = run(bad_write)
print("PARTIAL %s" % ("refused" if refused else "ACCEPTED AN UNCAVEATED CLAIM"))
print("PARTIAL-BYTES %s" % ("ok" if open(reg, "rb").read() == before else "the register changed"))
# The refusal has to name the fix AND the naming rule, or a five-second correction becomes a
# support question and the reader coins "FAIR-lite" instead.
want = ("--deviations", "the claim without the caveat", "FAIR-lite", "open-fair")
missing = [w for w in want if w not in msg]
print("PARTIAL-WHY %s" % ("ok" if not missing else "the refusal omits %s" % ", ".join(missing)))
# ...and it accepts the same claim WITH its caveat. A guard proving only the refusal cannot
# tell "refuses correctly" from "refuses everything".
refused, _ = run(bad_write + ["--deviations", "no monetised loss magnitude"])
print("PARTIAL-ACCEPTS %s" % ("ok" if not refused else "a stated deviation was still refused"))

# It LOADS. A register already carrying the combination opens, scores and renders.
legacy = seed("legacy.rr")
store = sr.load_register(legacy)
store["risks"][0]["analysisMethod"] = {
    "name": "OPEN FAIR", "type": "quantitative", "conformance": "partial",
    "deviations": "", "setBy": "Tester", "asOf": "2026-05-01"}
sr.save_register(store, legacy)
try:
    sr.load_register(legacy)
    print("PARTIAL-LOADS ok")
except Exception as exc:                                # noqa: BLE001 — any escape is a fail
    print("PARTIAL-LOADS a register carrying it no longer opens: %s" % exc)

# --- half 2: EXTERNAL -------------------------------------------------------------
def escalated(method, currency=""):
    store = sr.load_register(seed("esc-%s.rr" % abs(hash(json.dumps(method, sort_keys=True)))))
    store["settings"]["currency"] = currency
    store["risks"][0]["analysisMethod"] = method
    store["risks"][0]["provisionalScore"] = False
    return [e["trigger"] for e in sr.escalations(store, today="2026-07-31")
            if e["trigger"] == "method-prerequisite-unmet"]


def method(name, mtype="quantitative", conf="partial", dev=""):
    return {"name": name, "type": mtype, "conformance": conf, "deviations": dev,
            "setBy": "Tester", "asOf": "2026-05-01"}


# Both v1 conditions are true on this record. Both are correctly suppressed, because the
# prerequisites that matter for Monte Carlo are not in this file.
print("EXTERNAL %s" % ("ok" if not escalated(method("Monte Carlo"))
                       else "an external method escalated on prerequisites we cannot see"))
print("EXTERNAL-LICENSED %s" % ("ok" if not escalated(method("OPEN FAIR"))
                                else "a licensed third-party method escalated"))
# ...and the trigger is NOT simply off. A checkable method with the same two gaps fires twice.
print("CHECKABLE %s" % ("ok" if len(escalated(method("Workshop scoring"))) == 2
                        else "the trigger is disabled, not bounded: %r"
                             % escalated(method("Workshop scoring"))))
print("CHECKABLE-CLEARS %s" % (
    "ok" if not escalated(method("Workshop scoring", conf="full"), currency="GBP")
    else "a fully-recorded method still escalated"))

# --- B6: the mixed-method disclosure, in all three states -------------------------
import _common as C                                      # noqa: E402


def sentence(types):
    path = os.path.join(work, "mix-%s.rr" % "-".join(t or "none" for t in types))
    run(["init", path, "--client", "Mix Co", "--assessor", "Tester"])
    store = sr.load_register(path)
    for i, t in enumerate(types, start=1):
        risk = sr.empty_risk("R-%03d" % i)
        risk.update({"title": "R%d" % i, "description": "If x, then y",
                     "inherent": {"likelihood": 3, "impact": 3},
                     "residual": {"likelihood": 3, "impact": 3},
                     "provisionalScore": False, "provisionalTitle": False,
                     "analysisMethod": method("Workshop scoring", t, "full") if t else None})
        store["risks"].append(risk)
    sr.save_register(store, path)

    class _Args:
        register = path
        today = "2026-07-31"
        age_threshold = 90
        out = os.path.join(work, "unused.html")
        translations = ""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        ctx = C.Context(_Args())
    return ctx.method_mix_sentence()


print("MIXED %s" % ("ok" if "not all analysed the same way" in sentence(
    ["qualitative", "quantitative"]) else "a mixed register disclosed nothing"))
print("SINGLE %s" % ("ok" if sentence(["qualitative", "qualitative"]) == ""
                     else "a single-method register carried a mixed-method caveat"))
print("UNDECLARED %s" % ("ok" if sentence([None, None]) == ""
                         else "an all-undeclared register read as a mix"))
PYEOF

if [ ! -s "$work/out" ]; then
  bad "the probe ran" "$(head -3 "$work/err" || echo 'no output at all')"
else
  for want in \
      "PARTIAL refused:partial conformance with no deviation is refused on write" \
      "PARTIAL-BYTES ok:...and the register is byte-identical afterwards" \
      "PARTIAL-WHY ok:...and the refusal names the flag, the reason and the naming rule" \
      "PARTIAL-ACCEPTS ok:the same claim WITH its caveat is accepted" \
      "PARTIAL-LOADS ok:a register already carrying the combination still LOADS" \
      "EXTERNAL ok:an external method escalates nothing, both conditions true" \
      "EXTERNAL-LICENSED ok:...including a licensed third-party method" \
      "CHECKABLE ok:while a checkable method with the same two gaps fires twice" \
      "CHECKABLE-CLEARS ok:...and clears once both are recorded" \
      "MIXED ok:a register of mixed declared types discloses it" \
      "SINGLE ok:a single-type register does not" \
      "UNDECLARED ok:and an all-undeclared register does not read as single-method"; do
    line="${want%%:*}"; label="${want#*:}"
    if grep -qx "$line" "$work/out"; then ok "$label"
    else bad "$label" "$(grep "^${line%% *} " "$work/out" || echo 'the check printed nothing')"
    fi
  done
fi

if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'analysis-method: ran %d checks, expected %d — a case stopped executing\n' \
         "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'analysis-method: %d of %d checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'analysis-method: all %d checks passed\n' "$checks"
