#!/usr/bin/env bash
# CAC-EL-1 fixes the escalation KEYS. It does not fix the TYPE of `evidence`, and both shapes
# have to reach both deliverables.
#
# `risk-register`, `metrics-register` and `exceptions-register` emit a structured delta —
# `{from, to, baseline, detail}` — because a band crossing is a movement and both ends of it
# are the fact. `vendor-register` and `ai-register` emit a finished sentence. Both are valid
# producer output under the contract.
#
# `render_pack.py` assumed the dict at two call sites. A pack carrying a `vendor` or `ai`
# section assembled cleanly and then died:
#
#     AttributeError: 'str' object has no attribute 'get'
#
# It died in the HTML path, which runs first, so a PowerPoint-only request was blocked by a
# deliverable it had not asked for. Two shipped sections could not reach a page for two
# releases, and an external release test found it rather than this suite — because the
# specimen manifest carried five sections and every eval here builds on the specimen.
#
# So this suite does what that test recommended, and does it three ways: vendor-only, AI-only,
# and all seven. Vendor-only and AI-only matter separately from the seven — a combined pack
# has dict evidence in it, so a renderer that crashed only on the FIRST string would still
# look fine if the risk section happened to be rendered first.
#
# The properties, in both directions:
#
#   1. Both shapes are actually present. A run over evidence that turned out to be all one
#      type would pass having proved nothing, which is the shape of every vacuous eval.
#   2. String evidence reaches the page UNCHANGED. Not summarised, not re-wrapped.
#   3. Dict evidence still renders through its `detail`, and carries the movement and the
#      baseline with it.
#   4. No raw Python dict repr anywhere on either deliverable. That is the failure mode a
#      naive `str(evidence)` fix would introduce, and it is the one a reader cannot diagnose:
#      `{'from': 12, 'to': 15}` on a board page reads as a data problem, not a code one.
#   5. Both deliverables are written, for all three manifests. Six files.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
repo="$(cd "$skill/../.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=18
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

A="$skill/scripts/assemble_pack.py"
R="$skill/renderers/render_pack.py"
M="$skill/examples/pack.manifest.json"
echo "mixed-evidence: $($PY -V 2>&1)"

# Three manifests from the shipped specimen, paths absolutised so a copy in a temp directory
# still resolves — the same reason _variant.py exists.
"$PY" - "$M" "$work" <<'PYEOF'
import json, os, sys
src, work = sys.argv[1], sys.argv[2]
base = os.path.dirname(os.path.abspath(src))
m = json.load(open(src, encoding="utf-8"))
for entry in m.get("sections") or []:
    for key in ("store", "translations"):
        if entry.get(key):
            entry[key] = os.path.normpath(os.path.join(base, entry[key]))
if m.get("throughLine"):
    m["throughLine"] = os.path.normpath(os.path.join(base, m["throughLine"]))
picks = {"vendor-only": ("vendor",), "ai-only": ("ai",),
         "seven": tuple(s["section"] for s in m["sections"])}
for name, keep in picks.items():
    out = dict(m, sections=[s for s in m["sections"] if s["section"] in keep])
    json.dump(out, open(os.path.join(work, name + ".manifest.json"), "w",
                        encoding="utf-8"), indent=2)
if len(picks["seven"]) != 7:
    raise SystemExit("the specimen carries %d sections, not 7" % len(picks["seven"]))
PYEOF
if [ ! -f "$work/seven.manifest.json" ]; then
  echo "mixed-evidence: could not build the manifests — the specimen moved"; exit 1
fi

for name in vendor-only ai-only seven; do
  if "$PY" "$A" assemble "$work/$name.manifest.json" --out "$work/$name.json" \
       >/dev/null 2>"$work/$name.aerr"; then
    ok "$name assembles"
  else
    bad "$name assembles" "$(tail -2 "$work/$name.aerr")"
    continue
  fi
  # Both deliverables in one call, which is how the crash presented: the HTML path runs
  # first, so asking only for a deck still went through it.
  if (cd "$skill/renderers" && "$PY" "$R" --in "$work/$name.json" \
        --html "$work/$name.html" --pptx "$work/$name.pptx") \
       >/dev/null 2>"$work/$name.rerr"; then
    ok "...and renders BOTH deliverables"
  else
    bad "$name renders both deliverables" "$(tail -3 "$work/$name.rerr" | tr '\n' ' ')"
    continue
  fi
  if [ -s "$work/$name.html" ] && [ -s "$work/$name.pptx" ]; then
    ok "...both files are non-empty"
  else
    bad "$name writes non-empty files" "one of the two is zero bytes"
  fi
done

# --- the seven-section pack is where both shapes meet -------------------------
res=$("$PY" - "$work/seven.json" "$work/seven.html" "$work/seven.pptx" <<'PYEOF'
import html as H, json, re, sys, zipfile
pack = json.load(open(sys.argv[1], encoding="utf-8"))
page = open(sys.argv[2], encoding="utf-8").read()
z = zipfile.ZipFile(sys.argv[3])
deck = "".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist()
               if re.match(r"ppt/slides/slide\d+\.xml", n))
esc = pack.get("escalations") or []
strings = [e for e in esc if isinstance(e.get("evidence"), str) and e["evidence"].strip()]
dicts = [e for e in esc if isinstance(e.get("evidence"), dict)]
problems = []

# 1. anti-vacuity
if len(strings) < 1 or len(dicts) < 1:
    problems.append("BOTHSHAPES only %d string and %d dict — this proved nothing about the "
                    "mix" % (len(strings), len(dicts)))
