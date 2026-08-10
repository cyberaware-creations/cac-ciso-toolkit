#!/usr/bin/env bash
# A crown jewel's criticality has TWO legal shapes on disk, and both are read.
#
# BL-216 R-3 phase 3, decided 2026-08-10 as Q-2. `business-context` writes `criticality` as a
# `declared()` record carrying its own basis. Every `.biz` written before v0.74.0 holds a bare
# string. `SCHEMA_VERSION` was NOT bumped, no converter exists, and no store is ever refused —
# so both shapes persist on disk indefinitely, and every consumer has to read both.
#
# The cleaner alternative was weighed and declined. Bumping the schema and refusing the old
# shape is better engineering and worse product: BL-169 D-2 says stopping part-way must leave a
# loadable store, and a toolkit whose argument is *your records persist and stay defensible*
# cannot ship a read that refuses a CISO's existing file.
#
# ⚠️ WHY THIS GUARD EXISTS RATHER THAN A COMMENT. A field with two shapes reads as an
# inconsistency, and the obvious tidy-up is to force one. Both directions are plausible edits
# and both are silent:
#
#   forcing the RECORD shape  -> every store written before v0.74.0 stops deriving a level
#   forcing the BARE string   -> every store written after it does, and the basis is discarded
#
# Neither breaks a self-test that fixtures only its own shape, and neither is visible until a
# real store meets the engine. So the two halves here are one per direction, and the registered
# mutations are exactly those two tidy-ups.
#
# THE THIRD CHECK IS THE ANTI-VACUITY ONE. A reader that returns a level for anything would
# pass both halves. A container that is not a declared record must still refuse, and so must a
# record whose `value` is itself a container — otherwise the Python repr this whole line of work
# exists to keep out of a governance level (BL-209, BL-216 phase 0b) is back one layer in.
#
# AND THE WRITER IS CHECKED AGAINST THE READER. The record fixture is not hand-written here: it
# comes out of `add_crown_jewel`, so if the writer's shape ever moves, the record half is
# testing the shape that is actually produced rather than the one this file remembers.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
root="$(cd "$skill/../.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=8
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

echo "criticality-shapes: $($PY -V 2>&1)"

"$PY" - "$root" >"$work/out" 2>"$work/err" <<'PYEOF'
import importlib.util, os, sys

root = sys.argv[1]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(root, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bc = load("bc", "skills/business-context/scripts/business_context.py")
engines = [
    ("VENDOR", load("vr", "skills/vendor-register/scripts/vendor_register.py")),
    ("AI", load("ar", "skills/ai-register/scripts/ai_register.py")),
]

# The record shape comes OUT OF THE WRITER, never hand-written here. If `add_crown_jewel`
# changes what it stores, this fixture changes with it and the record half keeps testing the
# shape that actually reaches disk.
store = bc.new_store("Fixture Ltd", "Tester")
written = bc.add_crown_jewel(
    store, "Plant historian", "production scheduling", "a day of lost output",
    by="Head of Engineering", criticality="high",
    criticality_basis="FY26 business impact analysis")
record = written.get("criticality")
print("WRITER %s" % ("ok" if isinstance(record, dict) and record.get("value") == "high"
                     and record.get("basis") else "the writer no longer stores a record: %r"
                     % (record,)))

# The pre-v0.74.0 shape. Not a fixture of convenience — it is what every `.biz` written before
# this release holds, and nothing converts it.
BARE = "high"

levels = {}
for tag, eng in engines:
    for shape_name, shape in (("BARE", BARE), ("RECORD", record)):
        ctx = {"crownJewels": [{"system": "Plant historian", "criticality": shape}]}
        try:
            level, _path, _trunc = eng.derive_criticality({"supports": "Plant historian"}, ctx)
        except Exception as exc:                        # noqa: BLE001 — any escape is a fail
            level = "RAISED %s: %s" % (type(exc).__name__, str(exc).splitlines()[0][:90])
        levels[(tag, shape_name)] = level
        print("%s-%s %s" % (shape_name, tag, level))

same = {levels[k] for k in levels}
print("AGREE %s" % ("ok" if same == {"high"} else "the shapes disagree: %r" % (levels,)))

# Anti-vacuity. A reader that answered "high" for anything would have passed everything above.
refused = {}
for label, shape in (("NOTARECORD", {"tier": "high"}),
                     ("NESTED", {"value": {"tier": "high"}})):
    outcomes = []
    for tag, eng in engines:
        ctx = {"crownJewels": [{"system": "Plant historian", "criticality": shape}]}
        try:
            eng.derive_criticality({"supports": "Plant historian"}, ctx)
            outcomes.append("%s returned a level" % tag)
        except eng.Refusal:
            pass
        except Exception as exc:                        # noqa: BLE001
            outcomes.append("%s raised %s, not a Refusal" % (tag, type(exc).__name__))
    refused[label] = outcomes
    print("%s %s" % (label, "ok" if not outcomes else "; ".join(outcomes)))
PYEOF

if [ ! -s "$work/out" ]; then
  bad "the shape probe ran at all" "$(tail -3 "$work/err")"
  bad "(remaining checks skipped)" "the probe produced no output"
  checks=$EXPECTED_CHECKS
else
  # --- half 1: BARE — a store written before v0.74.0 still derives its level -----
  for want in "BARE-VENDOR high:vendor-register derives a level from a pre-v0.74.0 bare string" \
              "BARE-AI high:...and so does ai-register, on the byte-identical walk"; do
    line="${want%%:*}"; label="${want#*:}"
    if grep -qx "$line" "$work/out"; then ok "$label"
    else bad "$label" "$(grep "^${line%% *} " "$work/out" || echo 'the check printed nothing')"
    fi
  done

  # --- half 2: RECORD — the shape the writer produces today ---------------------
  for want in "RECORD-VENDOR high:vendor-register derives a level from a declared() record" \
              "RECORD-AI high:...and so does ai-register"; do
    line="${want%%:*}"; label="${want#*:}"
    if grep -qx "$line" "$work/out"; then ok "$label"
    else bad "$label" "$(grep "^${line%% *} " "$work/out" || echo 'the check printed nothing')"
    fi
  done

  # --- shared: the claim the polymorphism actually makes ------------------------
  for want in "AGREE ok:both shapes derive the SAME level, in both engines" \
              "WRITER ok:and the record fixture is what add_crown_jewel really writes" \
              "NOTARECORD ok:a container that is not a declared record still refuses" \
              "NESTED ok:and so does a record whose value is itself a container"; do
    line="${want%%:*}"; label="${want#*:}"
    if grep -qx "$line" "$work/out"; then ok "$label"
    else bad "$label" "$(grep "^${line%% *} " "$work/out" || echo 'the check printed nothing')"
    fi
  done
fi

if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'criticality-shapes: ran %d checks, expected %d — a case stopped executing\n' \
         "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'criticality-shapes: %d of %d checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'criticality-shapes: all %d checks passed\n' "$checks"
