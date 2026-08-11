#!/usr/bin/env bash
# Ingesting documents changes NOTHING until a person assesses (BL-240).
#
# The acceptance test is borrowed verbatim from `vendor-register/SKILL.md`, which states it as
# the property that makes a reading layer trustworthy:
#
#     "ask → 7 open ← the reading layer changed NOTHING… If proposing ever moves the count,
#      something is wrong."
#
# So: ingest a payload of documents, and every requirement state, every count and the whole
# rendered read model must come back byte-identical. A hundred documents in, nothing moved.
#
# ⚠️ ONE FIELD IS EXCLUDED FROM THE COMPARISON, AND IT HAD TO BE FOUND BY RUNNING IT.
# `analyze` stamps `generatedAt` with wall-clock time, so a naive byte-compare of two runs
# differs ALWAYS — for a reason that has nothing to do with the register. A check written that
# way would have been red on day one, been "fixed" by someone loosening it, and stopped
# guarding anything. It is excluded by name here, and by name only: everything else in the
# report is compared exactly.
#
# THE SECOND HALF is the one the source documents actively push against. A policy PDF says
# "this policy addresses access control" in those words, and `REQUIREMENT_STATES` has no state
# meaning covered, met, satisfied or compliant — every state describes the DOCUMENTS. An
# extraction must therefore produce a PROPOSED AIM, and confirming it must still say only that
# a document exists and is aimed there. This is the most likely place in the product to breach
# that boundary, which is why the vocabulary is asserted on the intake surfaces too and not
# left to `no-coverage-claim.sh` alone.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=18
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }
eq()  { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "expected '$2', got '$3'"; fi; }

echo "intake-proposes-only: $($PY -V 2>&1)"

P="$skill/scripts/policy_register.py"
S="$work/s.pol"
"$PY" "$P" init "$S" --org "Thameside plc" --owner CISO >/dev/null 2>&1 || {
  printf 'intake-proposes-only: FIXTURE FAILED — init errored\n'; exit 1; }

# A payload with real citations, a mapping, and prose that TALKS LIKE A POLICY DOCUMENT —
# "addresses", "ensures compliance" — because that is what the extraction will actually carry.
"$PY" - "$work/p.json" <<'PYEOF'
import json, sys
json.dump({"contractVersion": "CAC-PI-1", "documents": [
    {"title": "Access Control Policy", "owner": "Head of Security", "version": "3.0",
     "citation": "s 4.2, p. 11",
     "note": "The document states that it addresses access control and ensures compliance.",
     "mappedTo": [{"requirement": "AC-1", "citation": "s 4.2.1, p. 12"},
                  {"requirement": "IA-2", "citation": "s 5.1, p. 15"}]},
    {"title": "Incident Response Plan", "owner": "CISO", "version": "2.1",
     "citation": "heading 'Scope', p. 3", "mappedTo": []}]},
    open(sys.argv[1], "w"), indent=1)
PYEOF

report() {   # the read model, with the wall-clock stamp removed — see the header
  "$PY" "$P" analyze "$1" --json 2>/dev/null | "$PY" -c 'import json,sys
d = json.load(sys.stdin); d.pop("generatedAt", None)
print(json.dumps(d, sort_keys=True, indent=1))'
}
sha() { "$PY" -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$1"; }

report "$S" > "$work/before.txt"
before_store="$(sha "$S")"

# --- 1. A REFUSED INGEST LEAVES THE STORE BYTE-IDENTICAL -------------------------------
# `Refusal` fires before the store is opened for writing, and a payload of a hundred documents
# with one bad citation must not half-land.
"$PY" - "$work/nocite.json" <<'PYEOF'
import json, sys
json.dump({"contractVersion": "CAC-PI-1", "documents": [
    {"title": "Good One", "owner": "CISO", "citation": "s 1, p. 1", "mappedTo": []},
    {"title": "No Citation", "owner": "CISO", "mappedTo": []}]},
    open(sys.argv[1], "w"), indent=1)
PYEOF
nocite="$("$PY" "$P" ingest "$S" "$work/nocite.json" 2>&1 || true)"
case "$nocite" in
  *"no citation"*) ok "a document with no citation is refused" ;;
  *) bad "a document with no citation is refused" "got: $nocite" ;;
esac
eq "...and the refusal leaves the store byte-identical — nothing half-landed" \
   "$before_store" "$(sha "$S")"

"$PY" - "$work/nomapcite.json" <<'PYEOF'
import json, sys
json.dump({"contractVersion": "CAC-PI-1", "documents": [
    {"title": "T", "owner": "CISO", "citation": "s 1, p. 1",
     "mappedTo": [{"requirement": "AC-1"}]}]}, open(sys.argv[1], "w"), indent=1)
PYEOF
nomap="$("$PY" "$P" ingest "$S" "$work/nomapcite.json" 2>&1 || true)"
case "$nomap" in
  *"AC-1"*) case "$nomap" in
      *"no citation"*) ok "a MAPPING with no citation is refused, naming the requirement" ;;
      *) bad "a MAPPING with no citation is refused, naming the requirement" "got: $nomap" ;;
    esac ;;
  *) bad "a MAPPING with no citation is refused, naming the requirement" "got: $nomap" ;;
esac

badver="$("$PY" - "$work/badver.json" <<'PYEOF'
import json, sys
json.dump({"contractVersion": "CAC-PI-9", "documents": [
    {"title": "T", "owner": "O", "citation": "c", "mappedTo": []}]},
    open(sys.argv[1], "w"), indent=1)
