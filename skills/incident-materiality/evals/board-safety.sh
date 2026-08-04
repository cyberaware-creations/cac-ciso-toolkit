#!/usr/bin/env bash
# Board-safety for the incident section — the extended guard.
#
# It inherits the toolkit rule (no confidence vocabulary reaches a board view; age and
# distance are distances, never claims about how true a number still is) and adds three
# obligations this skill carries that the siblings do not:
#
#   1. **No catastrophizing.** The kill report was explicit: SEC cyber-disclosure enforcement
#      pulled back, and fear-based framing is disqualifying. An incident page that reads as a
#      threat is selling something. It is also, separately, discoverable — a document that
#      describes an incident in terms nobody would defend later is a bad artifact whatever
#      its sales value.
#   2. **No verdict.** Nothing generated may read as the tool's own materiality conclusion.
#      Every determination on a rendered page must be attributed to the person who made it.
#   3. **Not legal advice, on every artifact**, together with the rule that the Item 1.05
#      window starts at the determination — the fact whose absence most reliably misleads.
#
# Two populations, two word lists, for the reason the original states: the rendered HTML mixes
# our prose with the user's own incident titles and rationales, so it is scanned narrowly over
# the shipped example; our source has no legitimate use for any of the vocabulary, so it is
# banned by stem.
#
# Check 17 is the guard checking itself. A scanner nobody has seen fail is a scanner nobody
# knows is wired up.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=19
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

echo "board-safety (incident): $($PY -V 2>&1)"

$PY "$skill/scripts/incident_analysis.py" analyze "$skill/examples/example-incident.inc" \
    --today 2026-07-31 --now 2026-07-31T09:00:00+00:00 --out "$work/a.json" >/dev/null
(cd "$skill/renderers" && $PY render_board.py --in "$work/a.json" \
   --translations "$skill/examples/example-translations.json" \
   --out "$work/board.html" --offline) >/dev/null
(cd "$skill/renderers" && $PY render_worksheet.py --in "$work/a.json" \
   --out "$work/ws.html" --offline) >/dev/null

# scan <file> <list-name> — returns the banned words present in the rendered text.
scan() {
  $PY - "$1" "$2" <<'PY'
import re, sys
text = re.sub(r"<[^>]+>", " ", open(sys.argv[1], encoding="utf-8").read()).lower()
LISTS = {
  # Words that make a claim about how much our own numbers can be believed.
  "confidence": ("confidence", "degrading", "degraded", "decaying", "decay",
                 "no longer reliable", "less reliable", "unreliable"),
  # Words that turn a governance record into a threat. Deliberately not "severe",
  # "critical" or "major" — those are the classification vocabulary the regimes
  # themselves use, and banning them would ban the subject matter.
  "catastrophe": ("catastroph", "devastat", "existential", "crippl", "disastrous",
                  "nightmare", "ruinous", "calamit", "apocalyp", "bet-the-company",
                  "reputational ruin", "could destroy", "wiped out"),
  # Sentences that would read as the tool's own conclusion.
  "verdict": ("we recommend", "we assess", "appears material", "likely material",
              "you must file", "you should file", "materiality score",
              "the tool determines"),
}
print(",".join(w for w in LISTS[sys.argv[2]] if w in text))
PY
}

# 1-6. The rendered pages, three lists each.
for page in board ws; do
  label=$([ "$page" = board ] && echo "board" || echo "worksheet")
  for list in confidence catastrophe verdict; do
    hit=$(scan "$work/$page.html" "$list")
    if [ -z "$hit" ]; then ok "no $list vocabulary in the rendered $label view"
    else bad "no $list vocabulary in the rendered $label view" "found: $hit"; fi
  done
done

# 7. Our source, by stem. Docstrings are exempt — every refusal has to be explainable, and
# every file here carries a paragraph naming the claim it declines to make.
res=$($PY - "$skill" <<'PY'
import ast, pathlib, sys
root = pathlib.Path(sys.argv[1])
STEMS = ("confiden", "degrad", "decay", "reliab", "assumed", "certainty", "uncertain",
         "doubt", "catastroph", "devastat", "existential", "crippl", "disastrous",
         "nightmare", "ruinous", "calamit", "apocalyp", "we recommend", "we assess",
         "materiality score")
FILES = ("renderers/_common.py", "renderers/render_board.py",
         "renderers/render_worksheet.py", "scripts/incident_analysis.py")
problems, scanned = [], 0
for rel in FILES:
    path = root / rel
    if not path.exists():
        problems.append(f"{rel}: missing — the check read nothing")
        continue
    scanned += 1
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            d = ast.get_docstring(node, clean=False)
            if d is not None:
                docstrings.add(d)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in docstrings:
                continue
            low = node.value.lower()
            for s in STEMS:
                if s in low:
                    problems.append(f"{rel}:{node.lineno} contains {s!r}: {node.value[:60]!r}")
if scanned != len(FILES):
    problems.append(f"scanned {scanned} of {len(FILES)} files")
print("\n".join(problems))
PY
)
if [ -z "$res" ]; then ok "no banned vocabulary in the source of any board-facing view"
else bad "no banned vocabulary in the source of any board-facing view" "$res"; fi

