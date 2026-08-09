#!/usr/bin/env bash
# CAC-AP-1 against a real consumer, driven through the CLI.
#
# This is the suite the applicability contract lives or dies on. `business_context.py
# self-test` pins the narrowing logic where it is written; this pins what happens when the
# decision crosses a file boundary into a skill that must not import it.
#
# The load-bearing case is the additivity check. `--context` is optional, and everything it
# adds must be strictly additive: a profile that narrows nothing must leave the output
# EXACTLY as it was, plus the context blocks and nothing else. So a payload whose every
# battery is asked is run, its context blocks stripped, and the remainder compared
# byte-for-byte — with a companion check that the blocks were in fact added, because a
# strip-and-compare passing on two identical plain files proves nothing.
#
# It is deliberately NOT run against a payload that DOES narrow. Narrowing removes the
# windows of a battery nobody asked about, which is the entire point of it; a strip-compare
# there could only pass if the feature did nothing. Those differences are asserted one at a
# time instead.
#
# The absent-`--context` case cannot be pinned from inside this suite — there is no
# pre-change binary to compare against — so it is asserted structurally (no `context` key
# anywhere) and was diffed once, by hand, against artifacts captured before the change.
#
# The second load-bearing case is §2.3 in both directions, asserted inside ONE analysis: the
# same run has an incident whose own declaration re-adds a battery the profile removed and
# another whose declaration removes one the profile kept. Two separate runs could each pass
# with a rule that only ever moves batteries one way.
#
# Anti-vacuity: EXPECTED_CHECKS pins the count; every absence check is paired with a presence
# check on the same run; and the refusal cases assert the store is left byte-identical rather
# than merely that the exit code was non-zero.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
suite="$(cd "$skill/.." && pwd)"
E="$skill/scripts/incident_analysis.py"
BC="$suite/business-context/scripts/business_context.py"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=58
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }
eq()  { # eq <label> <expected> <actual>
  if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "expected '$2', got '$3'"; fi; }
has() { # has <label> <needle> <haystack-file>
  if grep -qF "$2" "$3"; then ok "$1"; else bad "$1" "'$2' is not in $3"; fi; }
hasnt() { # hasnt <label> <needle> <haystack-file>
  if grep -qF "$2" "$3"; then bad "$1" "'$2' should not be in $3"; else ok "$1"; fi; }

S="$work/t.inc"
P="$work/profile.json"
PLAIN="$work/plain.json"
NARROW="$work/narrow.json"

echo "applicability: $($PY -V 2>&1)"

# --- the payload, hand-written -------------------------------------------------
#
# Written by hand rather than exported from business-context, deliberately: `--context` is a
# DATA contract, and a suite that only ever feeds it one producer's output proves the two
# programs agree, not that the consumer reads the documented shape. The end-to-end case
# against the real exporter is in section 10, and it is not a substitute for these.
"$PY" - "$P" <<'PYEOF'
import json, sys
def declared(v, by, on, basis):
    return {"value": v, "declaredBy": by, "declaredOn": on, "basis": basis}

profile = {
    "listedEntity": declared(False, "General Counsel", "2026-03-02",
                             "Privately held; no securities admitted to trading."),
    # The gate the SEC battery actually reads. Declared SEPARATELY from the listing fact
    # above, and the two disagree on purpose: this fixture is a private company that files
    # nothing, and the point of BL-175 is that neither flag implies the other.
    "secItem105Scope": declared(False, "General Counsel", "2026-03-02",
                                "No class registered under the Exchange Act and no s.15(d) "
                                "reporting obligation."),
    "doraScope": declared(True, "General Counsel", "2026-04-11",
                          "Dublin subsidiary authorised as a payment institution."),
    "nydfsScope": declared(False, "General Counsel", "2026-03-02",
                           "No New York licensed activity."),
}
def sentence(label, flag, rec):
    return ("%s — not assessed. Organisation profile: `%s: false`, declared %s by %s — %s"
            % (label, flag, rec["declaredOn"], rec["declaredBy"], rec["basis"]))

