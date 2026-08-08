# Changelog

Every released version of the CAC CISO toolkit, newest first.

**This file starts late, and that is the first thing worth recording.** The `v0.11.0` release
note said the repo had "run to 0.10.5 across 65 commits without one, so the version strings
were the only record of what an installed copy actually was." That problem was named, fixed
once with a single tag, and then recurred immediately: the repo ran from **0.12.0 to 0.37.0
across 28 versions** with no tag and no changelog. Those 28 tags were reconstructed from the
manifest history on 2026-08-07 and every one was verified to point at a tree whose manifest
declares that version. The entries below were written from the commits, not from notes taken
at the time — so they are accurate about *what* changed and thinner than they should be about
*why*.

The guard in `tools/check-versions.py` now fails a change that moves the version without
adding an entry here. A release step a human has to remember is not a check — the same
reasoning that put the four manifests under a guard in the first place.

Versions are `MAJOR.MINOR.PATCH`. `0.13.0`–`0.15.0` never existed; the version jumped from
`0.12.0` to `0.16.0`.

---

## v0.42.3 — 2026-08-08

**The three remaining red cases were expectations, not skills — and one of them turned out not to
be.** All three are changed here, before the run that scores them, so no number in this release is
argued from the change that produced it.

**B6 and B7 become pipe lists, argued from CAC-AP-1 rather than from where they landed.** B6 →
`business-context|incident-materiality`: the applicability profile is a **contract between two
skills**, so *"which questions apply to us for an incident"* has two correct doors by
construction — §2.4 has the consumer embed the skip sentence, which only makes sense if the
consumer is a place the question can arrive. B7 → `business-context|vendor-register`: §2.3's
subject-outranks-profile rule is carried by `applies --subject-declares`, called by the **subject
register**, because that is what knows about the subject. What each widening costs is written
down too: B6 can no longer tell the profile side from the consumer side.

**A14 was not widened, and that is the finding.** *"Are we in scope for the EU AI Act as a
deployer?"* had reached two skills on two runs with a good answer each time, and a pipe list would
have made the case agree with whatever happened — by contradicting the checklist's own stated
boundary, which is that `ai-register` *stays quiet on regulatory scope*. The side was already
picked. So the cause is fixed instead, on the pattern T3, B4 and V6 set: the description claimed
only that the skill "does not perform conformity assessment" — much narrower and more technical
than *does not decide whether the AI Act applies to you* — while `references/scope.md` and the
empty `regimes.json` carried the real boundary where a routing decision never reads it. It now
names regulatory scope alongside bias, spells out the roles (deployer, provider, importer), says
the determination is declared in the applicability profile on legal advice, and repeats it in the
NOT list. **That is a prediction that can fail**: if A14 still lands on `ai-register`, the
description was not the cause.

Also corrects a drift between `ai-register`'s case table and its `prompts.tsv` — A13 was widened
to `ai-register|risk-register` before the second run and the table, which is the pre-registered
expectation, still said `risk-register`.

**All three re-scored PASS, and the A14 prediction held.** `business-context` reaches **15/15** and
`ai-register` reaches **15/15**, both in a commit that does not contain the change. A14's answer
cites the new clause back almost word for word — *"`ai-register` says the same in its own
boundaries: it inventories and assesses security, it does not determine regulatory scope"* — which
is about as direct as causal evidence gets in a routing test. A2, A4 and A6 ran alongside it to
check the narrowed description pushed nothing out; A2 returned `error_max_turns`, was not folded
into any total, and passed on a re-run. Seven cases plus one retry, $4.27.

**Every routing checklist in the suite is now at full marks except two cases**, both of which are
prompts rather than skills: `attention-surface` T6, whose *"give me a digest"* has no security
referent, and `ai-register` A1, which reads two ways and has passed two runs of three.

## v0.42.2 — 2026-08-08

**T3 and B4 were the same defect in two skills, and one of them had an engine gap behind it.**
Both cases are phrased as questions about something already held — *"what changed since our last
security review?"* and *"what did the board actually say? I want the exact words on file"* — and
both sessions went looking for a **file**: the working directory, then git, then Drive, Notion
and a mailbox. It is `vendor-register`'s V6 exactly, and it gets V6's fix: the description leads
with retrieval as well as recording, carries the words people actually type, and says outright
that the skill is *for* the case where no document can be found.

**`business-context` could not read back the one sentence it exists to hold.** `set-fact
--board-tolerance` stored the board's words verbatim from the first release and refused an
unattributed one — and `show` never printed them. The quote was reachable only through `--json`.
Widening the description without this would have routed B4 here and then answered it with a page
that does not mention the board. `show` now prints every recorded sentence word for word with who
said it and when, and prints `NONE RECORDED` when there are none, naming the distinction: nobody
wrote down what the board said is a different fact from the board having said nothing. Under five
new self-test checks; segments, strategic goals and contractual obligations render too.

