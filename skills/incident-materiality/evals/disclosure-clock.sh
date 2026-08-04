#!/usr/bin/env bash
# Disclosure clocks, driven through the CLI rather than the Python API.
#
# `self-test` already pins the arithmetic by calling the functions directly. This suite exists
# because the arithmetic is not the only way to get a clock wrong: an argument that never
# reaches the engine, a date that survives argparse and dies in the store, a state that is
# computed correctly and rendered from the wrong key — none of those are visible from inside
# the module. So everything here goes through `python3 scripts/incident_analysis.py`, the way
# a user does.
#
# The load-bearing case is #6. Item 1.05 runs four business days from the DETERMINATION, not
# from the discovery. Anchoring on discovery invents a deadline that does not exist, and a
# false overdue flag will eventually push somebody into filing something they had not yet
# decided was true.
#
# Anti-vacuity: EXPECTED_CHECKS pins the count, so a case that silently stops running fails
# the suite rather than passing it; and the last check asserts that every clock state this
# fixture is supposed to reach was actually observed, so a suite that can no longer produce
# an `overdue` or an `anchor-missing` cannot quietly report all-clear.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
E="$skill/scripts/incident_analysis.py"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=38
checks=0
fails=0
seen_states=""
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }
eq()  { # eq <label> <expected> <actual>
  if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "expected '$2', got '$3'"; fi; }

S="$work/t.inc"
J="$work/a.json"

