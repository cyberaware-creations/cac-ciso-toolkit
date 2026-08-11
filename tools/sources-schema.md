# CAC-RW-1 — the source manifest

**Applies to:** every skill in `cac-ciso-toolkit`
**Implemented by:** `tools/check-sources.py`, run in CI on the 3.9 floor
**In force since:** v0.52.0
**Sibling standards:** [CAC-GP-1](guard-proof-standard.md) · [CAC-LE-1](eval-lint-standard.md)

---

## The problem, stated exactly

Before this file, **exactly two source families in the product carried a freshness stamp**: the
crosswalk bundle (`sourceExport.retrievedAt`) and the Cyber AI Profile dataset. Every legal
citation, every NIST methodology publication and every statistic was undated at the point of use.

That is not a hypothetical. The v0.48.0–v0.51.0 verification pass read six reference families
against their primary sources and found **twelve defects**, every one of them an *amendment*
failure — the citation was right when written and the instrument moved underneath it:

- IR 8286 r1, 8286A r1 and 8286C r1 went from initial public draft to final; the repo described
  the drafts as "the revisions".
- The SEC's technical-detail carve-out was stated to cover the incident, which Item 1.05(a)
  compels.
- DORA's reporting windows had no instrument behind them at all, and a misread carve-out reached
  the engine as a **false overdue** on a regulatory clock.
- NYDFS deleted a compensating-controls route the toolkit still offered.
- SP 800-30 Rev. 1 turned out never to have defined the scoring model attributed to it.

**Not one of those was careless authorship, and not one would have been caught by re-reading the
repo.** Only opening the instrument catches them. This manifest exists so the next pass knows
what to open, and so the gap between passes is visible rather than silent.

The pattern being copied is already in the tree: the crosswalk bundle is the one place with a
stamp discipline, and it is the one place a validator enforces one. That is not a coincidence.

---

## The standard

### RW-1.1 Every skill ships a `sources.json`

`skills/<skill>/sources.json`, schema version 1. A skill that cites nothing ships an **empty
`sources` array** — that is the honest answer, not a missing file, and the check accepts it.
`board-pack` is the live example: it owns no data and computes nothing, so every fact arrives
from a producer that stamped it.

### RW-1.2 A row carries only what serves disclosure and the check

```json
{
  "id": "dora-rts-2024-1774",
  "label": "DORA ICT risk-management RTS",
  "publisher": "European Commission",
  "instrument": "Commission Delegated Regulation (EU) 2024/1774, Art. 3, point (d)(iii)-(iv)",
  "version": "OJ L, 25.6.2024; in force 15 July 2024",
  "checkedOn": "2026-08-08",
  "checkedBy": "claude-code",
  "gated": true,
  "reviewIntervalDays": 365,
  "usedFor": ["references/exceptions.md"],
  "renderedAs": "DORA RTS (EU) 2024/1774 Art. 3(d)"
}
```

Binding strength, volatility class, watch URL, watch method and monitoring state are **private
maintainer data and never ship**. The two gate fields — `gated` and `reviewIntervalDays` — are
policy rather than monitoring state, which is what lets the release gate run with no private
store behind it.

> **D-9, confirmed by the maintainer on 2026-08-08.** Shipping these two fields narrows the
> original rule that no cadence appears in the shipped file. The judgment is that a boolean and
> an integer are *policy*, not monitoring state, and that a self-contained release gate is worth
> the narrowing — it is what lets this ship complete rather than waiting on the private store.
> Recorded here rather than left in a chat log, because the alternative reading is defensible and
> a future maintainer is entitled to know it was decided rather than overlooked.

**`checkedBy: "claude-code"` means machine-verified against the primary source and *not*
human-reviewed.** It is deliberately not a person's name. A human sign-off replaces it with one.

**`checkedBy: "unverified"` requires `whyUnverified`.** Without a reason the value degrades into
a shrug, and the next maintainer cannot tell *"nobody got to it"* from *"the source is paywalled
and trying again will not help"*. Both remaining unverified rows in this repo are the second
kind — ISO/IEC standards, where iso.org's browsing platform returns 403 and verification needs a
licensed copy — and recording that saves someone an afternoon.

