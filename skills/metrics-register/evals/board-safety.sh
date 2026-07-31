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

EXPECTED_CHECKS=5
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

# 3. Our source, by stem. Docstrings are exempt — the refusal has to be explainable, and
# every file here carries a paragraph naming the claim it declines to make.
res=$($PY - "$skill" <<'PY'
import ast, pathlib, sys
root = pathlib.Path(sys.argv[1])
STEMS = ("confiden", "degrad", "decay", "reliab", "assumed",
         "trust", "certainty", "uncertain", "doubt")
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

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'board-safety (metrics): ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'board-safety (metrics): %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'board-safety (metrics): all %s checks passed\n' "$checks"
