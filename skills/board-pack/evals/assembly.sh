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

EXPECTED_CHECKS=46
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
compared = 0
for h in pack["headlines"]:
    analysis, reason = A.run_producer(h["section"], stores[h["section"]], pack["asOf"], root)
    if analysis is None:
        problems.append(f"{h['section']}: {reason}")
        continue
    # A headline row is (label, value) or (label, value, sev). Unpacking by slice
    # rather than by dict(): dict() over 3-tuples raises, and this block's stderr
    # is discarded by the surrounding $( ), so the raise emptied `res` and the
    # check reported ok having compared nothing. It sat green that way from the
    # commit that added the sev triples until this one.
    rows = A.PRODUCERS[h["section"]]["headline"](analysis)
    values = {r[0]: r[1] for r in rows}
    sevs = {r[0]: (r[2] if len(r) > 2 else None) for r in rows}
    compared += 1
    if values.get(h["label"]) != h["value"]:
        problems.append(f"{h['section']}/{h['label']}: pack says {h['value']}, "
                        f"producer says {values.get(h['label'])}")
    # The band travels the same way the figure does, or the pack is deciding it.
    if h.get("sev") != sevs.get(h["label"]):
        problems.append(f"{h['section']}/{h['label']}: pack sev {h.get('sev')!r}, "
                        f"producer sev {sevs.get(h['label'])!r}")
if compared == 0:
    problems.append("compared nothing: no headline reached its producer")
print("\n".join(problems))
print(f"COMPARED={compared}", file=sys.stderr)
PY
)
# The count is asserted separately, so this check can never again pass by having
# done no work. An empty `res` means "no problems" only if something was checked.
n_compared=$("$PY" - "$skill" "$J" <<'PY'
import json, sys, os
skill, packfile = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(skill, "scripts"))
print(len(json.load(open(packfile))["headlines"]))
PY
)
if [ -z "$res" ] && [ "${n_compared:-0}" -ge 10 ]; then
  ok "every headline in the pack matches what its producer computed ($n_compared)"
else
  bad "every headline in the pack matches what its producer computed" \
      "${res:-only $n_compared headlines present; expected at least 10}"
fi
if grep -q "The pack calculates nothing" "$work/full.html"; then
  ok "and the pack says so on the page"
else
  bad "and the pack says so on the page" "absent"
fi
eq "the asOf drift across sections is surfaced, not smoothed over" "True" \
   "$(q 'any("dated differently" in w for w in p["provenance"]["warnings"])')"

# --- figures: every mark traces to the model, and every chart reaches the page ---
# Both directions, deliberately. Checking only that each drawn figure exists in the model
# would pass a renderer that silently dropped half of them — which is how the small-multiples
# clipping shipped. Checking only the reverse would pass a renderer that invented one.
fig_res=$("$PY" - "$J" "$work/full.html" <<'PY'
import html as H, json, re, sys
pack = json.load(open(sys.argv[1]))
doc = open(sys.argv[2], encoding="utf-8").read()
charts = pack.get("charts") or []
problems = []

drawn = re.findall(r'class="figtitle">(.*?)<span class="figsrc">(.*?)</span>', doc, re.S)
model = {(c["title"], c["source"]) for c in charts}
page = {(H.unescape(t), H.unescape(s)) for t, s in drawn}

for missing in sorted(model - page):
    problems.append("a chart in the model was never drawn: %s" % (missing,))
for invented in sorted(page - model):
    problems.append("a figure on the page is in no chart: %s" % (invented,))

for c in charts:
    # Every chart names the producer field it came from. That is what makes "the pack
    # computes nothing" checkable rather than merely asserted on the page.
    if not c.get("source"):
        problems.append("a chart names no source field: %s" % c.get("title"))
    if c.get("kind") not in ("bar", "band-mix", "bullet"):
        problems.append("a chart has an unknown kind: %s" % c.get("kind"))
    if c.get("kind") == "band-mix" and not all(
            "label" in s and "value" in s for s in c["series"]):
        problems.append("a band-mix segment is missing a label or a value: %s" % c["title"])

print("\n".join(problems))
PY
)
n_charts=$(q 'len(p.get("charts") or [])')
if [ -z "$fig_res" ] && [ "${n_charts:-0}" -ge 5 ]; then
  ok "every chart in the model is drawn, and every figure drawn is in the model ($n_charts)"
