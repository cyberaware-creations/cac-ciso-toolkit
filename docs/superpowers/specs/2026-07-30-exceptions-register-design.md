# exceptions-register Skill — Design Spec

**Date:** 2026-07-30 (rev b — decisions locked; standalone skill)
**Status:** Design approved. Capability #3 in the next-skills sequence (2→3→4→1). **Standalone skill `exceptions-register`** — see the locked-decisions banner.
**Product family:** Cyber Aware Creations (CAC) / Limen Labs
**Part of:** `cyber-aware-creations` (v0.5.1)
**Companion to:** `research/feasibility-kill-report-2026-07-18.md` (this is *the* regulatory wedge it identified), `risk-register` SKILL.md + `references/schema.md` (the acceptance shape this reuses), `ciso-board-translation` (`regulatory-receipts.md`).

---

## ⟶ Decisions locked (2026-07-30) — READ FIRST, overrides the body

Six decisions were resolved with the user; where the original draft assumed a `risk-register` v2 extension, **these win:**

1. **Home → standalone skill `exceptions-register`.** Not a `risk-register` extension. It ships its own `.exc` store, engine, and renderers so the acceptance/exception inventory — and the DORA wedge — is usable by orgs that do **not** run a full risk register. The user accepted the modest duplication this implies.
2. **It is the system of record for acceptances + exceptions.** `risk-register` keeps only a lightweight `accepted` marker on a risk and can **export** an accepted risk into `exceptions-register`; the full lifecycle (justification, approver, re-validation, expiry, the DORA inventory) lives **here**, not in the register. So the `acceptance-revalidated` completion is built in this skill, not added to `risk-register`.
3. **GTM gate (G1) → build the engine now, defer the go-to-market.** The kill report's demand condition (10–15 DORA-scoped interviews) gates the *marketing/positioning*, not the build.
4. **Store extension → `.exc`.** (Was "inside the `.rr` file"; standalone means its own store.)
5. **Two object types, one lifecycle** (unchanged): risk **acceptances** (DORA Art. 3(d) inventory) and **exceptions** (control/policy deviations + compensating controls, NYDFS §500.12/§500.15).
6. **Exceptions unscored in v1**, `deviationFrom` = free text + optional control/standard ref (unchanged).

The body below is accurate for the method, the wedge, the receipts, and the guardrails; read §2/§4 through this banner (standalone store + engine, not register mutations).

---

## 1. What this is

A standalone **defensible-acceptance register**: a system of record for every time the organization knowingly **accepts a residual risk** or grants an **exception to a control/standard**, producing a structured, attributed, expiring, re-validatable record — the artifact DORA and NYDFS assume exists and that free text can't honestly carry. It answers the two questions an auditor or board actually asks: *"on what basis did we accept this, who approved it, and is that reasoning still valid?"* and *"where are we deviating from our own standards, what compensates, and who signed off?"*

It stands on its own (a vCISO can run it without a quantified risk register) and interlinks with the rest of the toolkit by ID.

Two object types, one lifecycle:
- **Acceptance** — an accepted residual risk. The DORA Art. 3(d) inventory. Structured approval + annual re-validation.
- **Exception** — a documented deviation from a control, policy, or standard, with its compensating control and written approval. The NYDFS §500.12/§500.15 artifact.

---

## 2. Architecture

New `skills/exceptions-register/`, mirroring the stateful-skill pattern (its own copy of the machinery — the accepted cost of standalone):
- **SKILL.md** — two workflows (record an acceptance/exception; run a re-validation review) + reporting. Neutral-professional voice.
- **`scripts/exceptions_register.py`** — deterministic engine + persistence: `init`, `accept-add`, `except-add`, `revalidate`, `close`, `export-inventory`, all append-only-history + schema-safe + canonical-date-refusing (patterns ported from `score_register.py`; standard library only). `self-test` asserts reference math against a golden `.exc` fixture.
- **`references/`** — `schema.md` (the `.exc` store), `exceptions.md` (the exception model + compensating-control discipline), `receipts.md` (DORA/NYDFS angles, pointing at `ciso-board-translation/regulatory-receipts.md` — not a copy), `brand.md`, `report-layout.md`.
- **`renderers/`** — operational inventory view + executive board view (`--translations`, emits `exceptions.board.json`); Limen-branded HTML.
- **`evals/`** — `revalidation-lifecycle.sh` (due/overdue/expired banding derived only from events; anti-vacuity rules mirrored from `risk-register/evals/confirmation-age.sh`), board-safety (no confidence vocabulary), trigger-accuracy.
- **`examples/`** — a worked `.exc` fixture + a filled `exceptions.board.json`.