`attention-surface` needed no engine change — `review` already computes the diff and already says
*no earlier review is recorded* rather than *nothing changed*. Its description now names the
wrong reading and rules it out: what changed means a diff over the escalations the registers
hold, not over files, code, git history or a session transcript.

Both skills gain a SKILL.md section answering the question in order, on the pattern V6 set.

**Both re-scored PASS**, in a commit that does not contain the fix. `attention-surface` goes to
**11/12** and `business-context` to **13/15**. T9, T10 and B9–B14 were re-run alongside them to
check the widening pulled nothing in — all nine still route to the skill each was written for.
Ten cases, $5.95.

Both re-scored answers name the trap in their own words. T3: *"I deliberately did not diff files,
git history, or this session; that's the wrong reading of the question."* B4: *"'On file' here
means this register. I didn't search Drive, Notion, or a mailbox — a document hunt answers a
different question."*

## v0.42.1 — 2026-08-08

**Every routing checklist in the suite now carries a real number from a real run.** The last two
— `attention-surface` and `business-context` — had shipped marked *"not yet run"*, and the six
cases held over from the first scored run are resolved.

| checklist | result |
|---|---|
| `vendor-register` | **15/15** — Y1 re-scored against a pipe list widened in a prior commit |
| `ai-register` | **14/15** — A1, A13 and A15 now pass; A14 recorded as unusable as written |
| `attention-surface` | **10/12** |
| `business-context` | **12/15** |

**The attention-surface run had to be done twice, and the first attempt is the more useful
story.** Ten of twelve cases returned at `$0.000` and ~16s: the OAuth token expired mid-run and
refreshed afterwards, so ten sessions died on a 401. `score-triggers.py` classified them as
ERRORED and **refused to fold them into a total** — which is the only reason that page does not
read "2/12". A scorer that counted an errored session as a routing miss would have condemned a
working skill on the strength of an expired token.

Three real misses, recorded and deliberately **not** fixed in the same commit:

- **T3** — *"what changed since our last security review?"* reached no skill, though **T5**
  — *"run the Monday security review"* — passed. The session read *what changed* as a diff over
  files and checked the directory, git, its memory store and the transcript. Every one of those
  is a reasonable reading of the phrase and none of them is a register.
- **T6** — *"give me a digest I can paste into the team channel"* has no security referent as
  written. **The case is at fault, not the skill**, and the session said so precisely.
- **B4** — *"what did the board actually say about outage tolerance? exact words on file"*
  reached no skill. The same shape as `vendor-register`'s V6: phrased as *what is on file*, so
  the session went looking for a **file** rather than for the register that holds the fact.

Nothing is rewritten here. Rewriting a case after watching it fail is the same error as
re-specifying an expectation after watching it pass, and the discipline holds in both directions.

**A14 is now recorded as unusable as written rather than widened a second time.** *"Are we in
scope for the EU AI Act as a deployer?"* reached `business-context` on one run and `ai-register`
on the next, refusing to determine scope and pointing at counsel both times. Two runs, two
skills, two correct answers. It was widened once already after the first run — widening it again
to match a second observation is a ratchet, not a test.

Documentation only. No engine, eval or manifest content changed.

---

## v0.42.0 — 2026-08-08

**`attention-surface`, skill #11 — the last in the sequence** business context → vendor → AI →
attention surface. What needs the CISO *this week*, derived entirely from what every other skill
already computes.

Twenty-eight escalation triggers across seven producers, each computed, dated, evidenced and
carrying a subject reference — and until now there was nowhere to look at them together on a
working cadence. `board-pack` reads the same escalations quarterly, for a board. This reads them
weekly, for the person who has to act.

- **It owns no data and computes no status.** Every fact comes from a producer's store, read at
  run time, with the producer named on the item. That discipline is what stops an attention list
  becoming a thirty-first opinion.
- **Grouped by decision, not by producer** — clocks running out, something moved under us,
  nobody owns it, we disagree with ourselves, uncontrolled exposure, over tolerance. The mapping
  is DATA in `references/clusters.json`; `evals/clusters.sh` asserts every trigger the shipped
  producers can emit has a home, reading that list out of the producers' own source rather than
  a hand-kept copy.
- **Ordered without a score.** Severity as the producer declared it, then age, then subject
  reference — three declared facts compared as a tuple, which is not arithmetic. A weighted
  blend would be this skill's own opinion about what matters, and it is the only voice in the
  room with no register behind it. Guarded both ways and registered under CAC-GP-1, which brings
  the suite to **eight guards and sixteen halves**.
