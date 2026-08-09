#!/usr/bin/env bash
# The board section contract, asserted across both shipped consumers.
#
# The contract itself is prose (references/section-contract.md); this is what holds the
# two renderers to it. It lives under board-pack rather than in either consumer because
# neither consumer owns the contract — the assembler does, and in Phase D it will validate
# every producer against the same rules these checks pin.
#
# The load-bearing assertion is #3/#4: a sidecar written before the contract existed must
# render BYTE-IDENTICALLY to a stamped one. That is what makes the retrofit additive. An
# equality check on the bytes is the only version of that claim worth making — "it still
# renders" would pass even if the stamp changed the page.
#
# Runs on the declared floor, like every other suite here, and refuses to report success
# over a partial run: EXPECTED_CHECKS is asserted at the end, so a case that silently stops
# executing fails loudly instead of printing a green count over half a suite.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=54
checks=0
fails=0

ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

RR="$repo/skills/risk-register"
NC="$repo/skills/nist-csf"
MX="$repo/skills/metrics-register"
XR="$repo/skills/exceptions-register"
IM="$repo/skills/incident-materiality"
CONTRACT="$repo/skills/board-pack/references/section-contract.md"

echo "section-contract: $($PY -V 2>&1)"

# --- 0. the contract doc names every section and its exact item keys ----------------
for pair in "risk:risks" "posture:gaps" "metrics:metrics" "exceptions:acceptances" "incident:incidents"; do
  sect="${pair%%:*}"; key="${pair##*:}"
  if grep -q "\`$sect\`" "$CONTRACT" && grep -q "\`$key\`" "$CONTRACT"; then
    ok "contract names section '$sect' and item key '$key'"
  else
    bad "contract names section '$sect' and item key '$key'" "one of them is absent"
  fi
done

# --- 1. build the two analyses the renderers consume --------------------------------
$PY "$NC/scripts/profile_analysis.py" analyze "$NC/examples/example-profile.csfp" \
    --today 2026-07-26 --out "$work/csf.json" >/dev/null 2>&1
$PY "$RR/scripts/score_register.py" score "$RR/examples/example-register-v2.rr" --json \
    > "$work/rr.json" 2>/dev/null

render_rr() {  # render_rr <sidecar> <out>  -> exit status of the renderer
  $PY "$RR/renderers/render_board.py" "$RR/examples/example-register-v2.rr" "$2" \
      --translations "$1" --offline >/dev/null 2>"$work/err.txt"
}
render_rr_any() {  # render_rr_any <renderer> <sidecar> <out>
  $PY "$RR/renderers/$1.py" "$RR/examples/example-register-v2.rr" "$3" \
      --translations "$2" --offline >/dev/null 2>"$work/err.txt"
}
render_nc() {  # render_nc <sidecar> <out>
  (cd "$NC/renderers" && $PY render_executive.py --in "$work/csf.json" \
      --translations "$1" --out "$2" --offline) >/dev/null 2>"$work/err.txt"
}

render_mx() {  # render_mx <sidecar> <out>
  (cd "$MX/renderers" && $PY render_executive.py --in "$work/mx.json" \
      --translations "$1" --out "$2" --offline) >/dev/null 2>"$work/err.txt"
}
$PY "$MX/scripts/metrics_analysis.py" analyze "$MX/examples/example-metrics.mtr" \
    --today 2026-07-31 --out "$work/mx.json" >/dev/null 2>&1

render_xr() {  # render_xr <sidecar> <out>
  (cd "$XR/renderers" && $PY render_board.py --in "$work/xr.json" \
      --translations "$1" --out "$2" --offline) >/dev/null 2>"$work/err.txt"
}
$PY "$XR/scripts/exceptions_register.py" analyze "$XR/examples/example.exc" \
    --today 2026-07-31 --out "$work/xr.json" >/dev/null 2>&1

render_im() {  # render_im <sidecar> <out>
  (cd "$IM/renderers" && $PY render_board.py --in "$work/im.json" \
      --translations "$1" --out "$2" --offline) >/dev/null 2>"$work/err.txt"
}
$PY "$IM/scripts/incident_analysis.py" analyze "$IM/examples/example-incident.inc" \
    --today 2026-07-31 --now 2026-07-31T09:00:00+00:00 --out "$work/im.json" >/dev/null 2>&1

# Strip the contract keys to make a pre-contract sidecar, and mutate them to make the
# refusal cases. Written by the same script so the only difference is the keys involved.
$PY - "$RR/references/example-translations.json" "$NC/references/example-translations.json" "$work" \
    "$MX/examples/example-translations.json" \
    "$XR/examples/example-translations.json" \
    "$IM/examples/example-translations.json" <<'PY'