### RW-1.3 `checkedOn` never renders

It is a claim about maintenance diligence, not a fact about the law. What renders is the
instrument identifier and, where it matters, the in-force date.

### RW-1.4 `renderedAs` is present only where a source actually renders

Its presence is what triggers the byte-equality check. Most non-legal sources have no
`renderedAs` at all, and **that absence is meaningful rather than incomplete**.

### RW-1.5 The renderer keeps its literal string; CI asserts byte-equality

Renderers do **not** read `sources.json` at runtime. Every shipped script in this repo runs
standalone with no cross-skill imports and a vendored `_common.py`; a runtime manifest dependency
would break that and invent a new failure mode where a missing file stops a board pack rendering.

Instead the manifest holds the canonical string and CI compares it byte-for-byte against the
renderer. One canonical value, no runtime coupling, drift caught at build time — the same
technique `CROSSWALK_EXPECTED` already uses to pin counts.

### RW-1.6 A stale gated source blocks a release, overridably with a recorded reason

`check-sources.py --release-gate` fails when a `gated` source is older than its
`reviewIntervalDays`. An override in `tools/release-overrides.json` must carry a reason, an owner
and a date; **an empty reason still fails.**

This is load-bearing for RW-1.3's converse: shipping precise, dated legal citations is only safe
while something keeps them current. If the gate is ever relaxed, rendered citations must fall
back to identifier-only, because a confident citation nobody maintains is worse than the vague
one it replaced.

### RW-1.7 An empty scan is a failure

Finding no manifests, or a manifest whose `usedFor` points at a file that no longer exists, fails
the run. The same anti-vacuity rule CAC-GP-1 applies to guards and CAC-LE-1 to suites.

---

## The six checks

| | Check | Fails when |
|---|---|---|
| **C1** | Presence | a skill has no `sources.json`, or it does not parse |
| **C2** | Shape | a required field is missing or empty, an id repeats within a skill, `checkedOn` is malformed or in the future, `gated` is true with no positive `reviewIntervalDays` |
| **C3** | Rendered citation | a `renderedAs` string is not found byte-for-byte in the files its row lists under `usedFor` |
| **C4** | `usedFor` exists | a listed path is not in the tree |
| **C5** | Do-not-cite | a withdrawn publication is cited as current, anywhere in the tree |
| **C6** | Declared | a designation cited in a covered file is in no row and no allowlist |

C3 is the one that catches the failure this standard is named for: a renderer whose citation
drifts from the manifest, or a manifest that was updated without touching the renderer.

---

### RW-1.10 Every citation in a covered file is declared, or allowlisted with an argument

**C4 and C6 are converses, and C4 alone is half a check.** C4 reads the manifest and asks
whether the tree still matches it. C6 reads the tree and asks whether the manifest covers it.

Until v0.57.0 only C4 existed, so a citation added to a reference file and never added to
`sources.json` was invisible to everything in this standard: never reviewed, never re-checked
against its publisher, never gated — and **indistinguishable from a citation that had been
verified**, because nothing recorded the difference (BL-190). C6 found ten on its first run,
across five shipped skills, including `NIST IR 8179` carrying `vendor-register`'s whole
two-hop criticality model and `47 CFR 64.2011` carrying a disclosure delay window.

**Covered file** means a file some row already lists in `usedFor` — the set C4 validates.
Widening past that is a different check with a different argument.

**Designations are canonical keys, not substrings.** `ISO/IEC 27001:2022` and `ISO 27001` are
one designation; substring matching was tried first and produced false positives on exactly
that pair, which is how a check earns being switched off. An ISO **edition year** is dropped;
a NIST **revision** is not, because `Rev. 2` and `Rev. 3` are different documents with
different obligations — the distinction `do-not-cite.json` exists to police.

Each pattern in the vocabulary carries a fixture asserting the key it produces, for the same
reason `mustFlag` does (RW-1.9.2): a detector that has stopped detecting reports "no
undeclared citations" in the same tone as one that works.

#### `designations` — for rows prose cannot be parsed for

Optional per row. A series row such as `"NIST IR 8286r1, 8286A r1, 8286C r1"` names three
publications and the detector can only see the first, because a bare `8286A r1` with no `IR`
prefix is not a shape worth matching in open prose. Guessing there trades false negatives for
false positives, and a noisy check gets turned off.