PYEOF
"$PY" "$P" ingest "$S" "$work/badver.json" 2>&1 || true)"
case "$badver" in
  *"contractVersion"*"CAC-PI-1"*) ok "a contract-version mismatch is refused, naming both" ;;
  *) bad "a contract-version mismatch is refused" "got: $badver" ;;
esac

# THE FIELDS AN IMPORT MAY NOT SET. Each is a way of asking the import to put a document in
# force without a person — the thing T5 exists to make impossible.
for field in state approval supersedes supersededOn; do
  "$PY" - "$work/f.json" "$field" <<'PYEOF'
import json, sys
json.dump({"contractVersion": "CAC-PI-1", "documents": [
    {"title": "T", "owner": "O", "citation": "c", "mappedTo": [], sys.argv[2]: "x"}]},
    open(sys.argv[1], "w"), indent=1)
PYEOF
  out="$("$PY" "$P" ingest "$S" "$work/f.json" 2>&1 || true)"
  case "$out" in
    *"may not set"*"$field"*) ok "an intake carrying \`$field\` is refused by name" ;;
    *) bad "an intake carrying \`$field\` is refused by name" "got: $out" ;;
  esac
done

# --- 2. THE COUNT DOES NOT MOVE --------------------------------------------------------
"$PY" "$P" ingest "$S" "$work/p.json" --actor eval >"$work/ing.txt" 2>&1 || {
  printf 'intake-proposes-only: FIXTURE FAILED — ingest errored\n'; exit 1; }
report "$S" > "$work/after.txt"

if diff -q "$work/before.txt" "$work/after.txt" >/dev/null; then
  ok "ingesting documents leaves the WHOLE read model byte-identical"
else
  bad "ingesting documents leaves the WHOLE read model byte-identical" \
      "$(diff "$work/before.txt" "$work/after.txt" | head -6)"
fi
eq "...and no policy record was created" "0" \
   "$("$PY" -c 'import json,sys;print(len(json.load(open(sys.argv[1]))["policies"]))' "$S")"
eq "...while the proposals ARE recorded, so the ingest did happen" "2" \
   "$("$PY" -c 'import json,sys;print(len(json.load(open(sys.argv[1]))["proposals"]))' "$S")"
# A check that only compared the report would pass on an engine that ingested nothing at all.
case "$(cat "$work/ing.txt")" in
  *"NOTHING ELSE CHANGED"*) ok "...and the command SAYS nothing else changed, every time" ;;
  *) bad "the command says nothing else changed" "got: $(cat "$work/ing.txt")" ;;
esac

# --- 3. assess IS THE ONLY ACT THAT CREATES A RECORD -----------------------------------
noby="$("$PY" "$P" assess "$S" --id PR-001 2>&1 || true)"
case "$noby" in
  *"needs --by"*) ok "assess without --by is refused" ;;
  *) bad "assess without --by is refused" "got: $noby" ;;
esac
nowhy="$("$PY" "$P" assess "$S" --id PR-002 --by CISO --reject 2>&1 || true)"
case "$nowhy" in
  *"needs --why"*) ok "...and rejecting without --why is refused" ;;
  *) bad "rejecting without --why is refused" "got: $nowhy" ;;
esac
"$PY" "$P" assess "$S" --id PR-001 --by "General Counsel" >/dev/null 2>&1

# T5: DRAFT, never in force. The supersession property is structural, not checked — a draft
# cannot be one of two approved documents governing the same requirements.
eq "a confirmed proposal creates a DRAFT, never an approved record" "draft" \
   "$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["policies"][0]["state"])' "$S")"
# T4: an auditor asking "where did this row come from" gets a document and a page.
eq "...carrying viaProposal with the citation, not the word 'import'" \
   "s 4.2, p. 11" \
   "$("$PY" -c 'import json,sys
ps = [p for p in json.load(open(sys.argv[1]))["policies"] if p.get("viaProposal")]
print(ps[0]["viaProposal"]["citation"] if ps else "<no record carries viaProposal>")' "$S")"

# --- 4. THE BOUNDARY THE SOURCE DOCUMENT PUSHES AGAINST --------------------------------
# The payload's own note says the document "addresses access control and ensures compliance".
# None of that vocabulary may reach a STATE or a rendered claim. Asserted on the intake
# surfaces specifically, because `no-coverage-claim.sh` scans the shipped engine and docs and
# would not see a state invented at intake time.
claims="$("$PY" -c 'import json,subprocess,sys
out = subprocess.run([sys.executable, sys.argv[1], "analyze", sys.argv[2], "--json"],
                     capture_output=True, text=True).stdout.lower()
banned = [w for w in ("covered", "compliant", "satisfied", "\"met\"") if w in out]
print(",".join(banned) or "none")' "$P" "$S")"
eq "no coverage vocabulary reaches the read model, whatever the document said" "none" "$claims"
props="$("$PY" "$P" proposals "$S" 2>&1)"
case "$props" in
  *"PROPOSED aim, not a coverage claim"*) ok "...and the proposals view says so in those words" ;;
  *) bad "the proposals view names the boundary" "got: $props" ;;
esac

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'intake-proposes-only: ran %d checks, expected %d — a case stopped executing\n' \
         "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'intake-proposes-only: %d of %d checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'intake-proposes-only: all %d checks passed\n' "$checks"