import json, sys
rr_src, nc_src, work = sys.argv[1], sys.argv[2], sys.argv[3]
rr, nc = json.load(open(rr_src)), json.load(open(nc_src))

def drop(d):
    d = dict(d); d.pop("contractVersion", None); d.pop("section", None); return d

json.dump(drop(rr), open(f"{work}/rr-precontract.json", "w"))
json.dump(drop(nc), open(f"{work}/nc-precontract.json", "w"))
json.dump(dict(rr, contractVersion=2), open(f"{work}/rr-v2.json", "w"))
json.dump(dict(nc, contractVersion=2), open(f"{work}/nc-v2.json", "w"))
json.dump(dict(rr, section="metrics"), open(f"{work}/rr-wrongsection.json", "w"))
json.dump(dict(nc, section="risk"), open(f"{work}/nc-wrongsection.json", "w"))
# The deprecated alias: same content, older spelling.
alias = dict(nc); alias["subcategories"] = alias.pop("gaps")
json.dump(alias, open(f"{work}/nc-alias.json", "w"))

mx = json.load(open(sys.argv[4]))
json.dump(drop(mx), open(f"{work}/mx-precontract.json", "w"))
json.dump(dict(mx, contractVersion=2), open(f"{work}/mx-v2.json", "w"))
json.dump(dict(mx, section="posture"), open(f"{work}/mx-wrongsection.json", "w"))

xr = json.load(open(sys.argv[5]))
json.dump(drop(xr), open(f"{work}/xr-precontract.json", "w"))
json.dump(dict(xr, contractVersion=2), open(f"{work}/xr-v2.json", "w"))
json.dump(dict(xr, section="metrics"), open(f"{work}/xr-wrongsection.json", "w"))

im = json.load(open(sys.argv[6]))
json.dump(drop(im), open(f"{work}/im-precontract.json", "w"))
json.dump(dict(im, contractVersion=2), open(f"{work}/im-v2.json", "w"))
json.dump(dict(im, section="exceptions"), open(f"{work}/im-wrongsection.json", "w"))
PY

# --- 2/3. every --translations consumer renders, and does so identically pre-contract
#
# All four go through the same loader, so one test would "prove" the other three by
# argument rather than by running them — and the day someone gives a renderer its own
# loading path is exactly the day that argument stops holding. Each is cheap; run it.
for r in render_board render_dashboard render_report; do
  if render_rr_any "$r" "$RR/references/example-translations.json" "$work/$r-stamped.html"; then
    ok "$r renders a stamped risk sidecar"
  else
    bad "$r renders a stamped risk sidecar" "$(tail -2 "$work/err.txt")"
  fi
  render_rr_any "$r" "$work/rr-precontract.json" "$work/$r-pre.html"
  if cmp -s "$work/$r-stamped.html" "$work/$r-pre.html"; then
    ok "$r: a pre-contract sidecar renders byte-identically"
  else
    bad "$r: a pre-contract sidecar renders byte-identically" "the stamp changed the page"
  fi
done
cp "$work/render_board-stamped.html" "$work/rr-stamped.html"

if render_nc "$NC/references/example-translations.json" "$work/nc-stamped.html"; then
  ok "render_executive renders a stamped posture sidecar"
else
  bad "render_executive renders a stamped posture sidecar" "$(tail -2 "$work/err.txt")"
fi
render_nc "$work/nc-precontract.json" "$work/nc-pre.html"
if cmp -s "$work/nc-stamped.html" "$work/nc-pre.html"; then
  ok "render_executive: a pre-contract sidecar renders byte-identically"
else
  bad "render_executive: a pre-contract sidecar renders byte-identically" "the stamp changed the page"
fi

if render_mx "$MX/examples/example-translations.json" "$work/mx-stamped.html"; then
  ok "metrics render_executive renders a stamped metrics sidecar"
else
  bad "metrics render_executive renders a stamped metrics sidecar" "$(tail -2 "$work/err.txt")"
fi
render_mx "$work/mx-precontract.json" "$work/mx-pre.html"
if cmp -s "$work/mx-stamped.html" "$work/mx-pre.html"; then
  ok "metrics: a pre-contract sidecar renders byte-identically"
else
  bad "metrics: a pre-contract sidecar renders byte-identically" "the stamp changed the page"
fi
if render_mx "$work/mx-v2.json" "$work/x.html"; then
  bad "metrics renderer refuses contractVersion 2" "it rendered"
else
  ok "metrics renderer refuses contractVersion 2"