```json
{ "id": "ir-8286-series",
  "instrument": "NIST IR 8286r1, 8286A r1, 8286C r1",
  "designations": ["ir-8286r1", "ir-8286ar1", "ir-8286cr1"] }
```

#### `citationAllowlist` — an argument, never an off switch

Top-level in `sources.json`. Each entry needs a `designation` **and a non-empty `reason`**; an
entry with an empty reason **fails the run**. Without that rule the allowlist would be a way to
switch C6 off one line at a time, while reading as considered judgement.

```json
"citationAllowlist": [
  { "designation": "iso-27001",
    "reason": "Named in the evidence-tier table as a KIND OF ARTIFACT a vendor hands over — 'ISO 27001 certificate with its Statement of Applicability' — not a citation to the standard's text. CAC also holds no ISO licence. Permanent, not pending." }
]
```

A good reason says why the designation is **not a source this skill relies on**, or why it
cannot be verified. "Pending verification" is a legitimate reason exactly once; a repo full of
them means C6 is being routed around rather than answered.

---

### RW-1.9 The do-not-cite list guards the citation that has not been written yet

**A manifest watches what a skill cites. It cannot see a withdrawn publication the skill does
not cite** — and that is the more dangerous class, because the defect arrives fresh rather than
sitting in existing text somebody could review.

The worked example: **SP 800-61 Rev. 2 is withdrawn** (SP 800-61 Rev. 3 became final on 3 April
2025). Its four-phase incident lifecycle is the most-quoted structure in incident response and
essentially every secondary source still repeats it. This toolkit cites it nowhere, so there is
nothing in the manifest to stamp — and the first person to write incident-response content will
reach for that lifecycle by reflex.

So `tools/do-not-cite.json` names withdrawn and superseded publications, and **C5** scans shipped
prose for them.

**The rule is not "never write the string."** Naming a withdrawn publication in order to say it
is withdrawn is exactly what this repo should do, and this document does it in the paragraph
above. What fails is the designation with **no withdrawal marker bound to it** — a citation
rather than a caution. Both directions are registered in the self-test, because a ban that also
forbade the warning would be switched off within a week.

#### RW-1.9.1 What "bound to it" means

A marker excuses a citation only when **all three** hold:

1. the marker is on the **same line** as the citation;
2. the marker is in the **same clause** — a clause ends at `.` `!` `?` `;` or a table-cell `|`,
   never at a comma or a dash, and never at a full stop inside the citation itself or one
   closing an abbreviation before a number (`Rev. 2`); and
3. of every watched publication **in that clause**, the one nearest the marker is this citation.

For an author, in one sentence: **put the warning in the same sentence as the citation.**

This replaced a proximity window that failed open four ways (BL-194). Clause binding arrived
later and separately, and why is worth recording. Rule 3 is a *comparison*, and a comparison
needs something to compare against — so when the citation was the only watched publication on
its line it was compared with itself, `mine <= mine` held, and rule 3 passed vacuously. The rule
collapsed to rule 1, and this sentence shipped clean for three releases:

> *The predecessor platform was retired. Follow SP 800-61 Rev. 2 for incident handling.*

The rule had been designed, documented and worked through against **two** publications, where
"nearest" means something. At one, the word has no referent. Rule 2 supplies the absolute
binding that rule 3 cannot (BL-201).

**The general lesson, which outlives this rule.** Three guards here have now failed the same
way: `[ -z "$res" ]` could not tell a clean scan from a crashed one (BL-121); `len(bounds) == 1`
could not tell a missing anchor from a legally excluded one (BL-176); and `all(...)` over a
single candidate could not tell nearest from only (BL-201). Each reads as discriminating and
stops discriminating when its input is minimal. **Read a check for what it does at n=0 and n=1,
not at n=typical** — and prove it by breaking it, because all three returned the right answer on
every case their authors thought to write.

**Two entries carry traps worth reading before using the list:**

- **SP 800-171 Rev. 2 runs both ways.** Withdrawn by NIST, and still contractually live under
  DFARS clauses that name it by revision. A defense contractor told it is irrelevant has been
  misled as badly as one told it is current NIST guidance.