**Small change to `risk-register` (additive, backward-compatible):** keep `accept` as a lightweight "this risk is accepted" marker; add `export-acceptances` that writes accepted risks in the `exceptions-register` intake shape (reusing the existing CSV/interop bridge pattern) so a register user can push acceptances into the SoR. No `revalidate` is added to `risk-register`; that lives here.

---

## 3. Scope

**Two core workflows:** (A) record an acceptance/exception; (B) run a **re-validation review** — surface everything due/overdue, capture "still valid / no longer → close or escalate," snapshot, report.

**v1:**
- **`.exc` store** with `acceptances[]` + `exceptions[]`, append-only history, canonical dates, refusal discipline (no approver/justification/revalidation → refused before the file is touched).
- **`revalidate`** writes the re-validation event (the DORA Art. 3(d)(iv) annual act), resets the clock, keeps the record live.
- **Derived status** for both types — `current` / `revalidation-due` / `revalidation-overdue` / `expired`, from dates + `--today`, distance-from-cadence **never** confidence (inherits board-safety checks 9/10).
- **Inventory export** (`export-inventory`, CSV + JSON) — the DORA evidence artifact.
- **Re-validation review ritual** documented.
- **Board section producer:** `exceptions.board.json`.
- **Cross-links:** `riskIds[]`, `csfSubcategoryIds[]`, `incidentIds[]` (optional).
- **`risk-register` `export-acceptances` bridge** + `accepted` marker.
- Self-test + evals.

**v2:** import an existing exception spreadsheet; delegated-approver model; expiry-driven escalation lists; bidirectional live sync with `risk-register` (beyond the one-way export).

**Parked:** approval/workflow routing (this records decisions, it is not a ticketing system); e-signature.

---

## 4. Data model (`.exc` store)

Top-level: `schemaVersion`, `family` ("exceptions-register"), `meta{clientName, owner, scopeNote, asOf}`, `acceptances[]`, `exceptions[]`, `history[]`, `createdAt`, `updatedAt`.

- **Acceptance:** `id`, `title`, `description`, `approver`, `justification`, `acceptedDate`, `expiryDate`, `revalidationDate`, `status` (`active`|`closed`), `riskIds[]`, `csfSubcategoryIds[]`, `sourceRiskRef?` (when exported from a register), `notes`.
- **Exception:** `id`, `title`, `deviationFrom` (free text or a control/standard ref — `NYDFS-500.12`, `CIS-4.1`, an internal policy id), `compensatingControl`, `approver`, `justification`, `acceptedDate`, `expiryDate`, `revalidationDate`, `status`, `riskIds[]`/`csfSubcategoryIds[]`, `notes`.
- **Change-log events (append-only):** `acceptance-added`, `acceptance-revalidated`, `acceptance-closed`, `exception-added`, `exception-revalidated`, `exception-closed`. Material ones require `--why`/structured fields; refusals leave the file byte-identical.
- **Derived-never-stored:** status band, re-validation due/overdue days, expiry countdown, inventory rollups.

---

## 5. Method — what makes it defensible (and the honest limits)