fi
if render_mx "$work/mx-wrongsection.json" "$work/x.html"; then
  bad "metrics renderer refuses a 'posture' sidecar" "it rendered"
else
  ok "metrics renderer refuses a 'posture' sidecar"
fi

if render_xr "$XR/examples/example-translations.json" "$work/xr-stamped.html"; then
  ok "exceptions render_board renders a stamped exceptions sidecar"
else
  bad "exceptions render_board renders a stamped exceptions sidecar" "$(tail -2 "$work/err.txt")"
fi
render_xr "$work/xr-precontract.json" "$work/xr-pre.html"
if cmp -s "$work/xr-stamped.html" "$work/xr-pre.html"; then
  ok "exceptions: a pre-contract sidecar renders byte-identically"
else
  bad "exceptions: a pre-contract sidecar renders byte-identically" "the stamp changed the page"
fi
if render_xr "$work/xr-v2.json" "$work/x.html"; then
  bad "exceptions renderer refuses contractVersion 2" "it rendered"
else
  ok "exceptions renderer refuses contractVersion 2"
fi
if render_xr "$work/xr-wrongsection.json" "$work/x.html"; then
  bad "exceptions renderer refuses a 'metrics' sidecar" "it rendered"
else
  ok "exceptions renderer refuses a 'metrics' sidecar"
fi

if render_im "$IM/examples/example-translations.json" "$work/im-stamped.html"; then
  ok "incident render_board renders a stamped incident sidecar"
else
  bad "incident render_board renders a stamped incident sidecar" "$(tail -2 "$work/err.txt")"
fi
render_im "$work/im-precontract.json" "$work/im-pre.html"
if cmp -s "$work/im-stamped.html" "$work/im-pre.html"; then
  ok "incident: a pre-contract sidecar renders byte-identically"
else
  bad "incident: a pre-contract sidecar renders byte-identically" "the stamp changed the page"
fi
if render_im "$work/im-v2.json" "$work/x.html"; then
  bad "incident renderer refuses contractVersion 2" "it rendered"
else
  ok "incident renderer refuses contractVersion 2"
fi
if render_im "$work/im-wrongsection.json" "$work/x.html"; then
  bad "incident renderer refuses an 'exceptions' sidecar" "it rendered"
else
  ok "incident renderer refuses an 'exceptions' sidecar"
fi

# --- 4. the deprecated alias still resolves -----------------------------------------
render_nc "$work/nc-alias.json" "$work/nc-alias.html"
if cmp -s "$work/nc-stamped.html" "$work/nc-alias.html"; then
  ok "the deprecated 'subcategories' alias renders identically to 'gaps'"
else
  bad "the deprecated 'subcategories' alias renders identically to 'gaps'" "alias broke"
fi

# --- 5. an unknown contract version is refused, not best-efforted -------------------
if render_rr "$work/rr-v2.json" "$work/x.html"; then
  bad "risk renderer refuses contractVersion 2" "it rendered"
else
  grep -q "contractVersion" "$work/err.txt" \
    && ok "risk renderer refuses contractVersion 2, naming the version" \
    || bad "risk renderer refuses contractVersion 2, naming the version" "$(tail -1 "$work/err.txt")"
fi
if render_nc "$work/nc-v2.json" "$work/x.html"; then
  bad "posture renderer refuses contractVersion 2" "it rendered"
else
  grep -q "contractVersion" "$work/err.txt" \
    && ok "posture renderer refuses contractVersion 2, naming the version" \
    || bad "posture renderer refuses contractVersion 2, naming the version" "$(tail -1 "$work/err.txt")"
fi

# --- 6. a sidecar for the wrong section is refused ----------------------------------
if render_rr "$work/rr-wrongsection.json" "$work/x.html"; then
  bad "risk renderer refuses a 'metrics' sidecar" "it rendered"
else
  ok "risk renderer refuses a 'metrics' sidecar"
fi
if render_nc "$work/nc-wrongsection.json" "$work/x.html"; then
  bad "posture renderer refuses a 'risk' sidecar" "it rendered"
else
  ok "posture renderer refuses a 'risk' sidecar"
fi

# --- 7. the older guard the contract inherits is still armed ------------------------
# A flat {id: sentence} map parses, so without this the render "succeeds" and every
# narrative falls back to a placeholder while the deck looks finished.
echo '{"R-003":"a flat map, which is the dangerous shape"}' > "$work/flat.json"
if render_rr "$work/flat.json" "$work/x.html"; then
  bad "a flat per-item map is still refused" "it rendered"
else
  ok "a flat per-item map is still refused"
fi

