#!/usr/bin/env bash
# Board-safety for the policy register: no confidence vocabulary reaches a reader-facing view.
#
# This is the same rule as risk-register/evals/board-safety.sh checks 9 and 10, applied to
# this skill's surface. It is a separate file rather than an extra case over there because
# each skill must be verifiable on its own — a user with only this directory can still run it.
#
# Two populations, two word lists, for the reason the original states: the rendered HTML mixes
# our prose with the user's own policy titles, so it is scanned narrowly; our source has no
# legitimate use for any of the vocabulary, so it is banned by stem.
#
# The stakes are specific here. This page is handed to an auditor. A sentence in it that
# sounds more sure than the data supports is not a wording problem — it is the organisation
# telling a regulator something it cannot evidence, in a document it produced itself.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
. "$here/../../../tools/eval-probe.sh"   # `probe` — a crashed check is not a clean one (BL-121)
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=7
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

echo "board-safety (policy): $($PY -V 2>&1)"

$PY "$skill/scripts/policy_register.py" analyze "$skill/examples/example.pol" \
    --today 2026-08-09 --out "$work/a.json" >/dev/null
(cd "$skill/renderers" && $PY render_requirements.py --in "$work/a.json" \
   --out "$work/req.html" --offline) >/dev/null

# 1. Rendered output. Narrow list: a user's own policy could legitimately be titled
# "Trusted Device Standard", so only the words that make a claim about our own certainty.
hit=$(probe "$work/req.html" <<'PY'
import re, sys
text = re.sub(r"<[^>]+>", " ", open(sys.argv[1], encoding="utf-8").read()).lower()
banned = ("confidence", "degrading", "degraded", "decaying", "decay",
          "no longer reliable", "less reliable", "unreliable")
print(",".join(b for b in banned if b in text))
PY
)
if [ -z "$hit" ]; then ok "no confidence vocabulary in the rendered requirement view"
else bad "no confidence vocabulary in the rendered requirement view" "found: $hit"; fi

# 2. Catastrophizing, on the same page. Deliberately NOT banning "severe", "critical" or
# "major": those are the classification vocabulary the frameworks themselves use, and banning
# them would ban the subject matter.
hit=$(probe "$work/req.html" <<'PY'
import re, sys
text = re.sub(r"<[^>]+>", " ", open(sys.argv[1], encoding="utf-8").read()).lower()
banned = ("catastroph", "devastat", "existential", "crippl", "disastrous", "nightmare",
          "ruinous", "calamit", "apocalyp", "bet-the-company", "reputational ruin",
          "could destroy", "wiped out")
print(",".join(b for b in banned if b in text))
PY
)
if [ -z "$hit" ]; then ok "no catastrophizing in the rendered requirement view"
else bad "no catastrophizing in the rendered requirement view" "found: $hit"; fi

# 3. Our source, by stem. Docstrings are exempt — the refusal has to be explainable, and
# every file here carries a paragraph naming the claim it declines to make.
res=$(probe "$skill" <<'PY'
import ast, pathlib, sys
root = pathlib.Path(sys.argv[1])
STEMS = ("confiden", "degrad", "decay", "reliab", "assumed",
         "trust", "certainty", "uncertain", "doubt",
         "catastroph", "devastat", "existential", "crippl", "disastrous",
         "nightmare", "ruinous", "calamit", "apocalyp")
FILES = ("renderers/_common.py", "renderers/render_requirements.py",
         "scripts/policy_register.py")
problems, scanned = [], 0
for rel in FILES:
    path = root / rel
    if not path.exists():
        problems.append("%s: missing — the check read nothing" % rel)
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
                    problems.append("%s:%d contains %r: %r"
                                    % (rel, node.lineno, s, node.value[:60]))
if scanned != len(FILES):
    problems.append("scanned %d of %d files" % (scanned, len(FILES)))
print("\n".join(problems))
PY
)
if [ -z "$res" ]; then ok "no confidence vocabulary in the source of the reader-facing view"
else bad "no confidence vocabulary in the source of the reader-facing view" "$res"; fi

# 4. The caveat that stops the whole misreading is ON THE PAGE, not tucked into a footer.
# This is the sharpest edge in this skill: a register that looks like a compliance dashboard
# and is handed to an auditor as one is worse than no register, and a reader who does not see
# this paragraph has not been told the thing that most affects how they should read it.
if grep -q "What a mapping does and does not say" "$work/req.html" \
   && grep -q "not evidence that the requirement is met" "$work/req.html"; then
  ok "the page carries the not-evidence caveat as a block, not a footnote"
else
  bad "the page carries the not-evidence caveat" "absent or reworded"
fi

# 5. Not legal advice, on the artifact.
if grep -q "Not legal advice" "$work/req.html"; then
  ok "the requirement view says it is not legal advice"
else
  bad "the requirement view says it is not legal advice" "absent"
fi

# --- The --offline guarantee, actually verified --------------------------------
#
# ONE exemption: the SVG namespace declaration each cac_graphics mark opens with.
# `xmlns="http://www.w3.org/2000/svg"` is an XML name, not a location. Stripped by exact
# string rather than by pattern, so an xlink:href, a <use href>, a url() inside a style
# attribute, or any other real URL still fails this check.
_f="$work/req.html"
if [ ! -s "$_f" ]; then
  bad "--offline emits no external request" "file missing or empty"
elif sed 's| xmlns="http://www.w3.org/2000/svg"||g' "$_f" | grep -q 'https\?://'; then
  bad "--offline emits no external request" \
      "found: $(sed 's| xmlns="http://www.w3.org/2000/svg"||g' "$_f" \
                | grep -o 'https\?://[^"'"'"' )]*' | sort -u | head -3 | tr '\n' ' ')"
else
  ok "--offline emits no external request"
fi

# --- C-1: the sentences carry a consequence, the decisions decide -------------
#
# The scan lives once, under board-pack, because nine copies of a linguistic rule would drift
# into nine slightly different rules. See board-pack/evals/outcome-framing.sh for the full
# argument and the mutation proofs; this is the per-producer call.
_scan="$(cd "$here/../../board-pack/evals" && pwd)/_outcomescan.py"
_sidecar=""
for _cand in "$skill"/references/example-translations.json \
             "$skill"/examples/example-translations.json \
             "$skill"/examples/pack.board.json; do
  [ -f "$_cand" ] && _sidecar="$_cand" && break
done
if [ -z "$_sidecar" ]; then
  # The policy register ships no board section in 1.0 — deliberately deferred so the release
  # surface does not widen. Asserted rather than skipped: the day it gains one, this fails
  # and somebody wires it in.
  ok "no board sidecar in this skill, so there is no board prose here to check"
elif "$PY" "$_scan" "$_sidecar" >/dev/null 2>"${TMPDIR:-/tmp}/cac-outcome.$$.err"; then
  ok "every board sentence carries a consequence and every decision decides (C-1)"
else
  bad "every board sentence carries a consequence and every decision decides (C-1)" \
      "$("$PY" "$_scan" "$_sidecar" 2>&1 >/dev/null | grep '^  FAIL' | head -3 | tr '\n' ' ')"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'board-safety (policy): ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'board-safety (policy): %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'board-safety (policy): all %s checks passed\n' "$checks"
