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

## Re-measure before you renew

An acceptance is a decision about a **quantity** — *we will carry this much exposure, on this
basis, until this date*. So a record may carry the magnitude it was accepted against, and
`revalidate` refuses to renew against a number nobody has re-measured since the last review:

```bash
python3 scripts/exceptions_register.py accept-add register.exc \
    --title "40-day patch window" ... \
    --magnitude 12 --magnitude-unit "residual exposure" --measured-on 2026-04-01
```

```
A-001 cannot be re-validated against a magnitude nobody has re-measured.
    accepted against: 12 residual exposure
    last measured:    2026-04-01
    last reviewed:    2026-08-01
```

The way through is to do the measuring, in the same act that records the review:

```bash
python3 scripts/exceptions_register.py revalidate register.exc --id A-001 \
    --on 2027-01-01 --next 2028-01-01 --remeasured 8 --measured-on 2026-12-20 \
    --why "Re-scored with IT before renewal; segmentation landed in November."
```

This is the same argument as `--why`, one level down. `--why` stops a renewal that records no
reasoning; this stops one whose reasoning rests on a number nobody re-checked.

Three properties keep it honest:

- **The register never demands a number it was never given.** A record with no magnitude is
  never refused. This skill stands alone without a quantified risk register, and requiring a
  quantity it never had would make an unquantified register unusable rather than more rigorous.
- **The staleness rule invents no interval.** *Older than the last time somebody reviewed this
  record* comes from the record's own history. A configurable window would be this skill naming
  a number that no standard sets.
- **The refusal lands on the act, never on the record.** A record awaiting re-measurement still
  counts, still analyses, still exports, still renders. One act is refused, not one record — and
  the refusal says so, because a reader who thinks a record has been hidden goes looking in the
  wrong place.

`analyze` puts these on the **`remeasureNeeded`** attention list, narrowed to records whose
review is actually due. Every quantified record needs re-measuring *eventually*; only the ones
with a review coming up belong on this quarter's agenda.

Records imported from `risk-register` arrive already measured — `export-acceptances` stamps the
residual exposure, its band, and the date the score was last affirmed. A refresh that carries no
magnitude leaves the recorded one alone, so the bridge cannot become a way around the refusal.

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

Work the attention lists — **overdue**, **due**, **expired**, **needs re-measurement**, **no
compensating control**, **unlinked**. For each, the review reaches one of three outcomes and records it:

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

Records that came across the bridge also carry **`relatedRef`** — the risk id this record is the
acceptance *of*, taken from `sourceRiskRef`. `risk-register` can escalate `acceptance-lapsed` on
its own marker for the same expiry, so declaring the link lets `board-pack` notice one fact
arriving twice without either register knowing the other exists. It is `sourceRiskRef` and not
`riskIds`: the first is identity, the second is only relatedness, and joining on relatedness
would flag two genuinely different facts as one.

Escalations are **derived on every run, never stored, never a history event** — and nothing
here blocks. An expired record still exports, still renders, still counts.

## From the risk register

```bash
python3 ../risk-register/scripts/score_register.py export-acceptances register.rr --out acc.json
python3 $E import-acceptances register.exc --from acc.json --actor "you"
```

One-way, and it now carries the magnitude too: each row brings the risk's residual exposure,
its band, and the date that score was last affirmed, so an imported acceptance arrives able to
answer *"what was this accepted against, and when was that last measured?"*

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

## The applicability profile (CAC-AP-1)

```bash
python3 $E analyze register.exc --context context.json
```

Optional, and absent is the normal case — a run without one behaves exactly as it always did
and its output is byte-for-byte identical. The payload comes from
`business_context.py export <file.biz>`; this skill reads it as **data** and imports nothing
(§2.6).

What a profile narrows here is the **question set**, not the arithmetic. An acceptance expires on its own date whether or not DORA applies. So what
changes is which completeness questions this skill puts to you:

- **DORA register of information** — gated on `doraScope`