# q <python expr over `a`> — one query helper, so every assertion reads the same way.
q() { "$PY" -c 'import json,sys
a = json.load(open(sys.argv[1]))
print(eval(sys.argv[2]))' "$J" "$1"; }

# snap <today> <now> — refresh the analysis, and remember every clock state it produced.
snap() {
  "$PY" "$E" analyze "$S" --today "$1" --now "$2" --out "$J" >/dev/null || {
    bad "analyze --today $1" "engine errored"; return 1; }
  seen_states="$seen_states $("$PY" -c 'import json,sys
a = json.load(open(sys.argv[1]))
print(" ".join(sorted({c["state"] for r in a["incidents"] for c in r["clocks"]})))' "$J")"
}

echo "disclosure-clock: $($PY -V 2>&1)"

# 2026-07-17 is a Friday and is the only holiday in this store, which is what makes case 5
# and case 6 differ by exactly one business day.
"$PY" "$E" init "$S" --client "Clock Co" --holiday 2026-07-17 --actor eval >/dev/null
"$PY" "$E" open "$S" --title "Vendor breach" --discovered 2026-07-06 \
  --regime sec-1.05 --actor eval >/dev/null

# 1-3. Nothing determined: no window, and the elapsed days are reported plainly.
snap 2026-07-13 2026-07-13T00:00:00+00:00
eq "no determination: the Item 1.05 clock has not started" "not-started" \
   "$(q 'a["incidents"][0]["clocks"][0]["state"]')"
eq "no determination: and there is no deadline" "None" \
   "$(q 'a["incidents"][0]["clocks"][0]["deadline"]')"
eq "no determination: days since discovery are reported as a plain distance" "7" \
   "$(q 'a["incidents"][0]["daysSinceDiscovery"]')"

# 4. An 'assessing' determination is not a determination of material. Still no window.
"$PY" "$E" determine "$S" --id I-001 --state assessing \
  --rationale "Scope not established; vendor forensics engaged." --decider CISO \
  --on 2026-07-09 --actor eval >/dev/null
snap 2026-07-13 2026-07-13T00:00:00+00:00
eq "under assessment: still no window open" "not-started" \
   "$(q 'a["incidents"][0]["clocks"][0]["state"]')"
eq "under assessment: and the band says so" "assessing" "$(q 'a["incidents"][0]["band"]')"

# 5-8. Determined material on Tue 2026-07-14. Fri 2026-07-17 is a holiday, so:
# Wed 15 (1), Thu 16 (2), Fri 17 holiday, Mon 20 (3), Tue 21 (4).
"$PY" "$E" determine "$S" --id I-001 --state material \
  --rationale "Exfiltration of employee records confirmed 13 July." \
  --decider "General Counsel" --on 2026-07-14 --actor eval >/dev/null
snap 2026-07-16 2026-07-16T00:00:00+00:00
eq "material: four business days, the holiday pushing it out by one" "2026-07-21" \
   "$(q 'a["incidents"][0]["clocks"][0]["deadline"]')"
eq "material: the window is open" "due" "$(q 'a["incidents"][0]["clocks"][0]["state"]')"
eq "material: five calendar days remain" "5" \
   "$(q 'a["incidents"][0]["clocks"][0]["daysRemaining"]')"
eq "material: but only two business days" "2" \
   "$(q 'a["incidents"][0]["clocks"][0]["businessDaysRemaining"]')"

# 9-10. THE case. The anchor is the determination, not the discovery. Discovery was
# 2026-07-06; anchoring there would give a deadline of 2026-07-10 and the incident would
# already be reading overdue on 2026-07-16, six days before it is actually due.
eq "the clock anchors on the determination" "determination" \
   "$(q 'a["incidents"][0]["clocks"][0]["anchorKind"]')"
eq "and on the determination DATE, not the 2026-07-06 discovery date" "2026-07-14" \
   "$(q 'a["incidents"][0]["clocks"][0]["anchor"]')"

# 11-12. Past the deadline with nothing filed.
snap 2026-07-22 2026-07-22T00:00:00+00:00
eq "past the deadline, unfiled, is overdue" "overdue" \
   "$(q 'a["incidents"][0]["clocks"][0]["state"]')"
eq "and it reaches the overdue attention list" "['I-001']" "$(q 'a["attention"]["overdue"]')"

# 13-15. A filing stops the clock, and only a filing does.
"$PY" "$E" set-disclosure "$S" --id I-001 --decision file \
  --basis "Determined material 14 July; 8-K within the window." --actor eval >/dev/null
snap 2026-07-22 2026-07-22T00:00:00+00:00
eq "a disclosure DECISION alone does not stop the clock" "overdue" \
   "$(q 'a["incidents"][0]["clocks"][0]["state"]')"
"$PY" "$E" record-filing "$S" --id I-001 --window sec-1.05:8-K --at 2026-07-20 \
  --actor eval >/dev/null
snap 2026-07-22 2026-07-22T00:00:00+00:00
eq "a recorded filing stops it" "filed" "$(q 'a["incidents"][0]["clocks"][0]["state"]')"
eq "and the overdue list clears" "[]" "$(q 'a["attention"]["overdue"]')"

# 16-19. DORA: hours, and an honest gap where an anchor is missing.
"$PY" "$E" open "$S" --title "Payment rail outage" --discovered 2026-07-06 \
  --regime dora --actor eval >/dev/null
snap 2026-07-07 2026-07-07T00:00:00+00:00
eq "DORA with no anchor recorded reports anchor-missing" "anchor-missing" \
   "$(q '[c for c in a["incidents"][1]["clocks"] if c["window"]=="initial"][0]["state"]')"
eq "and computes no deadline from a date it does not have" "None" \
   "$(q '[c for c in a["incidents"][1]["clocks"] if c["window"]=="initial"][0]["deadline"]')"
eq "a missing anchor is an open item, not a silent gap" "['I-002']" \
   "$(q 'a["attention"]["anchorMissing"]')"
eq "an incident outside a regime reports not-applicable, not not-started" "not-applicable" \
   "$(q '[c for c in a["incidents"][1]["clocks"] if c["regime"]=="sec-1.05"][0]["state"]')"

# 20-23. Aware 06:00 + 24h = 07-07T06:00. Classified 09:00 + 4h = 07-06T13:00. The EARLIER
# governs, so classifying does not buy time.
"$PY" "$E" set-anchor "$S" --id I-002 --aware 2026-07-06T06:00:00+00:00 \
  --classified 2026-07-06T09:00:00+00:00 --actor eval >/dev/null
snap 2026-07-06 2026-07-06T10:00:00+00:00
eq "DORA initial is the earlier of classification+4h and awareness+24h" \
   "2026-07-06T13:00:00+00:00" \
   "$(q '[c for c in a["incidents"][1]["clocks"] if c["window"]=="initial"][0]["deadline"]')"
eq "and the output names which anchor governed" "classification" \
   "$(q '[c for c in a["incidents"][1]["clocks"] if c["window"]=="initial"][0]["anchorKind"]')"
eq "three hours remain at 10:00" "3.0" \
   "$(q '[c for c in a["incidents"][1]["clocks"] if c["window"]=="initial"][0]["hoursRemaining"]')"
snap 2026-07-06 2026-07-06T14:00:00+00:00
eq "and it is overdue an hour after the window closes" "overdue" \
   "$(q '[c for c in a["incidents"][1]["clocks"] if c["window"]=="initial"][0]["state"]')"

# 24-27. Each DORA window anchors on the previous filing, not on the incident.
eq "the intermediate window has not started" "not-started" \
   "$(q '[c for c in a["incidents"][1]["clocks"] if c["window"]=="intermediate"][0]["state"]')"
eq "so a missed initial notification produces no phantom intermediate deadline" "None" \
   "$(q '[c for c in a["incidents"][1]["clocks"] if c["window"]=="intermediate"][0]["deadline"]')"
"$PY" "$E" record-filing "$S" --id I-002 --window dora:initial \
  --at 2026-07-06T12:30:00+00:00 --actor eval >/dev/null
snap 2026-07-07 2026-07-07T00:00:00+00:00
eq "intermediate is 72 hours from the initial notification" "2026-07-09T12:30:00+00:00" \
   "$(q '[c for c in a["incidents"][1]["clocks"] if c["window"]=="intermediate"][0]["deadline"]')"
"$PY" "$E" record-filing "$S" --id I-002 --window dora:intermediate \
  --at 2026-07-09T10:00:00+00:00 --actor eval >/dev/null
snap 2026-07-10 2026-07-10T00:00:00+00:00
eq "final is one month from the intermediate report" "2026-08-09T10:00:00+00:00" \
   "$(q '[c for c in a["incidents"][1]["clocks"] if c["window"]=="final"][0]["deadline"]')"

# 28. A live clock outranks the determination. "Not material for Item 1.05" and "no
# notification duty" are different questions; a band that read the determination first would
# hide the one of the two that has a date attached.
"$PY" "$E" set-disclosure "$S" --id I-002 --decision no-file \
  --basis "Reported under DORA; not material for Item 1.05." \
  --regime sec-1.05 --regime dora --actor eval >/dev/null
"$PY" "$E" determine "$S" --id I-002 --state not-material \
  --rationale "Latency only; no data affected." --decider "General Counsel" \
  --on 2026-07-09 --actor eval >/dev/null
snap 2026-07-10 2026-07-10T00:00:00+00:00
eq "a live DORA window outranks a not-material Item 1.05 determination" "disclosure-due" \
   "$(q 'a["incidents"][1]["band"]')"

# 29-31. Refusals leave the store byte-identical, and the appended history survives.
before="$("$PY" -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$S")"
"$PY" "$E" determine "$S" --id I-001 --state material --rationale x --decider y \
  --on 2026-7-14 >/dev/null 2>&1