# --- 8. the shipped examples name real ids, and no others ---------------------------
#
# "Never invent numbers" is the toolkit's own rule, and the example sidecars are where a
# reader learns what a good one looks like — so an id in an example that does not exist in
# its store teaches the opposite. This check exists because the first draft of the posture
# example claimed six outcomes were in scope when twenty-one were, and silently dropped the
# one gap that had never been assessed. Both were caught by hand; neither should have needed
# to be.
$PY - "$repo" "$work" <<'PY' > "$work/honesty.txt" 2>&1
import json, subprocess, sys
repo, work = sys.argv[1], sys.argv[2]
verdicts = []

side = json.load(open(f"{repo}/skills/nist-csf/references/example-translations.json"))
an = json.loads(subprocess.run(
    [sys.executable, f"{repo}/skills/nist-csf/scripts/profile_analysis.py", "analyze",
     f"{repo}/skills/nist-csf/examples/example-profile.csfp", "--today", "2026-07-26"],
    capture_output=True, text=True).stdout)
real = {g["subcategoryId"] for g in an["gaps"]}
mine = set(side.get("gaps") or {})
verdicts.append(("posture example invents no Subcategory id", sorted(mine - real)))
verdicts.append(("posture example leaves no real gap unwritten", sorted(real - mine)))

# Ids were never the whole risk. The shipped posture summary once claimed "twenty-one
# outcomes are in scope this cycle and nine of them have been assessed" over a store with
# nine in scope and eight assessed, and said three gaps were "one step short" when only one
# was — four false statements that every id check passed straight over. A board example that
# is wrong about its own store teaches the reader to trust prose the tool did not compute.
WORDS = {0: "no", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
         7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}
overall = (an.get("completeness") or {}).get("overall") or {}
summary = (side.get("executiveSummary") or "").lower()
claims = []
for value, phrase in ((overall.get("inScope"), "outcomes are in scope"),
                      (overall.get("assessed"), "of them have been assessed"),
                      (len(an["gaps"]), "fall short")):
    word = WORDS.get(value)
    if word is None:
        continue
    # Exact phrase only. A looser "is the word anywhere in the summary" test would have
    # let the original through: it said "twenty-one outcomes are in scope ... and NINE of
    # them have been assessed", so the word "nine" was present and the in-scope claim would
    # have passed on the strength of a different sentence being wrong.
    if f"{word} {phrase}" not in summary:
        claims.append(f"expected '{word} {phrase}' ({phrase}={value})")
verdicts.append(("posture example states its own store's counts", claims))

# "One step short" is a claim about a number, and it is checkable per gap.
by_id = {g["subcategoryId"]: g for g in an["gaps"]}
wrong_steps = []
for gid, sentence in (side.get("gaps") or {}).items():
    low = sentence.lower()
    gap = (by_id.get(gid) or {}).get("gap")
    if "one step short" in low and gap != 1:
        wrong_steps.append(f"{gid} says 'one step short' but its gap is {gap}")
    if "two steps short" in low and gap != 2:
        wrong_steps.append(f"{gid} says 'two steps short' but its gap is {gap}")
verdicts.append(("posture example describes each gap's true distance", wrong_steps))

rr = json.load(open(f"{repo}/skills/risk-register/examples/example-register-v2.rr"))
ids = {r["id"] for r in rr["risks"]}
rside = json.load(open(f"{repo}/skills/risk-register/references/example-translations.json"))
# The risk sidecar covers the top risks by design, so an unwritten risk is not a defect
# here — only an id that does not exist is.
verdicts.append(("risk example invents no risk id", sorted(set(rside.get("risks") or {}) - ids)))

mx = json.loads(subprocess.run(
    [sys.executable, f"{repo}/skills/metrics-register/scripts/metrics_analysis.py", "analyze",
     f"{repo}/skills/metrics-register/examples/example-metrics.mtr", "--today", "2026-07-31"],
    capture_output=True, text=True).stdout)
mids = {r["metricId"] for r in mx["metrics"]}
mside = json.load(open(f"{repo}/skills/metrics-register/examples/example-translations.json"))
mine = set(mside.get("metrics") or {})
verdicts.append(("metrics example invents no metric id", sorted(mine - mids)))
verdicts.append(("metrics example leaves no metric unwritten", sorted(mids - mine)))

xr = json.loads(subprocess.run(
    [sys.executable, f"{repo}/skills/exceptions-register/scripts/exceptions_register.py",
     "analyze", f"{repo}/skills/exceptions-register/examples/example.exc",
     "--today", "2026-07-31"], capture_output=True, text=True).stdout)
xids = {r["id"] for r in xr["records"] if r["band"] != "closed"}
xside = json.load(open(
    f"{repo}/skills/exceptions-register/examples/example-translations.json"))