# 8-9. Not legal advice, on every artifact — as a block, not only in the footer.
for page in board ws; do
  label=$([ "$page" = board ] && echo "board" || echo "worksheet")
  if grep -q "Not legal advice" "$work/$page.html" \
     && grep -q "not a substitute for counsel" "$work/$page.html"; then
    ok "the $label view says it is not legal advice, and says why"
  else
    bad "the $label view says it is not legal advice, and says why" "absent from $page"
  fi
done

# 10-11. The no-verdict statement.
for page in board ws; do
  label=$([ "$page" = board ] && echo "board" || echo "worksheet")
  if grep -q "does not make it" "$work/$page.html"; then
    ok "the $label view states that the record does not make the determination"
  else
    bad "the $label view states that the record does not make the determination" "absent"
  fi
done

# 12-13. The clock rule. Its absence is the most reliable way to mislead a reader here:
# a four-business-day window quoted without its anchor reads as running from discovery.
for page in board ws; do
  label=$([ "$page" = board ] && echo "board" || echo "worksheet")
  if grep -q "not from the date it was discovered" "$work/$page.html"; then
    ok "the $label view states that the window runs from the determination"
  else
    bad "the $label view states that the window runs from the determination" "absent"
  fi
done

# 14-15. The discoverability caveat, wherever an incident is linked to an accepted risk.
for page in board ws; do
  label=$([ "$page" = board ] && echo "board" || echo "worksheet")
  if grep -q "Discoverability" "$work/$page.html" \
     && grep -q "discoverable" "$work/$page.html"; then
    ok "the $label view carries the discoverability caveat"
  else
    bad "the $label view carries the discoverability caveat" "absent from $page"
  fi
done

# 16. Every determination rendered on the worksheet is attributed to a named decider. An
# unattributed determination reads as the tool's own, which is the exact failure this whole
# skill is built to avoid.
expected=$($PY -c 'import json,sys
a = json.load(open(sys.argv[1]))
print(sum(len(r["determinations"]) for r in a["incidents"]))' "$work/a.json")
actual=$(grep -o "recorded by" "$work/ws.html" | wc -l | tr -d ' ')
if [ "$expected" = "$actual" ] && [ "$expected" != "0" ]; then
  ok "all $expected determinations on the worksheet are attributed to a named decider"
else
  bad "all determinations on the worksheet are attributed to a named decider" \
      "$actual attributions for $expected determinations"
fi

# 17. The guard, checking itself. Inject fear framing into a copy of the rendered board page
# and assert the scanner catches it. Without this, a scanner that had quietly stopped reading
# the file would report a clean run forever.
sed 's/<h2>Incidents<\/h2>/<h2>Incidents<\/h2><p>This is a catastrophic and existential event.<\/p>/' \
  "$work/board.html" > "$work/injected.html"
inj=$(scan "$work/injected.html" catastrophe)
if [ -n "$inj" ]; then
  ok "injected fear framing IS caught by the guard (found: $inj)"
else
  bad "injected fear framing IS caught by the guard" \
      "the scanner passed a page containing 'catastrophic' and 'existential'"
fi


# --- The --offline guarantee, actually verified --------------------------------
#
# Every renderer here takes --offline and this suite has always passed it, but
# nothing checked that the resulting file makes no outbound request. A flag whose
# effect is never asserted is a flag that can quietly stop working -- and these
# artifacts are meant to open on a board member's laptop, in a room, offline.
#
# ONE exemption: the SVG namespace declaration each cac_graphics mark opens with.
# `xmlns="http://www.w3.org/2000/svg"` is an XML name, not a location -- nothing
# fetches it, and the markup is not SVG without it. Stripped by exact string
# rather than by pattern, so an xlink:href, a <use href>, a url() inside a style
# attribute, or any other real URL still fails this check.
for _f in "$work/board.html" "$work/ws.html"; do
  if [ ! -s "$_f" ]; then
    bad "--offline emits no external request ($(basename "$_f"))" "file missing or empty"
  elif sed 's| xmlns="http://www.w3.org/2000/svg"||g' "$_f" | grep -q 'https\?://'; then
    bad "--offline emits no external request ($(basename "$_f"))" \
        "found: $(sed 's| xmlns="http://www.w3.org/2000/svg"||g' "$_f" \
                  | grep -o 'https\?://[^"'"'"' )]*' | sort -u | head -3 | tr '\n' ' ')"
  else
    ok "--offline emits no external request ($(basename "$_f"))"
  fi
done

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'board-safety (incident): ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'board-safety (incident): %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'board-safety (incident): all %s checks passed\n' "$checks"