- **An unverified ban is as bad as an unverified citation.** The seed list for this file carried
  two errors — it conflated SP 800-53A with SP 800-53's patch schedule, and listed SP 800-100 as
  withdrawn when CSRC reports it final. Both were caught by checking. Candidates that could not
  be confirmed are recorded under `notYetVerified` and are **not enforced**.

---

## The three decisions of 2026-08-09

Three questions had sat open across several releases. All three are now rules in
`check-sources.py`, because a decision that lives in a chat log is a decision the next reader
has to re-make.

### RW-1.11 An unverified row ships. It does not fail the release gate.

**Decided: keep the gate as it is.** An unverified row is allowed, must never be `gated`, must
say why, and is counted on every run.

The alternative — failing the release on any unverified row — sounds stricter and is not. It
pressures whoever is trying to ship into stamping `checkedBy: "claude-code"` on a row nobody
read, which converts a **visible gap into an invisible lie**. This manifest exists to prevent
exactly that trade.

The cost is that `whyUnverified` is now load-bearing: it is the only thing separating *"we
looked and it is paywalled"* from *"nobody has got to it"*. So a placeholder there — `TODO`,
`n/a`, `pending` — **fails**. A first draft also rejected anything under twelve characters and
so rejected `paywalled`, which punishes concision rather than emptiness and would have taught
authors to pad; the floor is six.

### RW-1.12 `checkedBy` stays machine-honest, and a person may counter-sign beside it

**Decided: both, meaning different things.**

| Field | Answers |
|---|---|
| `checkedBy` | who **read** the source |
| `reviewedBy` + `reviewedOn` | who **accepted** that reading |

Replacing `claude-code` with a person's name would be false provenance — an agent opened the
publisher's page, and a manifest whose whole claim is *"somebody read the primary source"* must
not misreport who. Dropping the field for a human-only signature would lose the record of a
real check.

A machine may not countersign its own reading; a counter-signature needs a date, because an
endorsement that cannot age is the one thing this manifest does not measure.

**The count prints every run, and it is currently zero.** An honest number, and the point of
printing it.

> ⚠️ **This sentence used to end "zero of 45", and the 45 was wrong.** It was typed once and
> never moved: the item title said **51**, CHANGELOG entries said **52**, and the live tree on
> 2026-08-11 held **55**. Nothing was lying — **the CHANGELOG numbers were each correct on the
> day they were written**, and only this line was stale, because prose does not get recomputed.
> **So the denominator is no longer restated here.** `check-sources.py` prints it every run and
> `--report` prints it per row; a hardcoded total in a document is precisely the drift this
> standard exists to catch, one level up.

#### What a counter-signature asserts — decided 2026-08-11 (BL-228)

> **"I read the machine's reading and accept it."**

Not a re-verification of the primary text, not bare accountability. The middle claim, and it
gets its own state so it is confused with neither neighbour:

| state | meaning |
|---|---|
| `unverified` | no primary source has been opened; the row says why in `whyUnverified` |
| `claude-code` | machine-verified against the primary source, and **not** human-reviewed |
| `countersigned` | a named person read the machine's recorded reading and accepted it |

⚠️ **`countersigned` is NOT a read of the primary source.** The reviewer checked that the claim,
the locator and the version are consistent with **what was recorded**; they did not
independently open the instrument. That sentence is load-bearing — without it a reader, or
the maintainer in two years, takes a counter-signature for a read. This is the field where the
temptation to overclaim is largest, so the wording lives once in `STATES` in `check-sources.py`
and is quoted at every surface rather than paraphrased at each one.

**The state is DERIVED, not stored.** `checkedBy` still records who *read* and `reviewedBy` who
*accepted* — RW-1.12's first half stands, and no third `checkedBy` value was introduced, because
that would erase the record of the machine's read exactly as replacing it with a person's name
would have. `unverified` outranks a counter-signature: a countersigned unverified row reports
`unverified`, because endorsing a reading nobody made is still not a read.

#### ⛔ A counter-signature does NOT clear `gated`

