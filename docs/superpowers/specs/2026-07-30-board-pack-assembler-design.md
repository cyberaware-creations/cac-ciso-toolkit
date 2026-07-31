# board-pack Assembler — Design Spec

**Date:** 2026-07-30 (rev b — decisions locked)
**Status:** Design approved. Skill #1 in the next-skills sequence — **built last, by design.** The capstone that turns the section producers into the quarterly board deliverable.
**Product family:** Cyber Aware Creations (CAC) / Limen Labs
**Part of:** `cyber-aware-creations` (v0.5.1)
**Depends on:** the section-contract seam already shipped in `ciso-board-translation` (the `board.json` sidecar) and consumed by `risk-register` + `nist-csf`; extended by `metrics-register` (#2), the standalone `exceptions-register` (#3), and `incident-materiality` (#4).
**Realizes:** the "PPTX board pack" / "true PDF board pack" items parked across the register and csf designs.

---

## 0. Why last, and why thin — READ FIRST

The board pack is built last because it is an **assembler, not a system of record.** It owns no data. Every fact in it already lives in an underlying store (`.rr`, `.csfa`, `.mtr`, `.exc`, `.inc`) and is already translated to board language by `ciso-board-translation` via the `board.json` section objects. The assembler's job is the part none of the producers do: **stitch the sections into one coherent story, in one deliverable format (PPTX/PDF), with a single through-line and a consolidated set of decisions.**

Building it last means it can assume stable, structured inputs. That assumption is safe *because* #2/#3/#4 were each specced to emit the section contract — so "assemble last" costs nothing to re-plumb. This spec's main risk is scope creep: any time the assembler is tempted to *compute* or *re-translate* a section, that logic belongs back in the producing skill. The assembler consumes; it does not re-derive.

---

## 1. What this is

A skill that produces the **quarterly security board pack** — cover, executive through-line, per-topic sections (posture/framework, risk, metrics, acceptances & exceptions, incidents), consolidated decisions, and QoQ trend — as a polished PPTX and/or PDF, assembled from the section objects the other skills emit and narrated as one story by `ciso-board-translation`.

It answers the CISO's highest-stakes recurring deliverable: *"give me the board deck/report for this quarter, consistent with everything in my register, my CSF profile, my metrics, my acceptances, and any incident — in one narrative the board will act on."*

---

## 2. Architecture

New `skills/board-pack/`:
- **SKILL.md** — one core workflow (assemble a pack for a period/audience) + configuration. Neutral-professional voice.
- **`scripts/assemble_pack.py`** — the **deterministic assembly**: collect the section objects, order sections, **deduplicate and consolidate the `decisions[]`** across sections, compute cross-section headline counts (e.g. "9 over-appetite risks, 6 acceptances due for re-validation, 1 material incident"), roll QoQ deltas from each store's latest snapshot, and enforce placeholder-on-missing. It **never writes board prose** — that comes from `ciso-board-translation`.
- **`references/`** — `pack-structure.md` (section order, the through-line rules, audience variants board vs audit-committee), `section-contract.md` (**the canonical, versioned definition of `*.board.json`** — promoted here from documentation scattered across producers to the enforced contract), `brand.md`, `report-layout.md`.
- **`assets/`** — Limen-branded PPTX template + PDF layout.
- **Output via the `pptx` and `pdf` skills** (the platform document-format skills) — the assembler builds content; those skills build the file.
- **`evals/`** — `assembly.sh` (ordering, decision-dedup, count rollups, placeholder behavior over golden section fixtures), board-safety over the finished pack, trigger accuracy.
- **`examples/`** — a full set of section fixtures + an assembled example pack.

---

## 3. Scope

**One core workflow:** assemble a board pack for a given period and audience from the configured sources.

**v1:**
- **Source manifest** — which stores to include (`register.rr`, `profile.csfa`, `metrics.mtr`, `exceptions.exc`, `incidents.inc`), the period/snapshot to pull, the audience (board | audit-committee), and each source's `--translations` sidecar.
- **Orchestrated section production** — invoke each producer's executive path to (re)emit its `board.json` + HTML section, or consume already-emitted section objects. The assembler validates each against `section-contract.md`.
- **The through-line** — a single executive summary reconciling all sections into one posture story with a trend, composed through `ciso-board-translation` (fed the collected section summaries + cross-section counts). This is the assembler's signature value: not five stapled reports, one narrative.
- **Consolidated decisions** — dedupe/merge every section's `decisions[]` into one "decisions the board needs to make this quarter" slide/page (the thing a board actually votes on).
- **QoQ rollup** — cross-store "what changed since last board review," from each store's latest snapshot diff.
- **Assembled sections** — posture (CSF), risk, metrics, acceptances & exceptions, incident (included only if present).
- **Output** — PPTX **and** PDF, Limen-branded, footer + "Not affiliated with NIST" on every page; the incident section carries the not-legal-advice line.
- **Placeholder-on-missing** — a section whose translation slot is unfilled renders the marked placeholder; the assembler **never fabricates** a summary or a number to complete the pack.

**v2:** speaker notes generation; an appendix of the operational detail behind each section; a "board question prep" annex from `ciso-board-translation`'s question bank; multiple templates/brands; a diff pack ("what changed since last quarter" as its own short deck).

**Parked:** live data connectors; direct delivery to a board portal; non-security sections.

---

## 4. The section contract (promoted to enforced, versioned)

The `board.json` envelope, already shipped and consumed by two skills, becomes the assembler's formal input contract (`references/section-contract.md`), versioned so producers and assembler evolve together:

```
{
  "section":  "risk" | "posture" | "metrics" | "exceptions" | "incident",
  "executiveSummary": string,               // one paragraph, board language, with a trend
  "<itemsKey>": { "<id>": string, ... },     // per-item one-liners; key is risks(+themes)|gaps|metrics|acceptances+exceptions|incidents
  "decisions": [ string, ... ],              // section-level asks, each ends on fund/accept/decide
  "asOf": "YYYY-MM-DD",
  "contractVersion": 1
}
```

Exact per-section keys (defined once in `section-contract.md`): `risk`→`risks`(+`themes`), `posture`→`gaps`, `metrics`→`metrics`, `exceptions`→`acceptances`+`exceptions`, `incident`→`incidents`. Rules carried verbatim from the shipped sidecar: nested per-item maps (a flat map silently reverts to placeholders), one sentence per key in board language, guardrails apply, placeholder beats fabrication. The assembler validates `section`, `contractVersion`, nesting, and `asOf` alignment across sections (mismatched `asOf` is a surfaced warning — sections from different dates in one pack is a real error a CISO wants caught).

---

## 5. Method — what the assembler adds that no producer does

- **One story, not five reports.** The through-line reconciles sections ("the framework gap in Recover, the top residual risk, and the untested-backup metric are the same story") — a cross-section synthesis only something seeing all sections can write. Composed through `ciso-board-translation`, fed the section summaries + counts, never hand-rolled.
- **Consolidated, deduped decisions.** Boards act on decisions; scattered per-section asks bury them. Merging them into one list is the assembler's highest-value deterministic step.
- **Cross-section honesty checks.** Mismatched `asOf`, a section present with no data, a decision with no owner — surfaced, not smoothed over.
- **Format.** The producers emit HTML sections and JSON; the board wants a deck and a PDF. The assembler owns the PPTX/PDF build (via the format skills), which no producer does today.

---

## 6. Composition

- **`ciso-board-translation`** — the through-line executive summary and any cross-section narrative; the single source of board voice, keeping every pack consistent.
- **The five producers** — `risk-register`, `nist-csf`, `metrics-register`, `exceptions-register`, `incident-materiality` — each contributes its `*.board.json` section and HTML.
- **`pptx` / `pdf` platform skills** — the deliverable file build.
- The assembler is the only skill that composes *all* of them; it is the integration test for the whole toolkit.

---

## 7. Testing

- **Deterministic:** `assembly.sh` over golden section fixtures asserts section ordering, decision dedup/consolidation, cross-section count rollups, `asOf`-mismatch detection, and **placeholder-on-missing** (a missing translation must render a visible placeholder, never a fabricated line — the highest-value anti-vacuity check here).
- **Board-safety:** the finished pack passes all guards (no confidence vocabulary, no catastrophizing, disclaimers/footers present, not-legal-advice on the incident section).
- **Integration:** an end-to-end run over example stores for all five producers → one assembled PPTX + PDF; the toolkit's top-level integration test.
- **Trigger accuracy:** "build the board pack / assemble the quarterly board deck / put together the audit-committee pack" route here; "translate this one metric" or "run a risk review" route to their own skills.

---

## 8. Open decisions — RESOLVED (2026-07-30)

1. **Skill name** → **`board-pack`.**
2. **Config** → **`pack.manifest.json`** (sources, period, audience, translations paths, template).
3. **Invoke producers or consume sections?** → **both, with consume as the contract** — can orchestrate producers to refresh sections, but its formal input is the validated `*.board.json` set.
4. **PPTX and PDF, or one?** → **both** in v1.
5. **Audience variants** → **board** and **audit-committee** in v1.
6. **Contract versioning** → **`contractVersion: 1`** now, retrofit the two shipped consumers (Phase 0).

---

## 9. Guardrails

- Assembler owns no data and computes no section content; it consumes the contract. Any temptation to compute belongs in a producer.
- Placeholder beats fabrication — never invent a summary, number, or decision to finish a pack.
- One voice: all board prose through `ciso-board-translation`.
- Surface cross-section inconsistencies (`asOf` drift, empty sections, ownerless decisions) rather than hiding them.
- Footer + "Not affiliated with NIST" on every page; not-legal-advice on the incident section; discoverability caveat preserved where risk/exception/incident links appear.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
