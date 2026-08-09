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

## v0.59.0 — 2026-08-09

**BL-163 and BL-121 — two ways a board-safety suite reports a pass it did not earn.**

### BL-163 — the largest suite counted failures and not checks

Every other `board-safety.sh` asserts how many checks it ran. `risk-register`'s — the biggest,
and the one whose scanner has the most to say — asserted only that none of the checks it
happened to run had complained.

Its `chk` helper already closes one hole: a check written with the wrong helper name cannot
pass silently. It does not close the other. A check that stops **executing** — an early exit, a
fixture step that returns non-zero and skips the block beneath it, a branch that stops being
taken — deregisters itself. `fails` stays at zero and the suite prints "all checks passed".

`fails` answers *did anything I ran complain?*; `EXPECTED_CHECKS` answers *did I run what I
think I run?* Only the second can see an absence. Now `EXPECTED_CHECKS=12`, asserted **before**
the pass/fail verdict — a suite that ran the wrong number of checks has not earned the right to
report either answer.

### BL-121 — 51 checks across nine files read a crashed probe as a pass

```bash
hit=$($PY - "$file" <<'PY' ... PY)
if [ -z "$hit" ]; then ok "nothing wrong"; fi
```

**Command substitution discards the exit status.** A traceback goes to stderr and leaves stdout
empty — byte-for-byte what a clean run produces. The check prints `ok`, the suite exits zero,
and the thing it was written to examine was never examined.

The fix was written once, in `board-pack/evals/assembly.sh` at v0.43.1, and copied nowhere.
**Nine suites ran the broken idiom for fourteen versions.**

`probe` now lives in `tools/eval-probe.sh` and is **sourced, not copied** — a helper that must
be re-typed into each suite will diverge again. 26 capture sites across nine suites migrated.
`lint-evals.py` gains **LE-1.2**, which flags a raw inline capture in any file that sources the
helper, so a migrated suite cannot drift back one line at a time.

**Proved, not asserted.** Injecting `raise KeyError` into a probed block made
`metrics-register/board-safety.sh` print *"all 10 checks passed"* and exit 0 before the change,
and FAIL with the traceback quoted and exit 1 after it. Every suite's full output was diffed
against its pre-migration output: all nine identical bar BL-163's intentional count line.

### Three defects found while making the change

- **`probe -c` would have re-created the exact defect.** `probe` reads its script from stdin,
  so `probe -c "code"` ran `python - -c "code"`: an empty program, no output, exit 0, and the
  caller reads it as clean. Caught by diffing outputs rather than by reading the change. `probe`
  now handles both call shapes.
- **A heredoc opener inside a comment blanked the rest of a file from the linter.**
  `_strip_heredocs` never found a closing delimiter, because the closing line was commented too.
  `tools/eval-probe.sh` documents its own call shapes in prose, so `probe` vanished and every
  suite sourcing it was reported as calling a helper nobody defines. **A comment could switch
  this linter off for the rest of a file.**
- **A `$here/`-rooted `source` was skipped as "computed".** `$here` is this repo's universal
  name for the sourcing script's own directory, so it is resolvable. Skipping it made a sourced
  helper invisible — the same can't-see-it defect one level up.

**Verification:** `lint-evals` self-test 10 → **17 checks**, 50 suites clean; `risk-register`
board-safety 12/12 with the count assertion proved to bite; all nine suites byte-identical
pre/post migration; 46/48 eval scripts; `prove-guards` 17/27; `check-sources` 82 self-test and
clean; `check-versions` all six.

---

## v0.58.0 — 2026-08-09

**BL-95 — C-2 opportunity grounding. The rule existed; nothing enforced it.**

`GV.RM-07` asks that strategic opportunities be characterised, and `board-pack` refuses an
opportunity with no `cites`. The refusal message has always told authors to name *a declared
strategic goal or crown-jewel dependency from `business-context`* — and the assembler checked
only that the string was non-empty. **`goal:no-such-goal` assembled onto a board page.**

A citation nothing resolves reads on the page exactly like one that does. That makes the rule
decorative, and a decorative grounding rule on positive risk is worse than none, because the
page looks evidenced. It is the same failure this repo keeps finding: a check that reports
success without having tested anything.

### The refusal named a format the data model could not supply

`business-context` stores strategic goals as plain sentences — `add_listed` appends the text
and nothing else. **There is no `<id>` to cite**, so the format in the refusal message was
unachievable, and nothing noticed because nothing resolved it.

The id is now the sentence slugged. Both sides are slugged, so `goal:Reduce time to market` and
`goal:reduce-time-to-market` are one citation. No store change, no migration: every `.biz`
written before this grounds correctly and exports byte-identically. The shipped example pack
already cited its goal in full sentence form and grounds unchanged.

### Absent, empty, and bound are three different answers

| Bound context | Behaviour |
|---|---|
| none | presence check only — exactly as before (CAC-AP-1 §2.2) |
| unreadable or malformed | treated as none, matching `store_organisation`: refusing a pack because one store is quiet blocks the honest case to catch nothing |
| bound, declares nothing citable | **every opportunity is ungrounded and refused** — an empty set is not the same as no profile |
| bound, declares goals | each `cites` must resolve; the refusal lists what is citable |

### The eval assertion was flipped, not deleted

`section-contract.sh` carried a case asserting that `goal:no-such-goal` **was accepted**, with
a comment saying the assertion would have to flip when grounding landed. It has. Flipping
rather than deleting keeps the only record that the check ever had this hole, and the comment
above it is the argument for why the hole mattered. Six cases replace the one: no-profile
parity, an unresolvable citation, four resolvable spellings, empty-set versus None, a
`crown-jewel:` prefix that must not resolve against a goal, and `grounding_keys` reading a real
`.biz`.

**Verification:** `section-contract.sh` 54/54; `assemble_pack.py` self-test 137/137; 18/18
evals across board-pack, business-context and vendor-register; full sweep clean.

---

## v0.57.0 — 2026-08-09

**BL-194 and BL-190 — the last v0.53.0 blocker, and the half of C4 that was never written.**
Both in `tools/check-sources.py`, both the same shape: a check that could not see the thing it
was supposed to be checking.

### BL-194 — C5 was blind to 24 shipped files

`docs/` and `research/` sat in `_DNC_EXEMPT` alongside the registry, the code that reads it and
the schema that documents it. Those three belong there — each must carry watched designations
in order to police them. `docs/` and `research/` were exempt **by directory name**, and nothing
in either is about the registry. They are ordinary prose, which is exactly where a withdrawn
publication gets cited by reflex.

Removing them put 24 more files in C5's scope and found no existing violation — the outcome to
expect, and not a reason to have left the hole open, because C5's entire purpose is the
citation nobody has written yet.

Six self-test cases pin the scope in place: a planted `SP 800-61 Rev. 2` under `docs/`, under
`research/`, and nested deeper under `docs/` all fail; a genuine same-line warning under
`docs/` still passes; and `CHANGELOG.md` and `tools/sources-schema.md` stay exempt, so the fix
cannot be over-corrected into deleting the exemptions that earn their place. The test for
adding a path is now written down: *does this file need the string in order to police the
string?*

### BL-190 — C6, the converse of C4 (RW-1.10)

C4 reads the manifest and asks whether the tree still matches it. Nothing asked the other
direction. A citation added to a reference file and never added to `sources.json` was invisible
to every check in the standard — never reviewed, never re-checked against its publisher, never
gated, and **indistinguishable from a citation that had been verified**, because nothing
recorded the difference.

**C6 found ten undeclared citations across five shipped skills on its first run**, including
`NIST IR 8179`, which carries `vendor-register`'s entire two-hop criticality model, and
`47 CFR 64.2011`, which carries a disclosure delay window in `incident-materiality`.

Designations are canonicalised to stable keys rather than matched as substrings — the first
attempt reported `ISO/IEC 27001:2022` and `ISO 27001` as two different instruments, which is
how a check earns being switched off in a fortnight. An ISO **edition year** is dropped; a NIST
**revision** is not, because `Rev. 2` and `Rev. 3` are different documents with different
obligations, and every reference defect this repo has found has been an amendment failure.

