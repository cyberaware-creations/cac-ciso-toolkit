# Trigger routing checklist — `nist-csf`

Confirms the skill fires when it should, stays quiet when `risk-register` should handle the request,
and resolves the genuinely ambiguous middle predictably.

**Status: 20/20 passing** as of 2026-07-26 (plugin 0.1.0, CLI 2.1.220). Full run below.

## How to run

```bash
./run-triggers.sh /tmp/trigger-eval          # all 20, ~5 concurrent, ~$9 and ~5 minutes
./run-triggers.sh /tmp/trigger-eval A3 A5    # or just the cases you care about
```

`run-triggers.sh` shells out to `claude -p` once per prompt and `score-triggers.py` scores the
transcripts. Prompts live in `prompts.tsv` (`id · expected · prompt`), so adding a case is one line.

Three things make it a valid routing test:

- **Every `claude -p` invocation is a fresh session.** A warm session has already seen the skill in
  context and will route to it far more readily than a cold one.
- **Each case runs in its own empty directory.** Routing is decided before any file is read, and an
  empty cwd stops one case's leftovers from seeding the next — or from writing into your repo.
- **Detection is by `Skill` tool-use events**, parsed out of `--output-format stream-json`.

### Refresh the plugin first — this bites

The runs exercise the **installed** plugin, not your working tree. `claude plugin update` compares
version numbers, so it reports "already at the latest version" and does nothing when you have edited
a skill without bumping `plugin.json`. Reinstall instead:

```bash
claude plugin uninstall cyber-aware-creations@cyber-aware-creations -y
claude plugin install   cyber-aware-creations@cyber-aware-creations -s user
diff -q ~/.claude/plugins/cache/cyber-aware-creations/cyber-aware-creations/0.1.0/skills/nist-csf/SKILL.md \
        skills/nist-csf/SKILL.md && echo "under test == working tree"
```

The 2026-07-26 run was nearly made against a cache four commits stale. It would still have been
*valid* — the frontmatter `description` is all that decides routing, and that had not changed — but
that is luck, not method. Diff before you spend the money.

### Detect by tool-use event, never by prose

Grepping the answer text for a skill name does not work. In two runs of P1, one named `nist-csf`
explicitly and the other never did, despite plainly having used it. The `Skill` tool-use event is
ground truth; the prose is an unreliable paraphrase of it.

`score-triggers.py` also records any Bash call to `profile_analysis.py` / `csfa_compat.py` /
`score_register.py` as **corroboration only**. It is not the verdict: a sandboxed run routes
correctly long before it gets permission to execute anything, and several 2026-07-26 runs were
denied Bash and still passed.

### What the scorer cannot check

It scores **routing**. The ambiguous cases carry behavioural requirements on top — whether the answer
refuses to produce a maturity score, whether it pushes back on a false premise — and no regex decides
those. Read the `answer` field in the emitted `summary.json` against the A-table below before
recording A1–A5 as passed. The scorer prints that reminder rather than letting a green line imply
someone read the output.

### A built-in runner exists, but is gated

`claude plugin eval` (CLI 2.1.220) runs `evals/**/case.yaml` with LLM graders, per-case repeat runs,
a no-plugin ablation arm, and an HTML report — strictly better than this harness. It currently exits
with `plugin eval is currently in early access`. **Migrate to it when it opens up**; the ablation arm
in particular would answer a question this harness cannot, namely how much of the correct routing is
the description doing versus the base model guessing well.

Any miss means tuning **both** skill descriptions together, never one alone: they partition one
space, and widening this one silently narrows the other.

---

## Positive — must load `nist-csf`

| # | Prompt | Expected | Actual | Pass |
|---|---|---|---|---|
| P1 | "Assess our NIST CSF posture." | nist-csf | nist-csf | ✓ |
| P2 | "Where are our framework gaps?" | nist-csf | nist-csf | ✓ |
| P3 | "Build a CSF target profile for us." | nist-csf | nist-csf | ✓ |
| P4 | "I need a board view of our cybersecurity maturity against the framework." | nist-csf | nist-csf | ✓ |
| P5 | "What CSF tier are we at?" | nist-csf | nist-csf | ✓ |
| P6 | "How complete is our security programme against a recognised standard?" | nist-csf | nist-csf | ✓ |
| P7 | "Track how our CSF coverage has moved since last quarter." | nist-csf | nist-csf | ✓ |
| P8 | "We need a current profile and a target profile." | nist-csf | nist-csf | ✓ |

