#!/bin/bash
# Board-safety regression suite.
#
#   ./board-safety.sh [workdir]
#
# Every check here exists because a real artifact failed it. The board-facing renderers
# are the only place in this toolkit where a bug is *seen by the client's directors*
# rather than by the person who can fix it, so they get asserted against rendered HTML
# rather than by reading the code.
#
# Guarding one renderer is not enough and never was: the title guard was written into the
# executive dashboard first, and the printable report — the artifact most likely to be
# handed round a table on paper — kept exposing raw framework wording for a full release.
#
# Exit 0 = all pass. Exit 1 = at least one failure, listed.

set -u
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
work="${1:-$(mktemp -d)}"
# Overridable so the suite can be run on the supported Python floor, not just the
# author's interpreter:  PY=/usr/bin/python3 ./board-safety.sh
PY="${PY:-python3}"
RR="$repo/skills/risk-register"
CSF="$repo/skills/nist-csf"
mkdir -p "$work"

fails=0
chk() {  # chk <id> <description> <PASS|FAIL>
  printf '%-5s %-58s %s\n' "$1" "$2" "$3"
  [ "$3" = PASS ] || fails=$((fails + 1))
}
yn() { [ "$1" -eq 0 ] && echo PASS || echo FAIL; }

echo "Building a fixture: CSF Profile -> gap export -> register import"
"$PY" "$CSF/scripts/profile_analysis.py" init --name "Regression Co" \
  --out "$work/p.csfp" --owner CISO >/dev/null || {
    echo "board-safety: FIXTURE FAILED — profile init errored"; exit 1; }
"$PY" "$CSF/scripts/profile_analysis.py" quickstart-target "$work/p.csfp" >/dev/null || {
    echo "board-safety: FIXTURE FAILED — quickstart-target errored"; exit 1; }
"$PY" "$CSF/scripts/profile_analysis.py" intake add "$work/p.csfp" \
  --label "regression fixture seed" \
  --subjects PR.AA-01 GV.SC-07 DE.AE-03 ID.AM-01 RS.MA-01 RC.RP-01 >/dev/null || {
    echo "board-safety: FIXTURE FAILED — intake add errored"; exit 1; }
for s in PR.AA-01 GV.SC-07 DE.AE-03 ID.AM-01 RS.MA-01 RC.RP-01; do
  "$PY" "$CSF/scripts/profile_analysis.py" set "$work/p.csfp" "$s" \
    --current 0 --target 3 --source in-0001 --confirmed-by fixture \
    --rationale fixture >/dev/null || {
      echo "board-safety: FIXTURE FAILED — could not rate $s"; exit 1; }
done
"$PY" "$CSF/scripts/profile_analysis.py" export-gaps "$work/p.csfp" --out "$work/gaps.csv" >/dev/null || {
  echo "board-safety: FIXTURE FAILED — export-gaps errored"; exit 1; }
rm -f "$work/r.rr"
"$PY" "$RR/scripts/score_register.py" init "$work/r.rr" --client "Regression Co" \
  --assessor CISO >/dev/null || {
    echo "board-safety: FIXTURE FAILED — register init errored"; exit 1; }
# Snapshot BEFORE the import, deliberately. The change log only exists when there is a
# baseline to diff against, so an import-then-render fixture leaves it empty and check 1
# inspects a region that cannot fail. That blind spot shipped: the change log was the
# third route for raw framework wording onto a board page, and this suite passed over it
# for a full release. Do not "simplify" this snapshot away.
"$PY" "$RR/scripts/score_register.py" snapshot "$work/r.rr" \
  --label "Baseline" >/dev/null || {
    echo "board-safety: FIXTURE FAILED — snapshot errored"; exit 1; }
"$PY" "$RR/scripts/score_register.py" import-gaps "$work/gaps.csv" \
  --into "$work/r.rr" --write >/dev/null 2>&1 || {
    echo "board-safety: FIXTURE FAILED — import-gaps errored"; exit 1; }

# A score-only review: the path that used to authorise framework wording for a board.
"$PY" "$RR/scripts/score_register.py" set-score "$work/r.rr" R-001 --residual 5 5 \
  --why "scored, not reworded" >/dev/null || {
    echo "board-safety: FIXTURE FAILED — could not score R-001"; exit 1; }