- **What changed since you last looked**, keyed on producer + trigger + subject and deliberately
  NOT on the evidence string — evidence rewords itself as clocks advance, so keying on it would
  mark everything new every week, which is the same as marking nothing. `gone` is reported as
  *no longer firing*, never as *resolved*: the trigger stopped, and this surface cannot tell a
  fix from a changed record.
- **No mute, no snooze, no acknowledgement in v1.** If volume proves unusable the fix is
  threshold tuning at the producer — logged and visible. The shape an acknowledgement would have
  to take is recorded in the engine (ordering only, attributed, expiring) so whoever adds it
  inherits the constraints rather than reinventing them.
- **Absence is visible.** A register that could not be read is reported as NOT READ, above
  everything that looks like a result. A malformed escalation is shown rather than dropped.
  `nist-csf` is refused as a source by name, with the reason: a gap against a Target is a
  distance, not a clock.

Found on the first live run against all seven producers, and fixed:

- **The dict-repr leak, in a new consumer.** `risk-register`, `metrics-register` and
  `exceptions-register` emit `evidence` as a structured delta — `{from, to, baseline, detail}` —
  where `vendor-register` and `ai-register` emit a sentence. CAC-EL-1 fixes the six keys, not the
  type. The first renderer printed the raw dict on the page, which is exactly the defect
  `board-pack`'s `decisions-render.sh` exists for, reappearing because a shape was handled at a
  call site instead of in one function.
- **`no-priority-score.sh` flagged the engine's own `index` key** on its first run. It was a
  trigger-to-cluster lookup, not a priority — and the guard was right that next to a rule
  forbidding a computed number the word reads as one. Renamed `byTrigger`.
- **An argparse `choices=` gate swallowed a refusal.** `add-source --skill nist-csf` failed with
  a bare usage line, so the paragraph explaining why that skill is deliberately absent never
  reached the person who needed it. A gate that fires earlier than the explanation hides it.

---

## v0.41.3 — 2026-08-08

**CAC-GP-1: the guards are now proved on every run, not once at authoring.**

Seven guards protect rules the suite would otherwise lose to a reasonable-sounding change — no
vendor score, no closed state on an attack class, no percent-of-revenue materiality, no vendor
assertion closing a requirement. Six recorded, in prose, that they had been mutation-tested.
That sentence was true and the proof behind it was a paragraph: performed once, against code
that has since moved, and re-run by nothing. A guard that stops detecting its own defect goes on
printing `ok` forever, and the printing is indistinguishable from working.

- **`tools/prove-guards.sh`** runs every guard twice on a fresh copy — clean must PASS, then
  mutated must FAIL. Reporting only the second is the common mistake: a permanently broken guard
  would "pass" a test that only looks for failure.
- **Fourteen mutations registered as data**, two per guard, in
  `skills/*/evals/guard-proofs/*.json`. Each defeats *its own half specifically*. That
  constraint is load-bearing: a mutation writing `exposure[cls]["mitigated"] = True` trips both
  halves of `no-closed-state` and therefore proves neither, so the behavioural mutation writes
  the key as `"mitig" + "ated"` — invisible to a literal AST scan, caught in the store, which is
  exactly the escape the behavioural half exists for.
- **An unregistered guard is a failure, not a skip**, and a stale `find` is a failure too. Both
  paths are tested; so is the clean-copy direction, by breaking a guard deliberately and
  confirming the runner refuses to draw any conclusion from the mutated run.
- **`evidence-tiers.sh` is proved for the first time.** It was the one guard with no record of
  ever having been mutation-tested, and it protects the rule most exposed to commercial pressure
  — *"the vendor's trust centre says exactly what we need, why can't it count?"* Both halves now
  proved: removing the T1 scope-and-period refusal, and removing the end of the grace window so
  nothing can ever expire.
- Listed individually in CI, on the floor. `tools/guard-proof-standard.md` carries the rules and
  the registry.

GP-1.5 is not hypothetical. Writing these proofs, a first anchor no longer matched: the mutation
silently failed to apply, the guard ran against an unmutated tree, and the run printed PASS —
which reads as *"the guard missed it"* to anybody not checking whether the injection landed.

---

## v0.41.2 — 2026-08-08

**The V6 routing miss, fixed at its cause.** The first scored routing run found that *"does our
MSA with Fabrikam actually commit them to a breach notification window?"* reached **no skill at
all** — the session searched Drive and Dropbox for the contract, was blocked, and then reasoned
about typical notification windows from general knowledge. That last part is the freelancing
this register exists to replace, and it is the answer a CISO is most likely to act on wrongly.

The description already contained the phrase *"check what a contract commits a provider to"*,
buried at the end of a long list. That was not enough, and the reason is worth recording: the
prompt is shaped like a question about **a document the user has**, so the session went looking
for the document rather than for a register.

- **The description now leads with both jobs** — record an arrangement, and *interrogate* one
  already recorded — and carries the nouns people actually type: MSA, master services agreement,
  DPA, security addendum, breach notification window, audit rights.
