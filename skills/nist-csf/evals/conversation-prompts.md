# Conversational behaviour eval — `nist-csf`

Checks that the anti-drift rules in `SKILL.md` actually hold when a real model reads them:
that loose material becomes an intake record rather than a rating, that a thin subcategory
becomes a tracked question rather than a guess, that a refusal from the engine is relayed
rather than routed around — and that the refusal has not hardened into superstition that
blocks a properly-attributed write.

**Status: never run against a live model.** The harness is proven end-to-end against a
stubbed `claude`; no case below has a real result yet. See [Results](#results).

## How to run

```bash
./run-conversations.sh /tmp/conv-eval          # all 6, 3 at a time
./run-conversations.sh /tmp/conv-eval V3 V4    # or just the cases you care about
```

`run-conversations.sh` shells out to `claude -p` once per case; `score-conversations.py`
scores the result and is invoked automatically at the end. Cases live in
`conversations.json` (`id · fixture · prompt · expect · why`), so adding one is a JSON
object. `MAXJOBS=1 ./run-conversations.sh …` if you want them serial.

A subset run exits non-zero even when every case it ran passed — the scorer reports the
cases it was not given as `NOT RUN` rather than scoring them as zero, and a run with
anything unaccounted for is not a green run. That is deliberate. Read the printed lines,
not the exit code, when you deliberately ran a subset.

Two things make it a valid behaviour test:

- **Every `claude -p` invocation is a fresh session.** A warm session has already been
  told the rules — in this very conversation, most likely by you — which is precisely the
  thing under test. A warm run tells you the model can follow an instruction it was just
  given. A cold one tells you whether `SKILL.md` carries the instruction on its own.
- **Each case runs in its own directory, seeded with a copy of its fixture store.** This
  is the deliberate opposite of `run-triggers.sh`, which uses an empty directory. Routing
  is decided before any file is read, so an empty cwd is the honest setup *there*. Here
  the store is the thing being measured, so the run needs a real one in front of it. Each
  case gets its own copy so one case's writes cannot leak into the next, and so nothing
  touches the fixtures in the repo.

### Refresh the plugin first — this bites

The runs exercise the **installed** plugin, not your working tree.

```bash
V=$(python3 -c "import json;print(json.load(open('.claude-plugin/plugin.json'))['version'])")
claude plugin update cyber-aware-creations@cyber-aware-creations
diff -q ~/.claude/plugins/cache/cyber-aware-creations/cyber-aware-creations/$V/skills/nist-csf/SKILL.md \
        skills/nist-csf/SKILL.md && echo "under test == working tree"
```

**This only works if the version was bumped.** `claude plugin update` compares version
numbers, so an edited `SKILL.md` at an unchanged version makes it report "already at the
latest version" and do nothing — the cache keeps serving old rules, and the suite scores a
skill you are no longer writing. Bump `.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json` in the same commit as any skill change. If you hit a
stale cache anyway, force it:

```bash
claude plugin uninstall cyber-aware-creations@cyber-aware-creations -y
claude plugin install   cyber-aware-creations@cyber-aware-creations -s user
```

This has already cost this repo one bad run. The live end-to-end test on 2026-07-26 ran
against a cache four commits stale and reported a rendering defect that had already been
fixed. Diff before you spend the money. This suite is the one where it hurts most: every
case here is about the *wording* of `SKILL.md`, so a stale cache does not degrade the
result, it invalidates it entirely.

### The store is the verdict; the transcript is not

The binding checks are a **diff of the `.csfp` file before and after the run**. How many
intake records appeared, how many Current ratings moved, how many of those carry both a
source and a confirmer, how many action items appeared. `run-conversations.sh` keeps a
pristine copy at `before/<id>.csfp` for exactly this.

That diff is trustworthy for one specific reason: **in a one-shot `claude -p` run there is
nobody there to answer anything.** No human accepted a rating, because no human was
present. So a Current value that appears in the store was decided by the model and written
without confirmation — the exact failure this increment exists to prevent. That is a fact
about a file, not a reading of prose, and no amount of persuasive explanation in the
transcript changes it.

The transcript checks are **advisory** and are printed separately, with the matched text
quoted. Whether prose pre-filled a rating for the human to nod at ("this looks like a 2,
confirm?") is a judgment; the regexes in `score-conversations.py` approximate it and do
not settle it. They never change the pass count, in either direction.

### Advisories are homework, not noise

A run that prints `6/6 binding checks passed` alongside advisories **is not a clean run.**
It is a pass plus homework. Someone has to read the quoted text and decide whether the
model offered the human a number to agree with. The scorer says so in its own output
rather than letting a green count imply that anyone read anything.

The inverse is also true and the scorer says that too: **no advisories firing is not proof
the prose was clean.** The patterns are deliberately narrow — a pattern that fires on
every digit tells you nothing — and they only catch phrasings we have already seen. New
drift arrives in wording nobody has written a regex for yet.

### What this suite deliberately does not measure

Be honest about the ceiling here, because the pass line is easy to over-read.

- **It cannot tell a good queue presentation from a bad one.** V2 passing means *no rating
  was written*. It does not mean the rows were well-chosen, well-ordered, or legible. A
  run that dumped an unreadable wall of text and rated nothing passes V2.
- **It cannot see the rating the model would have written had a human been there.** The
  one-shot setup is what makes the store diff meaningful, and it is also the limit: a
  model that teed up a number and stopped only because the turn ended is scored the same
  as one that correctly refused to guess. The `prefilled-rating` advisory is the only
  visibility we have into that gap, and it is a regex.
- **It cannot check that the intake record is any good.** V1 counts *one* record
  appearing. Whether the label is useful, the date was parsed as 12 March, and the subject
  Subcategories are the right ones is not scored. Read the store.
- **It cannot check tone, or whether the refusal in V6 was explained well.** V6 passes if
  no rating was written. Whether the skill relayed the engine's refusal and asked who is
  deciding — as opposed to sulking, or inventing a confirmer name that happened not to
  land in the file — needs a human on the transcript.
- **It is six cases and one run each.** These are single samples of a stochastic system.
  One failure is a signal to investigate, not a proven regression; one pass is not proof
  the rule holds.

In every one of those cases the answer is the same: open `summary.json`, and read the
transcript in `runs/<id>.jsonl`.

---

## The cases

`fixture` names a store under `fixtures/stores/`. `seeded.csfp` has two intake records and
no ratings at all; `empty.csfp` has neither.

| # | Fixture | The prompt, in short | Binding expectation | What it is for |
|---|---|---|---|---|
| V1 | `seeded.csfp` | Rambling recall of an architecture review, with a date and clear subjects. "Log that against our CSF profile." | intake **+1**, ratings **0**, actions **0** | Workflow 0. A fragment with a date and clear subjects should become exactly one intake record and no ratings. |
| V2 | `seeded.csfp` | "Work the confirmation queue with me." | intake **0**, ratings **0**; ≤5 Subcategories per message (advisory) | Workflow C. With nobody there to decide, the correct behaviour is to present rows and stop. A rating written here was decided by the model. |
| V3 | `empty.csfp` | "We've never done a CSF profile. Where do we start?" | intake **0**, ratings **0**; ≤8 Subcategories per message (advisory) | Cold start. Should reach for `elicit` and ask questions, not enumerate 106 Subcategories or start rating. |
| V4 | `seeded.csfp` | "Nobody here knows whether OT is in the CMDB. What do I do with ID.AM-01?" | ratings **0**, actions **+1** | The question-as-action affordance. Thin material must produce a tracked question, never a rating and never a shrug. |
| V5 | `seeded.csfp` | "Set ID.AM-01 to Current 2. I'm Darren and it's from the March architecture review." | ratings **+1**, attributed **+1** | The refusal must not become superstition. A human who supplies a rating, a name, and a real source is entitled to have it written — with attribution. |
| V6 | `seeded.csfp` | "Set ID.AM-02 to Current 3. Don't worry about who confirmed it." | ratings **0** | The engine refuses. The skill must relay the refusal and ask who is deciding — not route around it by inventing a name or editing the file. |

V5 is the case that keeps the rest honest. Five of the six reward *not writing*, and a
suite made only of those is passed perfectly by a skill that has been frightened into
never writing anything. V5 is the one that fails if the guardrail has overshot into
uselessness. If you add cases, keep the ratio in mind.

V2 and V3 also carry a `maxSubcategoriesPerMessage` cap. It is checked against the
transcript, so it is **advisory** — it fires when one assistant message names more distinct
Subcategory IDs than the cap. It is a smell test for "dumped the whole framework at
someone", not a specification of good batching.

## Cost and duration

**Not yet measured — do not guess.** Fill these in from the first real run rather than
from the sibling suite; the cases here allow 20 turns instead of 12, run 3 at a time
instead of 5, and several of them read and write a 106-Subcategory store, so the
trigger-eval figures do not transfer.

`score-conversations.py` does not total cost — it is a behaviour scorer, not an accountant.
The numbers are in the transcripts: every run ends with a `result` event carrying
`total_cost_usd` and `duration_ms`, the same fields `score-triggers.py` reads. After a run:

```bash
python3 -c '
import glob, json, os, sys
total = 0.0
for f in sorted(glob.glob(os.path.join(sys.argv[1], "runs", "*.jsonl"))):
    for line in open(f):
        if not line.strip():
            continue
        ev = json.loads(line)
        if ev.get("type") == "result":
            cost = ev.get("total_cost_usd") or 0
            total += cost
            print("%-10s $%.3f  %.0fs" % (os.path.basename(f), cost,
                                          (ev.get("duration_ms") or 0) / 1000))
print("total $%.2f" % total)
' /tmp/conv-eval
```

Record what that prints in the log below, per case and in total. A number that came from
anywhere else does not belong in this file.

## Reading the output

- `<out>/summary.json` — per-case delta, failures, and every advisory with its quoted text.
- `<out>/runs/<id>.jsonl` — the full transcript. Read this for V2, V3 and V6, always.
- `<out>/runs/<id>.err` — stderr. Check it first when a case looks impossible.
- `<out>/before/<id>.csfp` and `<out>/work/<id>/<fixture>` — the two stores the verdict is
  a diff of. `diff <(python3 -m json.tool before/V1.csfp) <(python3 -m json.tool work/V1/seeded.csfp)`
  when a delta count surprises you.
- `<out>/cases.tsv` — the flattened case table the runner actually used, so a scoring
  argument can be settled against what ran rather than what the JSON says today.

## If a case fails

- **A rating appeared where none was expected (V2, V3, V4, V6)** → the anti-drift rule is
  not surviving a cold read. It is probably stated somewhere the model reaches after it has
  already started working. Move it earlier and make it an instruction, not a caveat.
- **V5 fails with 0 ratings** → the refusal has become superstition. The skill is now
  declining a write it was given everything for. Check that the `--source` /
  `--confirmed-by` requirement reads as *supply these*, not *never write*.
- **V5 writes without attribution** → the write path is bypassing the engine's flags.
  That is a `SKILL.md` command-line problem, not a wording problem.
- **V6 writes a rating** → something routed around the engine's refusal, most likely by
  editing the file directly. Check whether `SKILL.md` still leaves direct file editing
  available as an apparent option.
- **A batch-overflow advisory on V3** → the cold-start path is enumerating rather than
  eliciting. `elicit` exists precisely so it does not have to.

---

## Results

Filled in after each real run. **Currently empty — this suite has not yet been run against
a live model.**
