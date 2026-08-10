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

## v0.86.0 — 2026-08-10

**The register says which word it uses and whose it is.** BL-54 **Phase 0 / R-7 only** —
vocabulary corrections. Documentation, plus one renderer caption.

This skill cites **two NIST documents that do not use the same words for the same things**, and
until now it used one vocabulary while citing both. Six corrections, each with the source's own
sentence:

- **`exposure` is IR 8286r1's word** for likelihood × impact — *"the combination of impact and
  likelihood is referred to as exposure."* **SP 800-30 Rev. 1, cited here for the rating labels,
  calls the same quantity *level of risk*.** Aliases in this tool; **not** aliases in general —
  800-30 Rev. 1 combines the two through Table I-2, a 5×5 **lookup**, and this tool multiplies.
  Same axis, different calculation.
- **`inherent` is a stage, not a permanent partner to `residual`** — *"On the first iteration…
  this may also be considered the initial assessment, whereas subsequent cycles refer to this as
  inherent."* A register on its first pass records an **initial** assessment, and calling it
  inherent asserts a before/after relationship that pass has not established.
- **`residual` here is always the ACTUAL residual.** 8286r1 also uses *target residual risk*;
  this register does not record one, so a reader arriving from the source does not read the
  field as an aspiration.
- **Band order ranks severity; it does not schedule work** — *"priority is not necessarily a
  reflection of the chronological order in which risk should be mitigated."* The register ranks,
  the plan sequences, and they may differ as long as somebody can say why.
- **`vulnerability` is wider than a scanner finding** — *a condition that enables a threat event
  to occur*, including planning gaps, training deficiencies, physical access and supply chain. A
  register reading it as *unpatched software* silently excludes every risk whose enabling
  condition is a process nobody owns.
- **The heat map ships with its caution, on the page** — NIST IR 8286B-upd1 asks that such a
  graphic be *"used with caution… not necessarily an indicator of rigid boundaries."* A heat
  map's persuasive power is that the boundaries look real: a risk one point either side of a
  threshold lands in a different colour. The board reads the picture, not a reference file, so
  the caption carries it.

⚠️ **The quotes are transcribed from the register-alignment design, not re-read against the
published text in this pass**, and the section numbers are the design's. `sources.json` declares
IR 8286B-upd1 with `checkedBy: unverified` and a `whyUnverified` saying exactly that — 52
declared sources, 2 unverified, neither gated. **The board-facing caption names the document and
not the section:** an unverified locator does not belong on an artifact a director forwards.

**Phase 0 ships alone, by the plan's own design.** `git diff --stat` touches **one** `.py` — the
heat-map caption in `render_board.py` — and no engine. Every suite unchanged and green.

## v0.85.0 — 2026-08-10

**Nine copies of the brand tokens, declared at one end and compared at none — and registering
them found drift already there.** BL-213, closing the registry's sole `UNCOMPARED` scope
question.

`nist-csf/renderers/_common.py` has said since it was written: *"change the brand tokens in one
and you must change them in the other."* Only it and `risk-register` named each other. **The
other seven named nothing**, and there are nine copies.

**Enumerating the tokens to register the twin found two real divergences, neither visible in
any test:**

- **`business-context` requested a Manrope weight its own stylesheet never used, and never
  requested the one it did.** It asked for `400;600;800` while using `font-weight: 700` three
  times — so every bold heading on a business-context page rendered as a browser-synthesised
  bold off the 600 face, while the same heading on a risk-register or nist-csf page rendered in
  the real 700. Two weights were downloaded and never used.
- **Eight of the nine were missing the `fonts.gstatic.com` preconnect** — the one that reaches
  where the font *files* live, rather than just the stylesheet.

Both pages render, both stylesheets are valid, and a browser silently approximates a face it
was not given. That is why this was worth registering before there was anything to find, and
why there was something to find anyway.

**Converged on the fuller form**, not the majority one: matching eight files by deleting a
correct resource hint from the ninth would be the checker dictating the product.

`tools/check-twins.py` gained a nine-member `constant` entry over `FONTS`, `INK`, `LIME`,
`PATINA`, `SLATE`, `WB`, `WB_SURF`, `WB_LINE`, under **hub naming** — nine members is
seventy-two all-pairs references, a list nobody maintains. A member may now name a **tuple** of
symbols, so a set of constants that travel together is one registry row rather than eight
near-identical ones; a token defined in eight copies and not the ninth **fails**, because that
is the drift rather than an excuse to compare the eight.

**Seen to fail before it passed**, as the item required: changing `LIME` in `policy-register`
turns `check-twins` red and names both values; reverting turns it green. A constant twin over
values that already agree would otherwise be exactly the vacuous assertion this repo forbids.

**The `UNCOMPARED` row stays and is narrowed** — from *"everything except the age_bounds pair"*
to *"the derivation layer and the CLI surface, deliberately"*. An exemption that names what it
does not cover is the feature; deleting the row would claim the whole module is compared.

`check-twins` 11 twins, **334 comparisons** (was 326), **57 cross-skill references classified**
(was 43). Every eval suite green; 98 files on 3.9.6.

## v0.84.0 — 2026-08-10

**Four decisions the receipts already rested on, and two that put a floor under *Bingle*.**
BL-172 and BL-143 — one editorial pass over the same file, as the dossier's own note asks.

**BL-172 — the two the file leaned on implicitly.** *United Food & Commercial Workers Union v.
Zuckerberg*, 262 A.3d 1034 (Del. 2021) is the universal three-part demand-futility test
**Sorenson applied** — a receipt that turns on a pleading standard and does not name it invites
a reader to think the case was decided on the merits. *Marchand v. Barnhill*, 212 A.3d 805 (Del.
2019) is the "mission critical" line, carried with its own limit: it is authority for what a
prong-one failure looks like, **not** for cybersecurity being mission critical at any particular
company — that is a fact about a business, and *Marchand* was about food safety at an ice-cream
manufacturer. An earlier pass considered *Marchand* and deliberately declined it; that call is
superseded by RW-001's finding that the claims already rest on it.

**BL-143 — and the disclaimer now has authority behind it.** The *Bingle* bullet says do not
cite it for the proposition that a minimal system is sufficient, a caution the file had to state
on its own. *Giuliano v. Grenfell-Gardner* (Teligent, Del. Ch., 2 Sep. 2025) largely **denied**
dismissal on prong one and named the specific failure: *"a board's reporting practice that
allows management to elect to report (or not) on central compliance risks fails Caremark's
baseline requirement."* *Brewer v. Turner* (Regions Financial, Del. Ch., 29 Sep. 2025) rejected
the information-systems theory and sustained the red-flags theory on a whistleblower complaint
discussed in board minutes.

**The corollary, and it cuts both ways.** Documented board-level process earns prong-one
protection **and is the discoverable record that can establish prong-two knowledge** — *Brewer*
is that in one case. Not an argument for recording less: an argument for a recorded *decision*
with a rationale rather than a note that something was mentioned. A minute saying the board was
told is prong-two evidence with no prong-one benefit.

**And the negative finding, which is the more useful one in a room.** There has been **no
Delaware oversight decision squarely about cybersecurity since the *Bingle* affirmance of 17 May
2023.** Vendor posts asserting Delaware has recently expanded cyber-oversight expectations could
not be corroborated to any case. If somebody cites recent Delaware cyber authority, ask which.

⚠️ **The provenance is NOT uniform, and the file says so beside the block.** *Zuckerberg* and
*Marchand* are landmarks carried at their reporter citations. The four 2024–2026 decisions come
from the RW-001 dossier **alone** and were **not independently corroborated** in this pass —
unlike the *Sorenson* and *Bingle* dates, which two separate source paths agreed on.
`sources.json` records the distinction rather than flattening it, and the receipts file tells a
reader to pull the primary text before quoting any of them.

## v0.83.1 — 2026-08-10

**A DORA note that stated a fact and its negation in one sentence.** BL-176, open across ten
releases and reported unchanged six times.

Both anchors recorded — aware `2026-07-01T08:00Z`, classified 36 hours later — and the engine
printed:

> `4 hours from classification as major; classification came more than 24h after awareness, so
> Art. 5(2) of RTS 2025/301 governs and the awareness cap no longer binds` **`(the other anchor
> is not recorded, so this bound is used alone)`**

**The arithmetic was right and the audit record was false.** In a skill whose whole premise is
that it records reasoning rather than emitting a verdict, the note *is* the deliverable — and
it is what counsel or a supervisor reads closely, precisely when it matters.

**Root cause: a proxy standing in for a fact.** The suffix was gated on `len(bounds) == 1`, and
one bound happens for two opposite reasons the count cannot tell apart — a **data gap**, where
the suffix is true, and Art. 5(2) **deliberately excluding** the awareness bound, where it is
false. v0.49.0 added the second case and never told the suffix about it. The condition is now
`not aware or not classified`: test the fact, not a proxy for it.

**Suppressed rather than reworded**, per the item's own D-2 lean: the clause immediately before
it already says the awareness cap no longer binds, so the sentence is complete without a
replacement.

**Asserted in both directions**, in the self-test *and* the eval, because a one-sided check
would pass an engine that stopped explaining anything: the Art. 5(2) note must name the
provision and must **not** claim a missing anchor, and a classification-only incident must
still carry the missing-anchor sentence — a fix that deletes a true explanation is not a fix.

**Open question 2 answered.** Every other `len(...) == 1` in the suite is grammatical agreement
— *"carries"* against *"carry"*, *"its"* against *"their"*. None describes *why*. This is the
second instance of the shape overall (BL-120 was the first) and there is no third.

`incident_analysis.py self-test` 198 → **201**; `disclosure-clock.sh` 38 → **39**. No deadline,
state or hours-remaining value changed — this is a text fix and the surrounding assertions
prove it.

## v0.83.0 — 2026-08-10

**The SP 800-30 misattribution v0.51.0 removed is gone from the two places it survived — and
nothing can put it back quietly.** BL-187.

v0.51.0 exists to separate what SP 800-30 Rev. 1 actually provides — five qualitative rating
labels and a 5×5 Table I-2 lookup — from CAC's own conventions: the multiplication, the numeric
thresholds, the 4- and 3-level scales. It corrected five surfaces and **missed two**, and only
one of the two was ever reported.

- **`export-findings`'s `note` field** — shipped, user-facing JSON, retained as evidence,
  handed to auditors, read by `risk-register`. It said scoring happens *"under SP 800-30"*.
  This is the one place a third party is most likely to read the claim.
- **`no-vendor-score.sh`'s own header** — *"scored once, there, under L×I and SP 800-30"*. The
  misattribution was sitting **inside the guard that protects the neighbouring boundary**, in
  the paragraph a maintainer reads to understand why the rule exists. **No release test ever
  named it.** It was found by grepping for the pattern rather than checking the one reported
  line, in the time a grep takes — which is the whole argument for a scan rather than a fix.

**`check-versions.py` gained `check_sp80030_attribution`.** It fails any shipped file that puts
`SP 800-30` on the same line as scoring, arithmetic, banding or thresholds. Seven self-test
cases pin it, including **both real defect strings as rejections**.

A line may still NAME the misattribution in order to correct it — same reasoning as
`do-not-cite.json`'s markers: banning the string outright would ban the correction, and a repo
that cannot write down its own error stops writing them down. The marker is **possessive on
purpose** — `this tool's own`, `CAC's own` — because a bare `own` would launder
*"SP 800-30's own thresholds"*, which is the misattribution itself. That case is pinned too.

The engine's own self-test asserts the note as well: the scan is the net that catches the next
author explaining the bridge in their own words; the local check fails in the skill that owns
the string, and tells a reader of that file the sentence is load-bearing.

`vendor_register.py self-test` 236 → **238**; `check-versions.py --self-test` 61 → **68**;
`sp-800-30: 326 shipped files, nothing attributes scoring or banding to it`.

## v0.82.0 — 2026-08-10

**Seven `--context` consumers, one contract.** BL-226 T3, unblocked by both decisions being on
the ⚖️ record.

They held three different contracts, and each divergence was a real disagreement about what a
CAC-AP-1 consumer owes rather than a bug — which is why this waited for a decision instead of
being improvised. Measured by execution, not by reading:

| input | before | now |
|---|---|---|
| no `contractVersion` | `vendor-register` **accepted** | all seven refuse |
| no decided `applicability` | `vendor-register` and `ai-register` **accepted** | all seven refuse |
| a raw `.biz` store | **five accepted it** — the transport §2.6 forbids | all seven refuse, naming `business_context.py export` |