xmine = set(xside.get("acceptances") or {}) | set(xside.get("exceptions") or {})
verdicts.append(("exceptions example invents no record id", sorted(xmine - xids)))
verdicts.append(("exceptions example leaves no active record unwritten", sorted(xids - xmine)))

im = json.loads(subprocess.run(
    [sys.executable, f"{repo}/skills/incident-materiality/scripts/incident_analysis.py",
     "analyze", f"{repo}/skills/incident-materiality/examples/example-incident.inc",
     "--today", "2026-07-31", "--now", "2026-07-31T09:00:00+00:00"],
    capture_output=True, text=True).stdout)
iids = {r["id"] for r in im["incidents"]}
iside = json.load(open(
    f"{repo}/skills/incident-materiality/examples/example-translations.json"))
imine = set(iside.get("incidents") or {})
verdicts.append(("incident example invents no incident id", sorted(imine - iids)))
verdicts.append(("incident example leaves no incident unwritten", sorted(iids - imine)))

for label, offenders in verdicts:
    print(("PASS" if not offenders else "FAIL"), label, ",".join(offenders))
PY
while IFS= read -r line; do
  case "$line" in
    PASS*) ok "${line#PASS }" ;;
    FAIL*) bad "${line#FAIL }" "offending ids listed above" ;;
  esac
done < "$work/honesty.txt"

# --- the `vendor` section, added within contractVersion 1 ---------------------
#
# Additive: the version was NOT bumped, on the precedent already in assemble_pack.py above
# ENVELOPE_KEYS. The load-bearing pair is the last two checks — a NEW section must validate,
# and every sidecar written before it existed must still validate unchanged. Checking only
# the first would pass a change that quietly broke five shipped producers.
cat > "$work/vendor.board.json" <<'JSON'
{"section": "vendor",
 "executiveSummary": "Three production dependencies sit with one provider.",
 "arrangements": {"VA-001": "The plant historian runs on Contoso, and we have never tested leaving."},
 "decisions": ["Fund a second region, or accept single-provider dependency for a further year."],
 "asOf": "2026-06-30"}
JSON
if "$PY" - "$repo" "$work/vendor.board.json" <<'PYEOF' >"$work/vend.out" 2>"$work/vend.err"
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location(
    "ap", sys.argv[1] + "/skills/board-pack/scripts/assemble_pack.py")
ap = importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
raw = json.load(open(sys.argv[2], encoding="utf-8"))
ap.validate_section("vendor", raw, sys.argv[2])
print(ap.CONTRACT_VERSION)
print(",".join(ap.SECTION_KEYS["vendor"]))
print(",".join(ap.SECTION_ORDER["board"]))
PYEOF
then
  ok "a vendor sidecar validates against the contract"
else
  bad "a vendor sidecar validates against the contract" "$(cat "$work/vend.err")"
fi
ver=$(sed -n 1p "$work/vend.out")
key=$(sed -n 2p "$work/vend.out")
ord=$(sed -n 3p "$work/vend.out")
if [ "$ver" = "1" ]; then
  ok "the contract version is still 1 — every sidecar ever written still validates"
else
  bad "the contract version is still 1" "got $ver, which refuses every existing sidecar"
fi
if [ "$key" = "arrangements" ]; then
  ok "the item key is 'arrangements', named for what the section is about"
else
  bad "the vendor item key is 'arrangements'" "got '$key'"
fi
if [ "$ord" = "posture,risk,vendor,ai,metrics,exceptions,incident" ]; then
  ok "and vendor sits directly after risk: what we carry, then who we depend on for it"
else
  bad "vendor sits directly after risk in the board order" "got '$ord'"
fi

# --- the `ai` section, added the same way in v0.41.0 --------------------------
#
# The same load-bearing pair: the new section validates, and the version is untouched so
# every sidecar written before it existed still does. The ordering check is exact rather than
# a "contains" test, because the position IS the decision — `ai` after `vendor` in both
# audiences, so a board meets who supplies the models before it meets the models.
cat > "$work/ai.board.json" <<'JSON'
{"section": "ai",
 "executiveSummary": "One model screens job applicants; nobody has tested it adversarially.",
 "deployments": {"D-001": "The applicant screening model decides, and no red-team report covers it."},
 "decisions": ["Fund an adversarial test of the screening deployment, or move it back to recommending."],
 "asOf": "2026-06-30"}
JSON
if "$PY" - "$repo" "$work/ai.board.json" <<'PYEOF' >"$work/ai.out" 2>"$work/ai.err"
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location(
    "ap", sys.argv[1] + "/skills/board-pack/scripts/assemble_pack.py")