Each pattern carries a fixture asserting the key it produces, for the same reason `mustFlag`
does: a detector that has stopped detecting reports *"no undeclared citations"* in exactly the
tone of one that works. Writing those fixtures caught two dead patterns — the CFR pattern did
not match this repo's own ASCII `s` for `§`, so two rows added in the same commit went on
reporting themselves undeclared.

**Five publications were verified against primary sources and declared**, not written from
memory: SP 800-63B-4 (Final, 31 July 2025), IR 8179 (Final, 9 April 2018), IR 8286B-upd1 and
IR 8286D-upd1 (both Final, 26 February 2025), and 47 CFR § 64.2011. Two more were carried
across from already-verified rows in sibling skills. 39 → 45 declared sources.

**Two are allowlisted, permanently and with the argument recorded**: `iso-27002` and
`iso-27001` in `vendor-register`, where the mention names *a kind of artifact a vendor hands
over* rather than citing the standard's text — and CAC holds no ISO licence, so a verified row
would be a claim nobody checked. An allowlist entry with an empty `reason` fails the run;
otherwise the allowlist is a way to switch C6 off one line at a time while reading as
considered judgement.

**Verification:** `check-sources.py` self-test 54 → **82 checks, 0 failed**. Repo run clean:
11 skills, 45 declared sources, 1 unverified and ungated, 292 files scanned by C5.

---

## v0.56.0 — 2026-08-09

**BL-101, BL-99, BL-102 — the guard proofs, and what they were not proving.** Three items on
one file, shipped together because they are one argument: the runner could not see eight of
its guards, the eight it could not see had never been mutation-tested, and the test it applied
to the nine it *could* see did not establish what it claimed.

### BL-101 — discovery could not see eight guards (GP-1.8)

`prove-guards.sh` globbed `evals/no-*.sh` plus three literal filenames. Eight real guards were
invisible: seven copies of `decisions-render.sh` and `ai-register/exposure.sh`. The GP-1.7
registry check filtered through the same globs, so it compared the standard's table against
the blind spot and reported a clean bill.

No filename rule could have caught it — **the failure is an omission, and an omission has no
filename.** A marker line inside each guard was considered and rejected for the same reason: a
marker cannot detect its own absence.

Discovery now reads `tools/guard-registry.json`, which assigns each of the 48
`skills/*/evals/*.sh` on disk exactly one role — `guard` (17), `candidate` (11),
`not-a-guard` (20) — and a script in none of them fails the run.

Classifying the non-guards forced a verdict on files nobody had judged, which is where the
**eleven candidates** came from: guard-shaped, not yet enrolled — the nine `board-safety.sh`,
`vendor-register/questions.sh`, `business-context/archetype-advisory.sh`. That count now
prints on every run.

### BL-99 — the eight invisible guards, now proved

Eight new proof files, nine halves. `EXPECTED_GUARDS` 9 → 17, `EXPECTED_HALVES` 18 → 27.

The planning note assumed the seven `decisions-render.sh` were near-identical and one mutation
would serve. They are not: their check counts run 3/3/3/3/4/6/11 and the `_dtext` helper exists
in only four of the seven renderers. Seven bespoke mutations, plus one for `exposure.sh`.

**Two rejected mutations are recorded in the proof files, because they say more about the
guards than the accepted one does.** Returning the dict from `_dtext` makes `esc()` raise: the
renderer dies, no HTML is written, and the guard's greps find nothing and report **clean** —
BL-121's crashed-probe blindness, sitting inside five guards. Returning `str(d)` renders the
repr, but `esc()` escapes the quotes to `&#x27;`, so the literal `{'text'` the guard greps for
never appears — meaning **that grep would not catch the original P1 defect today either.**

### BL-102 — a non-zero exit is not proof the right half caught it (GP-1.9)

GP-1.1 has required since the beginning that each mutation defeat its own half specifically.
Nothing enforced it, and two guards were violating it while reporting the textbook
clean-pass/mutated-fail:

- **`proposal-boundary`** — the behavioural mutation added `"T3"` to `SATISFYING_TIERS`, which
  is also an inlined tier list, so the static half caught it too. Now assembled as
  `"T" + "3"`, invisible to a literal scan.
- **`evidence-tiers`** — disabling the T1 scope-and-period refusal let an undated T1 into the
  store, and the expiry half was reading `evidence[0]` **positionally**, so three expiry
  assertions failed for a reason with nothing to do with expiry. The mutation was not at fault
  here; **the guard was.** `status()` now selects the dated T1 by its period and asserts there
  is exactly one.

A third mutation was blunt rather than mis-aimed: `exposure`'s derivation half renamed `add`
to an undefined `_disabled_04`, raising NameError and taking NISTAML.03, .05 and the
availability pair down with it. Narrowed to `if False:` on the generative branch.

Every mutation now carries a `defeats` list naming the checks the mutated run must fail, and
the runner asserts the set exactly — all named checks fail, no unnamed check fails, none was
already failing clean. The cross-half rule is **distinguishability, not disjointness**:
`outcome-framing`'s two mutations both trip the checker's own self-test, a meta-check belonging
to neither half, and each still defeats one check the other does not.

GP-1.9 was mutation-tested against itself: deleting a `defeats` list fails the run, giving two
halves the same list fails it, naming a check the guard never prints fails it.

---

## v0.55.0 — 2026-08-09

**BL-193, BL-194, BL-195 — the v0.53.0 release blockers.** C5 shipped as a safety feature and
failed its own adversarial suite. Every failure was the same shape: a check reporting success
without having tested anything.

### BL-193 — SP 800-16 was withdrawn, and the search that missed it

`notYetVerified` recorded SP 800-16 as *"did not surface in a CSRC search; status unconfirmed"*.
It is **Withdrawn, 12 September 2024**, superseded by SP 800-50 Rev. 1 — which absorbed
role-based training so one document now covers awareness, training and education.

The reason it was missed is worth recording: a CSRC **keyword search** for `800-16` returns
SP 800-**18** and not it. Only the direct publication URL shows it. A search that returns
plausible neighbours reads exactly like a search that found nothing.

**CSF 1.1** also moved into enforcement — NIST's own site files it under a *"CSF 1.1 Archive"*
with 2.0 as current. Listed `superseded` rather than `withdrawn`: CSF is not in the CSRC
catalogue and carries no withdrawal record, and *archived* is NIST's word.

**SP 800-100 stays out, and the record is subtler than either earlier pass had it.** CSRC carries
two entries under that number: the October 2006 original, **Withdrawn 7 March 2007**, and the
March 2007 update, **Final**. The seed list's "confusing withdrawal record" was right; v0.53.0's
"CSRC reports it FINAL" was right about the current edition only. Because the *number* is current,
a bare `SP 800-100` is ambiguous rather than wrong, and banning it would flag every legitimate
reference. Deliberately not enforced.

### BL-194 — C5 failed open four ways, and the four were not the class

Fixed as a class, per the plan's warning that four named cases produce a guard that passes four
named cases. **RW-1.9.1** replaces the ±320-character proximity window with binding:

> A marker excuses a citation only when it is on the **same line**, and of every watched
> publication on that line, the one **nearest the marker** is this one.

Plus offset-preserving typography folding, so a non-breaking hyphen cannot smuggle a citation past
the pattern.

| Reported case | Before | After |
|---|---|---|
| Unicode hyphen `SP 800‑61` | passed | caught |
| En-dash `SP 800–61` | passed | caught |
| Unrelated nearby prose | passed | caught |
| Cross-publication warning | passed | caught |
| Blanket `docs/` exemption | passed | **open question — see below** |

**Then two more, invented after those were closed, and both still failed open:**

- a marker living inside a **URL** on the same line (`https://…/withdrawn/`), which sat nearer the
  citation than anything else and laundered it;
- a marker as a **substring of an identifier** (`obsoleteFlag`), which plain substring search
  counted as a warning.

Fixed by blanking URL runs before the marker search and requiring whole-word markers. **That the
independently-invented pair both failed is the evidence the reported four were not the class** —
had the four been added and the work stopped, C5 would still fail open two ways.

**One deliberate regression.** A marker on the *next* line no longer excuses a citation, and the
self-test case asserting the old behaviour was flipped. Same-line binding is stricter, and for a
check whose failure mode is silent success that is the right direction. It cost one reflow in
`tools/README.md`, where a hard-wrapped sentence put `[Withdrawn:]` and `CSF 1.1` on different
lines — and putting the qualifier beside the thing it qualifies is better writing anyway.