"$PY" "$E" set-anchor "$S" --id I-002 --aware 2026-07-06 >/dev/null 2>&1
"$PY" "$E" record-filing "$S" --id I-001 --window dora:initial \
  --at 2026-07-14T09:00:00+00:00 >/dev/null 2>&1
after="$("$PY" -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$S")"
eq "an unpadded date, a bare DORA anchor and an out-of-scope filing all refuse, leaving the store byte-identical" \
   "$before" "$after"
snap 2026-07-22 2026-07-22T00:00:00+00:00
eq "I-001 kept both determinations; the earlier one was not overwritten" "2" \
   "$(q 'len(a["incidents"][0]["determinations"])')"
eq "and the sequence is the record of what was decided when" \
   "['assessing', 'material']" \
   "$(q '[d["state"] for d in a["incidents"][0]["determinations"]]')"

# 32-33. The engine emits no verdict and no score, anywhere in its output.
if "$PY" "$E" analyze "$S" --today 2026-07-22 --now 2026-07-22T00:00:00+00:00 \
   | grep -Eiq 'score|verdict|recommend'; then
  bad "the analysis output contains no score, verdict or recommendation" "found one"
else
  ok "the analysis output contains no score, verdict or recommendation"
fi
if "$PY" -c 'import json,sys
a = json.load(open(sys.argv[1]))
r = a["incidents"][0]
sys.exit(0 if ("factorsAssessed" in r and "factorsUnassessed" in r
               and not any("bearing" in k.lower() for k in r)) else 1)' "$J"; then
  ok "completeness is reported as WHICH factors, never as a count of bearing ones"