ap = importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
raw = json.load(open(sys.argv[2], encoding="utf-8"))
ap.validate_section("ai", raw, sys.argv[2])
print(ap.CONTRACT_VERSION)
print(",".join(ap.SECTION_KEYS["ai"]))
print(",".join(ap.SECTION_ORDER["audit-committee"]))
PYEOF
then
  ok "an ai sidecar validates against the contract"
else
  bad "an ai sidecar validates against the contract" "$(cat "$work/ai.err")"
fi
if [ "$(sed -n 1p "$work/ai.out")" = "1" ]; then
  ok "...and the contract version is STILL 1 after a second additive section"
else
  bad "the contract version is still 1 after adding ai" \
      "got $(sed -n 1p "$work/ai.out") — every existing sidecar is now refused"
fi
if [ "$(sed -n 2p "$work/ai.out")" = "deployments" ]; then
  ok "the item key is 'deployments' — risk lives in the deployment, not the model"
else
  bad "the ai item key is 'deployments'" "got '$(sed -n 2p "$work/ai.out")'"
fi
if [ "$(sed -n 3p "$work/ai.out")" = "incident,exceptions,risk,vendor,ai,posture,metrics" ]; then
  ok "and ai follows vendor for an audit committee too, not only for a board"
else
  bad "ai follows vendor in the audit-committee order" \
      "got '$(sed -n 3p "$work/ai.out")'"
fi

# --- the two SECTION_TITLE maps agree -----------------------------------------
#
# The assembler and the renderer each hold one, because a skill directory has to run on its
# own and the renderer cannot import from `scripts/`. `vendor` and `ai` were added to the
# assembler's and not the renderer's, so every heading naming them on BOTH deliverables
# printed the bare key — "vendor", "ai" — for two releases. Nothing failed; a board page just
# read as unfinished, and no eval assembled a section that would have shown it.
#
# Keyed off PRODUCERS rather than listing today's seven, so the next section added to one map
# and not the other fails here instead of on somebody's screen.
if "$PY" -c '
import importlib.util, sys
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod
sys.path.insert(0, sys.argv[2].rsplit("/", 1)[0])
a = load("ap", sys.argv[1]); r = load("rp", sys.argv[2])
# Keyed off PRODUCERS, not a bare dict equality: `pack` is in the assembler map as the
# through-line pseudo-section and has no producer, so equality would fail for a reason that
# is not drift. Every REAL section is what has to agree, and has to be present in both.
bad_titles = {name: (a.SECTION_TITLE.get(name), r.SECTION_TITLE.get(name))
              for name in a.PRODUCERS
              if not a.SECTION_TITLE.get(name)
              or a.SECTION_TITLE.get(name) != r.SECTION_TITLE.get(name)}
if bad_titles:
    print("assembler vs renderer: %s" % bad_titles, file=sys.stderr)
    sys.exit(1)
if len(a.PRODUCERS) < 7:
    print("only %d producers — the scan is reading the wrong map" % len(a.PRODUCERS),
          file=sys.stderr); sys.exit(1)
' "$repo/skills/board-pack/scripts/assemble_pack.py" "$repo/skills/board-pack/renderers/render_pack.py" 2>"$work/title.err"; then
  ok "the assembler and the renderer name every section identically"
else
  bad "the two SECTION_TITLE maps agree" "$(cat "$work/title.err")"
fi

# --- `opportunities`, additive within contractVersion 1 -----------------------
#
# Third use of the precedent documented above ENVELOPE_KEYS, after `boundTo` and after the
# `vendor` and `ai` sections. Serves CSF 2.0 GV.RM-07, which the suite had no element for.
#
# The load-bearing pair: a sidecar that omits it must be unaffected, and one that carries an
# UNCITED entry must be refused rather than warned. The second is the whole design — an
# opportunity with no declared goal behind it is marketing copy on a board page, and a rule
# that lives only in guidance is the rule this repo keeps having to convert into a check.
BP="$repo/skills/board-pack"
if "$PY" -c '
import importlib.util, json, os, sys
spec = importlib.util.spec_from_file_location("ap", sys.argv[1])
ap = importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
work = sys.argv[2]

# 1. absent -> empty list, and nothing else moves.
assert ap.validate_opportunities(None, "x") == [], "absent"
assert ap.validate_opportunities([], "x") == [], "empty"

# 2. cited -> carried, with GV.RM-07 defaulted rather than demanded.
got = ap.validate_opportunities([{"text": "t", "cites": "goal:g"}], "x")
assert got == [{"text": "t", "cites": "goal:g", "gvsc": "GV.RM-07"}], got