- **Structured beats free text, but only if enforced.** No approver / no justification / no re-validation date → the record does not exist. That refusal discipline *is* the product.
- **Re-validation is an *act*, not a timer.** `revalidate` records that a human re-checked the reasoning and it still holds, with rationale — the literal DORA Art. 3(d)(iv) requirement. A lapsed clock surfaces the item; it never silently expires the reasoning.
- **Distance-from-cadence, never confidence** — enforced by the board-safety eval.
- **Receipts carry their limits** (from `ciso-board-translation/regulatory-receipts.md`): DORA RTS Art. 3(d) is real but **satisfiable by free text** and exempts Art. 16 simplified-framework entities — cite the RTS, never DORA Level 1. NYDFS requires written approval of compensating controls. **Discoverability caveat is load-bearing:** a permanent, queryable record of accepted risk is a litigation sword if it contradicts public statements (SolarWinds) — keep records governance-level, factual, aligned to disclosures. Surface this; never sell the record as pure protection.
- **Don't invent approvers, justifications, or compensating controls to fill the inventory.**

---

## 6. Reporting

- **Operational:** an acceptances-&-exceptions inventory table — object, what's accepted/deviated, approver, compensating control, status band, re-validation due, expiry; attention lists (overdue re-validation, expired, unowned, no-compensating-control).
- **Executive/board:** the inventory rolled up — "we formally accept N residual risks and M control exceptions; K are overdue for re-validation; here are the ones needing a board decision" — composed through `ciso-board-translation`.
- Limen-branded HTML; footer + "Not affiliated with NIST." The export doubles as the DORA evidence artifact.

---

## 7. Composition & the section contract

- **`ciso-board-translation`** — all board prose; "fund the close, or record the acceptance" is its native move.
- **Board-section object** — `exceptions.board.json`, standard envelope, per-item maps `acceptances{}` + `exceptions{}`, `contractVersion:1`:

```json
{
  "section": "exceptions",
  "executiveSummary": "We formally accept 6 residual risks and 4 control exceptions; 2 acceptances are overdue for annual re-validation.",
  "acceptances": {"A-014": "We accept a 40-day patch window on 9 internet-facing systems; CISO-approved, re-validation due this quarter."},
  "exceptions": {"X-003": "Finance runs without phishing-resistant MFA under a compensating control; the exception expires in 60 days."},
  "decisions": ["Re-validate or withdraw the 2 overdue acceptances; decide whether to extend exception X-003 or fund the fix."],
  "asOf": "2026-10-01",
  "contractVersion": 1
}
```

  Drop-in section for the board-pack assembler (#1) next to `risks.board.json`, `metrics.board.json`, `gaps.board.json`, `incident.board.json`.
- **`risk-register`** — one-way `export-acceptances` into this store in v1 (bidirectional sync v2). **`incident-materiality`** — an incident can link to the acceptance it realized (`incidentIds[]`), with the discoverability caveat visible.

---

## 8. Testing

- **Deterministic:** `self-test` covers all mutations; `revalidation-lifecycle.sh` asserts due/overdue/expired banding derived only from events over a store built by real commands (anti-vacuity rules from `confirmation-age.sh`).
- **Board-safety:** the executive inventory view passes checks 9/10.
- **Trigger accuracy:** "log an exception / compensating control / re-validate this acceptance / show our risk-acceptance inventory" route here; a one-shot "frame this acceptance for the board" still routes to `ciso-board-translation`; register asks stay with `risk-register`.
- **Register bridge:** `export-acceptances` round-trips into a valid `.exc` intake; existing register behavior regression-clean.

---

## 9. Open decisions — RESOLVED (2026-07-30)

1. Home → **standalone `exceptions-register` skill.**
2. Store → **`.exc`.**
3. Relationship to register → **this skill is the system of record**; register keeps an `accepted` marker + one-way `export-acceptances`.
4. GTM gate → **build engine now, defer marketing** (G1).
5. `deviationFrom` typing → free text + optional control/standard ref.
6. Exceptions scored? → **no** in v1; link to a risk for quantification.

---

## 10. Guardrails

- Refusal discipline is the feature: no approver/justification/re-validation date → no record.
- Re-validation is an act with rationale; clocks surface, never silently expire reasoning.
- Distance-from-cadence, never confidence; enforced.
- Preserve every receipt's honest limit; surface the discoverability caveat.
- Never invent approvers, justifications, or compensating controls.
- Append-only history; footer + "Not affiliated with NIST."

---

*A Cyber Aware Creation · Not affiliated with NIST.*
