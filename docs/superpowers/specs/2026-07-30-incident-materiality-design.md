# incident-materiality Skill — Design Spec

**Date:** 2026-07-30
**Status:** Design draft. Skill #4 in the next-skills sequence (2→3→4→1). **Standalone skill** (the one of the four that most warrants its own object). Episodic producer that also feeds the board pack.
**Product family:** Cyber Aware Creations (CAC) / Limen Labs
**Part of:** `cyber-aware-creations` (v0.5.1)
**Companion to:** `research/feasibility-kill-report-2026-07-18.md` (Q2/Q3 — the materiality decision point and its litigation limits), `ciso-board-translation` (composition + receipts), `risk-register` (incidents realize tracked risks).

---

## 0. Framing — READ FIRST

The kill report found exactly one *decision point* the disclosure regime genuinely creates: the **incident materiality determination**. **SEC Item 1.05** (8-K) requires disclosure of a material cybersecurity incident, and the determination must be made "**without unreasonable delay**," with the 8-K then due **four business days** after the company decides the incident is material (Item 1.05 expressly excuses technical detail). **DORA** adds a parallel, stricter classification-and-reporting clock for financial entities (initial / intermediate / final reports on defined windows). These are real, dated obligations that turn on a *judgment* a CISO must make and defend.

Three hard constraints the kill report imposes on how this is built and sold:
- **Do not sell SEC fear.** SEC cyber-disclosure enforcement pulled back — SolarWinds/Brown was dismissed with prejudice in Nov 2025, and the rules face rescission pressure. Fear-based framing is disqualifying (and violates the `ciso-board-translation` guardrail). This is a *preparedness and defensibility* tool, not a scare tactic.
- **Documentation is a double-edged sword.** Caremark rewards a documented oversight *process*; SolarWinds shows that granular internal records which contradict public statements are the *sword*. So the record must be governance-level, factual, and aligned to what is actually disclosed. Counsel belongs in the loop.
- **This is decision-support, never legal advice.** A materiality determination is a legal judgment. The skill *structures and records* it; it does not *make* it, and it says so, prominently and every time.

