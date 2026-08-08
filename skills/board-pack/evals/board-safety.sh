#!/usr/bin/env bash
# Board-safety over the finished pack — the last gate before a deck reaches a board.
#
# Every producer already passes its own board-safety. This suite exists because the pack is
# where their output is combined, reformatted and pushed into a second file format, and each
# of those steps is a chance to introduce a sentence nobody wrote.
#
# The load-bearing case is check 9. Every paragraph the pack presents as board prose must
# appear VERBATIM in one of the sidecars it was built from. That is a stronger claim than "no
# placeholder is missing": it says the assembler did not paraphrase, summarise, join or
# tidy — it carried. A renderer that helpfully trimmed a sentence would be writing board prose
# with extra steps, and the whole design rests on it never doing that.
#
# Both formats are scanned. A guard that only reads the HTML would miss anything the PPTX
# writer does on its own, and the PPTX is the file that actually goes in the board pack.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=12
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

echo "board-safety (board-pack): $($PY -V 2>&1)"

"$PY" "$skill/scripts/assemble_pack.py" assemble "$skill/examples/pack.manifest.json" \
    --out "$work/pack.json" >/dev/null 2>&1
(cd "$skill/renderers" && "$PY" render_pack.py --in "$work/pack.json" \
   --html "$work/pack.html" --pptx "$work/pack.pptx") >/dev/null 2>&1

# Flatten both deliverables to plain text, so the same word lists run over both.
"$PY" - "$work" <<'PY'
import re, sys, zipfile, os
work = sys.argv[1]
html = re.sub(r"<style.*?</style>", " ", open(os.path.join(work, "pack.html"),
                                              encoding="utf-8").read(), flags=re.S)
open(os.path.join(work, "pack.html.txt"), "w", encoding="utf-8").write(
    re.sub(r"<[^>]+>", " ", html))
zf = zipfile.ZipFile(os.path.join(work, "pack.pptx"))
xml = b"".join(zf.read(n) for n in zf.namelist() if n.startswith("ppt/slides/slide"))
open(os.path.join(work, "pack.pptx.txt"), "w", encoding="utf-8").write(
    re.sub(r"<[^>]+>", " ", xml.decode("utf-8")))
PY

scan() {  # scan <textfile> <list>
  "$PY" - "$1" "$2" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8").read().lower()
LISTS = {
  "confidence": ("confidence", "degrading", "degraded", "decaying", "decay",
                 "no longer reliable", "less reliable", "unreliable"),
  "catastrophe": ("catastroph", "devastat", "existential", "crippl", "disastrous",
                  "nightmare", "ruinous", "calamit", "apocalyp", "bet-the-company",
                  "reputational ruin", "could destroy", "wiped out"),
}
print(",".join(w for w in LISTS[sys.argv[2]] if w in text))
PY
}

# 1-4. Both deliverables, both word lists.
for fmt in html pptx; do
  for list in confidence catastrophe; do
    hit=$(scan "$work/pack.$fmt.txt" "$list")
    if [ -z "$hit" ]; then ok "no $list vocabulary in the rendered $fmt"
    else bad "no $list vocabulary in the rendered $fmt" "found: $hit"; fi
  done
done

# 5. Our own source, by stem. Docstrings exempt: every file here carries a paragraph naming
# the claim it declines to make, and those paragraphs have to be allowed to name it.
res=$("$PY" - "$skill" <<'PY'
import ast, pathlib, sys
root = pathlib.Path(sys.argv[1])
STEMS = ("confiden", "degrad", "decay", "reliab", "certainty", "uncertain", "doubt",
         "catastroph", "devastat", "existential", "crippl", "disastrous", "nightmare",
         "ruinous", "calamit", "apocalyp")
FILES = ("scripts/assemble_pack.py", "scripts/pptx_writer.py", "renderers/render_pack.py")
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
                    problems.append(f"{rel}:{node.lineno} contains {s!r}")
if scanned != len(FILES):
    problems.append(f"scanned {scanned} of {len(FILES)} files")
print("\n".join(problems))
PY
)
if [ -z "$res" ]; then ok "no banned vocabulary in the source of either renderer"
else bad "no banned vocabulary in the source of either renderer" "$res"; fi

# 6-7. The footer, on both deliverables. On the PPTX it must be on EVERY slide, because a
# deck gets split apart and pasted into other decks.
if grep -q "Not affiliated with NIST" "$work/pack.html.txt"; then
  ok "the HTML carries the footer"
else bad "the HTML carries the footer" "absent"; fi
res=$("$PY" - "$work/pack.pptx" <<'PY'
import re, sys, zipfile
zf = zipfile.ZipFile(sys.argv[1])
slides = sorted(n for n in zf.namelist()
                if n.startswith("ppt/slides/slide") and n.endswith(".xml"))
missing = [n for n in slides
           if "Not affiliated with NIST" not in re.sub(r"<[^>]+>", " ",
                                                       zf.read(n).decode("utf-8"))]
print(",".join(missing))
PY
)
if [ -z "$res" ]; then ok "and every slide in the deck carries it"
else bad "and every slide in the deck carries it" "missing from: $res"; fi