skipped = [
    {"battery": "nydfs-notification", "label": "NYDFS Part 500 notification",
     "flag": "nydfsScope", "source": "profile", "declaredBy": "General Counsel",
     "declaredOn": "2026-03-02", "basis": "No New York licensed activity.",
     "sentence": sentence("NYDFS Part 500 notification", "nydfsScope",
                          profile["nydfsScope"])},
    {"battery": "sec-item-105", "label": "SEC Item 1.05 disclosure window",
     "flag": "secItem105Scope", "source": "profile", "declaredBy": "General Counsel",
     "declaredOn": "2026-03-02",
     "basis": "No class registered under the Exchange Act and no s.15(d) reporting "
              "obligation.",
     "sentence": sentence("SEC Item 1.05 disclosure window", "secItem105Scope",
                          profile["secItem105Scope"])},
]
payload = {
    "contractVersion": "CAC-AP-1",
    "schemaVersion": 1,
    "orgName": "Northwind Manufacturing",
    "profileVersion": "FY26 close",
    "profileReviewedOn": "2026-08-07",
    "profile": profile,
    "revenue": {"exact": 412000000.0, "currency": "EUR", "fiscalYear": "FY26",
                "declaredBy": "CFO", "declaredOn": "2026-08-07",
                "basis": "FY26 audited consolidated accounts"},
    "crownJewels": [],
    "applicability": {"incident": {"ask": ["dora-windows"], "skipped": skipped}},
}
json.dump(payload, open(sys.argv[1], "w"), indent=2)
PYEOF

# --- the store -----------------------------------------------------------------
#
# I-001 tracks no regime, so a skipped battery has somewhere visible to land.
# I-002 tracks DORA, which the profile declares in scope — the presence half of the pair.
# I-003 declares, at the incident, that it happened at a listed subsidiary (§2.3, re-adds).
# I-004 declares that DORA does not reach it (§2.3, the other direction).
# I-005 says nothing at all, with `null` recorded — which must NOT override.
# I-006 tracks sec-1.05 against a profile that says the org is not listed — the conflict.
"$PY" "$E" init "$S" --client "Northwind Manufacturing" --actor eval >/dev/null
"$PY" "$E" open "$S" --title "Portal credential stuffing" --discovered 2026-07-06 \
  --actor eval >/dev/null
"$PY" "$E" open "$S" --title "EU payments latency" --discovered 2026-07-20 \
  --regime dora --actor eval >/dev/null
"$PY" "$E" set-anchor "$S" --id I-002 --aware 2026-07-20T08:00:00+00:00 --actor eval >/dev/null
"$PY" "$E" open "$S" --title "Listed subsidiary breach" --discovered 2026-07-22 \
  --actor eval >/dev/null
"$PY" "$E" open "$S" --title "Out-of-scope affiliate outage" --discovered 2026-07-23 \
  --actor eval >/dev/null
"$PY" "$E" open "$S" --title "Undeclared subject" --discovered 2026-07-24 \
  --actor eval >/dev/null
"$PY" "$E" open "$S" --title "Tracked against Item 1.05 anyway" --discovered 2026-07-25 \
  --regime sec-1.05 --actor eval >/dev/null

"$PY" "$E" declare-context "$S" --id I-003 --flag secItem105Scope --value true \
  --by "General Counsel" --on 2026-07-22 \
  --basis "The affected entity is the US subsidiary, itself an Exchange Act registrant." \
  --actor eval >/dev/null
"$PY" "$E" declare-context "$S" --id I-004 --flag doraScope --value false \
  --by "General Counsel" --on 2026-07-23 \
  --basis "The affiliate is outside the authorised entity and holds no ICT contract." \
  --actor eval >/dev/null
"$PY" "$E" declare-context "$S" --id I-005 --flag secItem105Scope --value null \
  --by "General Counsel" --on 2026-07-24 \
  --basis "Entity boundary not yet established; recorded so the gap is visible." \
  --actor eval >/dev/null

"$PY" "$E" analyze "$S" --today 2026-08-01 --out "$PLAIN" >/dev/null || {
  printf 'applicability: analyze without --context failed outright\n'; exit 1; }
"$PY" "$E" analyze "$S" --today 2026-08-01 --context "$P" --out "$NARROW" >/dev/null || {
  printf 'applicability: analyze --context failed outright\n'; exit 1; }