**Order is load-bearing in one place.** The `.biz` clause runs **before** the contract clause,
because a raw store carries no `contractVersion` and answering it with the generic contract
message would throw away the one sentence that tells the reader what to run. A refusal that
names no command turns a five-second correction into a support question.

**Exit codes converge on 1.** A refusal is the tool *working* — it read the input, understood
it and declined — and `2` is argparse's usage-error code, which several of these engines return
when no subcommand is given. Returning it for a refusal made a well-formed refusal
indistinguishable from a mistyped command line to anything scripting the suite. BL-218 Q1 named
`ai-register` and `vendor-register`; **`attention-surface` was a third, found by measuring
rather than by reading the item.**

**`tools/engine-standard.md` — CAC-EN-1**, beside the eval-lint and guard-proof standards, and
cross-linked from both. It states the exit-code convention (§1.1) and the strict `--context`
contract in the order it must be applied (§1.2), and it exists because neither divergence was a
bug in any one engine: both were the absence of a stated convention.

**The test that it landed: the three rows held OUT of the CAC-TW-1 refusal corpus moved INTO
it.** They were excluded while the copies disagreed, with the reason written into the registry
entry rather than the rows silently missing. The corpus grew by exactly what converged —
**305 → 326 comparisons**, three payloads × seven members — which is how the convergence is
checked rather than asserted.

Two fixtures gained a decided `applicability`, which is the change reaching a user: the shipped
`ai-register/examples/example-context.json` and one eval payload. Both were hand-written
minimal fixtures that a real `business_context.py export` would never have produced.

All 59 eval suites green; eleven engine self-tests unchanged.

## v0.81.0 — 2026-08-10

**The check the v0.44.0 release note said shipped, actually shipped.** BL-192, and it found
nine more commands than the item did.

That note claimed BL-115's fix came *"with a check that compares the list against `COMMANDS`"*.
**It did not.** Grepping every `.py`, `.sh` and `.md` found one consumer of any engine's
`COMMANDS` outside its own file, belonging to a different skill for a different purpose.
`SKILL.md` was careful where the note was not — *"can be checked against `COMMANDS` rather than
trusted"*. For a repo whose Gate 1 is *nothing shipped contradicts what the docs say it does*,
a release note announcing a guard nobody wrote is the defect in the document a reader trusts
most about what changed. The v0.44.0 entry now carries that correction, appended and visible.

**And the missing check is what would have caught the next one.** Within nine releases
`import-findings` — a real command, with a handler, named in `SKILL.md` — was absent from the
docstring `--help` prints. BL-115's defect, one surface over.

`tools/check-commands.py` (**CAC-CD-1**) asserts two different things, because there are two
different defects:

- **Help drift** — a command `--help` does not list. Only reachable in the three engines whose
  `main()` does `print(__doc__)`, because their help is prose somebody maintains. Two of the
  three were affected: `import-findings` and nist-csf's `crosswalk`. The nine argparse engines
  generate help from `add_parser` and **cannot** drift, and the checker says so per engine
  rather than pretending to have tested it.
- **Doc drift** — a command no shipped document names. Nine of them, across two skills.
  `vendor-register` was worst at six, **including `init`**, without which there is no register.

**Zero exemptions.** The check landed red and every command was documented, in one change — an
exemption list nobody must clear is how this drifted in the first place.

**Q1 decided: `SKILL.md` *and* `references/*.md` both count.** The question is *can a reader of
the shipped docs discover this command*, and a `references/` page is shipped documentation the
index points at. Counting `SKILL.md` alone would force a command documented in depth elsewhere
to be duplicated into the index to satisfy a checker — the tool dictating where prose lives.

Anti-vacuity is the point rather than a detail: an engine parsed to **zero** commands fails, an
engine named in the registry but absent from disk fails, and an empty registry fails. A checker
that reports success without having tested anything is precisely what is being fixed here, and
it is the failure that survives longest because it looks identical to working.

`check-commands --self-test` **10/10**; live: **12 engines, 128 commands**, each named in the
help surface and in a shipped document. Both new steps named individually in `evals.yml`.

## v0.80.0 — 2026-08-10

**Completeness counts against the framework, not against the store.** BL-109, and the widest
half of it was not in the title.

A Subcategory the Core has and the store does not simply **left the denominator**. So a Profile
missing rows reported complete coverage of a framework it no longer fully covered — exit 0, no
note, and the percentage reaches a board page. The opposite direction was always loud: an
assessment for a Subcategory the Core *removed* fails validation by name. The register was
strict about extra rows and silent about missing ones, which is the wrong way round.

**A missing row is UNASSESSED, never out of scope.** Out of scope is a declaration somebody
makes; absence is a declaration nobody made, and reading it as `notApplicable` would let a store
shrink its own denominator by deleting rows. Missing rows now count into `total` and `inScope`,
and `notInStore` reports how many there are. `byCategory` iterates the Core too, so a Category
the store never touched appears as fully unassessed instead of vanishing from the dashboard.

**Which data produced this Profile is now recorded and compared.**

- `profile.coreRef` — `{version, sha256}`, stamped by `save_store` on **every** write, in one
  place so a command added later cannot forget it. The identity is the export's hash, following
  BL-75: a date says when somebody downloaded a file, a hash says which file.
- `analyze` and `overlay list` emit `provenanceNotes`. `overlay list` printed the shipped
  dataset version and the in-force one **on adjacent lines and never compared them** — the
  cheapest place to notice, and the place it was not noticed.
- **Notes, never refusals.** A provenance mismatch is a fact about the data, not an invalid
  store; refusing would strand a CISO mid-assessment the day a dataset or Core moves, which is
  the BL-169 D-2 failure this repo declines everywhere else. Absent means *not recorded*, which
  is its own sentence and never agreement.

**And two shipped sentences were false.** `schema.md` and `cyber-ai-overlay.md` both said the
dataset version *"is stamped into snapshots"* — it was not; a snapshot's keys were exactly
`id, label, ts, note, assessments, actionItems, rollups`. Both also said stores *"keep reporting
that version until re-analyzed"*, which is **backwards**: analysis reports the shipped version
immediately and the stale stamp is what survives. Of the two ways to end a false claim, the
first is now **made true** — snapshots carry `datasetVersion` and `coreRef`, because a stored
report a board reads months later that cannot say what produced it is this item's own subject,
frozen. The second is corrected in place, with the error left visible.

`profile_analysis.py self-test` 656 → **667**. Every other engine, every eval suite,
`check-twins`, `check-sources` and the 3.9 floor unchanged.

## v0.79.1 — 2026-08-10

**The toolkit stops citing a publication NIST withdrew a year ago.** BL-224 T2 and T6 — the two
tasks that need no interpretation. T1 and T3–T7 need SP 800-63B-4 read against the surrounding
prose and are deliberately not here.

SP 800-63B was **withdrawn 2025-08-01**, superseded by SP 800-63B-4. The toolkit cited it for a
year and **both safety mechanisms stayed green**: `do-not-cite.json` had no entry and
`sources.json` had no row, so neither was broken and both were blind the same way. That is the
finding, and it is why the fix is the two mechanisms rather than the two strings.

- **`sp-800-63b-pre-r4` is now watched** in `do-not-cite.json` — nine entries. Its `mustFlag` /
  `mustNotFlag` fixtures execute on every run: a bare `SP 800-63B` **fails**, `SP 800-63B-4`
  does not over-match. Verified end to end against a probe tree, including the case the BL-201
  binding rule exists for — a withdrawal marker in a *different sentence* does not launder the
  citation.
- **The `sp-800-63b` row's `usedFor` now names both files**, not one. `evals/trigger-prompts.md`
  carried the second citation and the manifest could not see it.
- **Both citations state the withdrawal beside them** — the same line, the same clause, which is
  what CAC-RW-1.9.1 requires.

⚠️ **Neither citation is repointed to `-4`, deliberately.** Revision 4 moved the volume
boundaries, so a claim that lived in 800-63B in 2017 may now sit in 800-63A or the base 800-63.
Repointing without reading is a new error dressed as a fix, and both files now say so in the
product rather than only on the backlog item. The retitle is recorded in the registry entry too:
*Authentication and Lifecycle Management* became *Authentication and Authenticator Management*.

`check-sources` 343 files, **9** withdrawn publications watched, none cited as current; self-test
102 checks.

## v0.79.0 — 2026-08-10

**One vendored CPRT export, pinned by hash, checked on every run.** BL-75.

There were two. `tools/csf-2.0.xlsx` is pinned in `nist-csf-2.0-core.json` and was the file the
shipped Core was built from. `tools/crosswalks/_source_csf2.xlsx` was **not** pinned — its
provenance was a date, `RETRIEVED="2026-07-29"`, and it was the file the shipped crosswalks were
actually built from. Their bytes differed and `tools/README.md` asserted that the vendored XLSX
was *"provably the file the shipped Core was built from"* — true of the copy it named, and
silently untrue of the other.

**What they actually were, measured member by member:** the same CPRT release downloaded
fourteen days apart. 16 zip members, **14 byte-identical**; the two that differed were
`docProps/core.xml`'s created timestamp (2026-07-15 against 2026-07-29) and a time value on the
cover sheet. `sharedStrings.xml` and the data sheet matched exactly — and regenerating the
crosswalks from the pinned copy changed **every edge and every control not at all**, only the
provenance stamp. That is the good outcome, and it was not knowable without checking.

So the fix is a deletion, not a second pin.

- **`author_catalogs.py` reads `../csf-2.0.xlsx`** — the same export the Core does — and
  **refuses to run** if its hash is not the one the Core records. The build can no longer
  author crosswalks from a file the Core was not built from.
- **`retrievedAt` is replaced by `sha256`** in all six shipped crosswalk JSONs, matching what
  `nist-csf-2.0-core.json` has always carried. *A date says when somebody downloaded a file; a
  hash says which file* — and this item exists because two exports made the same claim about
  their origin and had different bytes.
- **`tools/crosswalks/_source_csf2.xlsx` is deleted.**
- **`check-versions.py` gained `check_source_pin`**, which runs in CI on every push and PR
  already. Three claims, each of which failed silently before: the export hashes to the Core's
  pin, every crosswalk stamps that hash, and there is **exactly one** `.xlsx` under `tools/`.
  The third is what stops a helpful re-download undoing this; a second file with a plausible
  name is how it arose. An empty match fails rather than passing vacuously.

`check-versions.py --self-test` 56 → **61**, with a case per failure mode including a crosswalk
still stamping a date. Crosswalk data unchanged: 731 · 62 · 329 edges, `validate_crosswalks`
3 catalogs / 0 errors / 0 warnings, `crosswalk-e2e` 39.

## v0.78.0 — 2026-08-10

**A risk is an event, and now the engine says so.** BL-81.

`SKILL.md`'s first named precondition — *risks are written as events, not topics* — has been
documented since v0.1 and enforced by nothing. `add --title "Phishing" --il 4 --ii 4 --rl 3
--ri 3` wrote `"description": ""`, and that one-word noun was scored, banded, counted in the
band mix and eligible for board views. The only trace was a muted *"No event statement
recorded."* on the rendered page, produced long after the number existed.

**It was worse than an omission.** Both import paths mark their rows `provisionalTitle` exactly
so raw CSF wording stays out of board views until a person rewords it. `add` set no such flag.
So the register held an imported control objective back and let a hand-typed noun straight
through — the opposite of the risk profile anyone would choose.

- **`add` refuses without `--description`**, and the refusal names the flag, says why a topic
  cannot be scored, and shows the house format. Nothing is written.
- **`set-score` refuses to re-score a risk that has none.** Refusals guard writes, never loads:
  a register written before this release still opens and renders unchanged, and refuses on the
  next write that revises the number — which is the same defect arriving a release later,
  through the one command whose whole purpose is to revise the number.
- **The shape is never validated.** No regex, no `startswith("If")`, no minimum length.
  Requiring the field is a record requirement; judging whether a human's sentence is a *good*
  risk statement is the tool deciding something a person should, and it would reject legitimate
  phrasings while passing anything from someone who worked out the rule. A wilfully unshaped
  but present statement is asserted to be **accepted**, so that limit is checked rather than
  remembered.

**The `set-score` refusal is gated on `provisionalTitle`, and that gate is load-bearing.** An
imported CSF gap has no description *by design*, and the sanctioned order is `set-score` to
assess, then `set-text` to reword. An unconditional refusal would have deadlocked the
register's main intake at its first step — the mechanism BL-81's own plan says must not break.
The guard proves the import path still works, so a version that refused everything cannot pass.