else
  bad "completeness is reported as WHICH factors, never as a count of bearing ones" \
      "a bearing tally reached the derived row"
fi

# 34. Anti-vacuity. If the fixture stops being able to reach these states, every absence
# assertion above becomes trivially true and this suite would report all-clear over a
# clock that no longer runs.
missing=""
for s in not-started anchor-missing due overdue filed not-applicable; do
  case " $seen_states " in *" $s "*) ;; *) missing="$missing $s";; esac
done
if [ -z "$missing" ]; then
  ok "every clock state this fixture should reach was actually observed"
else
  bad "every clock state this fixture should reach was actually observed" \
      "never reached:$missing"
fi

# --- The chronology mark agrees with the clock table --------------------------
#
# A dot that stays neutral while the chip beside it says "overdue" is the mark
# disagreeing with the number next to it. The shipped example has no lapsed DORA
# window, so this case is constructed rather than found: an unexercised branch is
# an untested one, and this one only fires after a statutory deadline has passed.
#
# Both directions are asserted. `due` must stay neutral — the DORA report is a
# date in the sequence on a normal incident, not a call anyone has made — and
# only the lapse is coloured. Checking the lapse alone would pass a renderer that
# painted every DORA dot red.
mark_probe=$("$PY" - "$skill/renderers" <<'PYEOF'
import sys
sys.path.insert(0, sys.argv[1])
import _common as C


def dora_dot(state):
    row = {"discoveredAt": "2026-07-01",
           "clocks": [{"regime": "dora", "window": "final", "state": state,
                       "deadline": "2026-08-23T11:30:00+00:00", "filedAt": None}]}
    ev = [e for e in C.timeline_events(row) if "DORA" in e["label"]]
    return ev[0] if ev else None


overdue = dora_dot("overdue")
due = dora_dot("due")
print("BANDED" if overdue and overdue.get("sev") == "critical" else "PLAIN")
print("PLAIN" if due and "sev" not in due else "BANDED")
print("LABELLED" if overdue and "overdue" in overdue["label"] else "UNLABELLED")
PYEOF
)
mp_overdue=$(echo "$mark_probe" | sed -n 1p)
mp_due=$(echo "$mark_probe" | sed -n 2p)
mp_label=$(echo "$mark_probe" | sed -n 3p)

if [ "$mp_overdue" = "BANDED" ]; then
  ok "a lapsed DORA window is coloured on the chronology, as the table shows it"
else
  bad "a lapsed DORA window is coloured on the chronology, as the table shows it" \
      "an overdue DORA dot carried no severity"
fi

if [ "$mp_due" = "PLAIN" ]; then
  ok "...and a DORA window merely due stays neutral"
else
  bad "...and a DORA window merely due stays neutral" \
      "a due DORA dot carried a severity it should not"
fi

if [ "$mp_label" = "LABELLED" ]; then
  ok "the lapse is in the label too, so colour is never its only carrier"
else
  bad "the lapse is in the label too, so colour is never its only carrier" \
      "the overdue milestone label does not say overdue"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'disclosure-clock: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'disclosure-clock: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'disclosure-clock: all %s checks passed\n' "$checks"
