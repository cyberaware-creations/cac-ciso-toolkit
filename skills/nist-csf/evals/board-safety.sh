#!/usr/bin/env bash
# Board-safety for the CSF Profile dashboards.
#
# This skill went four phases without one, which the README now says out loud. It renders
# two board-facing views and was the only producer in the suite with no inverted suite of
# its own, so the confidence-vocabulary rule the other five enforce was simply unenforced
# here. Everything below is the same shape as risk-register/evals/board-safety.sh checks 9
# and 10, plus the two claims that are specific to a Profile: a Tier is not a score, and a
# suppressed coverage figure must not reappear anywhere -- including on stdout.
#
# Two populations, two word lists, for the reason the original states: the rendered HTML
# mixes our prose with the user's own Subcategory notes and source labels, so it is scanned
# narrowly; our own source has no legitimate use for the vocabulary, so it is banned by stem.
#
# Two deliberate divergences from the metrics list, both of which this skill forced:
#
#   * `trust` is NOT banned. The evidence bar ends "...none of this says how much to trust
#     a rating", which is the disclaimer itself. Banning the word bans the sentence that
#     makes the refusal. Check 8 pins that sentence instead, so the word stays present in
#     exactly one form -- negated.
#   * The engine's `_cmd_self_test` is exempt alongside docstrings. It asserts that a queue
#     row carries no "confidence" key, which requires writing the word down. The refusal has
#     to be assertable for the same reason it has to be explainable.
#
# Every check below was mutation-tested: the skill was broken in a specific way and the
# check that claims the property was confirmed to be the one that failed. A check that has
# never failed is not a check. In order:
#
#   1,5   "distance from that cadence" -> "our confidence in the rating"
#   2     operational page title gains "— degraded"
#   3,4   each page title gains "a devastating quarter"
#   6     the "ratings do not expire" sentence replaced with "a freshness score"
#   7     the Core's Tier readerNote rewritten to "how mature the programme is, higher is better"
#   8     the "how much to trust a rating" sentence deleted
#   9,11  `if guard.get("suppressed")` -> `if False` in render_executive
#   10,11 the same, in render_operational
#   12,13 cov_label() returns "" — the mutant that makes 9-10 pass for nothing
#   14    the stdout guard's ternary forced to the non-suppressed branch
#   15,16 DISCLAIMER shortened so the footer no longer names NIST
#
# The first run of this suite failed that discipline in its own way: the coverage ratio was
# read from the wrong JSON keys, came back empty, and `grep -qF ""` matched every file. Four
# checks passed on an empty needle. The `case` guard below exists because of it.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=16
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

echo "board-safety (nist-csf): $($PY -V 2>&1)"

profile="$skill/examples/example-profile-v2.csfp"

# The shipped Profile has 4 of 105 in-scope Subcategories assessed, so the scope guard is
# ON and the headline coverage figure is withheld. That is the interesting state for a
# safety suite -- but a suite that only ever sees the suppressed page would pass just as
# happily against a renderer that never printed coverage at all. So a second fixture lowers
# `reporting.scopeThresholdPct` (a documented setting, not a fabricated rating) until the
# same Profile clears its own bar, and checks 12-13 require the figure to come back.
$PY - "$profile" "$work/open.csfp" <<'PY'
import json, sys
store = json.load(open(sys.argv[1], encoding="utf-8"))
store["profile"]["settings"]["reporting"]["scopeThresholdPct"] = 1
json.dump(store, open(sys.argv[2], "w", encoding="utf-8"), indent=2)
PY

$PY "$skill/scripts/profile_analysis.py" analyze "$profile" \
    --today 2026-07-31 --out "$work/a.json" >/dev/null
$PY "$skill/scripts/profile_analysis.py" analyze "$work/open.csfp" \
    --today 2026-07-31 --out "$work/open.json" >/dev/null

# stdout is captured, not discarded: check 14 is about what the renderer prints, and an
# agent reads stdout and repeats it to the user.
(cd "$skill/renderers" && $PY render_executive.py --in "$work/a.json" \
   --translations "$skill/references/example-translations.json" \
   --out "$work/board.html" --offline) > "$work/board.stdout"
(cd "$skill/renderers" && $PY render_operational.py --in "$work/a.json" \
   --out "$work/op.html" --offline) > "$work/op.stdout"