- `event-statement.sh` — NEW guard, 8 checks, halves `add` · `rescore`
- `score_register.py self-test` 216 → **225**; `confirmation-age.sh` 83, fixtures updated
- `prove-guards` **39 guards, 73 halves**, 96 of 384 proved (floor 91 → 96)

Two things the item named as *raise, do not fold in* are filed in ⚖️ Open Decisions as
**BL-81 D-4 / Q2**: whether `add` should also require `--why`, and whether a hand-added risk
should be gated by `provisionalTitle` the way an imported one is.

## v0.77.0 — 2026-08-10

**The last two board-safety suites read the engine.** BL-221, and with it GP-1.7 is complete
across all ten.

`ai-register` and `vendor-register` scanned their source through a shell glob —
`renderers/render_*.py` plus `renderers/_common.py` — so they reached **every renderer and no
engine script at all**, while `ai_register.py` and `vendor_register.py` write most of the
strings those renderers print. Both now recompute the population from the tree through a new
`_vocab.py --tree` mode, and each registers a `create` mutation landing in **`scripts/`**,
because a mutation in `renderers/` is one the old glob already covered and would prove nothing.

**The suites assert the population, not the count.** `scanned == len(files)` is true of any
list, including one with no engine in it — which was the state being fixed. The scan prints
`POPULATION:` and the suite checks the engine is in it.

Two things this conversion needed that the other eight did not:

- **A `self_test` exemption, by line span.** An assertion that a word is ABSENT has to name the
  word. `no key or value describes a class as mitigated, resolved, closed or accepted` is a
  self-test's own failure message; flagging it puts the check that forbids the vocabulary and
  the check that proves the forbidding works in direct contradiction. `nist-csf` has done it
  this way since v0.69.0. It removed the entire assertion population — and with it a `resolved`
  that was only ever the negation *"Controls are recorded, never resolved."*
- **An `UNDECIDED` map, which is new.** Three hits survive and none is a defect: two are
  NISTAML.01's own description of an attack class (*an attacker degrading the service* — the
  attacker's certainty, not ours), and one per skill is `FINDING_SCORING_KEYS`, a tuple of keys
  the engine **refuses**, where the word is present in order to be banned.

**Those three are allowed and ANNOUNCED, not excluded.** BL-221 D-3 says their disposition —
narrow the stems, move the class descriptions into data, or accept them — is a judgement about
product language to be raised rather than improvised. So each is printed on every run with its
reason, and an entry whose hit no longer occurs **fails**, exactly as an orphaned `EXCLUDE`
does. An exclusion is a decision; this is a decision that has not been made, kept visible until
it is. Filed in ⚖️ Open Decisions.

- `board-safety (ai-register)` 20 → **22 checks**, `(vendor-register)` 15 → **17**
- `prove-guards` 38 guards, **71 halves** (was 69), **91 of 376** proved (floor 89 → 91)
- `tools/guard-proof-standard.md` GP-1.7 no longer names a remainder

## v0.76.0 — 2026-08-10

**`--context <a directory>` was a raw traceback out of all seven consumers, and they agreed
about it perfectly.** BL-226 T1, T2 and T4.

`except FileNotFoundError` does not catch `IsADirectoryError`. So `--context .` or
`--context ~/ctx/` — an ordinary typo, and what a tab-completed path produces — came out of
`risk-register`, `nist-csf`, `metrics-register`, `exceptions-register`, `incident-materiality`,
`vendor-register` and `ai-register` alike as a Python traceback. It is the same BL-169 D-1
failure BL-218 was raised for, one exception class along. All seven now catch `OSError` after
`FileNotFoundError`, so a missing file keeps its own sentence and a directory, an unreadable
file or a symlink to nowhere get a phrased refusal.

**And the guard that should have caught it was structurally unable to.** CAC-TW-1's `refusal`
kind compares members to member zero, and all seven crashed **identically** — perfect
agreement, every copy wrong. That is exactly the hole the `atomic` kind opened `expect` for in
v0.71.0, and it gets the same answer: **every payload in a `refusal` corpus now states its
expected outcome**, and both checks run — the members must agree with each other *and* with the
contract. A payload with no stated outcome is a failure, not a comparison.

The self-test carries the proof in both directions: two copies crashing identically on a
directory now **fail**, and pass only once both catch it.

- seven `load_context` copies · `tools/check-twins.py` — the `AS_DIRECTORY` payload sentinel,
  the stated-outcome contract, four new self-test cases (30 → **34**)
- `check-twins` **305 comparisons** (was 293); `vendor_register` self-test 235 → **236**

**T3 is not here, and that is deliberate.** Three of the four disagreements the item measured
are genuine disagreements about what a CAC-AP-1 consumer owes — whether a raw `.biz`, an absent
`contractVersion` and an absent `applicability` must be refused — and converging them changes
what payloads two shipped engines accept. With the exit-code split (2 for two engines, 1 for
four), that is a decision rather than a fix, filed in ⚖️ Open Decisions as **BL-226 Q1/Q2**
rather than improvised here. Those rows stay out of the twin corpus with the reason written
into the registry entry, not silently absent.

## v0.75.1 — 2026-08-10

**The *Bingle* affirmance is an order, not an opinion — and the manifest now says which paths
checked these dates.** BL-142, closed on its remaining half.

The two Delaware dates this item was raised for were corrected in v0.54.0, and the item's brief
described a repo nine releases old. Three things it named were **not** done, and RW-001's
findings F6/F7/F10 make all three checkable.

- **The affirmance is a Supreme Court ORDER adopting the Chancery court's reasoning, not a
  signed opinion with independent analysis.** The receipt said only *"affirmed"* — not wrong,
  and not enough: an order and an opinion carry different weight, and counsel hears the
  difference. It now says so, quotes the order's own words, and names the **Final Order and
  Judgment of 13 October 2022** that the affirmance also affirms. Citing only the memorandum
  opinion was incomplete on the affirmance's own terms.
- **A material condition of the *Bingle* holding was missing:** the claim failed partly because
  plaintiffs did not allege violations of specific laws or regulations. A case where such
  violations *were* pleaded is not this case, and a receipt that omits that invites the wrong
  comparison.
- **Gerding is attributed to the *then*-Director.** He left the post in December 2024 (SEC PR
  2024-200); Jim Moloney has held it since October 2025 (PR 2025-115). The statement is still
  published and the quote is still accurate — the title is what went stale.

**And the manifest row stops overclaiming.** `checkedBy: "claude-code"` is defined as
*machine-verified against the primary source*. Two independent paths reached these dates — the
RW-001 dossier's primary-source pass, and authoritative secondary reporting — and **neither
opened a slip opinion**. The row now says exactly that, alongside the citator gap it already
recorded. *Do not claim more than was done*, applied to the field that was doing the claiming.

*Cite* Basic *for materiality only* was already carried in `materiality-factors.md`, and
`regulatory-receipts.md` does not cite *Basic* at all — checked, not assumed.

## v0.75.0 — 2026-08-10

**The SEC posture sentences now carry the dossier's own words, in all five places, plus the
SolarWinds limit and the origin of the error.** BL-141, finished properly.

v0.73.0 dated these claims but shipped **my wording**, because `research/refwatch-dossier-sec-posture-2026-08-08.md`
could not be found — it lives in a Claude Project the build sessions cannot read (BL-227). The
text has since been supplied. Every location now carries **findings F1 and F3 verbatim**, quoted
as blockquotes rather than paraphrased, because a paraphrase of a posture claim is exactly how
the undated original got here. The facts are unchanged from v0.73.0; the words are now the
approved ones and are visibly a quotation, which is checkable in a way a paraphrase is not.

- `incident-materiality/references/disclosure-clocks.md`, `references/materiality-factors.md`,
  `SKILL.md`, and `ciso-board-translation/references/regulatory-receipts.md` in two places

**F5 — the SolarWinds limit, which v0.73.0 did not touch.** `regulatory-receipts.md` said to
cite the matter *"never as standing precedent"*. That is imprecise in the direction that matters:
the voluntary dismissal ended the case but **did not vacate Judge Engelmayer's 2024-07-18
opinion**, which remains a published district-court decision on which cybersecurity statements
are actionable. F5's replacement wording lands verbatim, including the personal exposure a named
CISO carried for roughly two years — the part a board actually reacts to.

**And the v0.48.0 entry now says where the claim came from.** RW-001 finding F2: on 12 June 2025
the SEC withdrew fourteen pending rule **proposals** (Release 33-11377), two of them cyber —
S7-04-22 and S7-06-23. **Neither was ever adopted and neither was ever in force; the
public-company rules were untouched.** Reading *"SEC withdraws cybersecurity rules"* without
checking which rules is how that became a rescission-pressure claim about Items 1.05 and 106.
Recorded rather than quietly fixed: the mechanism — right headline, wrong instrument — is
reusable, and the next instance will not look like this one.

One claim from the item page is still **deliberately not shipped**: that the items are *"being
filed under in 2026"*. It rests on EDGAR counts BL-130's own method notes record as phrase-match
and directional only, and F1's verbatim text does not make it either.

## v0.74.0 — 2026-08-10

**A crown jewel's criticality carries its own basis — and two shapes live on disk permanently,
on purpose.** BL-216 R-3 phase 3, the last phase of R-3, unblocked by Q-2 being answered.

`--criticality` now requires `--criticality-basis` and is stored through `declared()`, matching
`sensitivity` since v0.68.2. No scale is validated here — this skill does not own one — so the
basis is the only thing a reader can follow back to who ranked a system where, and this level is
the top of a walk that ends on a board page.

**What was decided, and against what.** `schemaVersion` was **not** bumped, there is no
converter, and no store is ever refused. A `.biz` written before this release keeps its bare
string; one written after holds a record; both are legal indefinitely. The cleaner alternative —
bump and refuse the old shape — is better engineering and worse product: BL-169 D-2 requires
that stopping part-way leaves a loadable store, and a toolkit arguing *your records persist and
stay defensible* cannot ship a read that refuses a CISO's existing file. It is affordable only
because v0.68.1 had already collapsed four inline reads into one `declared_criticality()` per
consuming skill, so the polymorphism costs two lines instead of a migration.

**The new guard defends against a tidy-up, not against a bug.** Two shapes read as an
inconsistency and the obvious fix is to force one. Both directions are plausible and both are
silent — forcing the record breaks every store written to date, forcing the string discards the
basis — so `criticality-shapes.sh` carries one half per direction and the two registered
mutations *are* those two edits. It runs across both consuming engines, and CAC-TW-1's corpus
gained the record shapes so `vendor-register` and `ai-register` cannot diverge on them.

`example-org.biz` deliberately stays on the bare-string shape: it is now the suite's only
end-to-end exercise of a pre-v0.74.0 store, which is the estate this decision exists to protect.

- `business_context.py` — `--criticality-basis`, refusals in both directions, `declared()`
  storage. Self-test **216 → 221**, including a legacy store round-tripping unconverted
- `vendor_register.py` / `ai_register.py` — `declared_criticality()` reads both shapes; a
  container that is not a declared record still refuses, and so does `{"value": {...}}`.
  Self-tests **229 → 235** and **158 → 164**
- `render_context.py` — reads both shapes, and shows criticality's basis beside sensitivity's
- `criticality-shapes.sh` — NEW guard, 8 checks, halves `bare` · `record`
- `check-twins.py` — **293 comparisons** (was 281); `prove-guards` **38 guards, 69 halves**,
  89 of 372 proved
- `schema.md`, `applicability-contract.md`, `SKILL.md` and three docstrings state the two
  shapes as a choice. That is task 3d, and it is the one that gets skipped: undocumented, the
  next reader "fixes" the asymmetry by forcing one shape

## v0.73.0 — 2026-08-10

**The citation batch: one overstated claim in four files, one edition that lived only in prose,
and one stale item that turned out to be already fixed.**

### The SEC posture sentence was overstated, and undated (BL-141)

Four shipped files said, in one form or another, that the SEC cyber rules *"have faced rescission
pressure and a materially reduced enforcement posture"*. No date anywhere. **Both halves were
overstated.**

The rescission half is **one petition** — SEC File No. **4-856**, filed **22 May 2025** by five
financial trade associations, seeking to rescind Item 1.05 and the Form 6-K counterpart. A
petition is not a proposal and not a rule; the Commission has not acted on it; Items 1.05 and 106
are textually unchanged.

