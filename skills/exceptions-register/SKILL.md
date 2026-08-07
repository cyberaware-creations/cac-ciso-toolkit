---
name: exceptions-register
description: >-
  Maintain a defensible register of accepted residual risks and control
  exceptions that persists in a local file, so an auditor, a regulator or a board
  can be shown what the organisation knowingly accepted, on what basis, who
  approved it, and whether that reasoning is still valid. Records two object
  types with one lifecycle — acceptances and exceptions with their compensating
  controls — and refuses any record missing an approver, a justification or a
  re-validation date. Re-validation is recorded as an act with a rationale, never
  a timer reset. Derives current, due, overdue and expired status from the dates,
  exports the active inventory as the CSV or JSON evidence artifact a DORA or
  NYDFS reviewer asks for, and produces a board section whose language comes from
  ciso-board-translation. Use when asked to log or approve an exception or
  waiver, record a risk acceptance with its approver and expiry, run a
  re-validation review, list what is overdue for re-validation, or produce the
  risk-acceptance inventory. Accepted risks already in a risk register are fed in
  one-way with that skill's export-acceptances; this skill is the system of
  record for the lifecycle, and the register does not duplicate it.
---

# Exceptions Register

A system of record for every time the organisation **knowingly accepts a residual risk** or
**grants an exception to a control or standard**. It answers the two questions an auditor
actually asks: *"on what basis did you accept this, who approved it, and is that reasoning
still valid?"* and *"where are you deviating from your own standards, what compensates, and
who signed off?"*

It stands alone — a vCISO can run it without a quantified risk register — and links to the
rest of the toolkit by id.

## The refusal is the product

`accept-add` and `except-add` refuse without **approver**, **justification**, **accepted
date** and **re-validation date**; an exception additionally requires a **compensating
control**. The refusal names every missing field at once, and happens before the file is
opened, so nothing is half-written.

This is not validation fussiness. A register that accepts *"R-014, accepted, see email"*
reproduces the free text it was built to replace and passes an audit exactly as badly. A
deviation with nothing offsetting it is not an exception — it is an unmanaged gap, and
calling it an exception launders it.

## Re-validation is an act, not a timer

```bash
python3 scripts/exceptions_register.py revalidate register.exc --id A-002 \
    --on 2026-07-31 --next 2027-07-31 \
    --why "Reviewed with the board: vendor contract renewed on the same terms, insurance rider verified in force."
```

`--why` is required. Re-validation records that a **human re-checked the reasoning and it
still holds** — the literal thing DORA RTS Art. 3(d)(iv) asks an organisation to
demonstrate. A clock that resets itself is evidence of nothing, and without a stated reason
the event cannot be told apart from an automated renewal.

**A lapsed clock surfaces an item; it never expires the reasoning.** Overdue records stay in
the inventory and stay visible, because the organisation is still carrying that risk.

## Workflow A — record

```bash
E=scripts/exceptions_register.py
python3 $E init register.exc --client "Acme" --owner CISO --due-window-days 30 --actor "you"

python3 $E accept-add register.exc --title "40-day patch window on nine internet-facing systems" \
  --approver "CISO" --justification "Vendor cadence is quarterly; virtual patching in place." \
  --accepted 2026-04-01 --revalidation 2027-01-15 --expiry 2027-04-01 --risk R-006 --actor "you"

python3 $E except-add register.exc --title "Finance without phishing-resistant MFA" \
  --deviation-from "NYDFS-500.12" \
  --compensating "Out-of-band callback on every payment change above \$10,000." \
  --approver "CFO" --justification "Token rollout blocked until the ERP upgrade." \
  --accepted 2026-05-01 --revalidation 2026-11-01 --expiry 2026-11-30 --actor "you"
```

## Workflow B — the re-validation review

```bash
python3 $E analyze register.exc --today 2026-07-31 --out analysis.json
(cd renderers && python3 render_inventory.py --in ../analysis.json --out ../inventory.html)
```