- **It says explicitly that the skill is for the case where the contract cannot be found**,
  because that is when generalising is most tempting and least useful.
- **A new SKILL.md section answers that question in order**: check the register, refuse to
  generalise, emit the battery question, tier the document when it arrives, and record the
  arrangement if it was never there. An MSA is T2 and may satisfy; a trust page saying the same
  thing is T4 and satisfies nothing.

**Also — `no-regime-dates` was chasing verbs, and verbs leak.** The guard matched
`applies from` and missed `apply from` — one letter of subject-verb agreement — and missed
`take effect on` and `begin` outright. All three are what a well-meaning author actually
writes. The vocabulary leads with NOUNS now — obligation, duty, requirement, deadline, grace
period, enforcement, penalty — because those do not conjugate, and a sentence carrying one
alongside a year is making a claim about law. Ten phrasings are registered as the guard's own
probe: the six the audit found, and four negatives that must keep passing (a period end, an
assessment date, a report window, a cadence), because a guard that cries wolf over fixture
dates is one somebody switches off. A second mutant plants a phrasing the first vocabulary
would have let through.

No engine change in either. Descriptions, instructions and an eval.

---

## v0.41.1 — 2026-08-08

**The routing checklists are scored, and the scorer that scores them was broken.**

`vendor-register` 13/15, `ai-register` 11 of 13 scoreable. Both shipped at 0.39.0 and 0.41.0
marked *"Status: not yet run"*; both now carry a real number from a real run against v0.41.0,
with the caveats, because on this run the caveats are the more useful half.

- **`score-triggers.py` held a hardcoded seven-name list of "our" skills**, written before
  `business-context`, `vendor-register` and `ai-register` existed. A prompt routing *correctly*
  to any of the three scored as `none` with the right skill printed as `[non-toolkit: …]` — a
  correct routing reported as a miss, in the words that make it look like another plugin
  answered. Caught on the first case, run alone before committing to the other twenty-nine.
  Its own self-test could not see it: it validated `nist-csf/prompts.tsv`, whose expectations
  only name the original seven, and the checklist is a PARAMETER the validation never followed.
  The list is derived from the filesystem now, an empty scan raises, and the self-test walks
  every `skills/*/evals/prompts.tsv`. Same rot in the Bash corroboration regex, which listed
  three script names literally; built from `SCRIPT_TO_SKILL` now, and that map covers all ten.
- **`ai-register/evals/prompts.tsv` contradicted its own `trigger-prompts.md`**, shipped in the
  same commit: every row transcribed as expecting `ai-register`, including the five whose whole
  purpose is that the skill must *not* fire. Corrected against the table, which is the
  pre-registered expectation. A14 and A15 are excluded from the count — the table said "not this
  skill", the scorer has no vocabulary for that, and both were re-specified after seeing where
  they went, which is fitting the test to the result.
- **Two fails recorded as fails rather than quietly widened.** `V6` — *"does our MSA commit them
  to a breach notification window"* — reached no skill at all, though it is almost word-for-word
  the `contract-terms.incident-notice` question `vendor-register` generates; the session
  reasoned about typical notification windows unaided, which is the freelancing the skill exists
  to replace. `A13` fired `ai-register`, which opened with the no-score refusal and named
  `risk-register`; the expectation is probably what is wrong, and the next run is where that
  changes.

No engine behaviour changed. Evals, their expectations and their documentation only.

---

## v0.41.0 — 2026-08-08

**`ai-register`, skill #10.** A security inventory of the AI the organisation runs. Not an AI
governance programme — `references/scope.md` names what this skill does not own (model
evaluation, bias assessment, conformity assessment, regulatory scope) and cites why. Security is
one of the AI RMF's seven characteristics, and a tool that inventories AI and then reports on
all seven is claiming a competence its evidence does not support.

- **Risk lives in the deployment, not the model.** The same LLM drafting marketing copy and
  screening job applicants is one `system` and two `deployment` rows with different owners,
  different data and different exposure. A model-keyed register forces one answer, and it is
  the wrong one for whichever use mattered more.
- **Autonomy is declared, never inferred.** `informs` / `recommends` / `decides` / `acts`.
  `deploy` refuses without it and without an owner: autonomy gates every battery here, so an
  undeclared one would be assessed anyway, quietly, at whatever the default was.
- **Exposure is DERIVED from recorded attributes, and there is no command to select it.** Five
  classes following the shape of NIST's adversarial ML taxonomy — availability, integrity,
  privacy, misuse, supply chain — each carrying a `because` built from something declared.
  Misuse is generative-only; supply chain follows the model coming from outside, which is the
  join to `vendor-register`. A hand-selectable list becomes one somebody trims, and the class
  most likely to be trimmed is the one that took longest to explain.