else:
    print("BOTHSHAPES %d string, %d dict" % (len(strings), len(dicts)))

# 2. string evidence, unchanged, on both surfaces
for e in strings[:6]:
    text = e["evidence"]
    if H.escape(text) not in page:
        problems.append("STRINGHTML %s: %r is not on the page verbatim"
                        % (e["subjectRef"], text[:60]))
    if H.escape(text) not in deck and text not in deck:
        problems.append("STRINGDECK %s: %r is not in the deck verbatim"
                        % (e["subjectRef"], text[:60]))

# 3. dict evidence still renders through `detail`, with its movement and baseline
for e in dicts[:6]:
    ev = e["evidence"]
    detail = (ev.get("detail") or "").strip()
    if detail and H.escape(detail) not in page:
        problems.append("DICTHTML %s: the detail is not on the page" % e["subjectRef"])
    if ev.get("baseline") and H.escape("against %s" % ev["baseline"]) not in page:
        problems.append("DICTBASE %s: the baseline is not carried" % e["subjectRef"])
    if ev.get("from") not in (None, "") and ev.get("to") not in (None, ""):
        moved = H.escape("%s -> %s" % (ev["from"], ev["to"]))
        if moved not in page:
            problems.append("DICTMOVE %s: the movement is not carried" % e["subjectRef"])

# 4. no raw dict repr on either surface
for label, blob in (("page", page), ("deck", deck)):
    for needle in ("{'from'", "{'detail'", "'baseline':"):
        if needle in blob:
            problems.append("REPR a raw dict reached the %s: %s" % (label, needle))
print("\n".join(problems))
PYEOF
)
both=$(printf '%s\n' "$res" | grep '^BOTHSHAPES' || true)
probs=$(printf '%s\n' "$res" | grep -v '^BOTHSHAPES' | grep -v '^$' || true)

case "$both" in
  "BOTHSHAPES only"*|"") bad "the specimen carries BOTH evidence shapes" \
                             "${both:-the scan produced nothing}" ;;
  *) ok "the specimen carries both evidence shapes — ${both#BOTHSHAPES }" ;;
esac
for kind in STRINGHTML:"string evidence reaches the document unchanged" \
            STRINGDECK:"string evidence reaches the deck unchanged" \
            DICTHTML:"dict evidence still renders through its detail" \
            DICTBASE:"...carrying the baseline it was measured against" \
            DICTMOVE:"...and the movement, both ends of it" \
            REPR:"no raw Python dict reaches either deliverable"; do
  tag="${kind%%:*}"; label="${kind#*:}"
  hit=$(printf '%s\n' "$probs" | grep "^$tag " || true)
  if [ -z "$hit" ]; then ok "$label"; else bad "$label" "$(printf '%s' "$hit" | head -2)"; fi
done

# --- the shape handler itself, both branches ----------------------------------
if "$PY" -c '
import importlib.util, sys
sys.path.insert(0, sys.argv[1].rsplit("/", 1)[0])
spec = importlib.util.spec_from_file_location("rp", sys.argv[1])
rp = importlib.util.module_from_spec(spec); spec.loader.exec_module(rp)
assert rp.evidence_text("a plain sentence") == "a plain sentence", "string passthrough"
assert rp.evidence_text({"detail": "d", "from": 1, "to": 2, "baseline": "Q3"}) == \
    "d (1 -> 2; against Q3)", rp.evidence_text({"detail": "d", "from": 1, "to": 2,
                                                "baseline": "Q3"})
assert rp.evidence_text({}) == "", rp.evidence_text({})
assert rp.evidence_text(None) == "", rp.evidence_text(None)
# An unrecognised dict SAYS it was unrecognised rather than printing itself.
out = rp.evidence_text({"surprise": 1})
assert "structured evidence" in out and "surprise" in out, out
' "$R" 2>"$work/fn.err"; then
  ok "evidence_text handles a sentence, a delta, an empty dict and an unknown shape"
else
  bad "evidence_text handles every shape" "$(cat "$work/fn.err" | tail -3)"
fi

# The teeth. A renderer that went back to `.get("detail")` on a string must fail here, so the
# mutation is applied to a COPY and the render is expected to die.
mkdir -p "$work/mutant/renderers" "$work/mutant/scripts"
cp "$skill"/renderers/*.py "$work/mutant/renderers/"
cp "$skill"/scripts/*.py "$work/mutant/scripts/" 2>/dev/null || true
"$PY" - "$work/mutant/renderers/render_pack.py" <<'PYEOF'
import sys
p = sys.argv[1]
t = open(p, encoding="utf-8").read()
n = t.replace('    return str(evidence or "")',
              '    return (evidence or {}).get("detail") or ""')
if n == t:
    raise SystemExit("the mutation no longer applies — evidence_text moved (GP-1.5)")
open(p, "w", encoding="utf-8").write(n)
PYEOF
if (cd "$work/mutant/renderers" && "$PY" render_pack.py --in "$work/seven.json" \
      --html "$work/m.html" --pptx "$work/m.pptx") >/dev/null 2>&1; then
  bad "a renderer that assumes the dict shape FAILS this suite" \
      "the mutated renderer rendered cleanly — this suite would not have caught the defect"
else
  ok "and a renderer that assumes the dict shape fails: the defect is detectable"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'mixed-evidence: ran %s checks, expected %s — a case stopped executing\n' \
         "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'mixed-evidence: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'mixed-evidence: all %s checks passed\n' "$checks"
