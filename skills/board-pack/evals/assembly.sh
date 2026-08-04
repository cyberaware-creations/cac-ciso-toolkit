#!/usr/bin/env bash
# Assembly end to end: manifest -> validated sections -> content model -> HTML + PPTX.
#
# `self-test` pins the pure functions. This suite exists for what a module cannot see about
# itself: that the CLI wires the arguments through, that the shipped example manifest actually
# resolves against five real producer stores, that the two outputs agree with each other, and
# that a `.pptx` written by hand from `zipfile` is a structurally sound OPC container.
#
# The load-bearing case is the placeholder pair (checks 12-15). A missing translation must
# reach BOTH deliverables as a visibly unfilled slot. A pack that renders a plausible sentence
# into a hole is worse than one that fails, because only one of those gets noticed — and it is
# the failure the whole section contract exists to prevent.
#
# Anti-vacuity: EXPECTED_CHECKS is asserted at the end, and the placeholder cases assert both
# that the marker IS present when the sidecar is absent and that it is NOT present when it is
# supplied. A check that only ever looks for absence passes over an empty file.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=36
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }
eq()  { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "expected '$2', got '$3'"; fi; }

A="$skill/scripts/assemble_pack.py"
export FLAT="$work/flat.board.json"
export V2="$work/v2.board.json"
M="$skill/examples/pack.manifest.json"
J="$work/pack.json"