(cd "$skill/renderers" && $PY render_executive.py --in "$work/open.json" \
   --translations "$skill/references/example-translations.json" \
   --out "$work/open-board.html" --offline) > "$work/open-board.stdout"
(cd "$skill/renderers" && $PY render_operational.py --in "$work/open.json" \
   --out "$work/open-op.html" --offline) > "$work/open-op.stdout"

# Shared reader: strips <style> and <script> bodies before the tags, because a stylesheet is
# full of "100%" and "width:60%" and a percentage scan over raw HTML is noise.
read_text() {
  $PY - "$1" <<'PY'
import re, sys
html = open(sys.argv[1], encoding="utf-8").read()
html = re.sub(r"(?is)<(style|script)\b.*?</\1>", " ", html)
sys.stdout.write(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)))
PY
}

for page in board op; do
  read_text "$work/$page.html" > "$work/$page.txt"
done
for page in open-board open-op; do
  read_text "$work/$page.html" > "$work/$page.txt"
done

# 1-2. Rendered output, narrow list. A user's own source label could legitimately read
# "vendor trust review", so only the words that make a claim about our own certainty.
for page in board op; do
  hit=$($PY - "$work/$page.txt" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8").read().lower()
banned = ("confidence", "degrading", "degraded", "decaying", "decay",
          "no longer reliable", "less reliable", "unreliable")
print(",".join(b for b in banned if b in text))
PY
)
  if [ -z "$hit" ]; then ok "no confidence vocabulary in the rendered $page view"
  else bad "no confidence vocabulary in the rendered $page view" "found: $hit"; fi
done

# 3-4. Catastrophizing, same two pages. Deliberately NOT banning "severe", "critical" or
# "major": those are the frameworks' own classification vocabulary, and banning them would
# ban the subject matter.
for page in board op; do
  hit=$($PY - "$work/$page.txt" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8").read().lower()
banned = ("catastroph", "devastat", "existential", "crippl", "disastrous", "nightmare",
          "ruinous", "calamit", "apocalyp", "bet-the-company", "reputational ruin",
          "could destroy", "wiped out")
print(",".join(b for b in banned if b in text))
PY
)
  if [ -z "$hit" ]; then ok "no catastrophizing in the rendered $page view"
  else bad "no catastrophizing in the rendered $page view" "found: $hit"; fi
done

# 5. Our source, by stem. Docstrings and the engine's self-test are exempt: the refusal has
# to be explainable and assertable, and every file here carries a paragraph naming the claim
# it declines to make. `trust` is absent from STEMS on purpose -- see the header, and 8.
res=$($PY - "$skill" <<'PY'
import ast, pathlib, sys
root = pathlib.Path(sys.argv[1])
STEMS = ("confiden", "degrad", "decay", "reliab", "certainty", "uncertain", "doubt",
         "catastroph", "devastat", "existential", "crippl", "disastrous",
         "nightmare", "ruinous", "calamit", "apocalyp")
FILES = ("renderers/_common.py", "renderers/render_executive.py",
         "renderers/render_operational.py", "scripts/profile_analysis.py")
problems, scanned = [], 0
for rel in FILES:
    path = root / rel
    if not path.exists():
        problems.append("{}: missing -- the check read nothing".format(rel))
        continue
    scanned += 1
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings, exempt_spans = set(), []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            d = ast.get_docstring(node, clean=False)
            if d is not None:
                docstrings.add(d)
        if isinstance(node, ast.FunctionDef) and "self_test" in node.name:
            exempt_spans.append((node.lineno, node.end_lineno))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if node.value in docstrings:
            continue
        if any(lo <= node.lineno <= hi for lo, hi in exempt_spans):
            continue
        low = node.value.lower()
        for s in STEMS:
            if s in low:
                problems.append("{}:{} contains {!r}: {!r}".format(
                    rel, node.lineno, s, node.value[:60]))
if scanned != len(FILES):
    problems.append("scanned {} of {} files".format(scanned, len(FILES)))
print("\n".join(problems))
PY
)
if [ -z "$res" ]; then ok "no confidence vocabulary in the source of any board-facing view"
else bad "no confidence vocabulary in the source of any board-facing view" "$res"; fi

# 6. Age is stated as a distance from a chosen cadence, and nothing expires.
if grep -q "Ratings do not expire" "$work/board.txt" \
   && grep -q "distance from that cadence" "$work/board.txt"; then
  ok "the board view states that ratings do not expire and age is a distance"