- **An attack class has NO closed state.** No `mitigated`, `resolved`, `closed` or `accepted`
  field anywhere, and no command that sets one. Those mitigations are empirical rather than
  guaranteed and published defences have repeatedly been broken by adaptive attacks; a register
  that let somebody tick a class as handled would assert what the source declines to. Controls
  are recorded with evidence and a date. `accept_exposure` exists only to refuse, and names
  `exceptions-register` — a refusal with nowhere to go gets worked around.
- **A model card is T3**, and `ingest` refuses to record one higher. It is the most
  substantive-looking artifact in the whole AI supply chain and it is still the provider
  describing its own model.
- **Nine escalation triggers**, three of which fire at *every* criticality level:
  `model-changed`, `base-model-changed` and `unsanctioned-in-use`. `low` has no cadence by
  design, and a silent model swap is exactly the event that makes a low-criticality deployment
  stop being low. `base-model-changed` is its own trigger because a provider re-basing a product
  and leaving the version number alone is the change nothing else would notice — so `assess` now
  records the system, version, base model, hosting, autonomy and connected resources it was
  made against.
- **Shadow AI is a real row immediately.** `intake-discovered` refuses without a source and a
  sighting date, then records the system unsanctioned and in the register. No staging area: the
  failure mode of shadow AI is a finding that lives in a CASB console until somebody promotes it.
- **Regimes ship as dated data, and the dataset is empty**, on the precedent `vendor-register`
  set. `register_regime` refuses an obligation with no `source` and no `owningFunction`, and a
  regime with no `aiRole` — much of what these regimes say is addressed to *providers*, and a
  firm that buys and deploys AI is usually a deployer.
- **Two bridges, both one-way.** `export-findings` to `risk-register` through the *existing*
  import path, carrying no likelihood, impact or score; attack classes are deliberately not
  exported, because a class has no closed state and a risk does. `export-signal` gives
  `nist-csf`'s existing Cyber AI Profile scoping question counts as evidence — and only counts:
  a rating arriving there is refused, and with no signal the output is byte-for-byte unchanged.
- **The `ai` board section**, additive within `contractVersion: 1`, item key `deployments`,
  ordered after `vendor` in both audiences: most AI arrives through a third party, so the
  third-party section is the context this one is read against.

Found while building, and fixed:

- **`no-regime-dates.sh` caught its first defect on its first run — in this skill's own
  self-test fixture.** A source string read `"Article 1, checked 2026-01-01"`, which is exactly
  the shape the guard bans: a year inside a sentence citing a regulation. The fixture changed,
  not the guard. A dated citation belongs in `regimes.json`, behind an `asOf`.
- **The first `no-closed-state` scanner read a subscript key wrongly** — `node.slice.value`
  returns the inner AST node on 3.8 and the bare string on 3.9+, so a planted
  `exposure[cls]["mitigated"] = True` passed the assignment scan on every interpreter this
  suite actually runs on. It was masked because the only mutant testing that path also carried
  a give-away function name and went red for the other reason. Two mutants now, one per path.
- **The first exposure colour guard held four literal hex values** it believed were "the green
  one". The library's good band is `#E3EDE4`, which was not among them, so a planted green chip
  passed in silence. Replaced with a hue test.
- **`vendor_finding_to_risk` set `theme = "govern" if "govern" in CSF_FUNCTION_THEMES`**, whose
  keys are `GV` / `ID` / …, so it was always `None`: every finding imported from
  `vendor-register` since v0.39.0 landed outside every CSF theme, and a theme-filtered view
  dropped the lot in silence. Found while generalising that function to carry AI findings
  through the same path.
- **A pack with no `ai` sidecar gains one provenance line**, exactly as `vendor` did, and takes
  the same answer for the same reason: exempting it would restore byte-identity by making a
  whole board section silently absent. Pinned in `evals/assembly.sh`.

---

## v0.40.0 — 2026-08-08

**The assessment layer.** Plan 1 built the record; this builds the work — read what a vendor
supplied, work out what it genuinely covers, and emit the questions still worth asking.

- **Evidence is tiered, scoped and dated.** Only **T1** (an audited artifact) and **T2** (a
  contractual commitment) can satisfy a requirement. A T1 refuses without a scope *and* a
  period: a SOC 2 excluding the subservice organisation running the workload has not covered
  it, and a report with no period cannot expire. **A bridge letter is T3 and does not extend a
  T1's currency** — a management assertion is not an audited artifact.
- **The Layer A / Layer B boundary**, which is the safety property of the whole feature.
  `propose` refuses without a citation and refuses to cite T3 or T4 at all; only `assess`
  closes anything, and only with a named person. A model reading a trust page and ticking
  requirements produces a register full of green from marketing copy — worse than an empty
  one, because it looks finished.