A flag declared `false` removes its question and records the skip with the flag, the declarer
and the date, so an auditor can tell a question that was out of scope from one nobody asked
(§2.4). A flag that is **absent, or declared `null`, asks the question anyway** — §2.2, absence
asks more, because silently narrowing on undeclared data produces an assessment that looks
complete and is not.

**It asks; it does not answer.** Nothing in an `.exc` records whether a record belongs to a DORA register of information. A coverage figure would be inferred from data that is
not there, and this skill refuses to invent the number it asks for — the same rule that makes
it demand an approver and a justification rather than guess. That is also why there is no *conflict* record here as
there is in `incident-materiality`: a conflict needs both sides stated, and one side is missing.

A payload from another contract version, or one carrying no decision, is **refused** rather than
ignored: `--context` was passed on purpose, and a silently un-narrowed run reads as a profile
that decided nothing applied.

## Read before you sell this

`references/exceptions.md` carries the receipts **with their limits attached, in both
directions** — DORA RTS Art. 3(d) is real but satisfiable by free text and exempts Art. 16
entities; NYDFS §500.12 binds covered entities in New York and nobody else, and its sibling
**§500.15 permits compensating controls for encryption at rest only** — the in-transit route
was deleted by the Second Amendment, so an in-transit gap is non-compliance to acknowledge
under §500.17, not an exception to log here.

**And §500.19 exempts some covered entities from exactly those sections.** §500.19(a), the
limited exemption, reaches §500.15 but **not** §500.12 — the Second Amendment removed §500.12
from that list, so a small firm exempt from MFA before 1 November 2023 is not exempt now.
§500.19(c) and (d) reach both. §500.19(b), (e) and (g) exempt from the whole Part. Telling an
exempt firm that a lawful gap is a compliance failure produces remediation spend against a
phantom obligation and an exception record saying, in writing and with a date, that the firm
knowingly operated outside a rule that never applied to it. **Whether a given entity qualifies
is a legal determination this suite does not make** — record the limb counsel declared.

It also carries the **discoverability caveat**, which is surfaced on every rendered view
rather than buried: a permanent, dated inventory of accepted risk is a governance asset and
a potential litigation exhibit, and which one it becomes depends on whether it agrees with
what the organisation said publicly. Keep entries governance-level and factual, align them
with what is disclosed, and involve counsel on anything touching disclosure.

⚠️ The caveat carries **the corollary**, which is the part a CISO being sold the inventory
should hear in the same breath as the argument for keeping it: the documented process that
earns prong-one protection is **the same discoverable record** that can establish prong-two
knowledge. *Brewer v. Turner* (Del. Ch. 2025) is that in one case — one §220 production, both
jobs. It is an argument for keeping the record, and against keeping it carelessly.

**This is not legal advice.** The register structures and records a decision; it does not
make it.

## Rendering under a client brand

Every renderer takes `--brand FILE`:

```bash
python3 renderers/render_board.py analysis.json report.html --brand northwind.json
```

```json
{"ink": "#101820", "muted": "#5A4436", "patina": "#C0701F", "bg": "#FAF7F2",
 "measure": "#8A4B12", "measureTrack": "#EFE0D2", "patinaText": "#8A4B12",
 "wordmark": "Northwind Group", "mark": "Northwind", "whiteLabel": true}
```

**It is refused rather than approximated.** A palette that leaves body text on the dark band
below 4.5:1, or the patina kicker on the dark band below 4.5:1, is rejected with every failing pairing named — not
the first, and not silently nudged into range. `whiteLabel` drops the maker's name and keeps
the "Not affiliated with NIST" line, because one says who built the document and the other is
a statement about the world.

**What does not follow the brand, deliberately:** the RAG status ramp. Red/amber/green is a
contract with the reader about severity, not styling the client is buying. Only the shell —
ink, muted, background, patina, and the steps derived from them — moves.

## Reference

| File | What it covers |
|---|---|
| `references/schema.md` | the `.exc` store, required fields, the magnitude block, status bands, derived list |
| `references/exceptions.md` | the exception model, compensating controls, receipts and their limits, the discoverability caveat |

Verify the engine with `python3 scripts/exceptions_register.py self-test`.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