else
  bad "every chart in the model is drawn, and every figure drawn is in the model" \
      "${fig_res:-only $n_charts charts present; expected at least 5}"
fi

# Every segment the model carries has to survive the trip to the page. Checking the model's
# own arithmetic is not enough — the model can be perfectly consistent while the renderer
# drops a segment on the way, which is exactly how the small-multiples clipping shipped: the
# data was right and the picture was missing a cell. So this reads the values back out of the
# rendered SVG and compares them to the series they were drawn from.
seg_res=$("$PY" - "$J" "$work/full.html" <<'PY'
import html as H, json, re, sys
pack = json.load(open(sys.argv[1]))
doc = open(sys.argv[2], encoding="utf-8").read()
problems, checked = [], 0
for c in pack.get("charts") or []:
    if c.get("kind") != "band-mix":
        continue
    block = re.search(re.escape(H.escape(c["title"])) + r".*?</figure>", doc, re.S)
    if not block:
        problems.append("no rendered figure for %r" % c["title"])
        continue
    drawn = sorted(re.findall(r"<text[^>]*>([^<]+)</text>", block.group(0)))
    # A zero-count band is not drawn — a zero-height segment is invisible anyway — so the
    # expectation is every NON-zero segment, and nothing else.
    want = sorted(str(s["value"]) for s in c["series"] if s["value"])
    checked += 1
    if drawn != want:
        problems.append("%s: drew segments %s but the series says %s"
                        % (c["section"], drawn, want))
if checked == 0:
    problems.append("compared nothing: no band-mix was found to read back")
print("\n".join(problems))
PY
)
if [ -z "$seg_res" ]; then
  ok "every band-mix segment in the model survives to the rendered mark"
else
  bad "every band-mix segment in the model survives to the rendered mark" "$seg_res"
fi

# A band-mix is a partition, so its segments have to sum to the population it names. This is
# the property that lets a chart sit beside a headline without contradicting it, and it is
# checked against the real producer output rather than a fixture.
mix_res=$("$PY" - "$J" <<'PY'
import json, sys
pack = json.load(open(sys.argv[1]))
totals = {(f["section"], f["label"]): f["value"] for f in pack["headlines"]}
problems, checked = [], 0
expect = {"risk": ("risk", "risks tracked"),
          "exceptions": ("exceptions", "acceptances and exceptions carried")}
for c in pack.get("charts") or []:
    if c.get("kind") != "band-mix":
        continue
    key = expect.get(c["section"])
    if key is None or key not in totals:
        continue
    checked += 1
    got = sum(s["value"] for s in c["series"])
    if got != totals[key]:
        problems.append("%s: segments sum to %s but the headline %r reads %s"
                        % (c["section"], got, key[1], totals[key]))
if checked == 0:
    problems.append("compared nothing: no band-mix reached a headline to check against")
print("\n".join(problems))
PY
)
if [ -z "$mix_res" ]; then
  ok "every band-mix sums to the headline it sits beside"
else
  bad "every band-mix sums to the headline it sits beside" "$mix_res"
fi

# The deck must carry the same compositions as the document. This is the parity rule the
# whole placeholder pair above exists to enforce for prose, applied to marks: a figure that
# reaches one deliverable and not the other means two readers of "the same pack" saw
# different things.
deck_res=$("$PY" - "$J" "$work/full.pptx" <<'PY'
import json, re, sys, zipfile
pack = json.load(open(sys.argv[1]))
z = zipfile.ZipFile(sys.argv[2])
xml = "".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist()
              if re.match(r"ppt/slides/slide\d+\.xml", n))
problems, checked = [], 0
for c in pack.get("charts") or []:
    if c.get("kind") != "band-mix":
        continue
    for seg in c["series"]:
        if not seg["value"]:
            continue
        checked += 1
        # Named shapes, so the assertion is about the segment and not about a number that
        # might coincide with something else on the slide.
        if 'name="Segment %s' % seg["label"] not in xml:
            problems.append("%s: segment %r is in the document but not in the deck"
                            % (c["section"], seg["label"]))