- **`ask` subtracts.** Batteries left applicable, minus what T1/T2 evidence covers. **T3 and T4
  subtract nothing** — that is the product claim, asserted as a comparison: the same three
  requirements covered by an audited report shrink the set and covered by a trust page do not.
  Evidence in grace produces a re-confirmation question rather than silence, and an empty
  result prints a sentence.
- **The assessment clock now has an act that resets it.** `_last_assessed` had been reading an
  `assessments` list since v0.39.1 with nothing able to write to it.
- **The overlay mechanism ships empty, by decision.** No DORA, NYDFS, interagency or SEC
  content: those were drafted from secondary sources and marked `[verify]`, and a compliance
  tool asserting an obligation it cannot cite is worse than one that stays quiet.
  `register_overlay` **refuses an uncited requirement**, so this cannot be relaxed quietly.
  `export-roi` still ships, gated on a declared `doraScope`, and refuses to look complete when
  it is not — a named gap and a non-zero exit, never a blank cell.
- **A one-way findings bridge to `risk-register`**, carrying no likelihood, impact or band.
  Extended through the existing `merge_import` rather than a second importer. Escalations are
  deliberately *not* exported: they are derived and stateless, so exporting them would mint a
  fresh candidate risk every time a clock moved.

Found while building, and fixed:

- **`review_requirements` shipped in v0.39.0 without requiring a named person**, so a
  requirement could be marked met with nobody's judgement behind it — which made the "only a
  named person closes anything" claim false. Found by `proposal-boundary.sh`'s static scan on
  its first run.
- The board renderer's own new copy failed `board-safety.sh` for saying *"not a rating"* — the
  guard was right, and the sentence was reworded rather than the list weakened.

Self-test **88 → 224**; `risk-register` **170 → 177**; four new eval suites (`evidence-tiers`
11, `proposal-boundary` 10, `questions` 8, plus the existing four).

## v0.39.1 — 2026-08-07

Two follow-ups from the v0.39.0 review, both closed as checks rather than notes.

- **A pack with no `vendor` sidecar says so, and that is now a decision with a guard behind it.**
  Adding the section made an existing pack gain one provenance line — *"the `'vendor'` section is
  not in this pack"* — which broke a byte-identity check the plan had listed. The alternative was
  exempting `vendor` the way `incident` is exempted, restoring byte-identity by making an entire
  board section **silently absent**: a reader could then not tell *considered, and there are none*
  from *nobody asked*. `incident` is exempt because a quarter with no incident is a normal
  quarter; third-party risk is a board section in its own right. Two checks pin it, and exempting
  `vendor` fails both. 80 → **82**.
- **`vendor-register` gains its routing checklist** — 15 cases, 10 positive and 5 negative. The
  load-bearing one is `Y1`: *"give me a risk score for our hosting provider."* Every commercial
  third-party tool answers that with a vendor score; here it belongs to `risk-register`.
  `no-vendor-score.sh` proves nothing computes one, and `Y1` proves nothing offers to.
  **The checklist records that it has not been scored yet**, rather than carrying an invented
  number — its siblings all carry a real one from a real run.

## v0.39.0 — 2026-08-07

**`vendor-register`, skill #9** — third-party arrangements, with a criticality that is traced
rather than asserted. Plan 1 of two; the assessment layer follows.

- **Contract-centric, not vendor-centric.** One provider commonly holds several arrangements at
  different criticalities, and a vendor-shaped store forces one criticality per company.
- **Criticality is derived, then confirmed.** The walk traces what an arrangement supports back
  to a workflow whose criticality the business declared — two hops, following NISTIR 8179's
  Process E in shape. Derivation proposes; `--confirm` without `--by` is refused. A confirmed
  level that differs from the derived one is a *finding*, not an error, and escalates.
- **`untraced` is a value, not a gap.** Never `low`, not a member of the scale, and
  `criticality_rank` **raises** on it — one `sorted(key=rank)` placing it at the bottom would
  silently downgrade every untraceable arrangement behind a board table that looked complete. A
  truncated walk returns `untraced` *and* `truncated`, never a confident level from an
  unfinished walk. Mutation-tested three ways.
- **No vendor score**, under an eval with two halves: nothing emitted is named like one, and
  nothing computes one internally. Proven in both directions — a score renamed to
  `attentionIndex` escapes the first check and not the second.
- **Triggers fire at every criticality level.** `low` has no cadence by design, so a
  subprocessor change on a low arrangement is the only thing that catches it stopping being low.
- **The D-10 colour split**: criticality is RAG operationally, a classification on the board
  page, where RAG is reserved for what needs a decision. `untraced` is neutral on both and
  always carries its word.

