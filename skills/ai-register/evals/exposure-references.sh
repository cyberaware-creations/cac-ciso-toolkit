#!/usr/bin/env bash
# A cited reference survives, and never becomes a control (BL-119).
#
# NIST AI 100-2 E2025 cites MITRE ATLAS twice — s 2.2.4 p.16 and s 2.3.5 p.27, ref [248] — in
# the same publication this register draws `NISTAML.01`-`.05` from, and it cites it as a
# catalogue of REAL-WORLD INCIDENTS rather than a competing taxonomy. The classes say what kind
# of attack applies; a reference says whether anything in that class has actually happened to
# anyone. `record-reference` records the second without disturbing the first.
#
# THREE HALVES, and they fail in three different directions. Two are about the record surviving
# and one is about it not being promoted into something it is not:
#
#   1. PRESERVE — `map_exposure` REBUILDS `rec["exposure"]` from scratch on every recompute and
#      keeps only the keys it names. Before v0.97.0 it named `controls` alone, so a reference
#      would have been destroyed by the next attribute change: silently, with no error, after
#      the user recorded it and was told it was accepted. That is worse than not shipping the
#      field, and it is why this half exists rather than being assumed from a passing write.
#
#   2. RETAIN — the same destruction through the other door. A class that stops being derivable
#      is kept only if it carries something worth keeping, and that test used to read
#      `controls` alone. A class carrying references and NO controls was deleted outright,
#      taking them with it.
#
#   3. STATE — the opposite risk. `exposure_state()` returns exactly two values off `controls`,
#      and a reference must move nothing. Letting a cited technique ID read as
#      `controls-recorded` would make READING ABOUT an attack look like DEFENDING against one,
#      which is the most attractive wrong move available here and the one a later "improvement"
#      would reach for first.
#
# ⚠️ HALVES 1 AND 2 CANNOT BE COLLAPSED. Half 1 leaves `prior` intact, so retention still fires
# and half 2's check stays green under it; half 2 leaves the rebuild intact, so a reference
# still survives an ordinary recompute. Each is invisible to the other's mutation, which is
# what CAC-GP-1.9 separability means and why both are registered.
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

echo "exposure-references: $($PY -V 2>&1)"

A="$skill/scripts/ai_register.py"
cp "$skill/examples/example-ai.air" "$work/s.air"

# --- T1/T2. The command, and the two refusals ---------------------------------------
sha() { "$PY" -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$1"; }
before="$(sha "$work/s.air")"

empty="$("$PY" "$A" record-reference "$work/s.air" --deployment D-001 --class NISTAML.02 \
         --ref '' 2>&1 || true)"
case "$empty" in
  *"pointer to nothing"*) ok "an empty --ref is refused" ;;
  *) bad "an empty --ref is refused" "got: $empty" ;;
esac

# The same door `record_control` locks, locked the same way. Exposure is DERIVED; a class the
# deployment is not exposed to cannot be reached by citing something against it.
wrong="$("$PY" "$A" record-reference "$work/s.air" --deployment D-003 --class NISTAML.04 \
         --ref 'ATLAS AML.CS0011' 2>&1 || true)"
case "$wrong" in
  *"cannot be selected by hand"*"needs declaring"*)
    ok "a class the deployment is not exposed to is refused, pointing at the ATTRIBUTE" ;;
  *) bad "an underived class is refused" "got: $wrong" ;;
esac
eq "...and both refusals leave the store byte-identical" "$before" "$(sha "$work/s.air")"

# --- The three halves, driven through the module ------------------------------------
"$PY" - "$A" "$work" >"$work/out" 2>&1 <<'PYEOF'
import importlib.util, json, sys

spec = importlib.util.spec_from_file_location("ar", sys.argv[1])
ar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ar)
work = sys.argv[2]

st = ar.load(work + "/s.air")
dep = ar.find_deployment(st, "D-001")
sysrec = next(s for s in st["systems"] if s["id"] == dep["systemRef"])