# An over-appetite risk the board formally accepted, still current.
"$PY" "$RR/scripts/score_register.py" set-score "$work/r.rr" R-002 --residual 5 5 --why x >/dev/null || {
  echo "board-safety: FIXTURE FAILED — could not score R-002"; exit 1; }
"$PY" "$RR/scripts/score_register.py" accept "$work/r.rr" R-002 --approver "Audit Committee" \
  --justification "compensating controls; remediation funded" --revalidate 2099-01-31 \
  --why "board decision" >/dev/null || {
    echo "board-safety: FIXTURE FAILED — could not accept R-002"; exit 1; }

# An over-appetite risk the organisation has since treated out. Check 7 asserts the board
# figures stop counting it — the headline must improve when a risk is closed.
"$PY" "$RR/scripts/score_register.py" set-score "$work/r.rr" R-004 --residual 5 5 \
  --why "worst case before treatment" >/dev/null || {
    echo "board-safety: FIXTURE FAILED — could not score R-004"; exit 1; }
"$PY" "$RR/scripts/score_register.py" set-status "$work/r.rr" R-004 closed \
  --why "treated out; control verified" >/dev/null || {
    echo "board-safety: FIXTURE FAILED — could not close R-004"; exit 1; }

for r in render_board render_dashboard render_report; do
  "$PY" "$RR/renderers/$r.py" "$work/r.rr" "$work/$r.html" >/dev/null || {
    echo "board-safety: FIXTURE FAILED — $r.py errored"; exit 1; }
done
echo

# 1. No provisional raw title appears in any board-facing renderer.
raw=$("$PY" - "$work" <<'PY'
import json, re, sys, pathlib
work = pathlib.Path(sys.argv[1])
reg = json.loads((work / "r.rr").read_text())
titles = [r["title"] for r in reg["risks"] if r.get("provisionalTitle")]
leaks = []
for name in ("render_board", "render_report"):          # board-facing only
    html = (work / f"{name}.html").read_text()
    for t in titles:
        body = t.split(": ", 1)[-1].rstrip("…").strip()
        if len(body) > 30 and body[:60] in html:
            leaks.append(f"{name}:{t[:40]}")
print("|".join(leaks[:3]))
PY
)
chk 1 "no provisional raw title in any board renderer" "$([ -z "$raw" ] && echo PASS || echo "FAIL $raw")"

# 2. Score review alone does not authorize raw framework wording for a board.
chk 2 "score-only review keeps the title withheld" "$("$PY" -c "
import json;d=json.load(open('$work/r.rr'))
r=[x for x in d['risks'] if x['id']=='R-001'][0]
print('PASS' if r['provisionalTitle'] and not r['provisionalScore'] else 'FAIL')")"

# 3. A current accepted risk is never grouped under 'board decision needed'.
chk 3 "accepted risk kept out of 'board decision needed'" "$("$PY" -c "
s=open('$work/render_report.html',encoding='utf-8').read()
if 'board decision needed' not in s: print('FAIL no such section')
else:
    seg=s.split('board decision needed')[1].split('already accepted')[0]
    print('PASS' if 'R-002' not in seg else 'FAIL')")"

# 4. Closure without rationale exits non-zero and leaves the register byte-identical.
before=$(shasum -a 256 "$work/r.rr" | cut -d' ' -f1)
"$PY" "$RR/scripts/score_register.py" set-status "$work/r.rr" R-003 closed >/dev/null 2>&1
rc=$?
after=$(shasum -a 256 "$work/r.rr" | cut -d' ' -f1)
chk 4 "closure without --why refused, register untouched" \
    "$([ $rc -ne 0 ] && [ "$before" = "$after" ] && echo PASS || echo FAIL)"

# 5. Every artifact whose totals include candidates says so.
chk 5 "provisional disclosure present in board + report" \
    "$(grep -q 'risks are provisional' "$work/render_board.html" &&
       grep -q 'risks are provisional' "$work/render_report.html" && echo PASS || echo FAIL)"

# 6. --offline makes the promise in dashboards.md literally true.
"$PY" "$RR/renderers/render_board.py" "$work/r.rr" "$work/off.html" --offline >/dev/null || {
  echo "board-safety: FIXTURE FAILED — offline render_board errored"; exit 1; }
