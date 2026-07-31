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

EXPECTED_CHECKS=40
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