The enforcement half stated a posture **the Commission has never stated**. What is true is that
activity has visibly slowed and that the SolarWinds action was dismissed with prejudice on
**20 November 2025**. **Litigation Release No. 26423** records, in the same document, that the
dismissal *"does not necessarily reflect the Commission's position on any other case"* — and the
Enforcement Division's Cyber and Emerging Technologies Unit, announced **20 February 2025**, lists
*"public issuer fraudulent disclosure relating to cybersecurity"* among its stated priorities.
Reduced observed activity is not a policy change, and the product no longer reports one as if it
were.

All four now carry the dates: `incident-materiality/references/disclosure-clocks.md`,
`references/materiality-factors.md`, `incident-materiality/SKILL.md`, and
`ciso-board-translation/references/regulatory-receipts.md` in two places. The operational
conclusion is unchanged — a preparedness and defensibility tool, never an imminent-enforcement
one — and it now also refuses the opposite error, *"the rule is going away"*.

**The v0.48.0 entry is corrected in place, and the error left visible.** That sweep listed the
rescission framing among *twelve claims held*. It had checked whether the rule was still in
force, which it is, while the claim on the page said something else. A sweep that checks a
narrower question than the claim makes will report the claim as held.

**Two instruments the product now names are declared** (CAC-RW-1): the petition and Litigation
Release 26423, in both skills that cite them. The petition row is gated at **180 days** with an
`intervalBecause`, because the sentence it supports is a claim that the Commission *has not
acted* — a negative about a live docket, which stops being true without warning.

### `AI 100-2 E2025` is pinned in shipped code (BL-161)

The edition lived in `references/nistaml-exposure.md` and `sources.json` and nowhere in the
engine: `ai_register.py` said bare *"AI 100-2"* twice, and `SKILL.md` named no edition at all. The
`ai-100-2` manifest row listed only the reference file under `usedFor`, so **the release gate did
not watch the engine's own citation** — the next edition bump would have updated the prose and
silently left the code behind. Both mentions now say `E2025`, `SKILL.md` names it, and
`scripts/ai_register.py` is under the row. That omission was an instance of BL-190.

### BL-142 was already fixed, and the item was stale

Both Delaware decision dates — *Sorenson* at **5 October 2021** and *Bingle* at **6 September
2022** — were corrected in **v0.54.0**, along with the authoring judges. The item's evidence was
recorded against v0.52.1 and never re-measured. Nothing to change: the dates are right, the
affirmance (No. 411, 2022, Del. 17 May 2023) is right, and the full case names are used in both
`sources.json` and the *Cite as* table. Nowhere in the repo says *"In re Bingle"*.

One thing did need saying. The `delaware-cyber-cases` row now records that **no citator was run**
— no Shepard's, no KeyCite — so subsequent history beyond the recorded affirmance is unconfirmed.
`checkedBy: "claude-code"` means *machine-verified against the primary source*, and without that
note the row claimed more than the check delivered.

## v0.72.0 — 2026-08-10

**The AI security register answered a mistyped path with a stack trace** (BL-218).

Seven skills accept `--context`. Six refused a missing payload with a phrased message.
`ai-register` printed a raw Python traceback, because `load_context` opened the file with no
guard at all and the top-level handler catches only `Refusal`. A CISO who mistypes a path, or
who has not built a business-context store yet, got a traceback out of the AI security
register — the first-ten-minutes failure BL-169's entry-anywhere requirement exists to prevent.

It now carries its twin's guard (`vendor_register.py`), plus the `contractVersion` check the
five stricter consumers already had, so an arbitrary JSON object is no longer accepted as an
applicability profile. The `.biz` clause deliberately runs **before** the contract check: a raw
store carries no `contractVersion`, and answering it with the generic contract message would
throw away the one sentence naming the command that produces the file the user meant to pass.

**A second crash, in the copy this item named as its reference.** Registering the twin meant
running all seven consumers against one corpus, and `vendor-register` turned out to raise
`AttributeError` on a payload that is a JSON array — `[]` parses cleanly and `.get` fails on
the next line. Identical defect, identical cause, two lines from the function being copied.
Fixed here rather than filed, because shipping a known crash while fixing a crash is not a
scope boundary worth holding. Five of the seven already had the `isinstance` check; now all
seven do.

**`load_context` is a declared twin, compared by execution** (CAC-TW-1). A new `refusal` kind
in `tools/check-twins.py` materialises each payload as a file, hands every member the path, and
distinguishes **refused through the engine's own channel** from **anything else that escaped**.
That distinction is the entire point: a guard that only recorded "it raised" would have called
BL-218's `FileNotFoundError` a refusal and reported the seven as agreeing. Each member declares
its own channel by name — two refuse with `ValueError`, five with a local `Refusal` — because
the class is the top-level handler's business and not an agreement.

Reverting the fix reports it exactly:

```
PROBLEM load_context: given a path that does not exist
           vendor_register.py -> ('refused',)
           ai_register.py     -> ('crashed', 'FileNotFoundError')
```

**What the seven still do not agree about is recorded, not hidden** (BL-226). Three inputs are
deliberately outside the compared corpus, with the reason written into the registry entry: a
payload with no `contractVersion` (six refuse, `vendor-register` accepts), one with no decided
`applicability` (five refuse, two accept), and a raw `.biz` store (two refuse with the useful
sentence, five accept). A fourth is worse — **a directory path raises `IsADirectoryError` out
of all seven**, so member-to-member comparison would report perfect agreement while every copy
is wrong. BL-218's page recorded the other six consumers as "correct today"; executing them
says otherwise, and BL-226 carries the measured table.

Counts: `ai_register.py self-test` 151 → **158** (seven cases, each asserting the exception
class *and* the message, plus one well-formed payload that must still load — every refusal
above would pass equally well against a guard that refused everything).
`vendor_register.py self-test` 228 → **229**. `check-twins` 9 twins / 251 comparisons →
**10 / 281**; its own self-test 26 → **30**.

## v0.71.0 — 2026-08-10

**Two engines emptied the store before writing it** (BL-219).

`risk-register` and `nist-csf` saved with `open(path, "w")`, which **truncates the file before
the dump begins**. A process killed in between left a half-written store *and no copy of what
had been there* — there is no `.bak` scheme anywhere in the suite, deliberately. These are the
two largest stores it holds: a `.csfp` carries all 106 CSF 2.0 Subcategories from `init`
onwards, and a `.rr` grows with every gap and every finding imported into it. They are also
the two an import path bulk-loads, so the exposure sat exactly where the largest writes happen.

Both now use the pattern eight other engines already used (`ai_register.py:208-220`):
`tempfile.mkstemp` in the **destination directory**, then `os.replace`, then unlink on any
exception. Nothing here is a new idea. These two functions predate the pattern and were never
brought forward. `dir=directory` is not decoration — `os.replace` is atomic only within one
filesystem, so a temp file in `/tmp` would make the move a copy across a boundary.

**Why nine releases of green tests never saw it.** When nothing goes wrong, an atomic writer
and `open(path, "w")` produce byte-identical output. Every test took the happy path. So the
new checks take the other one: `json.dump` is replaced with one that raises `KeyboardInterrupt`
part-way, and the file left on disk is compared **byte for byte** with what was there before.
Asserting only that the store still parses would pass a rollback that left a valid but
different register — a different bug wearing this test's clothes.

**The store write is now a declared twin, compared by execution** (CAC-TW-1). Ten copies across
ten engines, with two additions to `tools/check-twins.py`:

- a new kind, `atomic`, which runs each member's write with the dump cut short and compares
  what survived against a **stated contract** rather than against member zero. Every other
  kind in that file asks whether the copies agree; this one asks whether each copy is right,
  because the defect it exists for was two copies agreeing with each other and neither with
  the pattern. Ten writers that truncate in unison agree perfectly and are all wrong.
- `"naming": "hub"`, because the existing rule — every member names every other member's path
  in its own source — is ninety references for a family of ten, and a list that size is one
  nobody maintains. Each copy names `ai_register.py`; `ai_register.py` lists the family. Every
  copy stays one hop from it, which is the property that rule buys. The default is unchanged
  and a self-test case holds it there.

Two mutations were run against the finished guard. Reverting one copy to `open(path, "w")`
reports `('KeyboardInterrupt', False, 0)` — the previous store did not survive. Narrowing one
copy's `except BaseException` to `except Exception` reports `('KeyboardInterrupt', True, 1)` —
the temp file it leaves behind. The second is *why* the house pattern catches `BaseException`,
and nothing in the repo had ever tested it.

**A correction to the record.** The item was filed as "nine of eleven engines write
atomically". It is **eight of ten**: `board-pack`'s `mkstemp` at `assemble_pack.py:1645` writes
an exported applicability payload, not a store, and `ciso-board-translation` has no store at
all.

Counts: `score_register.py self-test` 213 → **216**, `profile_analysis.py self-test` 653 →
**656**, `check-twins` 8 twins / 241 comparisons → **9 / 251**, its own self-test 19 → **26**.
Reverting either engine's fix turns that engine's own self-test red on the byte comparison,
verified both ways.

`fsync` before `os.replace` was **not** added. The eight existing copies do not, and diverging
one copy of a registered twin to answer a power-loss question that none of the others answers
is the drift this release is closing. Raised separately (BL-225).

## v0.70.0 — 2026-08-09

**The twelfth skill is wired into the product** (BL-212).

`policy-register` shipped in v0.64.0 — good store discipline, five guards, above-median refusal
prose — and was in no producer table. **A CISO with three policy reviews overdue asked what
needed them this week and got a clean list**, with no `NOT READ` row either, because a producer
this surface has never heard of cannot be reported as unread. That is silence dressed as an
all-clear, and it is the exact failure `attention-surface` exists to prevent.

The item read as *"add policy-register to a list"*. It was not. **Its escalation objects matched
one of CAC-EL-1 §1.3's six keys.** They emitted `{severity, kind, target, what, soWhat}` —
`kind` where the contract says `trigger`, `target` where it says `subjectRef`, and no
`subjectKind`, `since` or `evidence` at all. Registering the producer without reshaping them
would have surfaced every row as malformed: a visibly worse outcome than the silence.

Three layers, and the order was forced. Reshape → register → map.

**`escalations()` now emits the contract, and only two triggers.** `subjectKind` is genuinely
two values here — `policy` for a document that went stale, `requirement` for an obligation
nothing covers — so it could not be the constant it is in `vendor-register`. `since` is always a
date the store already held: the `review.nextOn` that passed, or the `supersededOn` of the act
that ended the cover. Never today; a derived date stamped on a historic fact is a fact the
register did not have. The CSF grounding that lived in `soWhat` survives into `evidence` rather
than being dropped, and the eval greps for `GV.PO-02` on the rendered weekly page to prove it.

**`review-due`, `no-review-date` and `draft-only` stopped escalating.** Four sibling skills state
the rule in nearly the same words — *due is the attention list; overdue is an escalation* —
because escalating a deadline nobody has missed teaches a reader to ignore the list by the
second quarter. They moved to `analyze()["attention"]`, a review agenda beside the escalations,
which **this skill did not have and now does**: a new block in the read model, a new section on
the requirement page, and a line in the terminal summary. The demotion was additive work, not
deletion.

**`draft-only` is the one worth writing down, and it is written down in four places**, because
it will read as a mistake later. It shares its end state with `superseded-only` — neither
requirement has an approved document in force. The distinction is not severity, it is whether
the gap is **visible**. A draft shows in the register as a draft. A requirement covered only by
superseded documents looks *populated*. Deceptive escalates; visible does not.

`review-overdue` maps to **clocks running out**, beside `revalidation-overdue` and
`assessment-overdue`, which are the same shape. `superseded-only` maps to **uncontrolled
exposure**, whose own definition — *something is exposed and nothing is recorded against it, a
standing condition rather than a deadline* — is that trigger restated. `clusters.json` goes to
`datasetVersion` 3.

`analyze` gains **`--json`**, matching `vendor-register` and `ai-register`. It had none: with no
`--out` it printed a human summary, so the obvious `PRODUCERS` entry would have failed with
*"did not emit JSON"*. A flag rather than a changed default, because swapping the summary for a
JSON dump breaks everyone running it at a terminal for a reason that has nothing to do with them.

**CAC-AP-1 is registered as `context: False`, and the SKILL.md says that is undecided rather
than declined.** Adopting it is a separate item with its own scope. Registering here does not
pre-empt it; `True` would, by asking for a flag the engine has no code for.