ar.record_reference(st, "D-001", "NISTAML.04", "ATLAS AML.CS0011",
                    note="VirusTotal poisoning, cited by NIST AI 100-2 E2025 s 2.3.5", by="rt")
e = dep["exposure"]["NISTAML.04"]
print("written %d" % len(e.get("references") or []))
print("controls-untouched %d" % len(e.get("controls") or []))
print("state-on-write %s" % ar.exposure_state(e))

# HALF 1 — an ordinary recompute, nothing else changed. The class is still derivable.
ar.map_exposure(st, "D-001")
e = dep["exposure"]["NISTAML.04"]
print("survives-recompute %d" % len(e.get("references") or []))
print("still-derived %s" % (not e.get("noLongerDerived")))
print("ref-intact %s" % ((e.get("references") or [{}])[0].get("ref")))

# HALF 3 — references present, controls absent. The state must not have moved.
print("state-after %s" % ar.exposure_state(e))

# HALF 2 — the class stops being derivable, and carries references but NO controls.
#
# On a FRESH load, deliberately, so this path never depends on the recompute above having
# preserved anything. Chaining them made half 1's mutation defeat half 2's checks as well —
# the reference was already gone before retention was reached — which CAC-GP-1.9 rejected as
# two halves that cannot be told apart. It was right to: retention reads `prior`, so what this
# half actually guards is reachable without a prior recompute, and testing it through one was
# measuring the wrong thing.
st2 = ar.load(work + "/s.air")
dep2 = ar.find_deployment(st2, "D-001")
sys2 = next(x for x in st2["systems"] if x["id"] == dep2["systemRef"])
ar.record_reference(st2, "D-001", "NISTAML.04", "ATLAS AML.CS0011", by="rt")
sys2["genAI"] = False
ar.map_exposure(st2, "D-001")
e = dep2["exposure"].get("NISTAML.04")
print("retained %s" % (e is not None))
print("marked %s" % bool((e or {}).get("noLongerDerived")))
print("refs-after-retention %d" % len((e or {}).get("references") or []))

# T6 — the history carries it, once, naming the class.
ev = [h for h in st.get("history", []) if h.get("event") == "reference-recorded"]
print("history %d %s %s" % (len(ev), ev[0].get("why") if ev else "-",
                            (ev[0].get("detail") or {}).get("class") if ev else "-"))
PYEOF
get() { grep -m1 "^$1 " "$work/out" | cut -d' ' -f2-; }

eq "a reference is written against the class" "1" "$(get written)"
eq "...and writing one adds no control" "0" "$(get controls-untouched)"

# ---- HALF 1: PRESERVE -----------------------------------------------------------------
eq "a reference SURVIVES an ordinary recompute" "1" "$(get survives-recompute)"
eq "...with its text intact, not an empty shell" "ATLAS AML.CS0011" "$(get ref-intact)"
eq "...and the class is still ordinarily derived, so this is not the retention path" \
   "True" "$(get still-derived)"

# ---- HALF 3: STATE --------------------------------------------------------------------
# Asserted on BOTH sides of the recompute. A state that was right on write and wrong after is
# the same defect arriving later, and it is the recompute that rebuilds the entry.
eq "a reference does not move exposure_state on write" "no-controls-recorded" "$(get state-on-write)"
eq "...nor after a recompute — reading about an attack is not defending against one" \
   "no-controls-recorded" "$(get state-after)"

# ---- HALF 2: RETAIN -------------------------------------------------------------------
eq "a class with references and NO controls survives losing its derivation" "True" "$(get retained)"
eq "...marked noLongerDerived rather than quietly still applicable" "True" "$(get marked)"
eq "...with its references still on it" "1" "$(get refs-after-retention)"

# ---- T6 -------------------------------------------------------------------------------
eq "the citation is on the history once, naming the class" \
   "1 ATLAS AML.CS0011 NISTAML.04" "$(get history)"

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'exposure-references: ran %d checks, expected %d — a case stopped executing\n' \
         "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'exposure-references: %d of %d checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'exposure-references: all %d checks passed\n' "$checks"