### BL-195 — the registry was trusted without being validated

C5 reads `status` and `supersededBy` only when building an error message, so an entry missing both
sat in the file looking like protection and would have crashed the first time it caught anything.
A pattern matching nothing at all was indistinguishable from one guarding an uncited publication.

**RW-1.9.2** validates the registry before use, and every entry now carries **`mustFlag`** — a
string its own pattern must match — with optional `mustNotFlag`. These are executable fixtures,
not documentation: a pattern that has stopped matching its own example is reported now rather than
discovered the day somebody cites the publication it was supposed to watch.

Self-test **40 → 54**.

### Raised, not resolved

**Is `docs/` in scope for C5?** The release says C5 scans shipped prose while `docs/` and
`research/` are blanket-exempt, so either the code is wrong or the sentence is. `docs/superpowers/`
legitimately discusses withdrawn publications in internal plans, so scanning it may be pure noise —
in which case the honest fix is the claim, not the scanner. Left for the maintainer.

---

## v0.54.1 — 2026-08-08

**The two ISO rows were not the same problem, and one of them was never unverifiable.**

The maintainer confirmed this project holds **no ISO licence**, which made the remaining two rows
look permanently stuck. Looking at what each actually relies on split them apart.

### The crosswalk row was verifiable all along

`nist-csf` does not rely on ISO's *text*. Its crosswalk carries **Annex A identifiers taken from
NIST's own CSF 2.0 Reference Export**, with CAC-paraphrased labels and `text: null` on every
control — the catalogue says so in its `provenance`, and `license: "iso-copyright"` with *"bring
your own copy"*.

That chain is checkable, and it checks out. The vendored `tools/csf-2.0.xlsx` hashes to
`cc4ec545…f9b616`, **matching the sha256 recorded inside `nist-csf-2.0-core.json` exactly**. 119
identifiers, 91 of them referenced by NIST's export, 329 mapping edges, authority declared as
`mixed-third-party`.

So the row is now **verified**, with its scope stated: identifiers and NIST's mapping, not ISO's
text. This is the crosswalk bundle proving the point made when `sources.json` was designed — it
was the one place in the product that already had a stamp discipline, and it is the one place
that could answer a provenance question without anybody's licence.

### The other row genuinely cannot be closed

`exceptions-register` cites **Cl. 6.1.3 / 8.3** for what they *require* — risk treatment and
residual-risk acceptance by risk owners. That is a claim about the standard's text, and no amount
of identifier-level verification touches it.

Its `whyUnverified` now records that this is **permanent, not pending**: no licence, `iso.org`
returns 403, do not re-attempt from the web. It also records the two ways to close it — read a
licensed copy, or narrow the claim in `references/exceptions.md` to clause *numbering*, which the
crosswalk already verifies.

**1 of 39 unverified**, and it is the honest one.

---

## v0.54.0 — 2026-08-08

**The five unverified sources, worked through — and two wrong dates in the Delaware receipts.**
`sources.json` shipped in v0.52.0 reporting *5 of 37 not yet verified against a primary source*.
That number was the point of printing it. It is now **2 of 39**, and both remaining are blocked
for a reason the manifest records.

### Two Delaware dates were wrong

The `Cite as` table in `regulatory-receipts.md` — the one whose stated purpose is that
*"the identifiers below are stable and let anyone retrieve the primary text"* — had two decision
dates off by weeks:

| Case | Was | Is |
|---|---|---|
| *Firemen's Ret. Sys. of St. Louis v. Sorenson* (Marriott) | Del. Ch. **26 Oct.** 2021 | Del. Ch. **5 October 2021** (Will, V.C.) |
| *Construction Industry Laborers Pension Fund v. Bingle* (SolarWinds) | Del. Ch. **5 Sep.** 2022 | Del. Ch. **6 September 2022** (Glasscock, V.C.) |

Both confirmed against CourtListener and the Delaware Court of Chancery's own opinion records.
*Boeing* (7 Sep. 2021) and the *Bingle* affirmance (No. 411, 2022, 17 May 2023) were already
right. The authoring judge is now named on each, because a docket number plus a date plus a judge
is retrievable in a way a docket number alone is not.

**These are exactly the citations BL-63 verified in v0.46.0 — and it verified the wrong ones.**
That pass checked *Caremark*, *Stone*, *TSC* and *Basic*, the four the item named, and left the
supporting cases alone because they already looked complete. A citation that carries a court, a
docket and a date looks verified. These two carried all three and were wrong.

### Verified and closed

- **NIST SP 1300** — *Cybersecurity Framework 2.0: Small Business Quick-Start Guide*, 2024. It
  does not appear in a CSRC keyword search, which is why it sat unverified; it is an SP 1xxx
  published through nist.gov rather than the 800-series catalogue.
- **NIST SP 800-53 Rev. 5** — Final, latest patch **Release 5.2.0, 27 Aug. 2025**. This
  independently confirms the v0.53.0 finding that the seed do-not-cite list had attached that
  patch to SP 800-53**A**, a different document.
- **CIS Critical Security Controls v8.1** — released 25 June 2024.
- **NIST IR 8596 (Cyber AI Profile)** — verified, and it **held**: an *Initial Preliminary Draft*
  of 16 December 2025. `nist-csf/SKILL.md` already says "preliminary draft" and the bundled
  dataset already carries `sourceStatus` and `sourcePublished` matching CSRC exactly. This was
  one of only two source families in the whole product that had a freshness stamp before
  v0.52.0, and it is still the best-disclosed reference in the repo. The row is gated at 180 days
  rather than 365, because a preliminary draft moves.

### The two that remain, and why they will not move

Both are **ISO/IEC 27001:2022**. ISO standards are paywalled and `iso.org`'s Online Browsing
Platform returns HTTP 403 here, so verifying clause numbering needs a licensed copy. That is a
**structural limit, not a transient failure**, and the manifest now says so — the next maintainer
should not spend an afternoon retrying it.

### RW-1.8 tightened: an unverified row must say why

`whyUnverified` is now required whenever `checkedBy` is `unverified`. Without it the value
degrades into a shrug, and a reader cannot tell *"nobody got to it"* from *"no amount of trying
will help"*. Both remaining rows are the second kind.

The three-catalogue `crosswalk-catalogues` row was also split into one row per catalogue — a row
covering three sources cannot honestly carry one verification status when two are verified and
one is blocked.

Self-test 39 → 40.

---

## v0.53.0 — 2026-08-08

**The do-not-cite list — the complement `sources.json` structurally cannot provide.** A manifest
watches what a skill *does* cite. It can never see a withdrawn publication the skill has **not**
cited yet, and that is the more dangerous class: the defect arrives fresh rather than sitting in
text somebody could review.

The worked example is why the list exists. **SP 800-61 Rev. 2 is withdrawn** — Rev. 3 became final
on 3 April 2025 — and its four-phase incident lifecycle is still repeated by nearly every secondary
source. This toolkit cites it nowhere, so no manifest has anything to stamp, and the first author
to write incident-response content reaches for it by reflex.

### The rule is not "never write the string"

Naming a withdrawn publication **in order to say it is withdrawn** is exactly what this repo should
do. `tools/do-not-cite.json` names them and **C5** scans shipped prose; what fails is a designation
with no withdrawal marker within about a paragraph — a citation rather than a caution. Both
directions are registered in the self-test, because a ban that also forbade the warning would be
switched off within a week. Window tuning is pinned too: a marker on the next line excuses a
mention, one three paragraphs away does not.

### The seed list had two errors, and checking caught both

The list was seeded from a prior session's research marked "all verified from CSRC". Re-verifying
each entry against the CSRC catalogue — the house rule — found:

- **SP 800-53A was conflated with SP 800-53.** The seed dated it to "patch 5.2.0, 2025-08-27",
  which belongs to the *controls catalogue*. SP 800-53A is the assessment guide and its Rev. 5 has
  been final since **25 January 2022**. Rev. 4 is genuinely withdrawn, so the entry survives with
  the right facts.