else
  bad "the board view states that ratings do not expire and age is a distance" \
      "one or both of the two sentences is missing"
fi

# 7. A Tier is rigor, and explicitly not a score derived from the ratings. NIST is explicit
# about this and it is the single easiest thing for a board to misread off a dashboard.
if grep -q "not a score calculated from the ratings" "$work/board.txt" \
   && grep -q "not automatically better" "$work/board.txt"; then
  ok "the Tier block says a Tier is not a score and higher is not automatically better"
else
  bad "the Tier block says a Tier is not a score and higher is not automatically better" \
      "the Tier disclaimer is missing or reworded"
fi

# 8. The one legitimate use of `trust` in this skill is the negation, which is why the stem
# list omits it. If this sentence is ever deleted or inverted, the omission stops being safe
# and this check is what notices.
if grep -q "none of this says how much to trust a rating" "$work/board.txt"; then
  ok "the evidence bar disclaims that any of it says how much to trust a rating"
else
  bad "the evidence bar disclaims that any of it says how much to trust a rating" \
      "the disclaimer is absent -- 'trust' is unbanned in check 5 on the strength of it"
fi

# 9-11. The scope guard binds BOTH dashboards. With 4 of 105 assessed the headline coverage
# figure is withheld; the ratio is the derived number itself, so it is the thing to look for
# rather than any one page's wording. The guard suppresses rather than caveats, but it must
# still say that it did -- a figure that is silently absent reads as a figure of zero.
ratio=$($PY - "$work/open.json" <<'PY'
import json, sys
cov = json.load(open(sys.argv[1], encoding="utf-8"))["coverage"]["overall"]
print("({}/{})".format(cov["n"], cov["d"]))
PY
)
# An empty needle makes `grep -qF` match every file, which would turn checks 9-13 into four
# guaranteed passes and one guaranteed failure. It did exactly that on the first run here.
case "$ratio" in
  "("*"/"*")") : ;;
  *) printf 'board-safety (nist-csf): could not read the coverage ratio (got %s)\n' \
       "${ratio:-<empty>}"; exit 1 ;;
esac
for page in board op; do
  if ! grep -qF "$ratio" "$work/$page.txt"; then
    ok "below threshold, the coverage figure $ratio does not appear in the $page view"
  else
    bad "below threshold, the coverage figure $ratio does not appear in the $page view" \
        "the suppressed headline reappeared"
  fi
done
if grep -q "No headline coverage figure is reported" "$work/board.txt" \
   && grep -q "No headline coverage figure is reported" "$work/op.txt"; then
  ok "both views say the figure was withheld rather than omitting it silently"
else
  bad "both views say the figure was withheld rather than omitting it silently" \
      "at least one view suppresses without explaining"
fi

# 12-13. Anti-vacuity. Checks 9-10 pass trivially against a renderer that never prints
# coverage at all, so the same Profile over its own lowered threshold must print it.
for page in open-board open-op; do
  if grep -qF "$ratio" "$work/$page.txt"; then
    ok "above threshold, the coverage figure $ratio does render in the ${page#open-} view"
  else
    bad "above threshold, the coverage figure $ratio does render in the ${page#open-} view" \
        "checks 9-10 are vacuous: this view never shows coverage either way"
  fi
done

# 14. The guard binds stdout too, which `_common.py` states in a comment and nothing tested.
# An agent reads what the renderer prints and repeats it to the user, so a number withheld
# from the page and printed to the terminal has not been withheld.
if grep -q "withheld" "$work/board.stdout" && ! grep -qF "$ratio" "$work/board.stdout" \
   && grep -q "withheld" "$work/op.stdout" && ! grep -qF "$ratio" "$work/op.stdout"; then
  ok "the suppressed figure is withheld from renderer stdout, not just from the page"
else
  bad "the suppressed figure is withheld from renderer stdout, not just from the page" \
      "stdout: $(tr '\n' ' ' < "$work/board.stdout")"
fi

# 15-16. The non-affiliation footer.
for page in board op; do
  if grep -q "Not affiliated with NIST" "$work/$page.txt"; then
    ok "the $page view carries the non-affiliation footer"
  else
    bad "the $page view carries the non-affiliation footer" "footer absent"
  fi
done

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'board-safety (nist-csf): ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'board-safety (nist-csf): %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'board-safety (nist-csf): all %s checks passed\n' "$checks"
