#!/usr/bin/env bash
# The archetype layer is ADVICE ABOUT DEPTH. The day it becomes scope, this fails.
#
# A release-readiness test ran a controlled A/B: sector, jurisdictions, regulatory scope, AI,
# OT, data, cloud, vendors and concentration held constant, and only revenue (USD 5m -> 50bn)
# and headcount (1-50 -> 100,000+) changed. The applicability objects came back byte-for-byte
# identical, and the report was right to call that SAFE — size must not invent a regulatory
# obligation. A Fortune 100 and an SMB with the same declared facts owe the same duties.
#
# It also meant the toolkit had nothing to say about size, and size genuinely changes how much
# assurance is proportionate. The archetype layer says it, in its own payload key.
#
# This suite exists because that separation is exactly the kind that erodes. "While we are
# here, a small organisation probably does not need the AI battery" is one plausible line away
# at any time, and it would be an exemption nobody declared — the single failure CAC-AP-1 was
# built to prevent. So the A/B test is not a thing that was run once; it is a check that runs
# on every push.
#
#   1. The A/B, permanently. Move ONLY the size facts and every applicability decision must be
#      byte-identical.
#   2. ...and the archetype must MOVE, or the layer is doing nothing and check 1 is vacuous.
#   3. `archetype` never appears inside `applicability`, at any depth.
#   4. Absence asks MORE. No size declared yields the full depth, never the smallest.
#   5. The higher of two declared bands wins, so an unusual size fact raises depth rather than
#      averaging away.
#   6. An unrecognised headcount string contributes nothing rather than being coerced.
#   7. The engine's own refusals: a broken dataset is refused rather than half-applied.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=9
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

B="$skill/scripts/business_context.py"
echo "archetype-advisory: $($PY -V 2>&1)"

# --- 1/2. the A/B, run here rather than remembered ----------------------------
res=$("$PY" - "$B" <<'PYEOF'
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("bc", sys.argv[1])
bc = importlib.util.module_from_spec(spec); spec.loader.exec_module(bc)

def org(revenue, headcount):
    """Same organisation, twice, differing ONLY in the two size facts."""
    s = bc.new_store("Probe Ltd")
    # Everything that could legitimately change scope, held constant and non-trivial: a
    # profile of all-absent flags would make every applicability object identical for a
    # reason that has nothing to do with size.
    for flag, value in (("listedEntity", True), ("euEntity", True), ("doraScope", True),
                        ("nydfsScope", False), ("ukEntity", True), ("aiInUse", True),
                        ("otPresent", True), ("cloudPosture", "hybrid"),
                        ("regulatedDataHeld", True), ("criticalVendorCount", 9),
                        ("concentrationConcern", True), ("primarySector", "manufacturing"),
                        ("jurisdictions", "IE,GB,US")):
        bc.declare_flag(s, flag, value, by="R. Calder", basis="A/B fixture")
    bc.set_revenue(s, exact=revenue, currency="USD", fiscal_year="FY26",
                   by="CFO", basis="A/B fixture")
    bc.declare_flag(s, "headcountBand", headcount, by="R. Calder", basis="A/B fixture")
    return s

small = bc.context_payload(org(5e6, "1-50"))
huge = bc.context_payload(org(50e9, "100,000+"))

problems = []
if json.dumps(small["applicability"], sort_keys=True) != \
   json.dumps(huge["applicability"], sort_keys=True):
    problems.append("SCOPE size changed an applicability decision, which is the one thing "
                    "this layer must never do")
# ...and the flags themselves, since applicability is derived from them.
flags_s = {k: v for k, v in small["profile"].items() if k not in ("headcountBand",)}
flags_h = {k: v for k, v in huge["profile"].items() if k not in ("headcountBand",)}
if json.dumps(flags_s, sort_keys=True) != json.dumps(flags_h, sort_keys=True):
    problems.append("SCOPE size changed a declared flag")

if small["archetype"]["id"] == huge["archetype"]["id"]:
    problems.append("VACUOUS both organisations got archetype %r, so check 1 compared two "
                    "identical things and proved nothing" % small["archetype"]["id"])
else:
    print("MOVED %s -> %s" % (small["archetype"]["id"], huge["archetype"]["id"]))

blob = json.dumps(small["applicability"])
if "archetype" in blob or small["archetype"]["title"] in blob:
    problems.append("LEAK the archetype reached the applicability block")
for key in ("appliesTo", "neverAffects"):
    if key not in small["archetype"]:
        problems.append("LABEL the archetype does not say %r, so a consumer has to infer "
                        "what it is for" % key)
print("\n".join(problems))
PYEOF
)
moved=$(printf '%s\n' "$res" | grep '^MOVED' || true)
probs=$(printf '%s\n' "$res" | grep -vE '^MOVED|^$' || true)

for kind in SCOPE:"size changes NO applicability decision and no declared flag" \
            VACUOUS:"...while the archetype itself moves, so that comparison means something" \
            LEAK:"the archetype never appears inside the applicability block" \
            LABEL:"and it says in the payload that it affects depth only"; do
  tag="${kind%%:*}"; label="${kind#*:}"
  hit=$(printf '%s\n' "$probs" | grep "^$tag " || true)
  if [ -z "$hit" ]; then
    extra=""
    [ "$tag" = "VACUOUS" ] && extra=" (${moved#MOVED })"
    ok "$label$extra"
  else
    bad "$label" "$hit"
  fi