- **SP 800-100 is not withdrawn.** CSRC reports it **Final** (7 March 2007). An old final is not a
  withdrawn document, and banning it would have been wrong. Removed.

Three more could not be confirmed — SP 800-16, CSF 1.1 and SP 800-100's status question — and are
recorded under `notYetVerified`, **not enforced**. An unverified ban is as bad as an unverified
citation.

### Six publications watched, and one real hit on the first run

`SP 800-61` (and Rev. 1, Rev. 2) · `SP 800-171` Rev. 1 and Rev. 2 · `SP 800-50` (2003) ·
`IR 8374` (2022) · `SP 800-53A` Rev. 1 and Rev. 4 · `SP 800-18` Rev. 1.

C5 immediately flagged `nist-csf/evals/trigger-prompts.md`, where a recorded routing answer named
**SP 800-171 with no revision** as an example of a mandatory standard. The record is left as
written — it is what the model said — with an editorial marker beside the citation and a note
carrying the caveat that makes this entry awkward in both directions: **Rev. 2 is withdrawn by NIST
and still contractually live under DFARS clauses that name it by revision.** A defense contractor
told Rev. 2 is irrelevant has been misled as badly as one told it is current guidance.

`SP 800-18 Rev. 1` is listed as `superseded` rather than `withdrawn`, because Rev. 2's final status
(30 June 2026) is verifiable and Rev. 1's own CSRC status was not confirmed. The distinction is
kept rather than guessed.

Self-test 31 → 39 checks.

---

## v0.52.1 — 2026-08-08

**D-9 confirmed: the release gate stays, and the manifest keeps its two gate fields.**

`gated` and `reviewIntervalDays` ship in `sources.json`, narrowing the original rule that no
cadence appears in a shipped file. The maintainer confirmed the narrowing on 2026-08-08: a boolean
and an integer are policy rather than monitoring state, and a self-contained release gate is worth
it — it is what let Phase 0 ship complete instead of waiting on the private store.

Recorded in `tools/sources-schema.md` rather than left in a chat log. The alternative reading was
defensible, and a future maintainer is entitled to know this was decided rather than overlooked.

The coupling this confirms is the one that matters: **rendered citations may carry instrument
identifiers and dates only while something keeps them current.** The gate is that something. If it
is ever removed, RW-1.3's converse applies and rendered citations fall back to identifier-only.

Still open, and not decided by this: whether `checkedBy: "claude-code"` should be replaced by a
human signature on the legal rows, and whether 365 days is the right interval for the SEC rule
specifically, given it is under active rescission pressure.

---

## v0.52.0 — 2026-08-08

**Reference Watch Phase 0 — `sources.json` and CAC-RW-1.** The structural fix the last four
releases argued for. Every skill now declares the sources it cites, when each was last read
against its primary text, and by whom.

### Why a manifest and not another sweep

v0.48.0–v0.51.0 read six reference families against their instruments and found **twelve
defects**. Every one was an *amendment* failure — the citation was correct when written and the
instrument moved underneath it. **Not one could have been caught by re-reading the repo.** Four
sweeps fixed four families; nothing recorded that they had been swept, so the fifth pass would
have started from zero.

The pattern being copied was already in the tree: the crosswalk bundle is the one place with a
freshness stamp, and the one place a validator enforces one.

### Four checks, and the one that matters

`tools/check-sources.py` runs **C1** presence, **C2** shape, **C3** rendered-citation
byte-equality and **C4** `usedFor` paths exist. C3 is the point: a renderer keeps its literal
string — renderers never read the manifest at runtime, because every shipped script here runs
standalone — and CI compares the two byte-for-byte. The same technique `CROSSWALK_EXPECTED`
already uses to pin counts.

C3 earned itself immediately. It failed on first run against `render_report.py`, which still
emitted the undated *"(DORA RTS Art. 3(d); NYDFS §500)"*. That string now names its instrument:
**(DORA RTS (EU) 2024/1774 Art. 3(d); NYDFS 23 NYCRR 500)**. C4 caught two manifests where a
shared row had carried another skill's file paths.

### RW-1.8 — `unverified` is a first-class value

A design addition made while authoring, and the most important decision in this release.
**5 of 37 rows record a citation nobody has yet read against its primary source**, and they say
so: `checkedBy: "unverified"`. The run prints that count on every invocation.

The alternative — stamping every row as checked on the day the manifest was authored — would have
been a **worse lie than the undated citations it replaced**, because it would look supervised.
An unverified row may never be `gated`; the check refuses it, since the gate would otherwise be
timing a check that never happened.

### The release gate

`--release-gate` fails when a gated source passes its `reviewIntervalDays` (365 for the legal
instruments). An override needs a reason, an owner and a date, and **an empty reason still
fails** — the same discipline `exceptions-register` applies to an unapproved acceptance.

That gate is what makes precise dated citations safe to ship. If it is ever relaxed, rendered
citations must fall back to identifier-only: a confident citation nobody maintains is worse than
the vague one it replaced.

### What it cannot do, stated in the standard

**A manifest watches what a skill cites. It cannot see a withdrawn publication the skill does not
cite.** SP 800-61 Rev. 2 was withdrawn on 2025-04-03; its four-phase incident lifecycle is still
repeated by nearly every secondary source. This toolkit cites it nowhere, so there is nothing to
fix — and no manifest would ever catch the first author who reaches for it by reflex. A
do-not-cite list is the complement, and is tracked separately.

Self-test 31 checks. Three CI steps, listed individually.

---

## v0.51.0 — 2026-08-08

**The last three reference families: SP 800-30 Rev. 1, NIST AI 100-2, and NIS2.** Small surfaces,
one large finding. Sources: the SP 800-30 Rev. 1 PDF from nvlpubs, NIS2 from EUR-Lex (CELEX
32022L2555), and the NIST CSRC catalogue for AI 100-2.

### SP 800-30 Rev. 1 does not define the scoring model this suite attributes to it

`score_register.py` opened with *"NIST anchors: Exposure = Likelihood x Impact (SP 800-30 Rev. 1,
qualitative model)"*, `schema.md` headed its rating table *"Labels (SP 800-30)"* across 5x5, 4x4 and
3x3 columns, and the band thresholds were described as *"the 800-30 banding"*.

**The phrase "likelihood x impact" appears nowhere in SP 800-30 Rev. 1.** Neither does "multiply",
nor any numeric band threshold. What it actually provides is **Table I-2, a 5x5 lookup** —
*"Assessment Scale – Level of Risk (Combination of Likelihood and Impact)"* — returning one of five
qualitative levels.

**And the lookup does not agree with a product.** At Likelihood = Very High with Impact = Very Low,
Table I-2 returns **Very Low**; multiplying gives 5 x 1 = 5, which lands mid-scale in this tool. So
the model was not merely attributed by a different route to the same answer — it produces different
answers from the table it named.

