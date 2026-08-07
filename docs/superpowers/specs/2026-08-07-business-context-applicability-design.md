# business-context Skill — Design Spec (CAC-AP-1)

**Date:** 2026-08-07
**Status:** **Written retrospectively.** The skill shipped in v0.30.0 (#62) and was extended to `board-pack` in v0.33.0 (#68). This document was reconstructed afterwards — see §0.
**Product family:** Cyber Aware Creations (CAC) / Limen Labs
**Part of:** `cyber-aware-creations` (v0.33.0)
**Normative contract:** `skills/business-context/references/applicability-contract.md`. **That file governs.** This one explains why it says what it says.
**Companion to:** `docs/superpowers/plans/2026-08-06-exposure-lifecycle-plan.md` (CAC-EL-1, the sibling contract), `skills/incident-materiality/` (the consumer that proved this one).

---

## 0. Provenance of this document — READ FIRST

This spec was written **after** the code, not before it, and it exists because an audit went looking for the design record and found none.

The implementation plan cited a design doc — `strategy/business-context-skill-design-2026-08-07.md`, "rev b — decisions locked" — as the source of decisions D-1 through D-5, and required reading it in full at pre-flight. That file was never committed to this repository and does not exist in it. `business-context` was therefore the only skill owning a normative cross-skill contract with no committed design record, while the sibling contract CAC-EL-1 has a full plan in `docs/superpowers/plans/`.

What that means for anyone trusting this document:

- Every decision below was **recovered from the shipped source and its comments**, and every behavioural claim was **executed** during the audit of 2026-08-07 rather than read and believed. Where a rationale survives only as a code comment, the file and line are cited so you can check it.
- It is **not** a contemporaneous record. It cannot tell you what was considered and rejected, only what was chosen and why the code says it was chosen. Anywhere the reasoning below is thinner than the sibling specs, that gap is real and is the cost of writing this late.

The lesson is worth keeping: the work was sound and the record of it was missing, which is a failure mode that looks like nothing at all until somebody needs to change the contract.

---

## 1. What this is

A store of **the organisation's own facts** — `<name>.biz` — and the **applicability profile** that lets every other skill in the suite ask only the questions that apply to this organisation.

Every skill here already asks the CISO to declare something and then refuses to invent it: `risk-register` takes an appetite band, `metrics-register` takes target/warn/critical, `exceptions-register` demands an approver and a justification, `incident-materiality` walks six factors and emits no verdict. The discipline was right and one thing was missing — anywhere to record **why the declared number is that number**. An appetite of `medium` traced to nothing; a materiality assessment weighing financial impact against a revenue base that lived in somebody's head.

This skill holds those facts, plus the profile. Solved **once, as a contract each skill implements**, rather than five times in five engines.

It answers: *"what is true about this organisation, who said so, on what basis, and which questions does that make it pointless to ask?"*

What it is **not**: an asset inventory, a CMDB, a compliance scoping tool, or anything that **infers**. Being an EU entity does not set DORA scope — a lawyer decides that, and this skill records the decision (`business_context.py:219`).

---

## 2. The problem the contract solves

Without a profile, every skill asks every question. A privately held UK manufacturer works through SEC Item 1.05 batteries; a firm with no OT answers OT scenario questions. The obvious fix — let each skill infer scope from whatever facts it has — is the wrong one twice over: it duplicates the logic five times, and it makes each skill's *guess* look like the organisation's *declaration*.

So the narrowing lives in one place, and it is declared rather than derived.

**The organising idea: the profile narrows the question set and never answers a question.**

---

## 3. The contract (CAC-AP-1)

Six clauses, normative in `references/applicability-contract.md`. Two of them carry the whole thing, and **both are the opposite of the obvious default** — which is precisely why they are written down rather than left to each implementer's instinct.

### The two that carry it

**§2.2 — Absence asks MORE, never less.** A missing profile, a missing flag, or a flag whose `value` is `None`, means *not declared* — never *does not apply*. Truthiness is banned: `False` is declared-not-applicable, `None`/absent is undeclared, and collapsing them silently narrows every assessment into something that **looks complete and is not**.

> This is the single failure mode most likely to ship undetected, because its symptom is a clean-looking result. `applies()` distinguishes the two explicitly; `business_context.py` self-test cases at :994–1067 exist for this clause alone.

**§2.3 — The subject outranks the profile, in both directions.** A subject-level declaration is applied *after* the profile and may **re-add** a battery the profile removed, or **remove** one the profile kept. An organisation that declared no AI in use still gets the full AI battery on a vendor whose own record says it processes data with a model.

### The other four

| | |
|---|---|
| **§2.1** | One profile, one owner. Not per-skill copies that drift. |
| **§2.4** | Every skipped battery is **recorded and visible**, with the flag, the declarer and the date — rendered as a sentence a consumer embeds verbatim. An artifact that silently omits a question is worse than one that asks it. |
| **§2.5** | The profile is **frozen by snapshot**. A determination made in Q1 was made against Q1's perimeter, and must still say so in Q4. |
| **§2.6** | **Transport is data, never imports.** No skill imports another. The payload travels as JSON via `--context`. |

### The payload

`business_context.py export` emits one flat, versioned object: `contractVersion` (`CAC-AP-1`), `schemaVersion`, `orgName`, `profileVersion`, `profileReviewedOn`, `profile`, `revenue`, `crownJewels`, and a pre-decided `applicability` map per skill. `profileVersion` is the last snapshot label, or the literal `unreviewed` — **present either way**, so a consumer never has to distinguish "no version" from "no key".

A consumer handed a raw `.biz` instead of a payload is refused, and the refusal names the command that produces the right thing.

---

## 4. The store

`.biz`, JSON, `schemaVersion: 1`. Bodies: `meta`, `profile`, `context`, `settings`, `history`, `snapshots`.

**Provenance on every declared value.** The wrapper is `{value, declaredBy, declaredOn, basis}`. A bare scalar is **legal on read** and reported as unattributed — never coerced on load, because validation guards *writes* and a `.biz` carrying a bad value must still open.

**The profile is a declared enumeration, not a gate.** Fifteen documented flags (`listedEntity`, `doraScope`, `nydfsScope`, `aiInUse`, `otPresent`, `regulatedDataHeld`, sector, headcount, jurisdictions…). An **unknown flag is accepted with a warning, not refused** — the regulatory perimeter list will outgrow anything written here, and a register that refuses tomorrow's regime is worse than one that records it unrecognised. The warning names the §2.2 consequence: consumers that do not know the flag will ask their full question set.

**Refusals leave the file byte-identical.** `declare` without `--basis`; a crown jewel without `--at-stake`; `review` without both `--label` and `--why`; `init` onto an existing path. Each raises before the file is opened. The `init` refusal says why in plain terms: this file holds the revenue base, the crown jewels and the board's own words, and there is no version of losing it that is recoverable.

**Board tolerance is stored verbatim.** Never paraphrased, never summarised on write — quotes and non-ASCII round-trip unchanged. It is the board's sentence, not a rendering of it.

---

## 5. Revenue — exact stored, band derived (D-2)

The materiality denominator needs the **exact** figure. What circulates in a board pack should be a **band**.

So the store holds `{exact, currency, fiscalYear, …provenance}` and **never a band**. The band is computed at render time from a module-level ladder, so it cannot drift from the figure it describes:

`<10m · 10-50m · 50-100m · 100-250m · 250-500m · 500m-1bn · 1-5bn · >5bn`

**Every boundary belongs to the band above it** — `10,000,000` is `10-50m`, not `<10m`. A ladder that puts a boundary in the band below reads as understatement exactly where precision matters.

The `framing` renderer bands by default. `--render-revenue exact` shows the figure **and writes the override into the provenance line**, so a reader can tell which artifact they are holding.

---

## 6. The guardrail — no derived materiality

The reason this skill is dangerous, and the check that makes it safe.

Once a revenue base is a machine-readable number sitting next to an incident's financial impact, the next commit computes a percentage, and the one after that compares it to a threshold — and the suite has quietly started making the legal judgment `incident-materiality` refuses to make by design.

`evals/no-derived-materiality.sh` (7 checks) stops it two ways, because either alone is weak:

1. **Behavioural** — no key in any output matches `materialityThreshold|pctOfRevenue|materialPercent|revenueShare`.
2. **Static** — no shipped `.py` divides or percentages the revenue base, *including through a local it was first assigned into* (`_derivedcheck.py` follows bindings to a fixed point; a check that only matched `impact / revenue` missed `exact = revenue.get("exact")` then `impact / exact`).

The guard is **proven in both directions**: the suite poisons a copy of the skill with the exact line it exists to stop and fails if the poison goes undetected. A guard never seen to fail is not known to work.

The revenue base reaches `incident-materiality` as **a stated figure the human weighs**. No threshold is derived from it, and that skill still emits no verdict.

---

## 7. Escalation

CAC-EL-1 §1.3 shape, `subjectKind: "context"`, **one trigger only: `profile-stale`** (default cadence 365 days, a setting).

This is the one escalation in the suite that is not an exposure. A crossed band or an expired acceptance says something got worse; this says **the lens every other skill is looking through has not been checked**, so the exposures they report may be measured against a perimeter that moved.

Flag-never-block, per §1.2: a stale profile still exports, still narrows, still renders.

**A never-reviewed store escalates nothing.** It is not stale, it is new — there is no earlier review to compare against and the owner has nothing to act on.

**`fact-unattributed` is deliberately deferred (D-3).** A freshly built `.biz` is nearly all unattributed, so shipping it would escalate on almost every field of a first run and teach the owner to skim the list — which costs more than the check is worth. Revisit with volume data from a real file.

---

## 8. The locked decisions

| | Decision | Why it is load-bearing |
|---|---|---|
| **D-1** | **Framing, not a sixth board section.** `board-pack`'s `section` enum stays at five values; this supplies cover, opening context, and a provenance stamp naming the profile version. | Adding a sixth section would have forced a change on every producer and every renderer for something that is context, not content. |
| **D-2** | **Revenue exact, rendered as a band.** | §5. The band is derived so it cannot drift. |
| **D-3** | **One escalation trigger in v1.** | §7. Noise on first run destroys the habit of reading the list. |
| **D-4** | **Manual declaration.** No ingestion of published reports. | An ingested fact has no declarer, and §2.2's whole discipline rests on knowing who said it. |
| **D-5** | **Single entity in v1**, with two forward-compatibility measures. | Below. |

### D-5 and the two measures

Single-entity is right for the firm this suite serves best — one company, however many offices — and wrong for a group with several regulated subsidiaries, where perimeter is genuinely per-entity.

**Measure 1 (shipped).** `profile` sits at the **top level** of the document, never nested under an entity. When groups arrive, a future `entities[]` **inherits** from the top-level profile, each entity carrying only the flags that differ. Nest the profile under an entity now and that reversal costs a migration. Recorded as a deliberate reservation in `business_context.py:97–106` and `references/schema.md:128`.

**Measure 2 (owed, not shipped).** The vendor skill must carry an optional `entityRef` on every vendor record **from its first commit**, defaulting to the single org. This belongs in the vendor plan **as a task, not a note** — without it, every vendor record written before groups are supported has to be revisited.

---

## 9. What proves it

The contract was proved against **exactly one consumer** before others were built on it — the sequencing that worked for CAC-EL-1, where `board-pack` was built against `risk-register` alone first.

`incident-materiality` was the right proof because its question set is *genuinely* conditional: SEC Item 1.05 turns on a listed entity, DORA windows on declared DORA scope, and its financial factor is exactly where the revenue base was always missing. A consumer whose narrowing was token would have proved nothing.

Verified on the 3.9 floor (audit of 2026-08-07, all executed rather than asserted):

- **`--context` absent ⇒ byte-identical output.** Diffed against the pre-change commit `ebd27cc`: 415 lines added to `incident_analysis.py`, `--out` JSON and store identical byte-for-byte.
- **§2.3 works per subject.** With the profile declaring not-listed, an incident declaring a listed subsidiary asks the SEC battery while its three siblings skip it.
- **§2.4 provenance survives to the record.** Each skip carries battery, label, flag, source, declarer, date and basis.
- **No percentage of revenue appears anywhere** in the output.
- Engine self-test 154 checks; consumer contract suite 58; guardrail 7; board-safety 10; 55 shipped files compile on Python 3.9.6.

`board-pack` reads the profile as of v0.33.0 — by **subprocess**, per §2.6, with every failure path returning a provenance note rather than raising.

---

## 10. Not in scope — the follow-on

- **`--context` for the four remaining producers** (`risk-register`, `metrics-register`, `exceptions-register`, `nist-csf`). Deferred until one consumer proved the shape; that condition is now met. Question sets for `risk`, `metrics`, `exceptions` and `vendor` are already defined in the engine; **`nist-csf` has none yet**, and `board-pack`'s provenance page names all four as not reading a profile.
- **D-5 measure 2** — `entityRef` in the vendor skill, from its first commit.
- **`fact-unattributed`** escalation, revisited with volume data from a real `.biz`.
- **Ingestion from published reports** (D-4, v2).

---

## 11. Handling

A `.biz` concentrates the revenue base, the crown jewels and the board's own words in a single document. That combination is **more sensitive than any of the registers it feeds** — it names what the organisation cannot afford to lose and what its board said about losing it. `SKILL.md` carries the handling note; it is not a file to mail around.

---

*A Cyber Aware Creation · Not affiliated with NIST. This tool is not legal advice.*