# q <file> <expr over `a`>
q() { "$PY" -c 'import json,sys
a = json.load(open(sys.argv[1]))
print(eval(sys.argv[2]))' "$1" "$2"; }
row() { # row <file> <id> <expr over `r`>
  "$PY" -c 'import json,sys
a = json.load(open(sys.argv[1]))
r = [x for x in a["incidents"] if x["id"] == sys.argv[2]][0]
print(eval(sys.argv[3]))' "$1" "$2" "$3"; }

# --- 1. an absent --context changes nothing ------------------------------------
if cmp -s "$PLAIN" "$NARROW"; then
  bad "the narrowed run differs from the plain one" \
      "--context produced an identical file, so every check below is vacuous"
else
  ok "the narrowed run differs from the plain one"
fi

# The additivity check, run against a payload that narrows NOTHING. A profile whose every
# battery is asked must leave the analysis exactly as it was, plus the context blocks and
# nothing else — so stripping those blocks reproduces the un-narrowed file byte-for-byte.
#
# This is deliberately NOT run against the narrowing payload. Narrowing removes the windows
# of a battery that was not asked, which is the whole point of it; a strip-and-compare there
# would only pass if the feature did nothing. The difference the narrowing payload does make
# is accounted for one check at a time further down.
"$PY" "$E" analyze "$skill/examples/example-incident.inc" --today 2026-07-31 \
  --out "$work/ex-plain.json" >/dev/null
"$PY" -c 'import json,sys
d=json.load(open(sys.argv[1]))
d["applicability"]["incident"] = {"ask": ["dora-windows", "sec-item-105"], "skipped": []}
json.dump(d, open(sys.argv[2],"w"), indent=2)' "$P" "$work/allask.json"
"$PY" "$E" analyze "$S" --today 2026-08-01 --context "$work/allask.json" \
  --out "$work/allask-an.json" >/dev/null
# Run against the SHIPPED example, which declares nothing at the incident level. The suite's
# own store cannot answer this question: I-004 declares itself out of DORA scope on the
# record, and a subject declaration narrows whatever the profile says — which is §2.3 doing
# exactly its job, and is asserted as such immediately below.
"$PY" "$E" analyze "$skill/examples/example-incident.inc" --today 2026-07-31 \
  --context "$work/allask.json" --out "$work/ex-allask.json" >/dev/null
"$PY" - "$work/ex-allask.json" "$work/stripped.json" <<'PYEOF'
import json, sys
def strip(node):
    if isinstance(node, dict):
        return {k: strip(v) for k, v in node.items() if k != "context"}
    if isinstance(node, list):
        return [strip(v) for v in node]
    return node
doc = strip(json.load(open(sys.argv[1])))
open(sys.argv[2], "w").write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
PYEOF

if cmp -s "$work/ex-plain.json" "$work/stripped.json"; then
  ok "a profile that narrows nothing changes nothing but the added context blocks"
else
  bad "a profile that narrows nothing changes nothing but the added context blocks" \
      "$(diff "$work/ex-plain.json" "$work/stripped.json" | head -6)"
fi
eq "...and it did add them, so that comparison was not comparing two plain files" \
   "True" "$(q "$work/ex-allask.json" '"context" in a and all("context" in r for r in a["incidents"])')"
eq "a subject declaration narrows even where the profile asks everything" \
   "subject" "$(row "$work/allask-an.json" I-004 '[s["source"] for s in r["context"]["skipped"] if s["battery"] == "dora-windows"][0]')"

# The same invariant against the SHIPPED example, which is a different shape: closed
# incidents, filings recorded, both regimes in play. A rule that holds only on a fixture
# built for it is not an invariant.
"$PY" "$E" analyze "$skill/examples/example-incident.inc" --today 2026-07-31 \
  --context "$P" --out "$work/ex-narrow.json" >/dev/null
"$PY" - "$work/ex-narrow.json" "$work/ex-stripped.json" <<'PYEOF'
import json, sys
def strip(node):
    if isinstance(node, dict):
        return {k: strip(v) for k, v in node.items() if k != "context"}
    if isinstance(node, list):
        return [strip(v) for v in node]
    return node
doc = strip(json.load(open(sys.argv[1])))
open(sys.argv[2], "w").write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
PYEOF
if cmp -s "$work/ex-plain.json" "$work/ex-stripped.json"; then
  ok "the same holds on the shipped example, whose incidents are all regime-tracked"
else
  bad "the same holds on the shipped example, whose incidents are all regime-tracked" \
      "$(diff "$work/ex-plain.json" "$work/ex-stripped.json" | head -6)"
fi

eq "no --context leaves no context block at the top level" \
   "False" "$(q "$PLAIN" '"context" in a')"
eq "and none on an incident row" \
   "False" "$(q "$PLAIN" 'any("context" in r for r in a["incidents"])')"

# --- 2. a declared-false flag skips its battery, with the reason ---------------
eq "the SEC battery is skipped on an incident that tracks no regime" \
   "sec-item-105" "$(row "$NARROW" I-001 '[s["battery"] for s in r["context"]["skipped"]][0]')"
eq "...attributed to the profile, not to the subject" \
   "profile" "$(row "$NARROW" I-001 '[s["source"] for s in r["context"]["skipped"]][0]')"
"$PY" -c 'import json,sys
a=json.load(open(sys.argv[1]))
r=[x for x in a["incidents"] if x["id"]=="I-001"][0]
open(sys.argv[2],"w").write(r["context"]["skipped"][0]["sentence"])' "$NARROW" "$work/sent.txt"
has "the §2.4 sentence names the flag" "secItem105Scope" "$work/sent.txt"
has "...the date it was declared" "2026-03-02" "$work/sent.txt"
has "...and who declared it" "General Counsel" "$work/sent.txt"
eq "the Item 1.05 window is not computed at all for a skipped battery" \
   "0" "$(row "$NARROW" I-001 'len([c for c in r["clocks"] if c["regime"] == "sec-1.05"])')"
# The presence half. An absence check alone passes just as well when the whole list is empty.
eq "...while the DORA windows, whose battery is asked, are all still there" \
   "3" "$(row "$NARROW" I-002 'len([c for c in r["clocks"] if c["regime"] == "dora"])')"
eq "...and that battery is recorded as asked" \
   "True" "$(row "$NARROW" I-002 '"dora-windows" in r["context"]["asked"]')"
eq "an asked battery is never also reported as skipped" \
   "True" "$(q "$NARROW" 'all(set(r["context"]["asked"]).isdisjoint(
      {s["battery"] for s in r["context"]["skipped"]}) for r in a["incidents"])')"