# Passes only when the file contains no absolute URL at all — not merely no font link.
#
# ONE exemption, added when this view started drawing cac_graphics marks: the SVG
# namespace declaration every mark opens with. `xmlns="http://www.w3.org/2000/svg"`
# is an XML name, not a location — nothing fetches it, and the markup is not SVG
# without it. It is removed by exact string before the grep rather than excluded by
# pattern, so an xlink:href, a <use href>, a url() inside a style attribute, or any
# other real URL — including one on the same <svg> element — still fails this check.
sed 's| xmlns="http://www.w3.org/2000/svg"||g' "$work/off.html" | grep -q 'https\?://'
chk 6 "--offline emits no external request" "$([ $? -ne 0 ] && echo PASS || echo FAIL)"

# 7. A closed risk is not counted as over appetite, and is not a top risk.
#
# The engine's summarize() counts every risk regardless of status — that is web-engine
# parity and it stays. The renderers must not repeat it: a headline that never improves
# as risks are treated out is a board figure that cannot be acted on, and the same page
# was reporting the count two different ways (KPI tile from summary, attention panel from
# the live set) inches apart.
chk 7 "closed risk excluded from board over-appetite figures" "$("$PY" - "$work" "$RR" <<'PY'
import json, re, sys, pathlib
work, rr = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
sys.path.insert(0, str(rr / "scripts"))
import score_register as sr

reg = json.loads((work / "r.rr").read_text())
size, appetite = reg["settings"]["matrixSize"], reg["settings"]["appetite"]
closed = [r for r in reg["risks"] if r.get("status") == "closed"]
live = [r for r in reg["risks"] if r.get("status") != "closed"]
expected = sum(1 for r in live if sr.over_appetite(
    sr.exposure(r["residual"]["likelihood"], r["residual"]["impact"]), size, appetite))
whole = sum(1 for r in reg["risks"] if sr.over_appetite(
    sr.exposure(r["residual"]["likelihood"], r["residual"]["impact"]), size, appetite))

problems = []
if not closed:
    problems.append("fixture has no closed risk")
elif expected == whole:
    # Without this the check passes for the wrong reason: if no closed risk is over
    # appetite, filtering and not filtering give the same number.
    problems.append("fixture's closed risk is not over appetite — check proves nothing")

board = (work / "render_board.html").read_text()
m = re.search(r'<div class="n">(\d+) of (\d+)(?: live)? risks</div>', board)
if not m:
    problems.append("board headline not found")
elif int(m.group(1)) != expected:
    problems.append(f"board headline says {m.group(1)} over appetite, live count is {expected}")
elif int(m.group(2)) != len(live):
    problems.append(f"board headline denominator {m.group(2)}, live count is {len(live)}")

for rid in (r["id"] for r in closed):
    for name in ("render_board", "render_dashboard"):
        for block in (work / f"{name}.html").read_text().split('class="toprisk"')[1:]:
            if rid in block[:500]:
                problems.append(f"{name}: closed {rid} listed as a top risk")

print("PASS" if not problems else "FAIL " + "; ".join(problems[:2]))
PY
)"

# 8. The board freshness line renders, and reports the LIVE population.
#
# The sentence opens on its own denominator, so the denominator is the part a director
# actually reasons from — every clause after it is read as a share of that number. The
# engine's summarize() counts closed risks (web-engine parity, see check 7), so "how many
# risks are there" has two answers in this codebase and the board must be given the one
# that shrinks when a risk is treated out.
#
# Matches BOTH "Of 1 live risk:" and "Of 105 live risks:" — freshness_line() pluralises,
# and a pattern that only knew the plural would report the sentence missing from a
# perfectly good single-risk page. Verified against both renderings, not assumed.
#
# BOTH board-facing renderers are required to carry it. freshness_line() lives in
# _common.py and both call it, which is the arrangement this suite's own header argues for:
# a board guard written for one renderer and not the other is how the printable report kept
# exposing raw framework wording for a full release.
chk 8 "board freshness line present and counts live risks" "$("$PY" - "$work" <<'PY'
import json, pathlib, re, sys
work = pathlib.Path(sys.argv[1])
reg = json.loads((work / "r.rr").read_text())
live = [r for r in reg["risks"] if r.get("status") != "closed"]
problems = []
# Anti-vacuity, same discipline as check 7: with no closed risk, live == total and the
# assertion below cannot tell the live population from the whole register.
if len(live) == len(reg["risks"]):
    problems.append("fixture has no closed risk — live == total, denominator proves nothing")