Work the attention lists — **overdue**, **due**, **expired**, **no compensating control**,
**unlinked**. For each, the review reaches one of three outcomes and records it:

- still valid → `revalidate` with the rationale
- no longer valid → `close` with the reason, and raise the underlying work
- valid but the situation changed → `close` and record a fresh acceptance on the new basis

Then export the evidence artifact:

```bash
python3 $E export-inventory register.exc --format csv --out acceptance-inventory.csv
```

Active records only — closed ones stay in the store and the change log, so the exclusion is
a view rather than a deletion. Overdue and expired items **are** included: hiding them would
be the one thing worse than not having an inventory.

### What the register raises without being asked

This skill owns the acceptance clock, so it is the one entitled to say a clock has run out.
`analyze` carries escalations in the suite-wide `CAC-EL-1 §1.3` shape, which `board-pack`
aggregates beside a crossed risk band and a breached metric without knowing anything about
any of the three:

| trigger | fires when | severity |
|---|---|---|
| `expired` | past the expiry date — **no current approval covers it** | `critical` |
| `revalidation-overdue` | past the re-validation date, approval still live | `high` |

**The severities are the reverse of what the band order suggests, and that is the point.**
`expired` is critical because the approval itself has lapsed: the organisation is carrying a
deviation nobody currently endorses. `revalidation-overdue` is high — the approval stands and
what has slipped is the *review* of it. One is an unapproved exposure, the other an unreviewed
approval, and the first is worse.

**`revalidation-due` is deliberately not a trigger.** A record inside its due window is on
schedule, and escalating a deadline nobody has missed teaches a reader to ignore the list by
the second quarter. Due is the attention list; overdue is an escalation.

`subjectKind` is `acceptance` or `exception` rather than one word for both, because a board
reads them differently: an accepted risk is a decision somebody made, a control exception is a
rule somebody is not following.

Escalations are **derived on every run, never stored, never a history event** — and nothing
here blocks. An expired record still exports, still renders, still counts.

## From the risk register

```bash
python3 ../risk-register/scripts/score_register.py export-acceptances register.rr --out acc.json
python3 $E import-acceptances register.exc --from acc.json --actor "you"
```

One-way. `risk-register` keeps its lightweight `accepted` marker and feeds it across; the
lifecycle lives **here**, and the register deliberately has no `revalidate`. Two homes for
the same clock is how the two come to disagree. The import is idempotent on the source risk
id, and every row still faces the same refusal a hand-entered record does — an import is not
a side door.

## Reporting

```bash
(cd renderers && python3 render_board.py --in ../analysis.json \
    --translations ../exceptions.board.json --out ../board.html)
```

Without `--translations`, every narrative slot renders a labelled placeholder. The sidecar
conforms to the section contract: section `exceptions`, with **two** per-item maps,
`acceptances` and `exceptions`.

## Read before you sell this

`references/exceptions.md` carries the receipts **with their limits attached** — DORA RTS
Art. 3(d) is real but satisfiable by free text and exempts Art. 16 entities; NYDFS §500.12
binds covered entities in New York and nobody else.

It also carries the **discoverability caveat**, which is surfaced on every rendered view
rather than buried: a permanent, dated inventory of accepted risk is a governance asset and
a potential litigation exhibit, and which one it becomes depends on whether it agrees with
what the organisation said publicly. Keep entries governance-level and factual, align them
with what is disclosed, and involve counsel on anything touching disclosure.

**This is not legal advice.** The register structures and records a decision; it does not
make it.

## Reference

| File | What it covers |
|---|---|
| `references/schema.md` | the `.exc` store, required fields, status bands, derived list |
| `references/exceptions.md` | the exception model, compensating controls, receipts and their limits, the discoverability caveat |

Verify the engine with `python3 scripts/exceptions_register.py self-test`.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