Nothing about the engine changed: it stays in parity with the Cyber Aware Creations web engine, and
the self-test still passes 213/213. What changed is what it claims. The five rating labels **are**
800-30's qualitative scale; the multiplication, the numeric thresholds, the four bands
(low/medium/high/critical, against 800-30's five levels) and the 4- and 3-level label sets are the
CAC model. Now described as **800-30-informed, not 800-30-defined**.

This is the same correction `risk-register/SKILL.md` already makes about NISTIR 8286A r1 and risk
**wording** — *"NIST does not prescribe the template"*. That fix landed on the sentences and never
reached the arithmetic, which is the more consequential half.

### NIS2 Art. 20 held, and gained the detail that matters

*"Management bodies … approve the cybersecurity risk-management measures … oversee its
implementation and **can be held liable for infringements**."* Verbatim, plus Art. 20(2)'s training
obligation, which was missing. Made explicit: the liability attaches to the **management body, not
the CISO** — which is exactly the overclaim that section already exists to prevent, and it was one
careless sentence away from making it.

The standing refutation also holds: nothing in Art. 20 requires a CISO to document *why decisions
were appropriate*.

### AI 100-2 was already honest, and now says which edition

`nistaml-exposure.md` needed no correction — it already states that the class identifiers are the
tool's own labels, that no publication numbers its categories that way, and that nothing in the file
should be relied on as a citation without checking the source. That is the standard the rest of this
programme has been retrofitting. It now also names the current edition, **NIST AI 100-2 E2025**
(final, 24 March 2025), so a reader knows which document to open.

---

## v0.50.0 — 2026-08-08

**The NYDFS Part 500 family — an exception the regulation no longer permits.** Fourth family in
the verification programme. Source of record: the **Second Amendment to 23 NYCRR 500** (effective
1 November 2023) from dfs.ny.gov, with consolidated section text for provisions the amendment left
untouched.

### The defect: a compensating-controls route that was deleted

`exceptions.md` told a covered entity that *"where MFA **or encryption** is not implemented as
specified, a written approval of compensating controls is required."*

**The Second Amendment deleted the in-transit encryption route.** §500.15(a) now requires
encryption of nonpublic information *"both in transit over external networks and at rest"*, and
only §500.15(b) — **at rest** — keeps an infeasibility route with CISO written approval. The
deletion is visible as bracketed text in the amendment itself.

This lands worse in `exceptions-register` than anywhere else, because logging exactly this kind of
controlled exception is the skill's whole job. An in-transit encryption gap is **not a deviation to
record and compensate — it is non-compliance**, and it belongs in the §500.17 acknowledgment. All
three places that discussed it now say so.

### §500.12 carries a condition nobody had noticed

*"**If the covered entity has a CISO**, the CISO may approve in writing the use of reasonably
equivalent or more secure compensating controls."* An entity without a CISO has no
compensating-controls route under §500.12 at all — which is precisely the smaller covered entity
most likely to want one.

### Claims held, and two got sharper

**§500.9(b)** — *"The Risk Assessment shall be carried out in accordance with written policies and
procedures and shall be documented."* Verbatim. Better still, §500.9(b)(3) requires those policies
to describe how risks *"will be mitigated or **accepted**"* — the acceptance object this suite
records, named in the regulation itself. That is a stronger receipt than the file was using, and it
is now quoted.

**§500.17(b)** — the acknowledgment claim held and gained three details it had missing: it is an
**annual** filing for the prior calendar year, signed by the **highest-ranking executive *and* the
CISO** (two signatures, not one), and the **five-year retention attaches to the supporting
records**, not to the acknowledgment alone.

### The transitional periods are all expired, and now it says so

Verified from §500.22 as amended: §500.17 at 30 days, §500.15 at one year (1 Nov. 2024), §500.12 at
two years (**1 Nov. 2025**) from the 1 November 2023 effective date. Everything cited is fully in
force.

---

## v0.49.0 — 2026-08-08

**The DORA reference family — and the first engine defect the verification programme has found.**
Every family before this produced prose corrections. This one produced a wrong number on a
regulatory clock.

Sources of record, all from EUR-Lex: **Regulation (EU) 2022/2554** (CELEX 32022R2554),
**Commission Delegated Regulation (EU) 2024/1774** (32024R1774), and **Commission Delegated
Regulation (EU) 2025/301** (32025R0301) — the last being the RTS that actually sets the reporting
windows, and which this repo had never cited.

### The initial-notification clock produced a false overdue

`disclosure-clocks.md` said the initial window is the earlier of *classification + 4h* and
*awareness + 24h*, and added that *"an entity that classifies late does not thereby extend the
24-hour awareness cap."* The engine implemented that as an unconditional `min()`.

**Article 5(2) of RTS 2025/301 says the opposite, in terms:**

> Where the financial entity has not classified an ICT-related incident as major within 24 hours
> from the moment the financial entity has become aware […] but classifies that ICT-related
> incident as major at a later stage, the financial entity shall submit the initial notification
> within four hours from the classification.

So on a late-classified incident the engine computed a deadline **already in the past** and
reported **overdue** while four hours still remained. A false overdue is the single failure this
same file argues a clock must never produce, in its own words about the SEC half: it *"will
eventually push somebody into filing something they had not yet decided was true."*

Fixed, and proved: reverting the carve-out drops the self-test from **177 to 172**. The engine
now names the governing provision in the clock's note.

### The eval had already recorded the defect reaching a user

`trigger-prompts.md` records routing case `N6` reproducing the windows and drawing *"the
consequence the reference implies without stating: **a late classification buys no time**."* That
observation is left exactly as written, with a correction beneath it, because it is the most
useful entry in the file: **the reference asserted a rule, the model reasoned correctly from the
reference, and emitted a confident statement of law that was wrong.** Routing evals score that as
a pass — it matches the reference. Only reading the instrument catches it.

### The windows had no instrument behind them

The tables gave 4h / 24h / 72h / one month and cited nothing. The one place that did cite an
instrument named **2024/1774**, which is the ICT risk-management RTS and sets no reporting
deadline at all. All three windows are now cited to **RTS 2025/301, Art. 5**, made under DORA
Art. 19(4).

### The next-working-day allowance was described too generously

Stated as relief where a deadline *"falls outside working hours or on a weekend or public
holiday."* Article 5(4) gives it only for a **weekend day or bank holiday**, and only until
**noon of the next working day** — and Article 5(5) **withdraws it entirely** for the initial and
intermediate reports by credit institutions, CCPs, trading-venue operators, and entities
identified as essential or important under NIS2 Art. 3. Also added: Article 5(3)'s obligation to
tell the competent authority *before* a deadline passes, which the engine does not track.

### Nine claims held

Both Art. 3(d) quotations verbatim; Art. 3 is indeed *ICT risk management*; 2024/1774 in force
15 Jul. 2024 (twentieth day after 25.6.2024 publication); DORA applicable 17 Jan. 2025 (Art. 64);
the Art. 16 simplified-framework carve-out; the 72-hour and one-month windows; and the standing
instruction to cite the RTS rather than DORA Level 1 for the residual-risk inventory.

---

## v0.48.0 — 2026-08-08

**The SEC reference family, read against the adopting release.** First family after 8286 in the
reference-verification programme, taken first because it carries the highest consequence if
wrong: a tool that miscounts a disclosure deadline, or tells a registrant it may withhold
something the rule requires, is worse than no tool.

Source of record: the **Federal Register**, 88 FR 51896 (4 Aug. 2023), Release Nos. 33-11216;
34-97989, File No. S7-09-22 — the official publication of the final rule, downloaded and checked
locally. SEC.gov returns HTTP 403 to this environment; the Federal Register does not, and it is
the primary publication either way.

### Twelve claims held

The four-business-day deadline (*"An Item 1.05 Form 8-K must be filed within four business days
of determining an incident was material"*), the *"without unreasonable delay after discovery"*
determination standard (Instruction 1, verbatim), the Attorney-General delay, registrant-only
scope, Item 106(b)'s *"in sufficient detail for a reasonable investor to understand those
processes"* (verbatim), **board oversight sitting in 106(c) and not 106(b)**, the release
numbers, the Gerding statement of 14 Dec. 2023 and its quotation, the SolarWinds dismissal with
prejudice on 20 Nov. 2025, `17 C.F.R. § 229.106`, the 5:30 p.m. EDGAR cutoff, and the
rescission-pressure framing — which remains accurate: **the rule is still in force.** Repeal was
requested in comment letters responding to the SEC's January 2026 Regulation S-K review; it has
not happened.

### The technical-detail carve-out was stated too widely — in three files

Three files said Item 1.05 *"does not require technical detail **about the incident** or the
response"*. Instruction 4 says a registrant *"need not disclose specific or technical information
about its **planned response** to the incident or its **cybersecurity systems, related networks
and devices**, or **potential system vulnerabilities**"*.

**The incident is not in the carve-out.** Item 1.05(a) requires the material aspects of its
nature, scope and timing. The repo's phrasing pointed at withholding the one thing the rule
compels — the direction of error that matters in a disclosure tool, and the reason this family
went first.

### A second delay mechanism was missing entirely

`disclosure-clocks.md` described *"a limited national-security delay mechanism"*, singular. There
are two. **Item 1.05(d)** lets a registrant subject to the FCC breach rule (**47 CFR 64.2011**)
delay up to **seven business days** after the notification that rule requires. Both are now
documented, with the Attorney-General ladder stated concretely (30 + 30 + 60, then Commission
exemptive order only).

### An unverifiable date removed, and better identifiers put in

The receipts table said the rule was *"adopted 26 July 2023"*. That is the SEC open-meeting date,
carried on a press release this environment cannot reach, and it is absent from the Federal
Register metadata. Rather than keep a date that could not be checked, the row now carries what
was verified and is more useful for retrieval: the release numbers, the file number, **88 FR
51896**, the 5 Sep. 2023 effective date, and the exact pages of the adopted text — **51942** for
Item 106, **51945** for Item 1.05 and its Instructions.

Those page numbers were themselves wrong on first writing. The row initially read *51942–44*,
guessed from the document's span; computing the page markers gave 51945 for Item 1.05. Caught
before commit, in the pass about uncaught citations.

---

## v0.47.0 — 2026-08-08

**Every claim this repo makes about an IR 8286 document, read against the document.** v0.46.0
corrected the *dates* and one quotation; this reads the *contents*. Eleven claims checked, six
held, five were wrong — and one of the five was written in v0.46.0 by the pass that found the
others.

### Six held

- **8286A r1 §2.2 (Risk Identification)** prescribes four elements and no template — the
  load-bearing claim behind the CAC house format. Verified in v0.46.0 and re-confirmed here,
  including the section's title.
- **8286r1 Table 1** does describe a `Priority` element: *"A relative indicator of the criticality
  of this entry in the risk register."* (`schema.md`)
- **8286r1's own example is cause-and-effect prose**, not if-then: *"External malicious actor
  deploys a ransomware attack causing unavailability of financial systems."*
- **8286C r1 §4.2.3** does carry the aggregation sentence. The section is titled *"Reviewing
  Whether Constraints Are Overly Stringent"*, which reads unrelated — the number was doubted
  mid-pass and confirmed correct on a second look.
- **8286C r1's candour** about positive risk being *"a field of interest that is new to many
  readers"* is verbatim.
- **`GV.RM-07`'s "included in"** is verbatim from the bundled CSF 2.0 core.

### Five were wrong

**A second misquote, in the same file as v0.46.0's first.** `positive-risk.md` had 8286r1's
lifecycle step 2 as *"catalog positive and negative uncertainties"*. That string is nowhere in the
document. Step 2 is *"Identify the risks"*, and asks for *"the comprehensive set of positive and
negative risks (i.e., determining which events could enhance or impede objectives), including the
risks of failing to pursue an opportunity."* The step number was right; the quotation was invented.

**A misattribution where the word was real and the source was not.** Two files had IR 8286C r1
"tracking opportunity ***alongside*** threats", quoted. `alongside` appears twice in 8286C r1,
neither time about opportunity. It comes from **CSF 2.0 `GV.RM-07`'s own implementation example** —
*"Calculate, document, and prioritize positive risks alongside negative risks."* Re-attributed
rather than deleted: the argument was sound, the citation was pointing at the wrong document.

**An overstatement.** 8286A r1 was said to hold that opportunities *"warrant the same systematic
identification as threats"*. It says it *"primarily focuses on negative risks"*, that positive
risks *"should be documented and reviewed as well"*, and that they involve *"a similar process"*.
Similar is not the same, and the file that exists to stop the suite inflating a source does not
get an exemption from it.

**v0.46.0's own new error.** That release added a note saying 8286B and 8286D *"carry no `r1`"*.
True, and misleading in the same breath — they are **`NIST IR 8286B-upd1`** and
**`NIST IR 8286D-upd1`** (Update 1, 26 February 2025). "No `r1`" reads as *no version marker*.

**And so the `citations:` check was teaching it.** Its error message named `8286B` and `8286D` as
acceptable, and its matcher accepted them, on an assumption about shared markers that nobody had
checked. A bare `8286B` names the withdrawn 2022 edition exactly as a bare `8286` names the
withdrawn 2020 one. Both are now flagged; `8286B-upd1` and `8286D-upd1` pass. Self-test 46 → 49.

**Nothing else cites 8286B or 8286D**, so the corrected check has no live work to do — which is
the right time to fix a checker, rather than when it is wrong about something that matters.

---

## v0.46.0 — 2026-08-08

**The citations.** Two backlog items about references that named a source without identifying
it — and, found while checking them, three wrong statements about sources this suite quotes.

### The doctrine the board layer rests on had no citation (BL-63)

*Caremark*, *TSC Industries* and *Basic v. Levinson* were named across nine files with **no
reporter, no court and no year** — in the same file that cites its supporting cases to a full
standard. `NOTICE` promises references "with their stated limits intact"; the README calls them
"sourced regulatory receipts".

Every citation below was **verified against the reporter before it was written down**, not
reproduced from memory, and each against two independent sources:

| Case | Cite | Verified against |
|---|---|---|
| *In re Caremark Int'l Inc. Derivative Litig.* | 698 A.2d 959 (Del. Ch. 1996), C.A. No. 13670, Allen, Ch. | CourtListener; Penn Carey Law Delaware Corporation Law Resource Center |
| *Stone v. Ritter* | 911 A.2d 362 (Del. 2006), No. 93, 2006 | CourtListener, two independent queries |
| *TSC Indus., Inc. v. Northway, Inc.* | 426 U.S. 438 (1976), No. 74-1471 | CourtListener; Cornell LII |
| *Basic Inc. v. Levinson* | 485 U.S. 224 (1988), No. 86-279 | CourtListener; Cornell LII |

**Two substantive corrections came with them.** *Stone v. Ritter* is the operative modern
statement of the oversight standard, so **citing *Caremark* alone is incomplete** — it names the
doctrine without the standard a court applies. And ***Basic* is now cited for materiality only**:
its fraud-on-the-market presumption has been narrowed by later authority, and an unqualified cite
claims more than the case still carries.

**Two cases in the research dossier were deliberately not added.** *Marchand v. Barnhill* supports
a "mission critical" framing that appears nowhere in this repo. *Zuckerberg* would have required
asserting that *Sorenson* applied it — a claim about a case this pass did not read. Adding either
would have been the defect this item exists to fix, in a new place.

### Three wrong statements about NIST sources, found while fixing two strings (BL-114)

The item was two bare `NISTIR 8286` references in README.md and the Codex manifest. A third was
in `NOTICE`. Repointing them meant re-reading the standard, and the standard had moved.

**IR 8286 r1, 8286A r1 and 8286C r1 were finalised on 18 December 2025.** February 2025 was their
*initial public draft*, not the revision. Two places in this repo called them "the February 2025
revisions", and v0.43.0's release note said every 8286 reference now pointed at them. That note
was describing drafts. (8286B and 8286D are different: those *were* finalised
26 February 2025 and carry no `r1`.)

**`positive-risk.md` misquoted 8286C r1 and mis-attributed the quote.** It had NIST "describing
*a balanced approach to considering, measuring, and managing the uncertainty of all types in
pursuit of the enterprise mission*". The document says *"a **more** balanced approach … the
uncertainty of all types **of risk** in pursuit of the enterprise mission"* — two words dropped
from a quotation — and says it in a closing note that positive risk *"is a field of interest that
is new to many readers and merits further exploration"*, describing an aspiration **for the risk
community**, not the standard's own method. Replaced with a sentence that says what was meant and
is actually in the document: *"The IR 8286 series stresses the importance of recording and acting
upon positive risk."*

**The load-bearing §2.2 claim survived.** `risk-register/SKILL.md` says 8286A r1 §2.2 prescribes
four scenario elements and no template. Checked against the December final: *"cybersecurity risk
identification is composed of four necessary inputs — parts A through D … Combining these elements
into a risk scenario helps to provide the full context of a potential loss event."* Asset, threat,
vulnerability, impact; no template. It holds.

### `citations:` — a new check, because this is the third sweep

`check-versions.py` now fails any shipped file citing NISTIR 8286 without a part or revision.
v0.43.0 swept twenty references and announced the job done; three survived where the sweep did not
look. A sweep is an act, and this makes it a property.

The matcher is registered in the self-test in **both directions** — a citation pattern fails
silently either way, and one that reddens correct cites gets deleted. It allows *"the IR 8286
series"*, which is how NIST refers to the family in the sentence this repo now quotes.

Its first draft keyed on file extension and so **skipped `NOTICE` entirely** — the one file
holding a bare citation — while reporting success. Precisely the shape v0.45.0's GP-1.7 was
written for, one layer over. Self-test 36 → 46.

---

## v0.45.0 — 2026-08-08

**The guard machinery — four guards were provably blind, and the document defining the standard
disagreed with the standard.** Both are the same failure: something that surveys a set asserted
only that the set was non-empty.

### Four guards were not reading the file most likely to carry the defect (BL-97)

Every static half walks `scripts/*.py` and `renderers/*.py`, prints the count it read, and the
guard asserted that count was **at least one**. Five scan helpers excluded `renderers/_common.py`
alongside `cac_graphics.py`, under a comment that only ever justified the brand file.
`cac_graphics.py` is vendored byte-identical from `tools/` and guarded there. `_common.py` is
500 lines of board-visible prose — the placeholder, the caveat, the *Not legal advice* footer —
and is the likeliest place in a skill that somebody adds the sentence a guard forbids.

The scans read **three files of five** and said so truthfully, in a sentence whose only claim was
"not zero". Nothing caught it because **every registered mutation plants into `scripts/`**, so
the exclusion was never once exercised.

Mutation-tested before and after: planting each guard's own registered defect into its
`renderers/_common.py` **passed** `no-regime-dates`, `no-closed-state`, `no-ai-score` and
`no-vendor-score`. All four now fail it.

The backlog item named one guard. The same three-line exclusion appears in five helpers, so all
five are fixed — `attention-surface` has no `renderers/` directory yet, which makes its copy
latent rather than live, and a trap for the day it grows one.

### GP-1.7 — a scan asserts what it read, and the registry asserts what exists

The one-line fix would have been silent the next time somebody narrowed a glob, so it is now a
rule with a check behind it. Each guard recomputes the expected file list **from the filesystem**
and asserts the scan read all of it. The recomputation is in the guard, not the helper: a helper
that both narrows its glob and reports what it should have read proves nothing. Verified by
re-adding the exclusion and watching the guard go red — *"it read 3 of 4"*.

Second half of the same rule, applied to the document: `prove-guards.sh` now compares the
registry table in `guard-proof-standard.md` against the guards it discovers, and fails on either
mismatch.

### The guard-proof standard was two minors stale (BL-100)

`tools/guard-proof-standard.md` — the document CAC-GP-1 is *defined* in — said **"eight guards,
sixteen halves"** while the runner asserted 9 / 18, and `outcome-framing.sh` was missing from the
registry table entirely. `tools/README.md` carried two more wrong counts in a single paragraph,
including *"seven guards across three skills"*.

The counts are now **removed from the prose rather than corrected**. They live in
`EXPECTED_GUARDS` and `EXPECTED_HALVES`, which are asserted, and the run prints them. `Status: in
force as of v0.41.3` became `In force since: v0.41.3` — a version claiming currency rots, a
version marking a starting point does not.

The new registry check found the `outcome-framing.sh` omission on its first run, before the doc
was touched.

### CAC-LE-1 has a home (BL-100, second half)

`tools/lint-evals.py` shipped in v0.43.1 introducing a second maintainer standard, wired into CI,
documented nowhere. Now `tools/eval-lint-standard.md`, a sibling to the guard-proof standard
rather than a section inside it — the two answer different questions, and renaming the older file
would break every link into it. Cross-referenced both ways. BL-121's candidate second rule (a
captured probe whose emptiness is read as a verdict) has a place to land.

### An eval label claimed a property it did not test (BL-96)

`section-contract.sh` printed *"an opportunity is carried when it cites a declared goal"*. The
assertions are presence-only: `{"cites": "goal:g"}` accepted, `{}` and `{"cites": "   "}` refused.
Nothing resolves the reference — `goal:no-such-goal` is accepted today. Anyone auditing C-2 from
the green ticks was told the grounding rule was under test when only non-emptiness was.

The label now says what it asserts, and the gap is **pinned as an assertion** rather than left as
an absence: the suite now proves an unresolvable citation is accepted. Grounding it is BL-95; when
that lands, this assertion fails and the label has to be rewritten alongside it.

---

## v0.44.0 — 2026-08-08

**The risk-register write path — four defects around `response.cost`, and they were not
independent.** Fixing the cost without fixing the parser produces a register that still eats
typos, which is why these ship together.

### Unknown flags now fail (BL-104)

`risk-register` is the **one engine in the suite that does not use `argparse`**, and the one
with the most mutation commands. `parse_flags` collected an unrecognised key and every command
ignored it, so `init --currency GBP` exited 0 with a success message and wrote nothing, and
`--appetitie medium` produced a register that did not contain what its author believed.

**This was the root cause behind the currency defect being silent rather than loud.**

A full argparse conversion was deliberately **not** done — that rewrites twenty commands in one
change, in the skill where a mistake costs most, for a benefit strict rejection delivers alone.
Instead `parse_flags` takes an optional `known` set, four commands declare theirs, and
`_FLAGS_UNDECLARED` names the fourteen not yet converted. **That list is the point, not the
compromise**: the self-test asserts every command either declares its flags or is on it, prints
the count, and holds it under a ceiling that can only be lowered. A new command that does
neither fails the suite — seen to fail before it was believed.

### Currency is settable (BL-103)

`settings.currency` was documented at `SKILL.md:152` and settable by no command. `init` now
honours `--currency`, and `set-currency` is modelled line-for-line on `set-escalation`: requires
`--why`, refuses a no-op, appends one event. `settings-changed` was already in
`KNOWN_EVENT_TYPES` and already classified, so no vocabulary moved.

**It relabels and never converts.** The amounts are the numbers somebody entered; re-denominating
them would be the tool deciding what a figure means. The command says so when costs are present.

### A cost cannot be negative, and can be corrected (BL-105)

`response.cost` accepted a negative, printed it into the board's treatment total, and was
**write-once** — `SKILL.md` forbids hand-editing the store and no command touched the field, so
a typo was permanent. A negative reduces a board figure, which is the direction nobody audits.

`_cost_opt` refuses a negative, a bare flag and a non-integer, and **accepts `0`** — priced, and
the answer is nothing, which is a different statement from absent. `set-response` is the
correction path, appending `response-changed`, the other event that had no writer.

### A zero cost rendered as absent (BL-106)

`${r.response.cost ? … : ''}` is a **falsy** test, so the shipped example's `cost: 0` risk showed
no cost at all. Now an explicit numeric check.

**And the currency beside it was hardcoded `$`** — not in the plan, and reachable only because
currency became settable an hour earlier: a GBP register would have printed `$45,000`. The rule
this skill already states is that a total in the wrong currency is worse than one in none.

### SKILL.md lists every command (BL-115)

The file inventory named ten of twenty. It now names all twenty, grouped by what they do, and a
check compares the list against `COMMANDS`.

## v0.43.1 — 2026-08-08

**A release test against v0.43.0 found three defects, and two of them were in the tests.** The
v0.42 runtime blockers stayed fixed, all 2,962 counted checks ran, and CI was green — while a
board pack shipped without two of its charts and two suites reported passes they had not run.
The pattern in all three is the same one this repo keeps having to relearn: an absence that
looks exactly like a success.

### The blocker: the vendor and AI charts were built, then silently discarded

`_vendor_figures` and `_ai_figures` in `assemble_pack.py` returned bare `{label, value}` series
points where the chart contract expects a figure — `kind`, `title`, `source`, `series`.
`_figure` in `render_pack.py` dispatches on `kind` and returns an empty string for anything it
does not recognise, so seven of the specimen's sixteen chart objects rendered as nothing at
all. The pack carried nine figure captions for sixteen model entries, no vendor-criticality
figure and no AI-autonomy figure.

**It was silent, and that is the whole severity.** The headline numbers were untouched, so a
reader saw a plausible pack rather than an error, and the only way to notice was to count
captions against model entries by hand. That is what the release test did.

Both adapters now emit a figure. Both are `bar` rather than `band-mix`, deliberately: a
band-mix earns RAG colour because the producer declared its bands *as severities*, and neither
of these is one. Vendor criticality is a declared scale of how much depends on an arrangement,
and that register refuses to rate a vendor — colouring the segments red-through-green would put
the vendor score back on the page through the chart. AI autonomy is an ordered scale of what a
deployment may do without a person, and `acts` is not a red band. Criticality is drawn in the
order the producer declares its scale, with `untraced` and `unclassified` after it and never
sorted into it, because they are states and not levels. Autonomy draws its zero levels, because
`acts: 0` and `acts` missing from the chart are very different statements and only one of them
is true.

**And the assembler now refuses a figure that does not meet the contract**, naming it on the
provenance page instead of passing it to a renderer that will drop it. A named absence is
recoverable; this one was not.

### The two false greens

`skills/board-pack/evals/assembly.sh` ran its chart comparison in command substitution. The
comparison raised `KeyError: 'title'` on exactly the malformed objects above, the shell captured
an empty string, and empty is this suite's word for "no problems" — so it printed OK, counted
the check and exited zero. The defect the check was written to catch was in front of it and it
passed. Every captured probe now runs through a `probe` helper that reads the exit status and
turns a crash into a failure carrying the traceback.

`skills/risk-register/evals/board-safety.sh` gained an outcome-framing check written with
`ok`/`bad`. That suite declares `chk` and neither of the other two. Under `set -u` without
`set -e` — which is the house convention here, deliberately, so one failing check does not abort
the forty after it — an unrecognised command is a silent no-op: the shell wrote
`ok: command not found`, the failure counter stayed at zero, and the suite reported
`all checks passed`. The check is registered through `chk` now.

**`tools/lint-evals.py` (CAC-LE-1)** makes the second one a class rather than an incident: for
every `evals/*.sh`, a harness helper that is called must be declared by the suite calling it. It
runs in CI beside the guard proofs, for the same reason they do. Running it over the repo for
the first time found two false positives in its own logic before it found anything else, and
both are now self-test cases.

### Two checks that would have caught the blocker directly

Consistency is not presence. `assembly.sh` verified that the model and the page agreed, and they
did — about a pack with no third-party and no AI figure in it. It now also asserts that **every
section of the specimen contributes at least one figure**, as a set and not a count, and that
**no figure was rejected by the chart contract**. Both fail against the v0.43.0 code and pass
against this one.

### Board copy

- The positive-risk slide printed `cites goal:Close the Dublin authorisation year` — a tagged
  field written the way a machine reads it, on a board slide, and the citation was welded to the
  end of the sentence with a mid-dot that collided with the bullet glyph. The citation now takes
  its own muted line, which is what `.from { display:block }` had always done in the HTML, and
  the tag is spaced from its value. Only the separator is touched: the declared goal is the
  business's own words and is printed back unaltered.
- The exceptions figure read `Active records only. No closed records not shown.` A fixed tail
  collided with a substitution that was itself a negative, on the commonest case of all — a
  register with nothing closed. Both that note and the incident note beside it (same trap, not
  in the report only because the specimen happens to carry a closed incident) are now written as
  two independent clauses. The self-test asserted the literal `"not shown"`, which is why it
  passed over a double negative for as long as it existed; it now asserts the two cases apart
  and asserts against the double negative directly.

### Not in this release

The shipped specimen still carries 14 board asks against the toolkit's own five-ask convention,
and 40 slides. The tool warns about both, correctly, so it is an editorial pass on sidecar prose
rather than a defect — but it should be edited before the specimen becomes the flagship
marketing example.

---

## v0.43.0 — 2026-08-08

**A release-readiness test against v0.42.0 returned a no-go, and it was right.** Everything it
found is fixed here, together with the board-outcome work the same review recommended.

### The blocker: two of seven sections could not reach a page

`render_pack.py` assumed every escalation's `evidence` was a dict with a `detail` field. CAC-EL-1
fixes the six KEYS an escalation carries and deliberately not the TYPE of `evidence` — risk,
metrics and exceptions emit a structured delta because a band crossing is a movement and both
ends of it are the fact, while vendor and AI emit a finished sentence. A pack carrying either of
the newer sections assembled cleanly and then died in the HTML path, which runs first, so a
PowerPoint-only request was blocked by a deliverable it never asked for.

**The cause was one level further back, and it was the more useful finding.** The specimen
manifest demonstrated the five sections that existed when it was written, and it is also the
fixture every board-pack eval builds on — so nothing assembled `vendor` or `ai` from it. Behind
that sat four more defects nobody had a way to see: the renderer's `SECTION_TITLE` never gained
the two new sections, so five headings on both deliverables read as the bare key `vendor` and
`ai`; neither section stated the population its counts were drawn from; the escalation
provenance check covered four producers of six; and seven sections put the board deck's core at
23 slides. The specimen is seven sections now, and a new `mixed-evidence.sh` renders vendor-only,
AI-only and all-seven packs to both deliverables — the acceptance test the report asked for.

### The weekly example depended on where you were standing

`attention-surface` resolved relative source paths against the process working directory. Run
from its own `examples/` the shipped store read all seven producers; run from the repository
root it reported all seven NOT READ. The worst possible failure for this skill in particular:
reporting an unreadable source is its correct behaviour, so a page of NOT READ looks deliberate.
The feature that makes absence visible is what made the defect invisible. Paths now resolve from
the store.

### C-1 — the translation contract's own requirements, enforced

Every `board-safety.sh` in the suite tested for **absence** — no confidence vocabulary, no
reworded score. None tested for **presence**, so a sidecar reading *"Patch compliance fell to
88%."* passed every test in the repository: a named thing, no consequence, no ask.

A shared checker now asserts that every item sentence carries a consequence and every
`decisions[]` entry ends on a decision, wired into all nine board-safety suites. The vocabulary
is data. The floor is 80% **and always tolerates one miss**, because on a four-item section an
80% floor is a 100% gate wearing a percentage — and every rejection names its sentence, since a
rejection a reader cannot act on is one they will disable. Registered under CAC-GP-1 with one
mutation per half; 9 guards, 18 halves.

### C-2 — positive risk, grounded (`GV.RM-07`)

CSF 2.0 asks that *"strategic opportunities (i.e., positive risks) are characterized and are
included in organizational cybersecurity risk discussions."* The suite had no element for it.

Sidecars may now carry an `opportunities` array, additive within `contractVersion: 1`. **An
entry must cite a declared strategic goal or crown-jewel dependency from `business-context`, and
the assembler refuses one that does not** — refused, not warned. That single rule is what
separates positive risk from marketing copy, and it is enforced at the contract rather than only
in guidance. It renders as its own block in patina, never blended into a risk sentence and never
in RAG green; absence renders nothing at all, with no "none identified" placeholder to
manufacture pressure to fill. This was correct to omit until `business-context` shipped, because
until then there was nothing for an upside claim to cite.

### Citations

Every NISTIR 8286 reference now points at the February 2025 revisions, and the if-then
attribution is corrected. `risk-register` said *"8286 wants this if-then framing"*; 8286A r1 §2.2
prescribes a four-part scenario and no template, and 8286r1's own example is cause-and-effect
prose. If-then stays — a topic cannot be scored — as the CAC house format carrying 8286A r1's
scenario elements. Documentation only; no behaviour changed.

### The archetype layer — depth, never scope

The same A/B test that found the applicability objects byte-identical across a USD 5m and a USD
50bn organisation was **right to call that safe**: size does not create a legal obligation. It
also meant the toolkit had nothing to say about size, and size genuinely changes how much
assurance is proportionate.

`business-context archetype` now returns advice on seven dimensions — evidence depth, review
cadence, role separation, metrics breadth, third-party coverage, AI governance depth, board-pack
density — in its own `--context` payload key, never inside `applicability`. Absence asks **more**
(no size declared recommends the full depth, not the smallest), the higher of the two declared
bands wins, and an unrecognised headcount string contributes nothing rather than being coerced.

`archetype-advisory.sh` runs the release test's own A/B on every push, because "a small
organisation probably does not need the AI battery" is one plausible line away at any time and
would be an exemption nobody declared.

### Also

`render_context.py` no longer claims a "five-value enum"; the Codex short description names all
eleven skills; and both manifests gained thirteen vendor keywords, without which the one skill a
reader would search for as "TPRM" was unfindable.

**Not done, and named rather than quietly skipped:** the empty `screenshots` list in the Codex
manifest. Choosing what a listing shows is a design judgement about positioning, and inventing
one here would put binary assets in the repo that nobody had reviewed.

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