found = {}
for name in ("render_board", "render_report"):          # board-facing only
    path = work / f"{name}.html"
    # read_text() on a missing page raises, which does fail this check — but the traceback
    # goes to stderr and chk is handed an empty string, so the suite prints a blank FAIL.
    # Say what happened instead.
    if not path.exists():
        problems.append(f"{name}: not rendered — check read nothing")
        continue
    found[name] = re.findall(r"Of (\d+) live risks?:", path.read_text())
# BOTH board-facing renderers are required to carry it. This arm used to be conditional on
# render_report — "assert it only if present, so the second page is covered the day it
# appears" — which sounded prudent and was a hole: deleting the sentence from the report
# entirely left this suite all-pass. A guard that cannot see a deletion is not guarding.
# The report now ships one (render_report.exec_summary), so the requirement is stated.
for _name in ("render_board", "render_report"):
    if _name in found and not found[_name]:
        problems.append(f"freshness line absent from {_name}")
for name, hits in found.items():
    if len(hits) > 1:
        problems.append(f"{name}: freshness line rendered {len(hits)} times; it is one caveat")
    elif hits and int(hits[0]) != len(live):
        problems.append(f"{name}: freshness line says {hits[0]} live, register has {len(live)}")
print("PASS" if not problems else "FAIL " + "; ".join(problems[:2]))
PY
)"

# 9. No confidence vocabulary reaches a board-facing view.
#
# An INVERTED check: it fails if anyone later reintroduces the claim this toolkit
# deliberately declines to make. The engine reports AGE — a number it derives from stored
# timestamps. "Confidence" is a decay RATE it cannot derive, on risks whose real rates
# differ wildly: a governance outcome and an asset inventory go stale at nothing like the
# same speed. Naming an age band after confidence would commit the engine to exactly the
# rate it argues is unknowable. External review asked for labelled confidence decay
# ("Current — confidence degrading", "Current (assumed)"); the answer was no, and this
# check is what makes that refusal enforced rather than remembered.
#
# The list here is deliberately NARROW, and check 10 is why. A rendered board page carries
# two populations of prose: the toolkit's own words, and the user's register content — risk
# titles, rationales, acceptance justifications, the translated narrative. "Backups are
# unreliable" is an honest risk statement; "this rating is unreliable" is the confidence
# claim we refuse. A substring scan of the finished page cannot tell them apart, so widening
# this list would start failing on a user's own honest wording — which is why `unreliable`
# is here but the stem `reliab` is not, and why "no longer reliable" slips past this check.
#
# Check 10 closes that gap from the other side, where the ambiguity does not exist: in the
# toolkit's SOURCE, none of this vocabulary has a legitimate use at all, so it can be banned
# by stem. Any phrasing a future contributor picks has to appear as a string literal there.
# The two checks are complementary — narrow over user-mixed output, broad over our own words.
#
# If a future fixture legitimately needs one of these words, change the fixture — not this
# list. The list is the decision.
#
# "expire" is deliberately ABSENT. "past expiry" already reaches board-facing prose from
# pre-existing acceptance-expiry code, and the skill is supposed to *state* the non-expiry
# stance; a substring blacklist cannot read a negation, so banning it would forbid the
# correct sentence. _common.freshness_line() words its closing clause around the term for
# this reason.
#
# Substring, not word-boundary: "decay" must also catch "decays"/"decayed", which is the
# form a reintroduction would most likely take, and the board pages carry no embedded JSON
# or script (render_dashboard does — its inline data repeats the key "acceptanceExpired"
# 106 times, which is the substring collision this check avoids by not scanning it).
#
# render_dashboard is NOT scanned. It is the operational work queue and may legitimately
# say things a board page must not — the same board-facing-only distinction as check 1.
chk 9 "no confidence vocabulary in any board-facing view" "$("$PY" - "$work" <<'PY'
import pathlib, sys
work = pathlib.Path(sys.argv[1])
banned = ("confidence", "degrading", "degraded", "decaying", "decay",
          "current (assumed)", "assumed current", "unreliable")