done

# --- 4-6. the engine's own rules ----------------------------------------------
if "$PY" -c '
import importlib.util, sys
spec = importlib.util.spec_from_file_location("bc", sys.argv[1])
bc = importlib.util.module_from_spec(spec); spec.loader.exec_module(bc)

# 4. Absence asks MORE. This is the one that would look harmless to get wrong.
bare = bc.archetype_for(bc.new_store("Nobody Ltd"))
assert bare["id"] == "undeclared", bare["id"]
assert "absence asks" in bare["basis"]["rule"], bare["basis"]["rule"]
full = bc.load_archetypes()["byId"]["enterprise"]
assert bare["evidenceDepth"] and bare["reviewCadence"], "the undeclared band has no advice"
assert bare["id"] != "small", "an undeclared size must never resolve to the smallest band"

# 5. The higher band wins, in both directions.
s = bc.new_store("Odd Ltd")
bc.set_revenue(s, exact=2e9, currency="USD", fiscal_year="FY26", by="C", basis="b")
bc.declare_flag(s, "headcountBand", "1-50", by="D", basis="b")
assert bc.archetype_for(s)["id"] == "large", bc.archetype_for(s)["id"]
s2 = bc.new_store("Other Ltd")
bc.set_revenue(s2, exact=5e6, currency="USD", fiscal_year="FY26", by="C", basis="b")
bc.declare_flag(s2, "headcountBand", "100,000+", by="D", basis="b")
assert bc.archetype_for(s2)["id"] == "enterprise", bc.archetype_for(s2)["id"]

# 6. An unrecognised headcount string contributes nothing rather than being coerced.
s3 = bc.new_store("Weird Ltd")
bc.declare_flag(s3, "headcountBand", "a few hundred-ish", by="D", basis="b")
got = bc.archetype_for(s3)
assert got["id"] == "undeclared", got["id"]
assert got["basis"]["fromHeadcount"] is None, got["basis"]
' "$B" 2>"$work/rules.err"; then
  ok "absence asks MORE, the higher band wins, and an unrecognised band is not coerced"
else
  bad "the engine's own rules hold" "$(tail -3 "$work/rules.err")"
fi

# --- 7. a broken dataset is refused -------------------------------------------
"$PY" -c '
import json, sys
json.dump({"archetypes": [{"id": "small"}]}, open(sys.argv[1], "w", encoding="utf-8"))' \
  "$work/gapped.json"
if "$PY" -c '
import importlib.util, sys
spec = importlib.util.spec_from_file_location("bc", sys.argv[1])
bc = importlib.util.module_from_spec(spec); spec.loader.exec_module(bc)
try:
    bc.load_archetypes(sys.argv[2])
except bc.Refusal as exc:
    assert "missing" in str(exc), exc
else:
    raise AssertionError("accepted a dataset with four bands missing")
' "$B" "$work/gapped.json" 2>"$work/ds.err"; then
  ok "a dataset missing bands is refused rather than half-applied"
else
  bad "a broken dataset is refused" "$(cat "$work/ds.err")"
fi

# --- 8-10. the shipped dataset, and what it says about itself -----------------
if "$PY" -c '
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("bc", sys.argv[1])
bc = importlib.util.module_from_spec(spec); spec.loader.exec_module(bc)
d = bc.load_archetypes()
missing = [a["id"] for a in d["archetypes"]
           if not all(a.get(k) for k in ("evidenceDepth", "reviewCadence", "roleSeparation",
                                         "metricsBreadth", "thirdPartyCoverage",
                                         "aiGovernanceDepth", "boardPackDensity"))]
if missing:
    print("bands with incomplete advice: %s" % missing, file=sys.stderr); sys.exit(1)
if len(d["archetypes"]) != 5:
    print("expected five bands, found %d" % len(d["archetypes"]), file=sys.stderr); sys.exit(1)
' "$B" 2>"$work/data.err"; then
  ok "every band carries advice on all seven dimensions, so none is a stub"
else
  bad "the shipped dataset is complete" "$(cat "$work/data.err")"
fi

if grep -q "NOT applicability" "$skill/references/archetypes.json" \
   && grep -q "never" "$skill/references/archetypes.json"; then
  ok "...and the dataset itself says, in words, that it is not applicability"
else
  bad "the dataset states its own boundary" \
      "nothing in the file tells a reader what this layer must not do"
fi

# The command a person actually runs has to say it too. A boundary that exists only in a
# JSON comment is a boundary the person reading the output never sees.
"$PY" "$B" archetype "$skill/examples/example-org.biz" > "$work/cli.out" 2>&1
if grep -q "changes no question set" "$work/cli.out" \
   && grep -q "Run \`applies\`" "$work/cli.out"; then
  ok 'and the command prints the boundary and points at applies for real scope'
else
  bad "the command states its own boundary" "$(tail -3 "$work/cli.out")"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'archetype-advisory: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"
  exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'archetype-advisory: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'archetype-advisory: all %s checks passed\n' "$checks"
