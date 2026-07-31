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

EXPECTED_CHECKS=27
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
eq "ten headline figures, two from each producer" "10" "$(q 'len(p["headlines"])')"
eq "and each names the section that computed it" "True" \
   "$(q 'all(h["section"] in {s["section"] for s in p["sections"]} for h in p["headlines"])')"
# The assembler must not invent a figure the producer did not compute. Every value here is
# an int lifted from an analysis; a string or a float would mean something was formatted or
# derived on the way through.
eq "every figure is an integer lifted from an analysis, not a derived or formatted one" "True" \
   "$(q 'all(isinstance(h["value"], int) for h in p["headlines"])')"

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

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'assembly: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'assembly: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'assembly: all %s checks passed\n' "$checks"