hits = []
for name in ("render_board", "render_report"):          # board-facing only
    path = work / f"{name}.html"
    # An inverted check that reads nothing reports "clean". Prove there was a page.
    if not path.exists():
        hits.append(f"{name}: not rendered — check read nothing")
        continue
    text = path.read_text().lower()
    if len(text) < 2000 or "regression co" not in text:
        hits.append(f"{name}: {len(text)} bytes, no client name — not a rendered board page")
        continue
    for word in banned:
        if word in text:
            i = text.index(word)
            # No comma inside an f-string replacement field anywhere in this file. bash
            # brace-expands the body of a heredoc that sits inside "$( ... )", so
            # {text[max(0, i - 25):i + 25]} arrives as the literal "text[max(0" — the
            # check still fails, but it quotes this script instead of the offending page.
            # zsh does not do this, so it only shows up in CI. Precompute the bounds.
            start, end = max(0, i - 25), i + 25
            hits.append(f"{name}:{word}:...{text[start:end]}...")
print("PASS" if not hits else "FAIL " + " | ".join(hits[:2]))
PY
)"

# 10. No confidence vocabulary in the source that writes board-facing prose.
#
# The other half of check 9, over the population where the word list can afford to be broad.
# Check 9 scans finished HTML, which mixes our prose with the user's register content, so it
# has to stay narrow enough not to fail on an honest risk title like "backups are
# unreliable" — and that narrowness is exactly what let "no longer reliable" through.
#
# In OUR source the ambiguity is gone: none of this vocabulary has a legitimate use in a
# string the toolkit emits, so it is banned by stem. Whatever phrasing a contributor reaches
# for has to appear as a literal here first, and stems catch the inflections a word list
# cannot enumerate — degrade/degrading/degraded, reliable/reliability/unreliable.
#
# DOCSTRINGS ARE EXEMPT, and that exemption is load-bearing rather than a convenience: the
# refusal has to be explainable, and every file involved carries a paragraph naming the claim
# it declines to make. Comments are exempt for free — they are not in the AST at all. So this
# scans exactly what ships to a page.
#
# _common.py is included because it builds the board freshness sentence. If an operational-
# only string ever genuinely needs this vocabulary it belongs in render_dashboard.py, which
# is not scanned here for the same reason it is not scanned by check 9.
#
# Stems chosen against the whole-word forms they would otherwise ban: `assumed` not `assum`
# (an "assumption" is a legitimate word), `certainty`/`uncertain` not `certain` ("certain
# risks" means "some"). Verified zero hits at the time of writing, so a hit is a change.
chk 10 "no confidence vocabulary in the source of any board-facing view" "$("$PY" - "$repo" <<'PY'
import ast, pathlib, sys
repo = pathlib.Path(sys.argv[1])
STEMS = ("confiden", "degrad", "decay", "reliab", "assumed",
         "trust", "certainty", "uncertain", "doubt")
FILES = ("skills/risk-register/renderers/render_board.py",
         "skills/risk-register/renderers/render_report.py",
         "skills/risk-register/renderers/_common.py")
problems = []
scanned = 0
for rel in FILES:
    path = repo / rel
    if not path.exists():
        problems.append("{}: missing — check read nothing".format(rel))
        continue
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            text = ast.get_docstring(node, clean=False)
            if text:
                docs.add(text)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if node.value in docs:
            continue
        scanned += 1
        low = node.value.lower()
        for stem in STEMS:
            if stem in low:
                snippet = node.value.strip()[:60]
                problems.append("{}:{} {} in {!r}".format(rel, node.lineno, stem, snippet))
# A scan that reads no literals is not a pass. Same rule as the fixture guards above.
if scanned == 0 and not problems:
    problems.append("no string literals scanned at all — the walk is broken, not the source clean")
print("PASS" if not problems else "FAIL " + "; ".join(problems[:2]))
PY
)"

echo
if [ "$fails" -eq 0 ]; then
  echo "board-safety: all checks passed"
else
  echo "board-safety: $fails check(s) FAILED"
fi
exit $([ "$fails" -eq 0 ] && echo 0 || echo 1)