q() { "$PY" -c 'import json,sys
p = json.load(open(sys.argv[1]))
print(eval(sys.argv[2]))' "$J" "$1"; }

# Every manifest variant is written into $work, where the shipped manifest relative paths no
# longer resolve. Absolutise them first, or a variant "fails" because nothing could be found
# and a refusal check passes for entirely the wrong reason. That is what happened on this
# suite first run: three refusal cases were green against manifests whose every path was
# broken, which is a vacuous pass wearing a tick.
variant() {  # variant <out.json> <python-snippet mutating `m`>
  "$PY" "$here/_variant.py" "$M" "$1" "$2"
}

echo "assembly: $($PY -V 2>&1)"

# --- 1-3. the shipped manifest resolves and validates -------------------------
if "$PY" "$A" validate "$M" >"$work/v.txt" 2>"$work/v.err"; then
  ok "the shipped manifest validates against the contract"
else
  bad "the shipped manifest validates against the contract" "$(tail -2 "$work/v.err")"
fi
if "$PY" "$A" assemble "$M" --out "$J" >/dev/null 2>"$work/a.err"; then
  ok "and assembles"
else
  bad "and assembles" "$(tail -2 "$work/a.err")"
fi
eq "all five producers are in the pack" "5" "$(q 'len(p["sections"])')"

# --- 4-6. ordering is by audience and is fixed --------------------------------
eq "board order: the frame first, then what we carry" \
   "['posture', 'risk', 'metrics', 'exceptions', 'incident']" \
   "$(q 'p["provenance"]["sectionOrder"]')"
variant "$work/ac.manifest.json" 'm["audience"] = "audit-committee"'
"$PY" "$A" assemble "$work/ac.manifest.json" --out "$work/ac.json" >/dev/null 2>&1
eq "audit-committee order: its own remit leads" \
   "['incident', 'exceptions', 'risk', 'posture', 'metrics']" \
   "$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["provenance"]["sectionOrder"])' "$work/ac.json")"
eq "the same sections appear in both, only re-ordered" "5" \
   "$("$PY" -c 'import json,sys;print(len(json.load(open(sys.argv[1]))["sections"]))' "$work/ac.json")"

# --- 7-9. headline figures are READ from the producers ------------------------
eq "eleven headline figures, read from five producers" "11" "$(q 'len(p["headlines"])')"
eq "and each names the section that computed it" "True" \
   "$(q 'all(h["section"] in {s["section"] for s in p["sections"]} for h in p["headlines"])')"
# The assembler must not invent or format a figure the producer did not compute. Counts stay
# ints; a float would mean something was derived on the way through.
#
# The treatment-cost figure is the one string, because the currency belongs to the register
# and a consumer that formatted it would be guessing. So the rule is not relaxed, it is made
# checkable the strong way: the string must appear VERBATIM in the risk producer's own
# output. An assembler that formatted "340000" into "GBP 340,000" itself would fail this,
# which is precisely the failure the int rule was written to catch.
eq "every counted figure is an integer, not a derived or formatted one" "True" \
   "$(q 'all(isinstance(h["value"], int) for h in p["headlines"] if not isinstance(h["value"], str))')"
cost_display="$("$PY" "$(cd "$skill/../risk-register" && pwd)/scripts/score_register.py" \
  score "$(cd "$skill/../risk-register" && pwd)/examples/example-register-v2.rr" --json \
  | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["summary"]["treatmentCost"]["display"])')"
eq "the treatment-cost string is the producer's own, lifted unchanged" "True" \
   "$(q "any(h[\"value\"] == \"$cost_display\" for h in p[\"headlines\"])")"
# A total without its denominator is the false precision this pack refuses everywhere else.
eq "and its label carries how many risks were priced" "True" \
   "$(q 'any(isinstance(h["value"], str) and "priced" in h["label"] for h in p["headlines"])')"

# --- 10-11. decisions consolidate, and duplicates are surfaced not merged ------
eq "the through-line's cross-cutting ask leads the decision list" "['pack']" \
   "$(q 'p["decisions"][0]["sections"]')"
if q 'any("name A-002" in w for w in p["provenance"]["warnings"])' | grep -q True; then
  ok "two sections asking about the same record are flagged, not silently merged"
else
  bad "two sections asking about the same record are flagged, not silently merged" \
      "no flag for A-002, which the exceptions and incident sections both name"
fi

# --- 12-15. THE placeholder pair ----------------------------------------------
# Both directions, because a check that only looks for absence passes over an empty file.
(cd "$skill/renderers" && "$PY" render_pack.py --in "$J" \
   --html "$work/full.html" --pptx "$work/full.pptx") >/dev/null 2>&1
if grep -q 'class="ph"' "$work/full.html"; then
  bad "a fully-translated pack renders NO placeholder" "found one"
else
  ok "a fully-translated pack renders NO placeholder"
fi
variant "$work/bare.manifest.json" 'm.pop("throughLine", None)
for e in m["sections"]: e.pop("translations", None)'
"$PY" "$A" assemble "$work/bare.manifest.json" --out "$work/bare.json" >/dev/null 2>&1
(cd "$skill/renderers" && "$PY" render_pack.py --in "$work/bare.json" \
   --html "$work/bare.html" --pptx "$work/bare.pptx") >/dev/null 2>&1
n=$(grep -o 'class="ph"' "$work/bare.html" | wc -l | tr -d ' ')
if [ "$n" -ge 6 ]; then
  ok "a pack with no sidecars renders a placeholder in every slot ($n)"
else
  bad "a pack with no sidecars renders a placeholder in every slot" "only $n"
fi
if grep -q "does not write board prose" "$work/bare.html"; then
  ok "and the placeholder says why, and what to run instead"
else
  bad "and the placeholder says why, and what to run instead" "absent"
fi
if "$PY" - "$work/bare.pptx" <<'PY'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
text = b"".join(z.read(n) for n in z.namelist() if n.startswith("ppt/slides/slide"))
sys.exit(0 if b"Not supplied" in text else 1)
PY
then ok "the placeholder reaches the PPTX too, not only the HTML"
else bad "the placeholder reaches the PPTX too, not only the HTML" "absent from every slide"; fi

# --- 16-20. the .pptx is a sound OPC container --------------------------------
res=$("$PY" - "$skill" "$work/full.pptx" <<'PY'
import sys, os
sys.path.insert(0, os.path.join(sys.argv[1], "scripts"))
import pptx_writer as P
print("\n".join(P.verify(sys.argv[2])))
PY
)
if [ -z "$res" ]; then ok "the written .pptx is a structurally sound OPC container"
else bad "the written .pptx is a structurally sound OPC container" "$res"; fi
eq "it holds a slide per section plus the front matter and provenance" "True" \
   "$("$PY" -c 'import zipfile,sys
z = zipfile.ZipFile(sys.argv[1])
print(len([n for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")]) >= 10)' "$work/full.pptx")"
# A deck that differs only by zip timestamps cannot be diffed between quarters.
(cd "$skill/renderers" && "$PY" render_pack.py --in "$J" \
   --html "$work/again.html" --pptx "$work/again.pptx") >/dev/null 2>&1
if cmp -s "$work/full.pptx" "$work/again.pptx"; then
  ok "two runs over the same pack produce byte-identical PPTX"
else
  bad "two runs over the same pack produce byte-identical PPTX" "the bytes differ"
fi
if cmp -s "$work/full.html" "$work/again.html"; then
  ok "and byte-identical HTML"
else
  bad "and byte-identical HTML" "the bytes differ"
fi
if "$PY" - "$work/full.pptx" <<'PY'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
text = b"".join(z.read(n) for n in z.namelist() if n.startswith("ppt/slides/slide"))
sys.exit(0 if b"Not affiliated with NIST" in text else 1)
PY
then ok "every deck carries the footer"
else bad "every deck carries the footer" "absent"; fi

# --- 20b. no two slides share a title -----------------------------------------
# A deck is navigated by its titles. Two slides called "Incidents" is a reader looking at the
# wrong one and not knowing. Found by actually opening the deck: the section summary and its
# item slides both resolved to the section name, because that section's only item map is
# named after the section.
res=$("$PY" - "$work/full.pptx" <<'PY'
import re, sys, zipfile
zf = zipfile.ZipFile(sys.argv[1])
titles = []
for i in range(1, 1 + len([n for n in zf.namelist()
                           if n.startswith("ppt/slides/slide") and n.endswith(".xml")])):
    runs = re.findall(r"<a:t>(.*?)</a:t>", zf.read(f"ppt/slides/slide{i}.xml").decode())
    titles.append(runs[1] if len(runs) > 1 else f"<slide {i} has no title>")
dupes = sorted({t for t in titles if titles.count(t) > 1})
print(",".join(dupes))
PY
)
if [ -z "$res" ]; then ok "no two slides in the deck share a title"
else bad "no two slides in the deck share a title" "duplicated: $res"; fi

# --- 21-23. the assembler consumes and never derives --------------------------
# A figure in the pack that no producer computed would be the assembler doing a producer's
# job. Compare each headline against the producer's own analysis output.
res=$("$PY" - "$skill" "$J" <<'PY'
import json, subprocess, sys, os
skill, packfile = sys.argv[1], sys.argv[2]
root = os.path.dirname(skill)
pack = json.load(open(packfile))
sys.path.insert(0, os.path.join(skill, "scripts"))
import assemble_pack as A
manifest = A.load_manifest(os.path.join(skill, "examples", "pack.manifest.json"))
stores = {e["section"]: e.get("storePath") for e in manifest["sections"]}
problems = []
for h in pack["headlines"]:
    analysis, reason = A.run_producer(h["section"], stores[h["section"]], pack["asOf"], root)
    if analysis is None:
        problems.append(f"{h['section']}: {reason}")
        continue
    values = dict(A.PRODUCERS[h["section"]]["headline"](analysis))
    if values.get(h["label"]) != h["value"]:
        problems.append(f"{h['section']}/{h['label']}: pack says {h['value']}, "
                        f"producer says {values.get(h['label'])}")
print("\n".join(problems))
PY
)
if [ -z "$res" ]; then ok "every headline in the pack matches what its producer computed"
else bad "every headline in the pack matches what its producer computed" "$res"; fi
if grep -q "The pack calculates nothing" "$work/full.html"; then
  ok "and the pack says so on the page"
else
  bad "and the pack says so on the page" "absent"
fi
eq "the asOf drift across sections is surfaced, not smoothed over" "True" \
   "$(q 'any("dated differently" in w for w in p["provenance"]["warnings"])')"

# --- 24-27. refusals ----------------------------------------------------------
echo '{"R-001": "a flat map, which is the dangerous shape"}' > "$work/flat.board.json"
variant "$work/flat.manifest.json" 'import os
for e in m["sections"]:
    if e["section"] == "risk":
        e["translations"] = os.environ["FLAT"]'
if "$PY" "$A" assemble "$work/flat.manifest.json" --out "$work/x.json" >/dev/null 2>&1; then
  bad "a flat per-item map is refused" "it assembled"
else
  ok "a flat per-item map is refused"
fi
variant "$work/v2.manifest.json" 'import json as J, os
side = J.load(open(m["sections"][0]["translations"]))
side["contractVersion"] = 2
J.dump(side, open(os.environ["V2"], "w"))
m["sections"][0]["translations"] = os.environ["V2"]'
if "$PY" "$A" assemble "$work/v2.manifest.json" --out "$work/x.json" >/dev/null 2>&1; then
  bad "an unknown contractVersion is refused" "it assembled"
else
  ok "an unknown contractVersion is refused"
fi
variant "$work/unknown.manifest.json" 'm["sections"].append(
    {"section": "budget", "translations": "nowhere.json"})'
if "$PY" "$A" assemble "$work/unknown.manifest.json" --out "$work/x.json" >/dev/null 2>&1; then
  bad "an unknown section name is refused" "it assembled"
else
  ok "an unknown section name is refused"
fi
if "$PY" "$A" assemble "$work/nope.json" --out "$work/x.json" >/dev/null 2>&1; then
  bad "a manifest that does not exist is refused" "it assembled"
else
  ok "a manifest that does not exist is refused"
fi

# --- 29. The shipped example must announce itself as a specimen ---------------
# Two independent reference-mode trigger cases (`P1`, `P3`, 2026-07-31) named the same
# hazard without being prompted: the example manifest assembles and renders a complete,
# professional-looking pack dated to the current quarter, so running the documented
# workflow with no data of your own produces "a finished board deck about a company that
# doesn't exist, correctly dated to your quarter". Both refused, which is the refusal
# working — but the refusal is a model behaviour and this is a file, so the file says it.
#
# The marker lives in `client` and `period` because those are display-only. `asOf` cannot
# carry it: it is passed to every producer as `--today`, so moving it would change every
# age band, clock state and overdue list in the pack — the fixture would stop meaning what
# it was built to mean. Marking the two free fields gets the same result for nothing.
#
# Checked on the RENDERED artifacts, in both formats, because that is what reaches a reader.
if grep -qi "SPECIMEN" "$work/full.html" && grep -qi "fictional" "$work/full.html"; then
  ok "the shipped example renders as an identified specimen, not as a real pack"
else
  bad "the shipped example renders as an identified specimen, not as a real pack" \
      "neither marker survived into the HTML cover"
fi

# --- 32-36. Decision altitude -------------------------------------------------
# The failure this prevents is a board being asked to decide things management already owns,
# which teaches a board to skim the one slide it must not skim. The failure it must NOT
# introduce is the opposite: a real board decision quietly filed away as a management action.
# So both directions are checked, and the unmarked case is checked explicitly — absent means
# unclassified, and unclassified stays in front of the board.
eq "the shipped example separates board decisions from management actions" "10 3" \
   "$(q 'str(sum(1 for d in p["decisions"] if d["altitude"] != "management")) + " " + str(sum(1 for d in p["decisions"] if d["altitude"] == "management"))')"
eq "and every decision carries an explicit altitude or an explicit None" "True" \
   "$(q 'all("altitude" in d for d in p["decisions"])')"

# An unmarked ask must reach the board, not the management block. Built here rather than
# asserted about the fixture, because the fixture is fully marked and so cannot show it.
"$PY" - "$skill" "$work" <<'PY'
import json, sys
sys.path.insert(0, sys.argv[1] + "/scripts")
sys.path.insert(0, sys.argv[1] + "/renderers")
import assemble_pack as A
from render_pack import split_by_altitude
mixed = A.consolidate_decisions([
    {"section": "risk", "itemCount": 0, "decisions": A.normalise_decisions(
        ["Unmarked ask.", {"text": "Board ask.", "altitude": "board"},
         {"text": "Management ask.", "altitude": "management"}], "x.json")}])
board, mgmt = split_by_altitude(mixed)
json.dump({"board": [d["text"] for d in board], "mgmt": [d["text"] for d in mgmt]},
          open(sys.argv[2] + "/altitude.json", "w"))
PY
eq "an unmarked ask stays in front of the board" "['Unmarked ask.', 'Board ask.']" \
   "$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["board"])' "$work/altitude.json")"
eq "and only an explicitly marked ask leaves it" "['Management ask.']" \
   "$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["mgmt"])' "$work/altitude.json")"

# The split must survive into what a reader actually opens, not just the content model.
if grep -q "Management actions" "$work/full.html" \
   && grep -q "Name an owner for supply-chain risk management" "$work/full.html"; then
  ok "the management block reaches the rendered HTML"
else
  bad "the management block reaches the rendered HTML" \
      "the heading or a known management ask did not survive rendering"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'assembly: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'assembly: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'assembly: all %s checks passed\n' "$checks"