# 3. uncited -> REFUSED, and the refusal has to say why and what to do instead.
for bad_entry in ({"text": "Stronger assurance would be a real differentiator."},
                  {"text": "t", "cites": "   "}):
    try:
        ap.validate_opportunities([bad_entry], "x")
    except ap.Refusal as exc:
        msg = str(exc)
        for needle in ("cites", "business-context", "Absence renders nothing"):
            assert needle in msg, "the refusal never mentions %r: %s" % (needle, msg)
        continue
    raise AssertionError("accepted an uncited opportunity: %r" % bad_entry)

# 4. a text-less entry is refused too, so an empty box cannot render as a heading.
try:
    ap.validate_opportunities([{"cites": "goal:g"}], "x")
except ap.Refusal:
    pass
else:
    raise AssertionError("accepted an opportunity with no text")

# 5. BL-95. This block used to pin the OPPOSITE: it asserted `goal:no-such-goal` was accepted,
#    and said in its own comment that the assertion would have to flip when grounding landed.
#    It has. Flipped rather than deleted — deleting it would remove the only record that the
#    check ever had this hole, and the comment above it is the argument for why the hole
#    mattered.
#
#    `grounded` is the set of resolvable keys. None means no applicability profile was bound,
#    which CAC-AP-1 §2.2 makes the normal case and which must behave exactly as before.
declared = {"goal:reduce-time-to-market", "crown-jewel:crm"}

# 5a. No profile bound -> presence only, byte-for-byte the old behaviour.
got = ap.validate_opportunities([{"text": "t", "cites": "goal:no-such-goal"}], "x")
assert got and got[0]["cites"] == "goal:no-such-goal", got
got = ap.validate_opportunities([{"text": "t", "cites": "goal:x"}], "x", None)
assert got, "an explicit None must behave as no profile bound"

# 5b. Profile bound -> the reference has to resolve, and the refusal has to be actionable.
try:
    ap.validate_opportunities([{"text": "t", "cites": "goal:no-such-goal"}], "x", declared)
except ap.Refusal as exc:
    msg = str(exc)
    for needle in ("does not declare", "reduce-time-to-market", "crown-jewel:crm",
                   "set-fact --goal"):
        assert needle in msg, "the refusal never mentions %r: %s" % (needle, msg)
else:
    raise AssertionError("accepted an opportunity citing a goal nobody declared")

# 5c. A declared goal resolves, by slug or by its own words.
for good in ("goal:reduce-time-to-market", "goal:Reduce time to market",
             "GOAL: Reduce  Time To Market", "crown-jewel:CRM"):
    got = ap.validate_opportunities([{"text": "t", "cites": good}], "x", declared)
    assert got and got[0]["cites"] == good, (good, got)

# 5d. An empty set is NOT None. A bound profile declaring nothing citable makes every
#     opportunity ungrounded, and that must be said rather than waved through.
try:
    ap.validate_opportunities([{"text": "t", "cites": "goal:anything"}], "x", set())
except ap.Refusal as exc:
    assert "nothing citable is declared" in str(exc), str(exc)
else:
    raise AssertionError("an empty grounding set behaved like no profile at all")

# 5e. The wrong prefix does not resolve against the right name.
try:
    ap.validate_opportunities([{"text": "t", "cites": "crown-jewel:reduce-time-to-market"}],
                              "x", declared)
except ap.Refusal:
    pass
else:
    raise AssertionError("a crown-jewel: prefix resolved against a goal")

# 5f. grounding_keys reads a real .biz shape and distinguishes absent from empty.
assert ap.grounding_keys(None) is None, "no context path must yield None"
assert ap.grounding_keys(os.path.join(work, "nope.biz")) is None, "unreadable must yield None"
biz = os.path.join(work, "g.biz")
with open(biz, "w", encoding="utf-8") as fh:
    json.dump({"context": {"strategicGoals": ["Reduce time to market", "  "],
                           "crownJewels": [{"system": "CRM"}, {"noSystem": True}]}}, fh)
assert ap.grounding_keys(biz) == declared, ap.grounding_keys(biz)
with open(biz, "w", encoding="utf-8") as fh:
    json.dump({"context": {"strategicGoals": [], "crownJewels": []}}, fh)
assert ap.grounding_keys(biz) == set(), "a context declaring nothing is an empty set, not None"
' "$BP/scripts/assemble_pack.py" "$work" 2>"$work/opp.err"; then
  ok "an opportunity is refused when uncited, and when its citation resolves to no declared goal or crown jewel (BL-95)"
else
  bad "an uncited or ungrounded opportunity is refused at the assembler" \
      "$(tail -3 "$work/opp.err")"