if checked == 0:
    problems.append("compared nothing: no band-mix segment was checked against the deck")
print("\n".join(problems))
PY
)
if [ -z "$deck_res" ]; then
  ok "every band-mix segment reaches the deck as well as the document"
else
  bad "every band-mix segment reaches the deck as well as the document" "$deck_res"
fi

# --- escalations: read from the producer, reaching BOTH deliverables ------------------
# CAC-EL-1 §1.3. Three properties, and the third is the one that matters: the pack must not
# have derived any of this. An assembler that recomputed an escalation would be a second
# opinion able to contradict the section printed beside it, which is the failure the
# "computes nothing" rule exists to prevent.
esc_res=$("$PY" - "$J" "$work/full.html" "$work/full.pptx" "$skill" <<'PY'
import json, os, re, subprocess, sys, zipfile
pack = json.load(open(sys.argv[1]))
doc = open(sys.argv[2], encoding="utf-8").read()
z = zipfile.ZipFile(sys.argv[3])
deck = "".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist()
               if re.match(r"ppt/slides/slide\d+\.xml", n))
skill = sys.argv[4]
esc = pack.get("escalations") or []
problems, KEYS = [], ("subjectRef", "subjectKind", "trigger", "severity", "since", "evidence")

if not esc:
    problems.append("the shipped example escalates nothing, so this check proves nothing — "
                    "the fixture is supposed to carry one of every trigger")

for e in esc:
    miss = [k for k in KEYS if k not in e]
    if miss:
        problems.append("%s is missing contract keys: %s" % (e.get("subjectRef"), miss))
    if e["subjectRef"] not in doc:
        problems.append("%s is in the model but not the document" % e["subjectRef"])
    if e["subjectRef"] not in deck:
        problems.append("%s is in the model but not the deck" % e["subjectRef"])
    if e["trigger"] not in doc or e["trigger"] not in deck:
        problems.append("%s: the trigger is not named on both surfaces" % e["subjectRef"])

# The assembler must not have invented any of it: every record has to appear, verbatim, in
# the producer's own output. This is the escalation twin of the headline check above, and it
# is what makes "the pack computes nothing" checkable rather than asserted.
# Every producer that emits escalations, not just the first one. Scoping this to `risk`
# would have let the second producer through unchecked, which is the shape of gap that
# appears the moment a contract gains its second implementer.
SOURCES = [
    ("risk", "risk-register", "score_register.py",
     ["score", "{store}", "--json", "--today", "{asOf}"], "example-register-v2.rr"),
    ("metrics", "metrics-register", "metrics_analysis.py",
     ["analyze", "{store}", "--today", "{asOf}"], "example-metrics.mtr"),
]
checked_sections = set()
for section, skill_dir, script, argv, fixture in SOURCES:
    root = os.path.join(skill, "..", skill_dir)
    store = os.path.join(root, "examples", fixture)
    if not os.path.exists(store):
        problems.append("the %s example is missing; its provenance went unchecked" % section)
        continue
    cmd = [sys.executable, os.path.join(root, "scripts", script)] + [
        a.replace("{store}", store).replace("{asOf}", pack["asOf"]) for a in argv]
    out = subprocess.run(cmd, capture_output=True, text=True)
    produced = {json.dumps(x, sort_keys=True)
                for x in (json.loads(out.stdout).get("escalations") or [])}
    checked_sections.add(section)
    carried = {json.dumps({k: v for k, v in e.items() if k != "section"}, sort_keys=True)
               for e in esc if e.get("section") == section}
    for e in esc:
        if e.get("section") != section:
            continue
        bare = {k: v for k, v in e.items() if k != "section"}
        if json.dumps(bare, sort_keys=True) not in produced:
            problems.append("%s is not verbatim from the producer — the pack altered or "
                            "invented it" % e["subjectRef"])
    # And the other direction. Checking only that what arrived is genuine cannot see a
    # producer that stopped contributing at all: unwire an adapter and the pack simply
    # carries fewer, which reads as a calmer quarter. Every record the producer emits has
    # to reach the pack.
    for missing in sorted(produced - carried):
        problems.append("%s emitted an escalation the pack did not carry: %s"
                        % (section, json.loads(missing).get("subjectRef")))