eq "the un-narrowed run computed the SEC window it was denied here" \
   "1" "$(row "$PLAIN" I-001 'len([c for c in r["clocks"] if c["regime"] == "sec-1.05"])')"

# --- 3. §2.3, both directions, in one analysis --------------------------------
eq "a subject declaring itself listed re-adds the battery the profile removed" \
   "True" "$(row "$NARROW" I-003 '"sec-item-105" in r["context"]["asked"]')"
eq "...and the same run still skips it where the subject said nothing" \
   "True" "$(row "$NARROW" I-001 '"sec-item-105" in [s["battery"] for s in r["context"]["skipped"]]')"
eq "the override is recorded, not just acted on" \
   "sec-item-105" "$(row "$NARROW" I-003 '[o["battery"] for o in r["context"]["overrides"]][0]')"
"$PY" -c 'import json,sys
a=json.load(open(sys.argv[1]))
r=[x for x in a["incidents"] if x["id"]=="I-003"][0]
open(sys.argv[2],"w").write(r["context"]["overrides"][0]["sentence"])' "$NARROW" "$work/ovr.txt"
has "...with the subject's own basis in the sentence" "Exchange Act registrant" "$work/ovr.txt"
has "...and its own declarer, which the org-level record cannot supply" \
    "General Counsel" "$work/ovr.txt"
eq "a subject declaring itself out of DORA removes a battery the profile kept" \
   "dora-windows" "$(row "$NARROW" I-004 '[s["battery"] for s in r["context"]["skipped"] if s["battery"] == "dora-windows"][0]')"
eq "...attributed to the subject, so an auditor is not told the org declined it" \
   "subject" "$(row "$NARROW" I-004 '[s["source"] for s in r["context"]["skipped"] if s["battery"] == "dora-windows"][0]')"
eq "...and none of its DORA windows are computed" \
   "0" "$(row "$NARROW" I-004 'len([c for c in r["clocks"] if c["regime"] == "dora"])')"
eq "a subject declaring null does not override the profile" \
   "profile" "$(row "$NARROW" I-005 '[s["source"] for s in r["context"]["skipped"] if s["battery"] == "sec-item-105"][0]')"
eq "...and the null declaration is still visible in the record" \
   "True" "$(row "$NARROW" I-005 '"secItem105Scope" in (r["context"]["subjectDeclared"] or {})')"

# --- 4. the conflict: the incident tracks a regime the profile says is out -----
eq "an incident tracking Item 1.05 against a not-listed profile is a conflict" \
   "sec-item-105" "$(row "$NARROW" I-006 '[c["battery"] for c in r["context"]["conflicts"]][0]')"