- **`decisions-render.sh` found a live defect on its first run**, before this skill had ever
  shipped. `ciso-board-translation` emits decisions as `{"text", "altitude"}` objects and the
  board renderer stringified them, printing a raw Python dict where a board decision belongs —
  the same P1 that shipped across this suite once before. Fixed, and the renderer now separates
  board asks from management actions rather than listing both as things to vote on.
- **`board-safety.sh`** inherits the confidence and catastrophizing checks every producer here
  carries and adds one this skill needs: **no scoring vocabulary on a page**. `no-vendor-score`
  proves nothing *computes* a score; this proves nothing *says* one.

Supporting changes:

- `business-context` crown jewels may declare `criticality` and `dependsOn`. Optional and
  additive — absent unless declared, so every `.biz` written before this exports byte-identically
  (asserted). This is where the walk's top hop lives, because how critical a workflow is, is a
  business judgement.
- `board-pack` gains a `vendor` section, **additive within `contractVersion: 1`** on the
  `boundTo` precedent. It sits after `risk` in both orderings — what we carry, then who we
  depend on to carry it — and both orderings are recorded as chosen rather than defaulted.
  A pack with no vendor sidecar is unchanged in every section, decision, headline and
  escalation; it gains one provenance line naming the section it does not have.

## v0.38.0 — 2026-08-07

An agenda can be wrong as a whole while every ask on it is right.

- Above **five** decisions pitched at the board, the pack says so on the provenance page, in
  the document and on a slide — naming the count and which sections it came from. Five is a
  convention this skill declares, not a standard it cites, so it is named in one constant a
  reader can disagree with rather than buried in a comparison.
- The same failure as the mixed-organisation pack and the hidden conflict: an artifact true on
  every page and unusable as a whole. Ten votes in one sitting does not get ten decisions — it
  gets a few and a queue nobody names. The shipped specimen carries ten, which an external
  retest read as a packaging problem; it is a fixture problem, and the pack now says so itself.
- **It counts and does not choose**, and it suggests no remedy on purpose. Re-pitching an ask
  from `board` to `management` would make the warning vanish and change nothing about the
  exposure; a governance tool that nudges toward relabelling decisions so a deck looks tidier
  is worse than one that stays quiet. Holding an ask back belongs in the minutes, not in an
  `altitude` field.
- Mutation-tested three ways: a warning that never fires, one that counts list length instead
  of altitude, and a threshold of zero each fail a named check. Self-test 132 → **133**,
  assembly 77 → **80**.

## v0.37.1 — 2026-08-07

A model-facing instruction that had been wrong for four releases.

- `skills/board-pack/SKILL.md` still said the applicability profile narrowed
  `incident-materiality` **alone**, and quoted a provenance sentence naming the other four as
  not reading one. That stopped being true at `v0.35.0` and `v0.36.0`. `SKILL.md` is
  operational guidance a model reads *instead of* the implementation, so a stale paragraph
  there is not a typo — it is an instruction to believe something false about four skills.
  Found by external retest, not by us.
- The correction is a check, not a better memory. `assembly.sh` now extracts the blockquote
  from `SKILL.md` and compares it, whitespace-normalised, against the note a real assembly
  writes to the provenance page. It pins no phrase of its own, so when the sentence changes
  because a producer implements the contract, the check fails until the doc is brought along.
  76 → 77 checks.

## v0.37.0 — 2026-08-07

Board prose is bound to the store it describes, and the deck has a board-length mode.

- **`boundTo` in a section sidecar** ties prose to the store state it was written against. A
  register edited after its sidecar produced a pack whose sentences described one state of the
  world and whose numbers described another — `asOf` is a reporting date, not a store version,
  so nothing noticed. Bound and matching is silent; bound and stale warns with both timestamps;
  unbound produces one note for the pack, never one per section.
- **`render_pack.py --deck-mode board`** takes the specimen from 31 slides to 15 before an
  appendix. It **moves and never drops**: the check diffs every text run of both decks, and the
  only thing the board deck does not say is `Section N of 5`.

## v0.36.0 — 2026-08-07

`nist-csf` reads the applicability profile, completing CAC-AP-1 across every register.

- The battery is the **NIST Cyber AI Profile overlay (IR 8596)**, gated on `aiInUse` — and on
  the `secure` and `defend` focus areas only. `thwart` covers attackers using AI against you
  and applies whether or not you use AI at all; gating the whole overlay would have narrowed
  away a question conditional on nothing the profile declares.
- First consumer that **answers** its question: a `.csfp` records the overlay state, so
  disagreement is reported in both directions.
- Fixed: `CONFLICT_KEYS` required `regime`, which a posture conflict does not have, so every
  one would have been rejected as malformed. Fixed: the provenance note vanished entirely once
  every section read a profile.

## v0.35.0 — 2026-08-07

`risk-register`, `metrics-register` and `exceptions-register` read the applicability profile.