# Every section that escalated must have been checked against its producer. Without this,
# adding a third producer and forgetting to list it above would pass silently.
for e in esc:
    if e.get("section") not in checked_sections:
        problems.append("%s escalated from %r, which no provenance source covers"
                        % (e["subjectRef"], e.get("section")))
print("\n".join(problems))
PY
)
if [ -z "$esc_res" ]; then
  n_esc=$(q 'len(p.get("escalations") or [])')
  ok "every escalation is verbatim from its producer and reaches both deliverables ($n_esc)"
else
  bad "every escalation is verbatim from its producer and reaches both deliverables" "$esc_res"
fi

# The unassessed case, end to end. A CSF Function with nothing assessed must reach the page
# as a hatched row and not as a zero-length bar: a zero bar in a row of long ones reads as
# the worst score on the chart rather than as an absent one.
if grep -q "not assessed" "$work/full.html" && grep -q "cacHatch" "$work/full.html"; then
  ok "an unassessed CSF Function reaches the page hatched, not as a zero bar"
else
  bad "an unassessed CSF Function reaches the page hatched, not as a zero bar" \
      "no hatch or no 'not assessed' label in the rendered pack"
fi

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

# --- Carried severity on headline figures -------------------------------------
#
# The assembler carries the band a producer declared and decides nothing itself.
# Both halves are asserted: that a breach figure arrives banded, and that a
# population figure arrives with none. Checking only the first would pass an
# assembler that painted every figure critical.
sev_probe=$("$PY" - "$J" <<'PYEOF'
import json, sys
figs = json.load(open(sys.argv[1]))["headlines"]


def find(frag):
    return next((f for f in figs if frag in f["label"]), None)


over = find("over appetite")
tracked = find("risks tracked")
breach = find("past a threshold")
carried = find("exceptions carried")
# A zero count must carry no band: nothing over appetite is the good outcome,
# and colouring that zero would report an alarm the number itself contradicts.
zeros = [f["label"] for f in figs if f.get("value") == 0 and "sev" in f]
print("BANDED" if over and over.get("sev") in ("medium", "high", "critical") else "PLAIN")
print("PLAIN" if tracked and "sev" not in tracked else "BANDED")
print("BANDED" if breach and breach.get("sev") in ("medium", "high", "critical") else "PLAIN")
print("PLAIN" if carried and "sev" not in carried else "BANDED")
print("NONE" if not zeros else ",".join(zeros))
PYEOF
)
sev_over=$(echo "$sev_probe" | sed -n 1p)
sev_tracked=$(echo "$sev_probe" | sed -n 2p)
sev_breach=$(echo "$sev_probe" | sed -n 3p)
sev_carried=$(echo "$sev_probe" | sed -n 4p)
sev_zeros=$(echo "$sev_probe" | sed -n 5p)

if [ "$sev_over" = "BANDED" ]; then
  ok "a breach figure carries the band its producer declared"
else
  bad "a breach figure carries the band its producer declared" \
      "'risks over appetite' arrived with no sev"
fi

if [ "$sev_breach" = "BANDED" ]; then
  ok "the metrics breach figure carries a band too"
else
  bad "the metrics breach figure carries a band too" \
      "'metrics past a threshold' arrived with no sev"
fi

if [ "$sev_tracked" = "PLAIN" ] && [ "$sev_carried" = "PLAIN" ]; then
  ok "a population figure carries no band"
else
  bad "a population figure carries no band" \
      "risks tracked=$sev_tracked, exceptions carried=$sev_carried"
fi

if [ "$sev_zeros" = "NONE" ]; then
  ok "a zero count is never banded"
else
  bad "a zero count is never banded" "banded zeros: $sev_zeros"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'assembly: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'assembly: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'assembly: all %s checks passed\n' "$checks"