eq "...and its window is still computed, because the tool does not overrule the assessor" \
   "1" "$(row "$NARROW" I-006 'len([c for c in r["clocks"] if c["regime"] == "sec-1.05"])')"
eq "...and the conflict is collected at the top level where somebody will see it" \
   "I-006" "$(q "$NARROW" '[c["id"] for c in a["context"]["conflicts"]][0]')"
eq "an incident with no such disagreement raises none" \
   "0" "$(row "$NARROW" I-001 'len(r["context"]["conflicts"])')"

# --- 5. the revenue base, stated and never divided ----------------------------
eq "the revenue base travels exact into the analysis" \
   "412000000.0" "$(q "$NARROW" 'a["context"]["revenueBase"]["exact"]')"
eq "...with the provenance the assessor needs to weigh it" \
   "CFO" "$(q "$NARROW" 'a["context"]["revenueBase"]["declaredBy"]')"
if "$PY" "$suite/business-context/evals/_derivedcheck.py" --stdin < "$NARROW" \
   | grep -q '^clean$'; then
  ok "no key in the analysis names a derived materiality figure"
else
  bad "no key in the analysis names a derived materiality figure" \
      "$("$PY" "$suite/business-context/evals/_derivedcheck.py" --stdin < "$NARROW")"
fi
if "$PY" "$suite/business-context/evals/_derivedcheck.py" --source "$skill" \
   | grep -q '^clean$'; then
  ok "and no shipped file in this skill divides by the revenue base"
else
  bad "and no shipped file in this skill divides by the revenue base" \
      "$("$PY" "$suite/business-context/evals/_derivedcheck.py" --source "$skill")"
fi
eq "the analysis states no percentage of revenue anywhere" \
   "0" "$(grep -c -i 'percent of revenue\|% of revenue\|pctOfRevenue' "$NARROW" || true)"

# --- 6. the determination freezes the profile it was made against (§2.5) ------
"$PY" "$E" determine "$S" --id I-001 --state not-material \
  --rationale "Latency only; no data affected and no customer impact recorded." \
  --decider "General Counsel" --on 2026-07-30 --context "$P" --actor eval >/dev/null
eq "a determination made with a profile freezes the version it used" \
   "FY26 close" "$("$PY" -c 'import json,sys
s=json.load(open(sys.argv[1]))
i=[x for x in s["incidents"] if x["id"]=="I-001"][0]
print(i["determinations"][-1]["contextFrozen"]["profileVersion"])' "$S")"
eq "...and the batteries it did not ask, so a year later the perimeter is readable" \
   "sec-item-105" "$("$PY" -c 'import json,sys
s=json.load(open(sys.argv[1]))
i=[x for x in s["incidents"] if x["id"]=="I-001"][0]
print([b["battery"] for b in i["determinations"][-1]["contextFrozen"]["skipped"]][0])' "$S")"
"$PY" "$E" determine "$S" --id I-002 --state assessing \
  --rationale "Forensics outstanding." --decider "CISO" --on 2026-07-30 \
  --actor eval >/dev/null
eq "a determination made without one carries no frozen block rather than an empty one" \
   "False" "$("$PY" -c 'import json,sys
s=json.load(open(sys.argv[1]))
i=[x for x in s["incidents"] if x["id"]=="I-002"][0]
print("contextFrozen" in i["determinations"][-1])' "$S")"

# --- 7. refusals, and the store left untouched --------------------------------
before="$($PY -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$S")"
echo '{"not": "a payload"}' > "$work/bad.json"
if "$PY" "$E" analyze "$S" --today 2026-08-01 --context "$work/bad.json" \
   > "$work/err.txt" 2>&1; then
  bad "a payload that is not CAC-AP-1 is refused" "it was accepted"
else
  ok "a payload that is not CAC-AP-1 is refused"
fi
has "...naming the contract it wanted" "CAC-AP-1" "$work/err.txt"
"$PY" -c 'import json,sys
d=json.load(open(sys.argv[1])); d.pop("applicability"); json.dump(d, open(sys.argv[2],"w"))' \
  "$P" "$work/noapp.json"
if "$PY" "$E" analyze "$S" --today 2026-08-01 --context "$work/noapp.json" \
   > "$work/err2.txt" 2>&1; then
  bad "a payload with no decided applicability is refused, not silently un-narrowed" \
      "it was accepted"
else
  ok "a payload with no decided applicability is refused, not silently un-narrowed"