The suite now emits 31 triggers across 8 producers — both read off the tree by
`_triggerscan.py`, not maintained in prose.

## v0.69.0 — 2026-08-09

**Eight board-safety suites now read their file list from the tree instead of carrying one**
(BL-211).

The scan that checks no catastrophizing or false-confidence vocabulary reaches a board page
walked a hardcoded `FILES` tuple and then asserted `scanned == len(FILES)`. That is a
tautology — the length of the list checking itself — and it cannot see a file that was never in
the list. `metrics-register/renderers/render_operational.py` was on disk, outside the tuple,
and a catastrophizing constant planted in it **passed the suite**, while the same suite
rendered that file's page and scanned the HTML. It treated the renderer as in scope for output
and out of scope for source.

Measured against `main` at v0.67.0: `risk-register` scanned 3 of 5 shipped files, `nist-csf`
4 of 6, `metrics-register` 3 of 4. The five suites whose tuple matched the tree were never
safe — they matched because somebody last edited the list by hand, which is a different
property from reading the tree and indistinguishable from it until a file is added.

Each of the eight now derives its population as `scripts/*.py` + `renderers/*.py` minus an
`EXCLUDE` map **in which every entry states its reason**, and an entry naming a file no longer
on disk fails the run. The reason requirement is the finding, not decoration: `risk-register`
was omitting `scripts/score_register.py` with nothing saying so, directly beside
`renderers/render_dashboard.py`, which it excluded *with a written reason*. An exclusion is a
decision and an omission is an accident, and a tuple cannot tell you which one it is.

**New in CAC-GP-1: a mutation may `create` a file, not only edit one.** No edit can prove a
guard reads its population from the tree, because every edit lands in a file the list already
names — which is exactly how this survived eleven minor versions. Each of the eight now
registers a mutation that drops a renderer or an export the guard has never heard of into the
skill, carrying the prose the guard forbids. The staleness rule inverts for this form: a target
that *exists* is stale, because the file has since been written for real. The A/B is on the
record — the same planted file passes `metrics-register`'s pre-conversion suite and fails the
converted one.

`risk-register`'s check 10, the largest source scan in the suite, had no registered mutation at
all and is proved here for the first time. Guards 37, halves 66 → 67, proved checks 85 → 86.

`ai-register` and `vendor-register` are **not** converted. They glob `renderers/render_*.py`
and so reach every renderer and no engine script at all; widening them surfaces real hits in
self-test assertions and in strings that *describe* an attack class rather than claim one — a
judgement per hit, not a mechanical widening. Filed separately, with the line numbers.

## v0.68.2 — 2026-08-09

**A crown jewel can now record what it holds, not only what stops when it stops** (BL-216 R-3,
partial).

Criticality and sensitivity are not two words for one judgement. A payroll file nobody's day
depends on can be the most sensitive thing in the estate; a build server everything depends on
can hold nothing worth reading. Collapsing them makes one of those two systems invisible, and
which one depends only on which word the register happened to use. `--sensitivity` is a second
field for the second question.

**Free text, no scale, and a required basis** — decided 2026-08-09. No scale because the
organisation's own classification is the answer, and imposing `low/moderate/high` here would
make this skill the author of a data-classification policy it has no business writing. The
basis is required *because* there is no scale: free text with nothing behind it is an
adjective, and it will sit on a record an assessor is entitled to follow. Naming who determined
it and from what is the difference between a determination and a word somebody typed.

Stored through `declared()`, so the value carries its own `declaredBy`, `declaredOn` and
`basis` rather than leaning on the record-level `basis`, which answers a different question
again: why this system is a crown jewel at all.

**The renderer showed neither criticality nor sensitivity**, which would have made the new rule
enforced on write and invisible on read. A required field nobody can see decays into ceremony,
so `render_context.py` now prints both, with the sensitivity's basis beside it. Criticality had
been recordable since v0.30.0 and absent from this page the whole time.

New guard **`sensitivity-basis.sh`** (CAC-GP-1, halves `refused` · `visible`), and the second
half is the one that would otherwise rot: an engine that refuses correctly while the renderer
drops the basis satisfies the letter of the rule and none of its purpose. `EXPECTED_GUARDS`
36 → 37, `EXPECTED_HALVES` 64 → 66, and the proved-checks ratchet **83 → 85**.

**What was deliberately NOT done.** `criticality` is still a bare string while `sensitivity` is
a record. Adding a key is additive and breaks nothing; changing `criticality`'s shape is a
migration `business-context` has no path for — it pins `schemaVersion 1` and refuses anything
else — and that decision is open. The asymmetry is stated in the engine, the SKILL.md and the
renderer rather than left for a reader to discover. Shipping the safe half was preferred to
shipping neither, and the unsafe half is not improvised.

Counts: business-context self-test 208 → **216**; `sensitivity-basis.sh` 8/8; the other five
business-context suites unchanged and green; `prove-guards` 37 guards / 66 halves, 85 of 364
checks proved.

## v0.68.1 — 2026-08-09

**The criticality walk would return a Python dict repr as a governance level.** Both the
third-party and AI registers trace what an arrangement or deployment supports up to a crown
jewel with a declared criticality (NISTIR 8179 Process E). Both read the field on the same
byte-identical line:

```python
if wf and str(wf.get("criticality") or "").strip():
    return str(wf["criticality"]).strip(), path, False
```

`str({...})` is truthy and non-empty. A crown jewel whose `criticality` was a record sailed
straight past that guard, and the walk returned `"{'value': 'high', 'basis': 'board said so'}"`
**as the criticality level** — confidently, from a read it had not understood, and only caught
later (if at all) when `_rank` refused it as off-scale.

That is v0.66.0's defect one layer below the renderers. `esc()` refuses a container because a
container never belongs in a text slot; a derived criticality level is a text slot with more
riding on it than a page. `declared_criticality()` now refuses one in both engines. A blank
value is still not a refusal — that is a crown jewel declaring no criticality, which is
ordinary and yields `untraced`; scalars still pass through so the off-scale message keeps
coming from `_rank`, which words it better.

**This is groundwork, not tidying.** BL-54's R-3 changes `crownJewels[].criticality` from a
bare string to a record carrying its own basis. The refusal is what makes that migration safe
rather than hopeful: until the reader lands, a container there means a store written against a
contract this engine does not implement, and saying so is the only honest answer.

**The walk was also an undeclared twin** (BL-217). `ai_register.py` declared the mirror in
eight places; `vendor_register.py` named it back nowhere, so a maintainer editing the original
had nothing telling them a second copy existed. CAC-TW-1 could not find the pair either — the
declaration named the *skill* rather than the *file*, and a skill name is not something you can
grep. That is the same ungreppable-prose failure `evidence_text` had in v0.68.0, in a second
pair, found within hours.

Both ends now carry the path and the pair is registered — **8 declared twins, 241 comparisons**,
over a corpus of contexts covering one hop, two hops, past the bound, a cycle, a blank
criticality and a container.

**The registration was done first, and it earned its keep immediately.** With the refusal
applied to `vendor-register` only, `check-twins` went red and named both container cases and
both sides' answers. That is a real half-finished edit caught by the guard rather than a
manufactured one — on the exact pair R-3 will require editing together.

Both skills also gained fixtures pinning the refusal, because `check-twins` proves the two
copies **agree** and cannot prove either is **right** — and until this release they agreed on
returning a repr.

Counts: vendor-register self-test 224 → **228**, ai-register 147 → **151**; all 14 eval suites
across both skills green; `check-twins` self-test 19/19 with 0 of 28 mutations surviving.

## v0.68.0 — 2026-08-09

**One escalation, a number on the weekly surface and a no-usable-evidence notice on the
quarterly pack — with a shipped docstring promising that could not happen** (BL-191).

`evidence_text` is duplicated between `attention-surface` and `board-pack` on purpose, and
`attention_surface.py` said so: *"the same escalation read by the weekly surface and by the
quarterly pack has to produce the same sentence."* One tested `is not None`, the other
`not in (None, "")`. On `{"from": "", "to": 5}` the surface rendered `" -> 5"` and the pack
rendered `"(structured evidence with no `detail`: from, to)"`. A CISO who read the weekly and
then presented the quarterly was presenting something that contradicted what they had read.

**An empty-string evidence bound means NOT RECORDED**, decided 2026-08-09. It is not a value
recorded as blank, and `" -> 5"` is half a fact — worse than none, because a reader cannot see
that it is half. `board-pack`'s reading was correct; `attention-surface` adopts it. `0` is a
recorded value and both copies keep it, which is what a careless "treat falsy as absent" fix
would have broken.

**`tools/check-twins.py` (CAC-TW-1) is the guard that had to land first.** Every declaration of
this kind ends with some version of *"each skill's own self-test is the only thing pinning them
to the same semantics"* — and **a self-test inside one skill cannot see the other copy, by
construction.** Nothing under `skills/*/evals/`, `tools/` or CI read both sides of any pair.

It compares **behaviour, not source**. `_iso_date`'s two copies reach their verdict through
`strptime` in one file and `date.fromisoformat` in the other, deliberately; `AGE_BAND_LABEL` is
twinned with the wording required to *diverge*. And `is not None` against `not in (None, "")`
reads as a stylistic difference — the audit that found BL-191 executed both functions rather
than reading them side by side, so the guard works the way the finding worked. Five kinds:
`behaviour`, `verdict` (accepted-or-rejected and the value stored, never the message),
`derived` (day boundaries against rendered day ranges), `constant`, and `divergent` — keys must
match, every value must differ.

**Run against the unfixed tree it reported ten problems, and three were not BL-191:**

- **`age_band` ships in three copies, not two.** `metrics_analysis.py` carries a third and its
  note claimed *"each carries a note pointing at the others"*. Neither of the other two
  mentioned it. A maintainer moving a boundary would have grepped one sibling and changed two
  copies of three.
- **Neither end of the `evidence_text` pair named the other's path.** The declaration said
  "`board-pack`'s renderer", which is not something you can grep, and the pack end said nothing
  at all — on the one pair that had actually drifted.
- **`metrics-register`'s `STATUS_SEV` said nothing back to the board pack** that cites it by
  name so a metric chip carries the same band as the metric's own bullet.

All are fixed, and the scan asserts what it read (GP-1.7): every cross-skill reference to
another skill's shipped `.py` must be a registered twin, an explicit not-a-twin with its own
reason, or a declared-but-uncompared row that is **counted and printed on every run** — the
same call v0.67.0 made about its unproved checks. The word "twin" is not the tell and the path
is: `AGE_BAND_LABEL`'s declaration says "carries the matching note back to here", and a
twin-vocabulary grep misses it entirely.

Both skills also gained fixtures pinning the empty-string bound, because `check-twins` proves
the two **agree** and cannot prove either is **right** — two copies can agree on a wrong answer.

Counts: 7 declared twins, 201 comparisons executed, 15 cross-skill references classified, 1
uncompared and printed; self-test 19/19, with **0 of 28 mutations surviving** in both
directions after four survivors exposed four missing cases.

## v0.67.1 — 2026-08-09

**The crosswalk licensing gate had never been seen to fire.** `validate_crosswalks.py` refuses
an ISO or CIS control that carries normative text — the invariant the whole crosswalk design
rests on, and the one this project has no licence to breach. It runs in CI on every push.
BL-204's mutation sweep suppressed each of the file's twelve guards in turn so it could never
report, and **ten survived `--self-test`**, that one among them (BL-205).

The shipped data could never have caught it. The real catalogues are clean, so the file prints
`3 catalogs · 0 errors · 0 warnings` whether its guards work or not — which is exactly the
condition under which a broken guard is invisible.

The self-test goes from **4 checks to 28**, built on synthetic three-framework catalogues that
are valid and then broken one rule at a time. Each case asserts the **specific message** and the
**error and warning counts**, not merely a non-zero exit: a carelessly built duplicate-id fixture
also trips the required-catalogue rule, and then one guard is proved by another guard's finding.
Most rules also get an acceptance case — 800-53 *may* carry its text, `text: ""` is an absent
field rather than a breach, a control in no grouping is fine, a column headed *"Not the official
title"* is allowed — because a guard that fires on everything discriminates nothing (GP-1.10).

Re-swept in both directions: every guard forced to `if False:` (never reports) and to `if True:`
(always reports). **0 of 24 mutations survive**, from 10 of 12.

