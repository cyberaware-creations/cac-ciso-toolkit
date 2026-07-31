#!/usr/bin/env bash
# Direction-aware derivations, over a register built by the real CLI.
#
# The engine's own self-test calls the functions directly. This suite goes through
# `add-metric`, `record`, `set-threshold` and `analyze` as a user would, because the layer
# between the two — argument parsing, refusal handling, the file round-trip — is where a
# derivation that is correct in isolation can still be wrong in practice.
#
# The case this exists for is polarity. A lower-better metric whose value RISES is
# slipping, and the naive implementation reports it as an improvement. That is not a
# subtle bug in a board pack: it states the opposite of the truth about the number, and it
# reads exactly like a correct answer.
#
# Anti-vacuity, mirrored from confirmation-age.sh:
#   - the store is built by commands, never hand-written, so a schema change breaks this
#     suite rather than sliding past it
#   - every derived expectation is worked by hand and written here as a literal
#   - EXPECTED_CHECKS is asserted at the end, so a case that stops executing fails loudly
#     instead of printing a green count over half a suite
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
ENGINE="$skill/scripts/metrics_analysis.py"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
S="$work/t.mtr"

EXPECTED_CHECKS=28
checks=0
fails=0

ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }
is()  { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "expected '$3', got '$2'"; fi; }

echo "metric-trend: $($PY -V 2>&1)"

q() {  # q <python-expression-over-d>   — read a value out of the analysis
  $PY -c "
import json,sys
d=json.load(open(sys.argv[1]))
m={r['metricId']: r for r in d['metrics']}
print($1)" "$work/a.json"
}
refresh() { $PY "$ENGINE" analyze "$S" --today "${1:-2026-07-31}" --out "$work/a.json" >/dev/null; }

# --- build a register with the real commands ----------------------------------------
$PY "$ENGINE" init "$S" --client "Eval Corp" --cadence-days 90 --actor eval >/dev/null
$PY "$ENGINE" add-metric "$S" --name "Patch SLA"   --direction higher-better \
    --archetype patch-coverage --unit percent --owner Infra --actor eval >/dev/null
$PY "$ENGINE" add-metric "$S" --name "Dwell time"  --direction lower-better \
    --archetype dwell-time --unit days --owner SOC --actor eval >/dev/null
$PY "$ENGINE" add-metric "$S" --name "Blocked"     --direction higher-better \
    --unit count --vanity-risk --actor eval >/dev/null
$PY "$ENGINE" set-threshold "$S" --metric M-001 --target 95 --warn 90 --critical 80 --actor eval >/dev/null
$PY "$ENGINE" set-threshold "$S" --metric M-002 --target 5 --warn 10 --critical 20 --actor eval >/dev/null
$PY "$ENGINE" record "$S" --metric M-001 --period 2026-Q2 --value 93 --date 2026-04-01 --actor eval >/dev/null
$PY "$ENGINE" record "$S" --metric M-001 --period 2026-Q3 --value 88 --date 2026-07-01 --actor eval >/dev/null
$PY "$ENGINE" record "$S" --metric M-002 --period 2026-Q2 --value 8  --date 2026-04-01 --actor eval >/dev/null
$PY "$ENGINE" record "$S" --metric M-002 --period 2026-Q3 --value 14 --date 2026-07-01 --actor eval >/dev/null
$PY "$ENGINE" record "$S" --metric M-003 --period 2026-Q3 --value 2000000 --date 2026-07-01 --actor eval >/dev/null

if [ -s "$S" ]; then ok "the CLI built a register"; else bad "the CLI built a register" "no store at $S"; fi
refresh

# --- polarity: the reason this suite exists -----------------------------------------
# M-001 higher-better 93 -> 88: fell, so slipping. M-002 lower-better 8 -> 14: ROSE, and
# rising is worse for this metric, so also slipping. A naive engine calls M-002 an
# improvement. Both hand-worked.
is "higher-better falling is slipping"      "$(q "m['M-001']['trend']")" "slipping"
is "lower-better RISING is slipping"        "$(q "m['M-002']['trend']")" "slipping"
is "delta keeps its raw sign on M-001"      "$(q "m['M-001']['delta']")" "-5.0"
is "delta stays POSITIVE on the worsening lower-better metric" \
                                            "$(q "m['M-002']['delta']")" "6.0"
is "one reading reports no-prior, not holding" "$(q "m['M-003']['trend']")" "no-prior"

# --- threshold polarity, and the boundary -------------------------------------------
is "88 against warn 90 on higher-better is warn"  "$(q "m['M-001']['status']")" "warn"
is "14 against warn 10 on lower-better is warn"   "$(q "m['M-002']['status']")" "warn"
is "no threshold set is not a breach"             "$(q "m['M-003']['status']")" "no-threshold"