`gated: true` on a `checkedBy: unverified` row is refused because the gate would time a check
that never happened — and **a counter-signature does not open the instrument**, so for a
permanently unreadable source the check still has not happened. The refusal names the
signature explicitly when one is present, so nobody concludes they mistyped it.

**BL-242's local verification is a different thing and does clear it** (the maintainer, 2026-08-11):
there a licensed deployment holds the actual text and the wording is checked against it, so a
check *has* happened. **Keep the two apart.** If they converge, this widens into *"any row can
claim to be gated"*, which is the failure the refusal exists to stop.

#### The limit that ships on the artifact

> A counter-signature is **one named person's review** of what was recorded. It is **not** a
> firm's sign-off, **not** an independent audit, and **not** counsel's opinion.

A solo founder's signature is one person's review, and an unqualified *"countersigned"* beside a
regulatory citation reads to an auditor or a buyer like something that was bought and was not.
Printed by `check-sources.py` whenever the count is non-zero, and always by `--report`.

**Not in scope here: signing the rows.** The machinery ships; the values stay at zero until a
person sits down and signs.

### RW-1.13 365 is the house default; a deviation must say why

The question asked was *"does 365 days suit the SEC rule?"* The honest answer is that **nothing
had ever decided** — every gated row in the repo carried 365, all twenty-odd of them, because
it was typed once and copied.

So the burden is inverted onto the only case where a burden is useful. The default needs no
defence. **A deviation requires `intervalBecause`**, and `intervalBecause` on a default-interval
row also fails, because a justification there reads as a deviation that is not one.

Applied: the eight **disclosure-clock** rows — SEC cyber rule, Item 106, Reg S-T 13, NIS2 Art.
23, DORA RTS 2025/301, FCC CPNI — move to **180 days**. The harm from a missed amendment there
is a late filing and it is asymmetric: nobody is penalised for reading the rule too often. The
operative text is comparatively stable, the staff interpretation around it is not, and it is
the interpretation that moves a deadline.

The rule found an unexplained 180 on `nist-csf/cyber-ai-profile` on its first run — set before
this rule existed, with no reason recorded. The cadence was right and now says so.

## RW-1.14 A correction is a claim, and gets checked like one

Added 2026-08-10 after a correction shipped that was wrong about the same passage it was
correcting.

A pass over `ciso-board-translation/references/regulatory-receipts.md` recorded that *Brewer v.
Turner* contains **no information-systems analysis at all**, and supported it with a count: the
phrase appeared **zero** times, as did two others. On the strength of that, a shipped paragraph
was condemned as asserting a holding the opinion does not contain, and the row's provenance in
`sources.json` was updated to say so.

The opinion says the opposite. The plaintiff pleaded both theories; the court addressed the
information-systems theory *"in short order"* and held there was *"no straight-faced argument
that Regions lacked an information system."* The count was real. What it counted was the **text
extractor**, which renders the phrase `i nformation - s ystems` — so a literal search for
`information systems` finds nothing, and finds nothing whether or not the opinion contains it.
The same search run on the squeezed text returns three.

Three rules follow, and they are cheap:

1. **A negative finding from extracted text is not a finding.** Absence of a string proves the
   string absent from *that extraction*. Before recording a zero, re-run it squeezed — strip
   everything but letters from both needle and haystack — or search for a term that must
   co-occur, to confirm the extraction contains the region at all.
2. **A zero that overturns something already shipped needs a second, differently-shaped
   check.** The asymmetry is deliberate. A positive finding is self-evidencing, because you can
   quote it; a negative one is only as good as the search that produced it, and the cost of
   being wrong is highest exactly when it is being used to delete somebody's earlier work.
3. **Correcting a characterisation means sweeping every sentence derived from it, in both
   directions.** The forward sweep — *does anything still repeat the old claim?* — was the one
   anticipated, and it was worth running: it found two live sentences overstating what *In re
   TransUnion* and *Marchner* do with *Bingle*. The backward sweep — *is the correction itself
   sound, and what did it wrongly delete?* — is the one that was skipped, and it is the one
   that mattered.

The provenance now carries the withdrawal rather than a quiet edit: the false statement is
named in `sources.json` as withdrawn, with the reason it was believed. A correction that
disappears teaches nobody why the check exists.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