This skill is **episodic** — it fires when an incident occurs, not quarterly — but when an incident happened in a reporting period, its record becomes the incident section of the board pack (#1).

---

## 1. What this is

A structured, defensible **materiality-determination and disclosure-decision workspace with a memory**. Given the facts of a security incident, it walks the CISO (with counsel) through the factors a materiality judgment turns on, tracks the regulatory clocks that start ticking, records the determination and its rationale as an append-only history as facts evolve, and produces the board/audit-committee narrative and the disclosure-decision artifact — all in language aligned to what the company will actually say publicly.

It answers: *"is this incident material, on what basis, who decided, and by when must we act — and can we show a regulator and a court that we made that call deliberately and consistently?"*

What it is **not**: a SIEM, a ticketing system, an incident-response runbook, or a substitute for counsel. It does not detect, triage, or remediate — it structures the *governance decision* around an incident and records it defensibly.

---

## 2. Architecture

New `skills/incident-materiality/`, mirroring the stateful-skill pattern:
- **SKILL.md** — two workflows (open/assess an incident determination; update as facts evolve → disclosure decision) + reporting. Neutral-professional voice; the not-legal-advice and no-catastrophizing guardrails front-and-centre.
- **`scripts/incident_analysis.py`** — the **deterministic** part is the *clocks*, not the judgment: business-day math for the Item 1.05 four-day window from a determination date; DORA report-window tracking; status bands (determination pending / disclosure due / filed / closed). The **factor assessment is guided judgment, recorded, never auto-decided** — the script never outputs "material: yes." `self_test` covers the date/clock math (the parity-critical part; an unpadded date or a weekend miscount is exactly the failure that matters here).
- **`references/`** — `materiality-factors.md` (the factor framework + how each is assessed, with honest limits), `disclosure-clocks.md` (SEC Item 1.05 + DORA windows, business-day rules, and their caveats), `schema.md` (the incident store), `report-layout.md`, `brand.md`.
- **`renderers/`** — an operational determination worksheet + an executive/board incident narrative (`render_board.py --translations`), Limen-branded HTML.
- **`evals/`** — `disclosure-clock.sh` (business-day deadline derivation, anti-vacuity rules), board-safety (no confidence vocabulary; **no catastrophizing** — extend the guard to flag fear framing), trigger-accuracy.
- **`examples/`** — a worked incident determination fixture + a filled `incident.board.json`.

---

## 3. Scope

**Two core workflows:** (A) open an incident and run the materiality determination; (B) update the determination as facts evolve and record the disclosure decision.

**v1:**
- **Incident record** with an append-only determination history (below).
- **Materiality factor framework** — a structured checklist the user assesses (never the tool): financial impact, operational disruption, data affected (types/volume/sensitivity), regulatory/contractual triggers, reputational, and the **aggregation rule** (related incidents considered together — an explicit SEC concern). Each factor: assessment + rationale + who/when. No scoring-to-a-verdict; the determination is the human's, recorded with its basis.
- **Disclosure clocks (deterministic):** from a recorded determination date, compute the Item 1.05 four-business-day deadline; track DORA initial/intermediate/final windows if the entity is in scope. Surface days remaining; flag overdue.
- **Determination states:** `assessing` / `material` / `not-material` / `not-yet-determinable`, each a recorded decision with rationale, revisable as facts change (every change appended, never overwritten — the "when did you know" question lives here).
- **Disclosure-decision artifact** + **board/audit-committee narrative** via `ciso-board-translation`.
- **`incident.board.json`** section producer.
- Cross-link to `risk-register` risks and to accepted risks / exceptions (§7).

**v2:** multi-incident aggregation view; templated 8-K/DORA narrative starters (counsel-reviewed); playbook-timer reminders; import from an IR platform.

**Parked:** actual regulatory filing/submission; jurisdiction expansion beyond SEC + DORA (state breach-notice, NIS2, sectoral) as a later reference pack; anything that reads as automated legal conclusion.

---

## 4. Data model

Light standalone store (proposed `.inc`), one record per incident:
`id`, `title`, `discoveredAt`, `scopeNote`, `factors[]` (each: `key`, `assessment`, `rationale`, `actor`, `ts`), `determination` (`state`, `rationale`, `decider`, `determinedAt`), `disclosure` (`regime` ∈ {sec-1.05, dora, none}, `deadline` (derived), `decision`, `basis`, `filedAt?`), `linkedRiskIds[]` / `linkedExceptionIds[]`, `history[]` (append-only), `notes`.

**Derived-never-stored:** the disclosure deadline (business-day math from `determinedAt`), days-remaining, status bands, "clock started but no determination" flags.

**The append-only determination history is the whole defensibility story** — it's the reconstructable "what did we know and when did we decide" record. Same append-only discipline and canonical-date rule as `risk-register`.

---

## 5. Method — structured judgment, honest limits

- **The tool structures; the human (with counsel) decides.** The factor framework forces completeness and records the basis; it never emits a materiality verdict. This is the `ciso-board-translation` philosophy applied to a legal judgment: supply the scaffold, never the conclusion.
- **The deterministic part is the clock, and it must be exact.** Business-day counting, canonical dates, and the "determination date starts the four-day clock — not the discovery date" distinction are where real mistakes happen; the engine owns these and `self_test` pins them.
- **Receipts with their limits (from `regulatory-receipts.md`):** Item 1.05 turns on a company-specific materiality judgment and excuses technical detail; the rules are under rescission pressure; SEC enforcement has pulled back. DORA's windows are firmer for in-scope entities. Cite each honestly, limit attached; never imply a filing obligation that isn't there.
- **Aligned to public statements.** Every board/disclosure narrative is drafted to be consistent with what the company discloses — the SolarWinds lesson baked in.
- **No catastrophizing, no false comfort.** Present the true picture and the decision; the board-safety guard is extended to fail on fear framing.
- **Not legal advice — stated every time**, with an explicit "involve counsel on the determination and any filing" note. This is both correct and the defensible posture (counsel-in-the-loop).

---

## 6. Reporting

- **Operational:** the determination worksheet — factors assessed with rationale, the determination state and its history, the live disclosure clock with days remaining, open items.
- **Executive/board:** an audit-committee-ready incident narrative — what happened, the materiality determination and its basis, the disclosure decision and timeline, and the governance decision needed — composed through `ciso-board-translation`, aligned to public statements.
- Limen-branded HTML; footer + "Not affiliated with NIST"; a standing not-legal-advice line on every incident artifact.

---

## 7. Composition & the section contract

- **`ciso-board-translation`** — all board/audit-committee prose; the "here's the exposure, here's the decision" move is native.
- **`risk-register`** — an incident often **realizes a tracked risk**; linking them is powerful and honest ("the third-party risk we accepted last quarter materialized"). Cross-link to `linkedRiskIds[]` and to accepted risks / exceptions from skill #3 (`exceptions-register`) — the most damning-or-defensible connection in the whole toolkit, so it must be handled with the discoverability caveat visible.
- **Board-section object** — `incident.board.json`, same envelope, keyed by incident id:

```json
{
  "section": "incident",
  "executiveSummary": "One incident this period reached a materiality determination; disclosure filed within the required window.",
  "incidents": {"I-001": "A vendor breach exposed limited customer contact data; determined not material on [date], basis recorded; no filing required."},
  "decisions": ["Note the determination; approve the proposed control change to the affected vendor relationship."],
  "asOf": "2026-10-01",
  "contractVersion": 1
}
```

  Drop-in section for the board-pack assembler (#1) — present only when an incident occurred in the period.

---

## 8. Testing

- **Deterministic:** `self_test` + `disclosure-clock.sh` pin business-day math, the determination-date-starts-the-clock rule, canonical dates, and DORA windows (anti-vacuity rules from `confirmation-age.sh`).
- **Board-safety (extended):** no confidence vocabulary **and** no catastrophizing/fear framing in any board-facing incident view.
- **Guardrail evals:** every incident artifact carries the not-legal-advice line; no output emits an automated materiality verdict.
- **Trigger accuracy:** "is this incident material / do we have to disclose / start the 8-K clock / draft the audit-committee incident update" route here; general incident-response *runbook* asks do not (out of scope).

---

## 9. Open decisions (RESOLVED 2026-07-30)

1. **Skill name** → **`incident-materiality`** (confirmed).
2. **Store** → standalone **`.inc`** (confirmed): an incident is a distinct object with its own clocks; it *links* to risks rather than being one.
3. **Jurisdiction scope v1** → **SEC Item 1.05 + DORA only** (confirmed); state breach-notice / NIS2 / sectoral as a v2 reference pack.
4. **Factor framework** → a **structured checklist with recorded rationale**, explicitly not a scoring model (confirmed).
5. **Persistence depth** → per-incident record with append-only determination history in v1; multi-incident aggregation view in v2.

---

## 10. Guardrails

- Decision-support, **not legal advice** — stated on every artifact; involve counsel on determination and filing.
- The tool never emits a materiality verdict; the human decides, the tool records the basis.
- No catastrophizing, no false comfort; enforced by an extended board-safety guard.
- Clocks are deterministic and exact (business days, canonical dates, determination-date start).
- Every board/disclosure narrative aligned to public statements (the SolarWinds lesson).
- Receipts carry their honest limits; never imply a filing duty that isn't there.
- Append-only determination history; footer + disclaimers; discoverability caveat visible on risk/exception links.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