$PY "$ENGINE" record "$S" --metric M-001 --period 2026-Q3b --value 90 --date 2026-07-02 --actor eval >/dev/null
refresh
is "exactly at warn is not breached"              "$(q "m['M-001']['status']")" "ok"
is "and the trend from 88 to 90 is gaining"       "$(q "m['M-001']['trend']")" "gaining"
$PY "$ENGINE" record "$S" --metric M-001 --period 2026-Q3c --value 79 --date 2026-07-03 --actor eval >/dev/null
refresh
is "past critical reports critical, not warn"     "$(q "m['M-001']['status']")" "critical"

# --- staleness is an age, banded against the cadence --------------------------------
# Latest M-002 reading is 2026-07-01. Hand-worked against a 90-day cadence:
#   2026-07-31  ->  30 days  -> within       (30 <= 45)
#   2026-08-16  ->  46 days  -> approaching  (46 > 45)
#   2026-09-29  ->  90 days  -> approaching  (meeting the cadence is meeting it)
#   2026-09-30  ->  91 days  -> beyond
#   2026-12-29  -> 181 days  -> wellBeyond   (> 180)
is "30 days is within"       "$(refresh 2026-07-31; q "m['M-002']['ageBand']")" "within"
is "46 days is approaching"  "$(refresh 2026-08-16; q "m['M-002']['ageBand']")" "approaching"
is "90 days is still approaching, because meeting a cadence is meeting it" \
                             "$(refresh 2026-09-29; q "m['M-002']['ageBand']")" "approaching"
is "91 days is beyond"       "$(refresh 2026-09-30; q "m['M-002']['ageBand']")" "beyond"
is "181 days is wellBeyond"  "$(refresh 2026-12-29; q "m['M-002']['ageBand']")" "wellBeyond"

# No confidence vocabulary may reach a band name — the whole point of calling it an age.
refresh 2026-12-29
if $PY -c "
import json,sys
d=json.load(open('$work/a.json'))
banned=('confiden','degrad','decay','reliab','assumed','trust','certainty','uncertain','doubt')
blob=json.dumps(d).lower()
sys.exit(1 if any(b in blob for b in banned) else 0)"; then
  ok "no confidence vocabulary anywhere in the derived output"
else
  bad "no confidence vocabulary anywhere in the derived output" "a banned stem is present"
fi

# --- attention lists -----------------------------------------------------------------
refresh 2026-07-31
is "the vanity flag is the author's, not inferred" "$(q "d['attention']['vanity']")" "['M-003']"
is "the untagged metric is the one with a null archetype" \
                                                   "$(q "d['attention']['untagged']")" "['M-003']"
is "the unowned metric is surfaced"                "$(q "d['attention']['unowned']")" "['M-003']"
is "nothing is stale at 30 days"                   "$(q "d['attention']['stale']")" "[]"
is "both slipping metrics are worsening"           "$(q "sorted(d['attention']['worsening'])")" "['M-001', 'M-002']"

# --- refusals leave the file byte-identical ------------------------------------------
before="$($PY -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$S")"
$PY "$ENGINE" record "$S" --metric M-001 --period 2026-Q4 --value 90 --date 2026-7-1 --actor eval >/dev/null 2>"$work/e1.txt"
r1=$?
$PY "$ENGINE" set-threshold "$S" --metric M-001 --warn 70 --actor eval >/dev/null 2>"$work/e2.txt"
r2=$?
after="$($PY -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$S")"
if [ "$r1" -ne 0 ]; then ok "an unpadded date is refused"; else bad "an unpadded date is refused" "exit 0"; fi
if grep -q "canonical zero-padded" "$work/e1.txt"; then
  ok "and the refusal explains why the padding matters"
else
  bad "and the refusal explains why the padding matters" "$(tail -1 "$work/e1.txt")"
fi
if [ "$r2" -ne 0 ]; then ok "moving a threshold without --why is refused"; else bad "moving a threshold without --why is refused" "exit 0"; fi
is "and both refusals left the store byte-identical" "$after" "$before"

# --- a sibling store is refused by family ---------------------------------------------
echo '{"schemaVersion":2,"risks":[]}' > "$work/other.rr"
if $PY "$ENGINE" analyze "$work/other.rr" >/dev/null 2>"$work/e3.txt"; then
  bad "a .rr handed to this engine is refused" "it was accepted"
else
  grep -q "not a metrics register" "$work/e3.txt" \
    && ok "a .rr handed to this engine is refused by family" \
    || bad "a .rr handed to this engine is refused by family" "$(tail -1 "$work/e3.txt")"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'metric-trend: ran %s checks, expected %s — a case stopped executing\n' "$checks" "$EXPECTED_CHECKS"
  exit 1
fi
if [ "$fails" -ne 0 ]; then
  printf 'metric-trend: %s of %s checks FAILED\n' "$fails" "$checks"
  exit 1
fi
printf 'metric-trend: all %s checks passed\n' "$checks"