fi

# Byte-identity: strip `opportunities` from the one shipped sidecar that has it and the rest
# of that section must render exactly as it did before the key existed.
"$PY" - "$repo/skills/vendor-register/examples/example-translations.json" \
       "$work/no-opp.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
d.pop("opportunities", None)
json.dump(d, open(sys.argv[2], "w", encoding="utf-8"), indent=2, ensure_ascii=False)
PYEOF
if "$PY" -c '
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("ap", sys.argv[1])
ap = importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
def load(path):
    with open(path, encoding="utf-8") as fh:
        return ap.validate_section("vendor", json.load(fh), path)
with_opp = load(sys.argv[2])
without = load(sys.argv[3])
a = {k: v for k, v in with_opp.items() if k not in ("opportunities", "path")}
b = {k: v for k, v in without.items() if k not in ("opportunities", "path")}
if a != b:
    print("the key changed something other than itself", file=sys.stderr); sys.exit(1)
if without["opportunities"] != []:
    print("a sidecar without the key did not get an empty list", file=sys.stderr); sys.exit(1)
if len(with_opp["opportunities"]) != 1:
    print("the shipped worked example lost its opportunity", file=sys.stderr); sys.exit(1)
' "$BP/scripts/assemble_pack.py" \
  "$repo/skills/vendor-register/examples/example-translations.json" "$work/no-opp.json" \
  2>"$work/ident.err"; then
  ok "...and a sidecar without the key is otherwise identical to one with it"
else
  bad "the key is additive" "$(cat "$work/ident.err")"
fi

# Colour: patina, never RAG. The brand system is explicit that patina does not signal "safe",
# and an opportunity is not a low-severity risk. Checked on the rendered page rather than in
# the source, because the source is where the intention lives and the page is where a reader
# would be misled.
"$PY" "$BP/scripts/assemble_pack.py" assemble "$BP/examples/pack.manifest.json" \
  --out "$work/opp-pack.json" >/dev/null 2>&1
(cd "$BP/renderers" && "$PY" render_pack.py --in "$work/opp-pack.json" \
   --html "$work/opp.html") >/dev/null 2>&1
if "$PY" -c '
import re, sys
page = open(sys.argv[1], encoding="utf-8").read()
if "Positive risk" not in page:
    print("the opportunity block did not render at all", file=sys.stderr); sys.exit(1)
if "cites goal:" not in page:
    print("the citation is not on the page beside the claim", file=sys.stderr); sys.exit(1)
# The rule the graphics standard states: a RAG value must never appear on this block, in any
# form. Read the block out of the page and look at what colour reaches it.
block = re.search(r"opp-h.*?</ol>", page, re.S)
if not block:
    print("could not isolate the opportunity block", file=sys.stderr); sys.exit(1)
css = re.search(r"h3\.opp-h\{[^}]*\}.*?ol\.opps\{[^}]*\}", page, re.S)
if not css:
    print("no styling for the opportunity block", file=sys.stderr); sys.exit(1)
# Tested against the RAG palette BY VALUE, not by hue. Patina is itself a green-leaning teal
# (#2FA98C), so a hue test would reject the one colour this block is supposed to wear — the
# first version of this check did exactly that. What must never appear is a value from the
# severity scale, because that is what makes a reader read the block as a band.
import importlib.util
gspec = importlib.util.spec_from_file_location("g", sys.argv[2])
G = importlib.util.module_from_spec(gspec); gspec.loader.exec_module(G)
rag = {v.lower() for band in G._RAG.values() for v in band.values()}
used = {h.lower() for h in re.findall(r"#[0-9A-Fa-f]{6}", css.group(0))}
hit = sorted(used & rag)
if hit:
    print("a RAG palette value reached the opportunity block: %s" % ", ".join(hit),
          file=sys.stderr)
    sys.exit(1)
if G._PATINA.lower() not in used:
    print("the block is not in patina; it uses %s" % sorted(used), file=sys.stderr)
    sys.exit(1)
' "$work/opp.html" "$repo/tools/cac_graphics.py" 2>"$work/rag.err"; then
  ok "the block renders with its citation, in patina, with no RAG green anywhere on it"
else
  bad "the opportunity block is patina, not RAG green" "$(cat "$work/rag.err")"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'section-contract: ran %s checks, expected %s — a case stopped executing\n' \
         "$checks" "$EXPECTED_CHECKS"
  exit 1
fi
if [ "$fails" -ne 0 ]; then
  printf 'section-contract: %s of %s checks FAILED\n' "$fails" "$checks"
  exit 1
fi
printf 'section-contract: all %s checks passed\n' "$checks"