Also removed from the module docstring: *"if a catalog declares expectedCounts and is marked
complete, counts must match."* No catalogue declares `expectedCounts` and no code reads it, so
the line described a rule that has never run. Removed rather than implemented — inventing an
enforcement contract for data that does not exist is how a docstring becomes the only place a
rule lives.

## v0.67.0 — 2026-08-09

**`51 halves, each proved in both directions` was true and misleading at once.** Halves are
counted from the proof file, so the framework's yardstick was the claim being made: a guard
running twenty checks and registering one mutation reported exactly what a fully covered guard
reported. Measured across the tree, **50 of 356 checks had ever been demonstrated to fail —
14%** (BL-210).

**Two things had to be fixed before the ratio could be computed at all.**

*A check needs a stable name.* Suites printed one label on success and another on failure —
`ok "no shipped .py assigns a closed-state field on an exposure class"` against
`bad "no shipped .py assigns a closed-state field"`. GP-1.9 matches the mutated run so the
proofs worked, but **33 of 83 `defeats` entries, 40%, across 15 of 36 guards, named a string no
clean run ever published.** A check whose name changes with the branch — or with interpolated
data, as in `ok "static scan --$mode ($scanned functions read)"` — cannot be counted, waived or
found by the next reader. All 33 are fixed and the runner now fails on a new one.

*The runner had to read its own clean run.* It always performed one, and only ever looked at
the exit status. The published labels were sitting in a file it had already written.

**`tools/proof-coverage.py`** (GP-1.11) enforces: every `defeats` entry names a published
check; every waived check exists; every guard defeats at least one of its own checks; and a
waiver carries a reason not byte-identical to another guard's — because `guard-registry.json`
already has 13 of 21 `not-a-guard` rows sharing one template, which is what
classification-by-boilerplate looks like from the outside.

**What was deliberately NOT done: mass-waiving the remainder.** It was the obvious move and it
is wrong. Reading the 273, a real fraction *are* the guarded property — `ai-register`'s
*"no decision renders as a raw Python dict — the defect this suite exists for"* was among them.
A waiver there is not a decision, it is the same false comfort in a new wrapper, and it would
read as settled. So the number is printed on every run and **`EXPECTED_PROVED` is a ratchet: it
may rise freely and may never fall.** A floor rather than a target, because the honest end
state is not 356 of 356 — an anti-vacuity assertion that a fixture was built is a precondition,
and a mutation for it would prove only that the fixture still works.

The run now closes with:

> `36 guard(s), 64 half/halves, each proved in both directions`
> `83 of 356 checks proved by a mutation (23%), 0 waived with a reason`

23% rather than 14% purely because the 33 relabelled checks now count — the same proofs,
finally attributable.

**Also closed here: BL-209's D-3.** That item required the anti-vacuity check to keep *its own*
mutation, and v0.66.0 let the `crash` half stand in for it by killing the page. One property
proving another is the substitution BL-209 exists to stop, so it was reintroducing the defect
inside its own fix. Each `decisions-render` guard now has three disjoint halves — `repr`,
`text`, `crash` — and `hastext` stays silent on a missing page so `wrote` owns that failure
alone.

**Recorded, not fixed: GP-1.7's own claim is stale.** It says *"each guard now recomputes the
expected file list from the filesystem"*. The ten `board-safety.sh` suites do not — they carry
a hardcoded tuple, so `risk-register` scans 3 of 5 shipped files, `nist-csf` 4 of 6 and
`metrics-register` 3 of 4. That is BL-211, and the numbers are now in the standard beside the
sentence rather than left as an aspiration.

Counts: `prove-guards` 36 guards / 59 halves → **36 / 64**; proved checks 50 → **83**; new
`proof-coverage` self-test **7**. Everything else unchanged and green.

---

## v0.66.0 — 2026-08-09

**A board decision was rendering as a Python dict on a shipped page, and five guards written to
prevent exactly that were green over it.**

`skills/risk-register/renderers/render_report.py` printed both board decisions as escaped
reprs on every operational report:

> `{&#x27;text&#x27;: &quot;Fund DMARC enforcement…&quot;, &#x27;altitude&#x27;: &#x27;board&#x27;}`

which a browser renders as `{'text': "Fund DMARC enforcement…", 'altitude': 'board'}`. That is
the original P1 the `decisions-render` suites exist for, live at v0.65.2.

**Why nothing saw it.** `C.esc()` was `html.escape(str(s))`. On a dict, `str()` makes the repr
and `html.escape` rewrites its quotes as `&#x27;` — so a grep for the literal `{'text'` finds
nothing on a page made entirely of them (BL-199). Five suites greped only the raw form. Two
other holes stacked on top: a `grep` over a file the renderer never wrote also finds nothing and
also reports clean, and `render_report.py` was rendered by no guard at all.