- What a profile narrows in a register is the **question set**, not the arithmetic. They ask
  and do not answer, because nothing in these stores records whether a record concerns OT or
  AI, and a coverage figure would be inferred from data that is not there.
- New `business-context/evals/consumers.sh`, which holds every consumer to the contract from
  the side that defines it. It found contract drift on its first run.

## v0.34.0 — 2026-08-07

A polished pack could describe two companies and hide a legal-perimeter conflict.

- **Mixed-organisation packs are refused.** The shipped specimen was itself assembling stores
  belonging to three different fictional firms. Override with an attributed `consolidation`
  block, printed on the provenance page.
- **Applicability conflicts reach the board.** `incident-materiality` reported four `sec-1.05`
  conflicts and the pack dropped all of them, printing "the profile narrowed incident" and
  Form 8-K three times. They now have their own page and slide, before the through-line.

## v0.33.0 — 2026-08-07

`board-pack` reads the applicability profile, so the pack and the worksheet agree.

## v0.32.1 — 2026-08-07

Metrics printed a count with no denominator to read it against.

## v0.32.0 — 2026-08-07

The deck paginated by counting items rather than measuring content, so long prose fell off the
bottom of a slide. New `deck-fit.sh`.

## v0.31.0 — 2026-08-07

Every chart label was measured against a background it never sat on. The contrast checker
resolved SVG text against the page ground rather than the mark behind it, so a band label at
2.62:1 survived four releases with two suites agreeing it was fine.

## v0.30.2 — 2026-08-07

The brand floor scored the cover kicker as decoration rather than as text.

## v0.30.1 — 2026-08-07

Closed the v0.29.0 external retest findings, and one the retest missed.

## v0.30.0 — 2026-08-07

**`business-context`, skill #8**, and the applicability contract **CAC-AP-1**, proved against
one consumer before any others were built on it.

- A `.biz` store: revenue base (exact, rendered banded), crown jewels, board-voiced tolerance,
  obligations — each with a declarer, a date and a basis.
- The profile narrows what other skills ask. **Absence asks more**; a subject declaration
  outranks the profile in both directions; every skipped battery is recorded with its reason.
- `incident-materiality` is the first consumer: SEC Item 1.05 gated on a listed entity, DORA
  windows on declared DORA scope, and the un-narrowed path byte-identical to before.

## v0.29.0 — 2026-08-06

Bands get room when a metric is banded near its ceiling. *(The version an external retest
reviewed; reachable by tag since 2026-08-07.)*

## v0.28.1 — 2026-08-06

The chip and the bullet agree on the boundary.

## v0.28.0 — 2026-08-06

A time axis that is linear in time — the Gantt positioned bars ordinally, not by date.

## v0.27.0 — 2026-08-06

One grid, one palette across every rendered mark.

## v0.26.0 — 2026-08-06

All five skills render under a client brand, with the palette floors enforced at apply time.

## v0.25.0 — 2026-08-06

Attribution comes from one place, and is checked there.

## v0.24.0 — 2026-08-06

`board-pack` notices when two producers escalate the same underlying record — flagged, never
merged.

## v0.23.0 — 2026-08-06

`exceptions-register`: re-measure before you renew. Re-validation is an act with a rationale,
never a timer reset.

## v0.22.0 — 2026-08-06

`incident-materiality` escalates the clocks, and nothing about materiality.

## v0.21.0 — 2026-08-06

`exceptions-register` escalates a lapsed clock, from the skill that owns it.

## v0.20.0 — 2026-08-06

`metrics-register` escalates a breach, and the slip before it.

## v0.19.0 — 2026-08-06

`board-pack` carries the escalations its producers raised — the aggregation no single skill can
do.

## v0.18.1 — 2026-08-06

Documented the second event partition, in the contract and in the skills.

## v0.18.0 — 2026-08-06

**The exposure lifecycle, CAC-EL-1.** `risk-register` raises its own hand: a derived, stateless
escalation record with one shape across the suite. Flag, never block.

## v0.17.0 — 2026-08-05

The pack model carries figures and the producers compute their own — a figure derived in the
assembler is a second number that can disagree with the section above it.

## v0.16.0 — 2026-08-04

**Presentation graphics**: a shared SVG library, a three-way colour contract (RAG / MEASURE /
PATINA), and an editable PowerPoint deck written from `zipfile` with no dependency.

## v0.12.0 — 2026-08-03

Three findings from the v0.11.0 external review.

## v0.11.0 — 2026-07-31

Seven skills, and the refusals they enforce. The first tagged release; see the
[release notes](https://github.com/cyberaware-creations/cac-ciso-toolkit/releases/tag/v0.11.0).

Everything before v0.11.0 predates both tagging and this file. The version strings in the
manifest history are the only record of it, and `git log -- .claude-plugin/plugin.json`
recovers the mapping.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
