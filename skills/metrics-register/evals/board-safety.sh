#!/usr/bin/env bash
# Board-safety for the metrics section: no confidence vocabulary reaches a board view.
#
# This is the same rule as risk-register/evals/board-safety.sh checks 9 and 10, applied to
# this skill's two surfaces. It is a separate file rather than an extra case over there
# because each skill must be verifiable on its own — a user with only this directory can
# still run it.
#
# Two populations, two word lists, for the reason the original states: the rendered HTML
# mixes our prose with the user's own metric names, so it is scanned narrowly; our source
# has no legitimate use for any of the vocabulary, so it is banned by stem.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=10
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

echo "board-safety (metrics): $($PY -V 2>&1)"

$PY "$skill/scripts/metrics_analysis.py" analyze "$skill/examples/example-metrics.mtr" \
    --today 2026-07-31 --out "$work/a.json" >/dev/null
(cd "$skill/renderers" && $PY render_executive.py --in "$work/a.json" \
   --translations "$skill/examples/example-translations.json" --out "$work/board.html" --offline) >/dev/null
(cd "$skill/renderers" && $PY render_operational.py --in "$work/a.json" \
   --out "$work/op.html" --offline) >/dev/null

# 1-2. Rendered output. Narrow list: a user's own metric could legitimately be named
# "vendor trust score", so only the words that make a claim about our own certainty.
for page in board op; do
  hit=$($PY - "$work/$page.html" <<'PY'
import re, sys
text = re.sub(r"<[^>]+>", " ", open(sys.argv[1], encoding="utf-8").read()).lower()
banned = ("confidence", "degrading", "degraded", "decaying", "decay",
          "no longer reliable", "less reliable", "unreliable")
print(",".join(b for b in banned if b in text))
PY
)
  if [ -z "$hit" ]; then ok "no confidence vocabulary in the rendered $page view"
  else bad "no confidence vocabulary in the rendered $page view" "found: $hit"; fi
done

# Catastrophizing, on the same two pages. Introduced for incident-materiality in Phase C and
# extended here after the board pack caught a shipped sidecar calling an untested backup the
# difference between "a bad week or an existential event". Deliberately NOT banning "severe",
# "critical" or "major": those are the classification vocabulary the frameworks themselves
# use, and banning them would ban the subject matter.
for page in board op; do
  hit=$($PY - "$work/$page.html" <<'PY'
import re, sys
text = re.sub(r"<[^>]+>", " ", open(sys.argv[1], encoding="utf-8").read()).lower()
banned = ("catastroph", "devastat", "existential", "crippl", "disastrous", "nightmare",
          "ruinous", "calamit", "apocalyp", "bet-the-company", "reputational ruin",
          "could destroy", "wiped out")
print(",".join(b for b in banned if b in text))
PY
)
  if [ -z "$hit" ]; then ok "no catastrophizing in the rendered $page view"
  else bad "no catastrophizing in the rendered $page view" "found: $hit"; fi
done

# 3. Our source, by stem. Docstrings are exempt — the refusal has to be explainable, and
# every file here carries a paragraph naming the claim it declines to make.
res=$($PY - "$skill" <<'PY'
import ast, pathlib, sys
root = pathlib.Path(sys.argv[1])
STEMS = ("confiden", "degrad", "decay", "reliab", "assumed",
         "trust", "certainty", "uncertain", "doubt",
         "catastroph", "devastat", "existential", "crippl", "disastrous",
         "nightmare", "ruinous", "calamit", "apocalyp")
FILES = ("renderers/_common.py", "renderers/render_executive.py",
         "scripts/metrics_analysis.py")
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
if [ -z "$res" ]; then ok "no confidence vocabulary in the source of any board-facing view"
else bad "no confidence vocabulary in the source of any board-facing view" "$res"; fi

# 4. The age vocabulary is present and is stated as a distance.
if grep -q "past cadence" "$work/op.html"; then
  ok "reading age is reported as distance from the chosen cadence"
else
  bad "reading age is reported as distance from the chosen cadence" "no cadence wording found"
fi

# 5. The non-affiliation footer.
if grep -q "Not affiliated with NIST" "$work/board.html"; then
  ok "the board view carries the non-affiliation footer"
else
  bad "the board view carries the non-affiliation footer" "footer absent"
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
for _f in "$work/board.html" "$work/op.html"; do
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


# --- C-1: the sentences carry a consequence, the decisions decide -------------
#
# Appended rather than woven in, so every check above is untouched. This suite has always
# tested for ABSENCE — no confidence vocabulary, no reworded score. Nothing tested for
# PRESENCE, and "Patch compliance fell to 88%." passed all of it: a named thing, no
# consequence, no ask.
#
# The scan lives once, under board-pack, because nine copies of a linguistic rule would drift
# into nine slightly different rules. See board-pack/evals/outcome-framing.sh for the full
# argument and the mutation proofs; this is the per-producer call.
_scan="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../board-pack/evals" && pwd)/_outcomescan.py"
_sidecar=""
for _cand in "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"/references/example-translations.json \
             "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"/examples/example-translations.json \
             "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"/examples/pack.board.json; do
  [ -f "$_cand" ] && _sidecar="$_cand" && break
done
if [ -z "$_sidecar" ]; then
  # business-context is framing rather than a section, so it ships no translations sidecar.
  # Asserted rather than skipped: the day it gains one, this fails and somebody wires it in.
  ok "no board sidecar in this skill, so there is no board prose here to check"
elif "$PY" "$_scan" "$_sidecar" >/dev/null 2>"${TMPDIR:-/tmp}/cac-outcome.$$.err"; then
  ok "every board sentence carries a consequence and every decision decides (C-1)"
else
  bad "every board sentence carries a consequence and every decision decides (C-1)" \
      "$("$PY" "$_scan" "$_sidecar" 2>&1 >/dev/null | grep '^  FAIL' | head -3 | tr '\n' ' ')"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'board-safety (metrics): ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'board-safety (metrics): %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'board-safety (metrics): all %s checks passed\n' "$checks"