# 8. Not legal advice, wherever the incident section appears.
if grep -q "Not legal advice" "$work/pack.html.txt" \
   && grep -q "Involve counsel" "$work/pack.pptx.txt"; then
  ok "the incident section says it is not legal advice, in both formats"
else
  bad "the incident section says it is not legal advice, in both formats" \
      "absent from one of them"
fi

# 9. THE check. Every paragraph the pack presents as board prose appears verbatim in a
# sidecar. Not paraphrased, not trimmed, not joined — carried.
res=$("$PY" - "$skill" "$work/pack.html" <<'PY'
import html as H, json, os, re, sys
skill, page = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(skill, "scripts"))
import assemble_pack as A
manifest = A.load_manifest(os.path.join(skill, "examples", "pack.manifest.json"))
sources = []
for entry in manifest["sections"]:
    if entry.get("translationsPath"):
        sources.append(json.load(open(entry["translationsPath"], encoding="utf-8")))
if manifest.get("throughLinePath"):
    sources.append(json.load(open(manifest["throughLinePath"], encoding="utf-8")))

allowed = set()
for side in sources:
    for key, value in side.items():
        if isinstance(value, str):
            allowed.add(value.strip())
        elif isinstance(value, dict):
            allowed.update(v.strip() for v in value.values() if isinstance(v, str))
        elif isinstance(value, list):
            allowed.update(v.strip() for v in value if isinstance(v, str))

doc = open(page, encoding="utf-8").read()
problems = []
for chunk in re.findall(r'<p class="lede">(.*?)</p>', doc, flags=re.S):
    text = H.unescape(re.sub(r"<[^>]+>", "", chunk)).strip()
    if text not in allowed:
        problems.append("a lede paragraph is not verbatim from any sidecar: "
                        + text[:90])
for chunk in re.findall(r"<dd>(.*?)</dd>", doc, flags=re.S):
    text = H.unescape(re.sub(r"<[^>]+>", "", chunk)).strip()
    if text.startswith(("no sidecar", "/")) or "·" in text:
        continue  # provenance rows, which are paths rather than prose
    if text not in allowed:
        problems.append("an item sentence is not verbatim from any sidecar: " + text[:90])
if not allowed:
    problems.append("no sidecar text was loaded; the check read nothing")
print("\n".join(problems))
PY
)
if [ -z "$res" ]; then
  ok "every board sentence in the pack is verbatim from a sidecar — nothing was written here"
else
  bad "every board sentence in the pack is verbatim from a sidecar" "$res"
fi

# 10-11. The guard checking itself, in both directions.
"$PY" - "$work" <<'PY'
import sys, os
work = sys.argv[1]
doc = open(os.path.join(work, "pack.html"), encoding="utf-8").read()
doc = doc.replace("<h2>Decisions</h2>",
                  "<h2>Decisions</h2><p class=\"lede\">This is a catastrophic and "
                  "existential event that we invented right here.</p>", 1)
open(os.path.join(work, "injected.html"), "w", encoding="utf-8").write(doc)
import re
open(os.path.join(work, "injected.txt"), "w", encoding="utf-8").write(
    re.sub(r"<[^>]+>", " ", re.sub(r"<style.*?</style>", " ", doc, flags=re.S)))
PY
inj=$(scan "$work/injected.txt" catastrophe)
if [ -n "$inj" ]; then
  ok "injected fear framing IS caught by the guard (found: $inj)"
else
  bad "injected fear framing IS caught by the guard" "the scanner passed it"
fi
res=$("$PY" - "$skill" "$work/injected.html" <<'PY'
import html as H, json, os, re, sys
skill, page = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(skill, "scripts"))
import assemble_pack as A
manifest = A.load_manifest(os.path.join(skill, "examples", "pack.manifest.json"))
allowed = set()
paths = [e["translationsPath"] for e in manifest["sections"] if e.get("translationsPath")]
paths.append(manifest["throughLinePath"])
for p in paths:
    side = json.load(open(p, encoding="utf-8"))
    for value in side.values():
        if isinstance(value, str):
            allowed.add(value.strip())
        elif isinstance(value, dict):
            allowed.update(v.strip() for v in value.values() if isinstance(v, str))
        elif isinstance(value, list):
            allowed.update(v.strip() for v in value if isinstance(v, str))
doc = open(page, encoding="utf-8").read()
bad_ = [H.unescape(re.sub(r"<[^>]+>", "", c)).strip()
        for c in re.findall(r'<p class="lede">(.*?)</p>', doc, flags=re.S)]
print(",".join(t[:40] for t in bad_ if t not in allowed))
PY
)
if [ -n "$res" ]; then
  ok "an invented board sentence IS caught by the verbatim check"
else
  bad "an invented board sentence IS caught by the verbatim check" "it passed"
fi


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
  printf 'board-safety (board-pack): ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'board-safety (board-pack): %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'board-safety (board-pack): all %s checks passed\n' "$checks"