fi
has "...naming the command that produces one" "business_context.py export" "$work/err2.txt"
if "$PY" "$E" declare-context "$S" --id I-001 --flag secItem105Scope --value true \
   --by "GC" --actor eval > /dev/null 2>&1; then
  bad "a subject declaration with no --basis is refused" "it was accepted"
else
  ok "a subject declaration with no --basis is refused"
fi
if "$PY" "$E" declare-context "$S" --id I-001 --flag secItem105Scope --value true \
   --basis "because" --actor eval > /dev/null 2>&1; then
  bad "a subject declaration with no --by is refused" "it was accepted"
else
  ok "a subject declaration with no --by is refused"
fi
after="$($PY -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$S")"
eq "both refusals left the store byte-identical" "$before" "$after"

# --- 8. narrowing never moves an escalation -----------------------------------
#
# It cannot, by construction: a battery is only dropped where the incident tracks no such
# regime, and a window that was never tracked was already `not-applicable`, which escalates
# nothing. Asserted rather than assumed, because the day that stops being true is the day a
# profile flag starts suppressing an overdue disclosure window.
"$PY" "$E" analyze "$S" --today 2026-08-01 --out "$work/p2.json" >/dev/null
"$PY" "$E" analyze "$S" --today 2026-08-01 --context "$P" --out "$work/n2.json" >/dev/null
eq "the escalations are identical with and without a profile" \
   "$(q "$work/p2.json" 'json.dumps(a["escalations"], sort_keys=True)')" \
   "$(q "$work/n2.json" 'json.dumps(a["escalations"], sort_keys=True)')"
eq "...and there were some, so that comparison compared something" \
   "True" "$(q "$work/n2.json" 'len(a["escalations"]) > 0')"

# --- 9. a battery this skill does not implement is named, not swallowed -------
eq "a profile answer this skill has no question for is reported, not dropped" \
   "nydfs-notification" "$(q "$NARROW" 'a["context"]["unimplementedBatteries"][0]')"

# --- 10. the real producer, end to end ----------------------------------------
"$PY" "$BC" export "$suite/business-context/examples/example-org.biz" \
  > "$work/real.json" 2>/dev/null || bad "business_context.py export ran" "it did not"
if "$PY" "$E" analyze "$S" --today 2026-08-01 --context "$work/real.json" \
   --out "$work/real-an.json" >/dev/null 2>&1; then
  ok "the real exporter's payload is consumed without adaptation"
else
  ok_out="$("$PY" "$E" analyze "$S" --today 2026-08-01 --context "$work/real.json" 2>&1 | tail -2)"
  bad "the real exporter's payload is consumed without adaptation" "$ok_out"
fi
eq "...and narrows the same way the hand-written one did" \
   "True" "$(row "$work/real-an.json" I-001 '"sec-item-105" in [s["battery"] for s in r["context"]["skipped"]]')"

# --- 11. it reaches the page ---------------------------------------------------
(cd "$skill/renderers" && "$PY" render_worksheet.py --in "$NARROW" \
  --out "$work/w-narrow.html" >/dev/null)
(cd "$skill/renderers" && "$PY" render_worksheet.py --in "$PLAIN" \
  --out "$work/w-plain.html" >/dev/null)
(cd "$skill/renderers" && "$PY" render_board.py --in "$NARROW" \
  --out "$work/b-narrow.html" >/dev/null)
# The needle is the block heading and the declarer, NOT the phrase "not assessed": the
# factor table has printed "not assessed" for an unassessed factor since long before any of
# this existed, so that needle passed on the un-narrowed page too and proved nothing.
has "the worksheet carries the skip sentence where the window would be" \
    "Questions narrowed by the profile" "$work/w-narrow.html"
has "...naming the declarer, so the page answers 'why is this missing'" \
    "General Counsel" "$work/w-narrow.html"
has "the worksheet states the revenue base against the financial factor" \
    "412,000,000" "$work/w-narrow.html"
has "the board render names the profile version the pack was assembled against" \
    "FY26 close" "$work/b-narrow.html"
hasnt "and none of it appears when no profile was supplied" \
      "Questions narrowed by the profile" "$work/w-plain.html"
hasnt "...nor the revenue base, which has no business on an un-narrowed page" \
      "412,000,000" "$work/w-plain.html"
hasnt "the board render never carries the revenue base, narrowed or not" \
      "412,000,000" "$work/b-narrow.html"

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'applicability: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'applicability: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'applicability: all %s checks passed\n' "$checks"