**The previous proof file diagnosed this correctly and stepped around it.** Its own note says
returning `str(d)` renders the repr but *"esc() turns the quotes into &#x27; so the literal
{'text' the guard greps for never appears"*, and that returning the dict makes the renderer die
into the crashed-probe blindness of BL-121. Having written both down, it registered a mutation
that avoided them — so what was proved was that the decision text reaches the page, not that the
repr never does.

**The fix, at the cause.** `esc()` now refuses a container. A runtime census over every eval
suite in the repo — 21,213 strings, 595 ints, four dicts — settled the fork the item carried:
refusing non-strings would break 595 legitimate call sites (`esc(42)` is "42" and should be),
while all four container calls were the defect. So the rule is not *strings only*; it is that a
dict, list, tuple or set never belongs in a text slot, and it raises at the call site holding
the object rather than three layers later in a page nobody diffed. Nine copies.

**And at the symptom, because the guard must be able to fail.** The five now grep the escaped
form, assert the renderer actually wrote a page, and — for risk-register — render *both*
renderers that emit decisions. `ai-register` and `vendor-register` already handled the escaped
form and were not among the five.

**Every registered mutation is now the real defect.** `repr` (`_dtext → str(d)`) defeats the
repr checks; `crash` (`_dtext → d`, which `esc()` now refuses) defeats the wrote-a-page and
text-present checks; risk-register adds `report-repr` so the new second-renderer coverage is
proved rather than asserted. `norepr` stays silent on a missing page so `wrote` owns that
failure alone — otherwise one mutation defeats every check and proves nothing about any of them.

Counts: `prove-guards` 36 guards / 53 halves → **36 / 59**; `decisions-render` suites 3→4, 3→4,
3→4, 4→5 and 3→**8** for risk-register. Everything else unchanged and green.

---

## v0.65.2 — 2026-08-09

**The three limits BL-188's sweep left open, closed — and the tempting fix for one of them was
wrong.**

BL-188 fixed three NYDFS receipts that scoped only outward, at who the rule does not reach, and
said nothing about who inside the perimeter is exempt. Its D-4 sweep read all 31 outward-scoping
sentences in the repo and left three unanswered, because answering them meant reading two more
regulations rather than pattern-matching. Both were read against their primary texts.

**DORA — and this is why the one-line edit was refused.** Two shipped files already attach the
**Art. 16 simplified framework** limit to the residual-risk receipts under RTS 2024/1774, so
copying it into the incident-reporting receipt under RTS 2025/301 looked like consistency. It
would have been a **fabricated exemption in a disclosure record.** Art. 16 disapplies
*"Articles 5 to 15"* and nothing else; incident reporting is **Chapter III, Arts. 17–23**, with
major-incident reporting at Art. 19 — untouched. The only mention of microenterprises anywhere
in Chapter III is a mandate to the ESAs to bear their capacity in mind when setting the Art. 18
classification criteria, which is not an exemption.

The real inward limit is **Art. 2(3)**, which takes six categories out of DORA from inside the
financial-entity list — AIFMs under Art. 3(2) of 2011/61/EU, insurers under Art. 4 of
2009/138/EC, IORPs with no more than 15 members, persons exempted under Arts. 2–3 of 2014/65/EU,
SME insurance intermediaries, and post office giro institutions — plus **Art. 2(4)**, which lets
a Member State exclude more, so the answer can differ by country.

**SEC Item 106 — the answer is "nobody", and that is worth writing down.** 17 CFR 229.106 read
in full carries **no exemption**: definitions, risk management and strategy, governance, a
structured-data requirement, nothing scaled or omitted for any registrant inside its perimeter.
Its one inward variation is **Instruction 1 to Item 106(c)**, a two-tier-board accommodation for
a foreign private issuer, which relieves nobody of the disclosure.

**SEC Item 1.05** — the inward material already existed in `disclosure-clocks.md` (the 1.05(c)
and 1.05(d) delay mechanisms, the Form 8-K boundary, and declared rather than inferred registrant
status). `materiality-factors.md` and the skill's own scope section now point at it instead of
stopping at *"registrants and nobody else"*.

**`two-directional-limits.sh`** generalises D-4 into a check. Its registry in `_limitcheck.py` is
a record of primary-source reads that happened, six (file, regime) pairs deep, and the guard only
asserts the shipped prose still carries them — adding a regime without doing the read would make
it a green light over a guess. Two halves: *inward-stated*, and **no-borrowed-limit**, which
fails if a file names Art. 16 beside reporting without saying what Art. 16 actually disapplies.
The second half exists to freeze a near-miss rather than a defect.

**One citation removed rather than declared.** Item 106's Instruction 1 cross-refers to another
CFR rule; quoting that number would have shipped a citation nobody here has read, and CAC-RW-1
caught it. The accommodation is described instead.

Counts: `prove-guards` 35 guards / 51 halves → **36 / 53**; new `two-directional-limits` **9**;
`lint-evals` 59 → **60** suites. Everything else unchanged and green.

---

## v0.65.1 — 2026-08-09

**An exempt firm was told a lawful gap was non-compliance.** Three shipped locations stated
that NYDFS §500.12 (MFA) and §500.15 (encryption) bind a covered entity. **§500.19 exempts
qualifying covered entities from exactly those sections**, and §500.19 appeared nowhere in
`skills/` at all — five release tests confirmed it absent. Following this suite's own guidance,
such a firm would then log a controlled exception, with a remediation timeline and a date,
against an obligation it does not have. If that record reaches an examiner, the toolkit
manufactured the finding (BL-188).

**The pattern, not the three typos.** Every one of the three carried a careful limit, and every
limit scoped in one direction:

> *"it binds covered entities in New York financial services and nobody else"*
> *"NYDFS §500.12 binds covered entities in New York and nobody else"*
> *"it applies only to covered financial entities"* — annotated **HONEST LIMIT (load-bearing)**

They are written to stop the claim reaching firms **outside** the perimeter and say nothing
about which firms **inside** it are exempt. The discipline that produced them guards against
over-claiming outward and had no equivalent habit for over-claiming inward.

**Read against the primary text before anything was written.** §500.19 was read in full from the
DFS official adoption text of the Second Amendment, cross-read against the DFS consolidated copy
— which agrees word for word and carries its own notice that it is not an official version. The
limbs are **not interchangeable**, which is why every location now names them:

- **§500.19(a)**, the limited exemption — under any one of three tests (fewer than 20 employees
  and independent contractors including affiliates, under $7.5M gross annual revenue in each of
  the last three fiscal years, or under $15M year-end total assets) — reaches **§500.15 but not
  §500.12**.
- **§500.19(c) and (d)** reach **both**.
- **§500.19(b), (e) and (g)** reach the **whole Part**, §500.17 included.

**The Second Amendment removed §500.12 from (a)** — it is bracketed as deleted matter in the
adoption text. A firm exempt from MFA before 1 Nov 2023 is not exempt now; §500.12 bound it from
1 Nov 2025 under the §500.22(d)(4) transition. So *"small covered entities are exempt from MFA"*
was right until Nov 2023 and has been wrong since, and the receipts now say so.

**`nydfsExemption` records the limb, and gates nothing.** Declared by counsel on the same
pattern as `secItem105Scope`, it holds `500.19(a)` / `500.19(c)` / `500.19(g)` / `none` rather
than a yes/no, because the limbs reach different sections. It is deliberately **not** a battery
gate: a section-level exemption cannot gate a whole battery, and wiring it to
`nydfs-notification` would drop the notification question for a limited-exemption firm that
still owes it. The engine self-test asserts it gates nothing, because the obvious "improvement"
is to wire it up and it would be silent.

**Qualification is never computed.** The tests read like arithmetic — a headcount, a revenue
figure, an asset total — and that is the trap: affiliate aggregation, what counts as operating
under a license, and whether an entity "otherwise qualifies as a covered entity" are legal
determinations. The guard's second half fails a location that prints a threshold without the
sentence saying so.

**`nydfs-exemptions.sh`**, two halves, both seen to fail: *stated* (each location names §500.19
and distinguishes its limbs) and *not-computed*. It lives in `exceptions-register` because
`ciso-board-translation` ships no evals directory, and it covers both.

**The D-4 sweep, recorded rather than assumed.** All 31 outward-scoping sentences under
`skills/` were read against *does this regulation exempt anyone inside the perimeter it names?*
Already two-directional: the DORA RTS Art. 3(d) receipts, which name the Art. 16 simplified
framework, and SEC Item 1.05 in `disclosure-clocks.md`. Fixed here: the NYDFS three.
**Outward-only and unverified:** `materiality-factors.md` on DORA and on SEC Item 106, and
`incident-materiality/SKILL.md` on Item 1.05 — filed rather than fixed, because whether Art. 16
reaches incident *reporting* under RTS 2025/301 the way it reaches the residual-risk inventory
under RTS 2024/1774 has not been read against the primary source, and copying a limit between
regimes is how the next BL-188 gets written.

Counts: `business_context` 193 → **208**; `prove-guards` 34 guards / 49 halves → **35 / 51**;
new `nydfs-exemptions` **10**. Everything else unchanged and green.

---

## v0.65.0 — 2026-08-09

**A statutory filing deadline was computed off the wrong fact for twelve releases.**
`business-context` documented a profile flag as:

> `"listedEntity": "shares admitted to trading — the SEC Item 1.05 perimeter"`

Two facts, joined by an em dash. The first is a listing fact, true of any exchange anywhere;
the second is a US securities-law fact about who must file current reports on Form 8-K. The
definition asserted they were the same thing, and `QUESTION_SETS["incident"]["sec-item-105"]`
then drove a four-business-day clock off it.

It failed in both directions, and eight release tests reproduced both. A London-listed company
with no Exchange Act obligation was handed an 8-K deadline it does not owe — a manufactured
legal date, in a compliance product, which gets acted on. An unlisted US issuer reporting under
Exchange Act s.15(d) was denied one it does, and the skip sentence **quoted the disqualifying
fact as its own justification**: named declarer, date, basis, every provenance signal a
reviewer looks for, and wrong.

Nothing in that is an inference the engine performs. The arithmetic was right and every review
passed, because the wrong fact was selected one layer up — in a dictionary of English sentences
and a mapping, neither of which any test read (BL-175, decision AP-2).

**The fix, in three parts.**

- **`secItem105Scope` is its own declared flag** — required to file current reports on Form 8-K
  under the Exchange Act, declared by counsel, inferred from nothing. `listedEntity` keeps its
  narrow meaning and gates nothing.
- **CAC-AP-1 gains §2.4.1.** §2.2 already said absence asks; it never said the asking leaves a
  trace, so a battery asked on a declaration and one asked on a silence reached the consumer as
  the same entry in the same list. `applies()` now also returns `undeclared` — a subset of
  `ask`, with its own sentence that never says "not assessed", because the battery *was*
  assessed.
- **No perimeter, no clock — and no silence either.** Where SEC scope is undeclared,
  `incident-materiality` asks the battery in full and renders the window as
  `scope-not-declared`, naming the flag that would settle it. Where the incident is tracked
  against the regime anyway, `scopeUndeclared` escalates the missing declaration. Both halves:
  withholding alone would trade a false date for a blank one, and a firm that had simply not
  filled in its profile would then look identical to one genuinely out of scope.

**Existing stores need no migration.** A `.biz` carrying only `listedEntity` has not declared
SEC scope, so it asks and withholds — by the rule, with no migration step. Asserted on the
unmodified worked example rather than claimed.

**Two guards, four halves, both seen to fail.** `one-fact-per-flag.sh` (business-context) fails
on a definition that joins two facts *and* on a battery gated by a flag that does not name its
regime — separately, because the repo shipped a clean-looking definition on a wrongly-gated
battery and either check alone passes that state. `scope-withheld.sh` (incident-materiality)
fails on a computed deadline and on a withheld one that stops escalating.

Counts: `business_context` 172 → **193**; `incident_analysis` 177 → **198**;
`prove-guards` 32 guards / 45 halves → **34 / 49**; `applicability.sh` 58; `consumers.sh` 36 →
**37**; new `one-fact-per-flag` 8 and `scope-withheld` 14. Full suite green.

**Not closed with it, and filed rather than left implied:** BL-188 — the NYDFS §500.19
exemption, which AP-2 pairs with this item on the same declared-fact design.

---

## v0.64.1 — 2026-08-09

**C5's fourth fail-open, closed three releases after the other three.** This sentence passed the
withdrawn-citation guard, and it cites withdrawn guidance as current:

> *The predecessor platform was retired. Follow SP 800-61 Rev. 2 for incident handling.*

### Why a rule that reads correctly stopped working

RW-1.9.1 excused a marker only when it was on the same line **and** nearer this publication than
any other on that line. The second clause is a *comparison*, and a comparison needs something to
compare against. When the citation was the only watched publication on its line — the common
case, not the exotic one — `all(...)` iterated over the match itself and evaluated `mine <=
mine`. Always true. So the rule collapsed to same-line, and any marker anywhere on the line
excused any citation: `retired`, `withdrawn`, `superseded`, describing anything at all.

The rule had been designed, documented and worked through against **two** publications, where
"nearest" means something. At one, the word has no referent.

### The fix: a marker must be in the same CLAUSE

RW-1.9.1 now requires all three of same line, **same clause**, and nearest-within-that-clause.
A clause ends at `.` `!` `?` `;` or a table-cell `|` — never at a comma or a dash, because
`SP 800-61 Rev. 2, withdrawn in 2025,` and `SP 800-61 Rev. 2 — withdrawn` are the two commonest
honest forms here and a rule that split on either would reject the warning it exists to permit.

For an author the rule is still one sentence: **put the warning in the same sentence as the
citation.**

Two things stop the splitter severing a citation from its own warning. Cuts are never taken at
an offset a matched publication occupies; and a full stop closing a citation abbreviation before
a number — `Rev. 2`, `No. 5` — is not a sentence end. The second is not belt-and-braces: the
publication patterns match the STEM only, so the stop in `Rev. 2` falls outside every span where
the first rule cannot see it. Six acceptance cases went red on exactly that before the
abbreviation list existed.

### Mutation-testing found three more holes, and it found them after the suite was green

Eight new cases passed on the first run. Then three separate reversions of the fix left the
suite **entirely green** — clause-scoping of the nearest rule, the width of the abbreviation
exemption, and the in-span cut exclusion were each asserted by nothing. Three more cases were
built to go red for exactly one of them.

A fourth turned up in passing: `BL-194/B` was supposed to prove that a marker appearing inside
an identifier (`obsoleteFlag`) is not a warning, but its fixture never listed `obsolete` as a
marker — so the citation was caught for an unrelated reason, and replacing the whole-word
matcher with a plain substring search left the suite green. Fixed.

**A suite that returns the right verdict can still be returning it for the wrong reason, and
only running the broken version tells you which.**

### The generalisation, now written into the standard

Three guards in this repository have failed the same way. `[ -z "$res" ]` could not tell a clean
scan from a crashed one (BL-121). `len(bounds) == 1` could not tell a missing anchor from a
legally excluded one (BL-176). `all(...)` over a single candidate could not tell nearest from
only (BL-201). Each reads as discriminating and stops discriminating when its input is minimal,
and each returned the right answer on every case its author thought to write.

**Read a check for what it does at n=0 and n=1, not at n=typical.** Recorded in
`tools/sources-schema.md` under RW-1.9.1 rather than only in this entry.

### Also

- **The stricter rule found two real instances in shipped content** on its first run, both in
  `skills/nist-csf/evals/trigger-prompts.md`: a citation whose withdrawal note sat two sentences
  away inside a dense table cell, and another split across a sentence boundary. Both rewritten so
  the warning sits beside the citation. Neither was caught by the rule it replaced.
- `tools/sources-schema.md` still described the **pre-BL-194 proximity window** — *"no withdrawal
  marker within about a paragraph of it"* — which had been wrong since v0.55.0. RW-1.9.1 now has
  its own subsection stating the rule the code actually implements.
- The self-test asserts a **floor of 101 checks**. It has always printed its count and asserted
  nothing about it, so a deleted case would have shown up only as a smaller number in a line
  nobody diffs — and "0 failed" reads identically whether 101 checks ran or nine did.

Counts: `check-sources --self-test` **101 checks, 0 failed** (up from 91); scan clean over 324
files; release gate clean. All eleven engine self-tests, `prove-guards` 32/45, `lint-evals` 56
suites unchanged and green.

---

## v0.64.0 — 2026-08-09

**`policy-register` — the twelfth skill, and the last capability before 1.0.** GV.PO was the
only CSF 2.0 GOVERN category with no coverage at all, and *"show me your policies and which
requirement each one satisfies"* is asked of every CISO by every auditor every year. The
toolkit had no answer.

### The refusal is the product

A mapped policy is **never** evidence that a requirement is met. *"We have a policy for that"*,
accepted as *"that risk is controlled"*, is the most common quiet untruth in this industry —
and a register that permitted the slide would make a CISO **less** defensible for having used
it, because a register looks like a system.

So the four states a requirement row can carry all describe the **documents** — `not-declared`,
`draft-only`, `superseded-only`, `approved-policy` — and none describes the requirement. There
is no fifth state, and adding one is a red run rather than a quiet expansion of what the
product claims.

The other refusals: counts and never proportions; `approve` refused without a named approver
**and** a date; supersession and never deletion; a requirement with no policy reading NOT
DECLARED rather than "no policy exists"; an overdue review that flags and never blocks.

### The guards went in with the capability, not after it

Five new guards and eight new halves, registered under CAC-GP-1 **as each capability landed**:
`no-coverage-claim` and `no-coverage-percentage` (two halves each), `no-deletion` (two halves),
`requirement-drift` and `board-safety` (one each). `EXPECTED_GUARDS` moves 27 → **32** and
`EXPECTED_HALVES` 37 → **45** in this same change, which is the only way those numbers ever
mean anything.

That sequencing was the reason this item was blocked rather than queued: a capability added
after a truth pass re-opens the truth pass.

**Every `defeats` list was derived by running the mutation**, never written from memory —
which is what GP-1.9 asserts and why two of them turned out to name checks the author had not
predicted. Writing the guards also found three defects in the code they guard and two in the
guards themselves: a static scan that blanked its own file count when it found something (so
one mutation appeared to defeat two independent checks), and a precondition that duplicated the
rule it was supposed to make meaningful.

### Grounded in what already shipped

The twenty Policy and Procedures controls — `AC-1` through `SR-1` — come from the bundled
`800-53-r5.catalog.json`, and GV.PO-01/-02 with their nine implementation examples from the
bundled CSF Core. **No new dataset, no ingest, no licensing question.** The join between them
is NIST's own: the CSF Core's informative references for GV.PO-01 and GV.PO-02 name all twenty.

The record shape is read off those implementation examples rather than invented — *"Require
approval from senior management on policy"* is why `approval.by` and `approval.on` are
mandatory, and *"acknowledge receipt … when first hired, annually, and whenever policy is
updated"* is why `acknowledgement.cadence` accepts exactly those three values.

The spine is **vendored** so the skill runs with nothing else installed, and
`requirement-drift.sh` regenerates it from the `nist-csf` artifacts on every run and compares
all 112 fields.

### Built to BL-169 from the start

D-1 entry anywhere: this skill reads no other store and requires no other skill to have run.
D-2 resumable: every mutation leaves a schema-valid file. D-4 a partial programme is the
**normal** state — an empty register analyses cleanly, reports twenty-two requirements as not
declared, and raises nothing. It does not nag.

`kind` ships in the schema defaulting to `policy`, with `plan` and `playbook` reserved and
refused at write time. A field is cheap; migrating a store already in the wild is not, and
CSF ID.IM-04 is this lifecycle exactly with a different record kind.

### Counts

Engine self-test **75 checks**. Six suites: `no-coverage-claim` 9, `no-coverage-percentage` 9,
`no-deletion` 10, `requirement-drift` 5, `board-safety` 7, `lifecycle` 16. `prove-guards`
**32 guards, 45 halves**, 54 eval scripts classified, 0 candidates awaiting enrolment.
`lint-evals` 56 suites. `check-sources` 12 skills, 47 declared sources. The tenth
`cac_graphics.py` copy is byte-identical to the other nine.

Every new eval is named individually in `.github/workflows/evals.yml`. No globs.

### Also

- The prose spelling `SP 800-53r5` is ambiguous under CAC-RW-1's citation vocabulary — the
  pattern's optional letter absorbs the `r`, canonicalising it to `sp-800-53r` rather than
  `sp-800-53r5`. Normalised to `SP 800-53 Rev. 5`, the spelling the rest of the repository
  already uses. Found by C6 on its first run against the new skill.

---

## v0.63.0 — 2026-08-09

**The three open decisions, each turned into a rule.** A decision that lives in a chat log is
one the next reader has to re-make.

### RW-1.11 — an unverified row ships; the gate stays as it is

Decided: keep it. An unverified row is allowed, never `gated`, must say why, and is counted on
every run. Failing the release on one sounds stricter and is not — it pressures whoever is
shipping into stamping `checkedBy: "claude-code"` on a row nobody read, which converts a
**visible gap into an invisible lie**. This manifest exists to prevent that trade.

The cost is that `whyUnverified` is now load-bearing: it is the only thing separating *"we
looked and it is paywalled"* from *"nobody has got to it"*. A placeholder there — `TODO`,
`n/a`, `pending` — now fails.

### RW-1.12 — `checkedBy` stays machine-honest; a person may counter-sign beside it

`checkedBy` records who **read** the source; new optional `reviewedBy` + `reviewedOn` record
who **accepted** that reading. Replacing `claude-code` with a person's name would be false
provenance; dropping it for a human-only signature would lose the record of a real check.

A machine may not countersign its own work, and an endorsement needs a date, because one that
cannot age is the single thing this manifest measures. **The count prints every run: 0 of 45.**
An honest number, and the reason for printing it.

### RW-1.13 — 365 is the house default; a deviation must say why

The question was *"does 365 suit the SEC rule?"* The honest answer is that **nothing had ever
decided** — every gated row carried 365, all twenty-odd, because it was typed once and copied.

The burden is inverted onto the only case where it helps: the default needs no defence, a
deviation requires `intervalBecause`, and `intervalBecause` on a default-interval row also
fails because it reads as a deviation that is not one.

Applied: the eight **disclosure-clock** rows — SEC cyber rule, Item 106, Reg S-T 13, NIS2 Art.
23, DORA RTS 2025/301, FCC CPNI — move to **180 days**. The harm from a missed amendment there
is a late filing and it is asymmetric; nobody is penalised for reading the rule too often. The
operative text is comparatively stable, the staff interpretation is not, and it is the
interpretation that moves a deadline.

**The rule found a pre-existing unexplained 180** on `nist-csf/cyber-ai-profile` on its first
run — set before this rule existed, no reason recorded. The cadence was right and now says so.

### A first draft of RW-1.11 was wrong and an old test caught it

The placeholder check initially rejected anything under twelve characters, which rejected
`paywalled` — punishing concision rather than emptiness, and teaching authors to pad. The
existing case asserting that a *valid* unverified row passes failed immediately. **Cases that
assert the permitted direction earn their place exactly here**; a suite that only tests the
forbidden direction would have shipped it.

**Verification:** `check-sources.py --self-test` 82 → **91 checks, 0 failed**; repo and release
gate clean; all five new rules proved to fail on their own violation.

---

## v0.62.0 — 2026-08-09

**`candidate` gains a third answer: `permanent`.** the maintainer's decision, closing the enrolment
item at one candidate rather than eleven or zero.

`business-context/evals/archetype-advisory.sh` will never be enrolled, and the reason is worth
more than an enrolment would have been. It runs an A/B holding every declared fact constant and
moving only revenue and headcount, asserting the applicability objects come back byte-identical.
To defeat it a mutation must make A and B **differ** — but `applies(profile, question_sets,
subject)` never receives the store, so revenue and headcount are **structurally unreachable
from the function that decides scope**. The separation this suite protects is enforced by the
call signature, not by convention, and a mutation would have to widen that signature first,
which is a design change and not a proof.

### The decision is data, and the printed line stops overstating

`candidate` meant *"guard-shaped, not yet enrolled"*, and the summary line said so. That is now
false for the only candidate left. **Printing a settled verdict as "not yet enrolled" would be
a small, permanent untruth in the one line a reader trusts for scope**, so the two kinds are
counted apart:

```
48 eval script(s) classified; 0 candidate(s) awaiting enrolment, 1 permanent (unmutatable by design)
```

`"permanent": true` is valid on a candidate and nowhere else. Both misuses fail the run and
were tested: `false` instead of absent, and the flag on an enrolled guard.

The registry row records the condition under which the decision expires: **if `applies()` ever
gains access to the store, the defect becomes expressible and a mutation becomes both possible
and required.** A permanent verdict with no stated way to reverse it is a comment, not a rule.

**Verification:** `prove-guards.sh` 27 guards, 37 halves, all green; both `permanent` misuses
fail; lint-evals, check-sources and check-versions clean.

---

## v0.61.0 — 2026-08-09

**Two of the last three candidates enrolled.** `EXPECTED_GUARDS` 25 → 27, `EXPECTED_HALVES`
35 → 37, candidates **3 → 1**.

- **`risk-register/board-safety.sh`** — render the raw title for a risk still marked
  provisional. `C.risk_title` is the withholding path; swapping it for the plain title is a
  one-line *"why are we hiding this"* change that reads as a fix. It stayed a candidate a
  release longer than its eight siblings because both of their mutation shapes pass here: its
  checks assert **behaviour**, so the anchor had to be found against what it actually does.
- **`vendor-register/questions.sh`** — let T3 satisfy. This is the defect the tier model exists
  to prevent and **it looks exactly like success, because the question set gets smaller**.
  Written as `"T" + "3"` so a literal scan cannot see it, for the same reason
  `no-closed-state`'s behavioural mutation writes `"mitig" + "ated"`.

### GP-1.9 caught a false green in the runner itself

The `risk-register` mutation was correctly detected by the guard, and `prove-guards` reported
*"the mutated run named no failing check at all."* The suites use two reporting shapes — most
print `  FAIL  <label>`, the `chk` idiom prints `<id>  <label>  FAIL` — and the label reader
knew only the first.

A false negative, but the right kind: **GP-1.9 refused to accept a non-zero exit as proof that
the registered half was the half that caught it.** Under the pre-v0.56.0 runner this mutation
would have been recorded as proved without anyone learning that the runner could not read the
suite's output. The reader now understands both shapes and skips summary lines.

### `business-context/archetype-advisory.sh` stays a candidate, and the reason is the finding

No mutation defeats it, and that is worth more than the enrolment. The suite runs an A/B
holding every declared fact constant and moving only revenue and headcount, asserting the
applicability objects come back byte-identical. To defeat it, a mutation must make A and B
**differ** — but `applies(profile, question_sets, subject)` never receives the store, so
revenue and headcount are **structurally unreachable from the function that decides scope**.

The separation is enforced by the call signature, not by convention. A mutation would have to
widen that signature first, which is a design change and not a proof. Recorded in the registry
rather than forced: registering something that trips an adjacent check is the failure GP-1.9
exists for.

**Verification:** `prove-guards.sh` 27 guards, 37 halves, all green; 48 scripts classified,
1 candidate.

---

## v0.60.0 — 2026-08-09

**Eight of the eleven `candidate` guards enrolled.** `EXPECTED_GUARDS` 17 → 25,
`EXPECTED_HALVES` 27 → 35, candidates 11 → 3.

These nine `board-safety.sh` suites have been guard-shaped since they were written. They became
**countable** when BL-101's registry forced a verdict on every eval script, and they became
**enrollable** when BL-121 closed in v0.59.0 — until then, 51 of their checks read a crashed
probe as a pass, so a mutation registered against one would have been registered against a
check that could not fail.

### The mutations were found by running, not by pattern

Six suites scan renderer source for catastrophizing and false-confidence vocabulary, and take
the same shape of mutation: a module-level constant carrying a banned sentence, planted in a
shipped renderer. That is the way in that matters — nobody writes *catastrophic* into a board
pack on purpose, they write it into a helper's default string and it reaches the page months
later. A constant rather than an edit to live output proves the **source** half specifically,
which exists because a string can ship without ever being rendered in the fixture.

**Three suites did not trip on it**, and assuming they would is how a proof gets registered
against nothing. `ai-register` and `vendor-register` do not scan renderer source at all; their
anchor is the `Not legal advice` footer, one list comprehension away at all times, on the
artifact a director forwards to counsel.

### `risk-register` stays a candidate, and says why

Its checks use the `chk` registration idiom and assert behaviour — provisional titles,
accepted-risk grouping, closure rationale — so neither the source-scan nor the footer mutation
touches it. Rather than register a mutation that trips something adjacent, its registry entry
now records what a real anchor has to be found against. A guard proved by the wrong mutation is
the failure GP-1.9 was written for.

Also still `candidate`: `vendor-register/evals/questions.sh` and
`business-context/evals/archetype-advisory.sh`.

**Verification:** `prove-guards.sh` 25 guards, 35 halves, all green on the first run — every
`defeats` set derived by running the mutation and reading the labels, none written from memory.
48 scripts classified, 3 candidates.

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

> **CORRECTED 2026-08-10 (BL-141), and left visible rather than rewritten.** The last item in
> that list — *the rescission-pressure framing* — should not have been held. This sweep asked
> whether the rule was still in force, which it is, and the framing said something else: that
> the rules *"have faced rescission pressure and a materially reduced enforcement posture"*,
> undated, in four shipped files. **Both halves were overstated and neither carried a date.**
> The rescission half is one petition — SEC File No. 4-856, filed 22 May 2025 by five financial
> trade associations — that the Commission has not acted on. The enforcement half stated a
> posture the Commission has never stated: Litigation Release No. 26423 records that the
> SolarWinds dismissal *"does not necessarily reflect the Commission's position on any other
> case"*, and the Cyber and Emerging Technologies Unit has listed public-issuer cyber
> disclosure among its priorities since 20 February 2025.
>
> The attribution above is also wrong on its own terms: the rescission request this repo was
> carrying is the **May 2025 petition**, not comment letters on a January 2026 Regulation S-K
> review. **A sweep that checks a narrower question than the claim makes will report the claim
> as held** — the same shape as v0.46.0 verifying four citations and leaving two wrong dates
> beside them (see v0.54.0). Corrected in v0.73.0; the record of the error stays here.
>
> **WHERE THE CLAIM CAME FROM, added 2026-08-10 from RW-001 finding F2, and it is the part
> worth keeping.** The origin is a conflation, not an invention. On **12 June 2025** the SEC
> *did* withdraw cybersecurity rules: **Release 33-11377** withdrew fourteen pending rule
> **proposals**, two of them cyber — **S7-04-22** (advisers and funds) and **S7-06-23**
> (broker-dealers). **Neither had ever been adopted. Neither was ever in force. The
> public-company rules were untouched.** Reading *"SEC withdraws cybersecurity rules"* without
> checking **which** rules is how the withdrawal of two never-adopted proposals became a
> rescission-pressure claim about Items 1.05 and 106.
>
> That is the error this publishing arm exists to correct in other people, made here, and then
> carried through a sweep that reported it as checked. It is recorded rather than quietly fixed
> because the mechanism — right headline, wrong instrument — is reusable, and the next instance
> will not look like this one.

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

> **CORRECTED 2026-08-10 (BL-192), and left visible rather than rewritten.** The first sentence
> is true and re-verified — 20 of 20, set difference empty in both directions. **The second was
> false when it was written.** No such check existed. Grepping every `.py`, `.sh` and `.md`
> found exactly one consumer of any engine's `COMMANDS` outside its own file, and it belongs to
> a different skill for a different purpose. `SKILL.md` was careful where this note was not: it
> said the list *"can be checked against `COMMANDS` rather than trusted"*, which was accurate.
>
> **And the missing check is exactly what would have caught the next one.** Within nine
> releases, `import-findings` — a real command with a handler, named in `SKILL.md` — was absent
> from the module docstring that `--help` prints. BL-115's defect, one surface over, undetected
> because the guard this note announced was never built.
>
> A release note claiming a guard that does not exist is the same defect class as BL-95 and
> BL-103, in the document a reader trusts most about what changed. `tools/check-commands.py`
> ships in v0.81.0 and does what this sentence said — across all twelve engines rather than
> one, where it found nine more commands no shipped document named.

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