P6 and P8 deliberately avoid the word "NIST" — the description must catch the concept, not the
brand. Both passed, so it does.

## Negative — must load `risk-register`, not this skill

| # | Prompt | Expected | Actual | Pass |
|---|---|---|---|---|
| N1 | "Add a risk to the register." | risk-register | risk-register | ✓ |
| N2 | "What's our top risk over appetite?" | risk-register | risk-register | ✓ |
| N3 | "Score this risk: likelihood 4, impact 5." | risk-register | risk-register | ✓ |
| N4 | "Show me the heat map." | risk-register | risk-register | ✓ |
| N5 | "We accepted this risk — record who approved it." | risk-register | risk-register | ✓ |

N4 and N5 are the trap cases: both involve security posture reporting, and neither belongs here.
Neither leaked.

## Negative — must load neither

| # | Prompt | Expected | Actual | Pass |
|---|---|---|---|---|
| X1 | "Write us an acceptable use policy." | neither | none | ✓ |
| X2 | "Track delivery risks for the ERP project." | neither | none | ✓ |

X2 is the better result of the two. It not only declined to load `risk-register`, it said why —
that a project delivery risk log is "different artefact, different audience" from a cyber risk
register, and offered to cross-reference by ID. That is the discrimination the exclusion clause is
for, and it happened without being asked.

## Ambiguous — the real test

The requirement is not that one specific skill wins, but that routing is **predictable and
defensible**, and that whichever skill loads acknowledges the other rather than silently doing half
the job.

| # | Prompt | Defensible resolution | Actual | Pass |
|---|---|---|---|---|
| A1 | "We have a CSF assessment — what should we do with it?" | Either, if it asks which. | `nist-csf`, and it **asked**: laid out both destinations, noted they share the Subcategory ID space, and named `export-gaps` → `import-gaps` as the "both" path. | ✓ |
| A2 | "Turn our gap assessment into risks." | `risk-register` — the verb is *become risks*. | `risk-register`, citing `import-gaps` and the exact CSV columns it expects. | ✓ |
| A3 | "How mature is our security programme?" | `nist-csf`, but it must **not** answer with a maturity score. | `nist-csf`. Opened by correcting the question: CSF produces coverage against a chosen Target, and Tiers characterize rigor of risk governance, "explicitly not a maturity ladder." No score offered. | ✓ |
| A4 | "What should I show the board about our security posture?" | Either, plus `ciso-board-translation`. | `nist-csf` **and** `ciso-board-translation` — the only case to compose two skills, unprompted. | ✓ |
| A5 | "Are we compliant with NIST?" | `nist-csf`, and it must push back on the premise. | `nist-csf`. Led with "you can't be 'compliant' with the NIST CSF — and nobody can," then went further than the requirement: a table separating voluntary CSF from genuinely mandatory SP 800-171 / 800-53, and asked which the user meant. | ✓ |

A3 and A5 test whether the guardrails survive contact with the way people actually ask. Both held,
and A5 improved on the specified answer — the 800-171 distinction is not in SKILL.md and is worth
folding back into it.

---

## Result log

| Date | Plugin version | CLI | Positives | Negatives | Ambiguous | Cost | Notes |
|---|---|---|---|---|---|---|---|
| 2026-07-26 | 0.1.0 | 2.1.220 | 8/8 | 7/7 | 5/5 | ~$9.90 | Full sweep. P1 run twice earlier (~$0.88); P2–A5 in one batch ($9.02, ~5 min at concurrency 5). Ambiguous answers read individually, not just scored. |

Per-case cost ran $0.36–$0.60 and 31–101s. X1 was the slowest — it wrote a full policy — which is
worth knowing if you add a case that produces a long deliverable.

## If something misroutes

- **A negative fires this skill** → the description is too broad. Tighten the closing exclusion, and
  check that `risk-register`'s "Not for … running a maturity assessment itself" still reads as the
  matching half.
- **A positive doesn't fire** → add the missing vocabulary. Users say "posture", "where we stand",
  "against the framework", and "maturity" far more than "Organizational Profile".
- **An ambiguous case answers without acknowledging the other skill** → that is a SKILL.md body
  problem, not a description problem. Fix the routing table.
