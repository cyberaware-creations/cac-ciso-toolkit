# Exceptions, compensating controls, and the honest limits

## What an exception is

A documented, approved deviation from a control, policy or standard, with something in
place that offsets it. Three parts, and all three are required:

1. **What you are not doing** — `deviationFrom`, naming the control or standard.
2. **What you are doing instead** — `compensatingControl`.
3. **Who decided that was acceptable, and why** — `approver` and `justification`.

Drop the second and it is not an exception, it is an unmanaged gap wearing the word
"exception". Drop the third and it is not a decision, it is a description. The engine
refuses records missing any of them, and that refusal is the product.

## The compensating control has to actually compensate

The engine cannot judge this — no engine can — but the review should, and the report puts
the deviation and its compensating control on the same line so the comparison is unavoidable.

A compensating control that restates the deviation ("MFA not enforced; users are reminded to
choose strong passwords") is the common failure. It reads as a control and functions as a
sentence. When the review cannot say what an attacker now has to defeat, the honest options
are to fix the deviation, to accept the residual risk explicitly as an **acceptance** rather
than dressing it as an exception, or to escalate.

Three tests that separate a control from a sentence:

1. **What does an attacker now have to defeat that they did not before?** If there is no
   answer, there is no control.
2. **Does anything fail closed?** A measure that depends on the same population whose
   behaviour is the risk has not changed the outcome, only the paperwork.
3. **What evidence would show it operated?** "The reminder was sent" is evidence the reminder
   was sent. It is not evidence that a single password got stronger.

The reminder example fails a fourth way worth naming, because it is easy to miss: it is aimed
at an objective the standard abandoned. **NIST SP 800-63B-4 §3.1.1.2** moved off user-chosen
complexity in favour of length, screening against breached-password corpora, and no forced
rotation. It also raises the minimum to **15 characters for single-factor** authentication
(8 where a second factor is used). Exhorting users toward "strong" passwords asks them to do
the thing the guidance stopped asking for — so the measure is not merely weak, it is pointed at
the wrong target.

*Cited at SECTION level, not to the bare volume, and that is the lesson of this repoint rather
than a formatting preference. Revision 4 renumbered 800-63B wholly and moved several subjects
into other volumes; a bare-volume citation would have gone stale silently, where a section cite
makes the next revision's boundary move **visible**. All three limbs of the claim above were
confirmed to have stayed in 63B-4 §3.1.1.2 before the pointer was changed.*

What a real compensating control for unenforced MFA looks like: MFA at a layer that *can* be
enforced (VPN, SSO front end, jump host); breached-credential screening at set-time and
periodically, with forced reset on a hit; network reachability cut so a stolen credential is
unusable from the internet; or rate limiting and lockout with alerting on anomalous
authentication. Each of those changes an attacker's job, and each produces evidence.

## Acceptance or exception?

| | acceptance | exception |
|---|---|---|
| the object | a residual risk you are carrying | a rule you are not following |
| the question it answers | "why is this level of risk acceptable?" | "why are we not doing this, and what offsets it?" |
| requires a compensating control | no | **yes** |
| typical receipt | DORA RTS Art. 3(d) | NYDFS §500.12 / §500.15 |

The same situation can produce both, and often should: an exception to the MFA standard, and
an acceptance of the residual risk that exception leaves. They are separate records with
separate lifecycles, linked by `riskIds`.

## Re-validation is an act, not a timer

`revalidate` records that a human re-checked the reasoning and it still holds, with a
rationale, on a date. That is the literal thing DORA RTS Art. 3(d)(iv) asks for, and it is
why the command refuses without `--why`.

A clock that resets itself is not evidence of anything. If the register let a date be bumped
without a stated reason, the event would be indistinguishable from an automated renewal —
which is exactly the practice the requirement exists to rule out.

**A lapsed clock surfaces the item; it never expires the reasoning.** Overdue acceptances stay
in the inventory, and stay visible, because the organisation is still carrying that risk. A
register that dropped them would delete the record it exists to keep.

## Receipts, with their limits attached

These are the real hooks, and each one is weaker than a vendor would tell you. The limits
travel with the citation — a receipt quoted without its limit is a sales claim.

**DORA RTS Art. 3(d)** — in-scope financial entities must document accepted residual ICT
risk, with justification and periodic re-validation. Real and dated. **Limits:** it is
satisfiable by free text, so nobody is required to buy a tool for it; and Art. 16 simplified
-framework entities are outside it. Cite the RTS, never DORA Level 1, which does not say this.

**NYDFS Part 500 §500.12 / §500.15** — a written CISO approval of compensating controls,
reviewed at least annually. The two sections are **not symmetrical**, and the difference decides
whether an exception is loggable at all:

- **§500.12(b) — MFA.** *"If the covered entity has a CISO, the CISO may approve in writing the
  use of reasonably equivalent or more secure compensating controls. Such controls shall be
  reviewed periodically, but at a minimum annually."* Note the condition: an entity with no CISO
  has no compensating-controls route here.
- **§500.15(b) — encryption AT REST only.** Where encryption of nonpublic information at rest is
  infeasible, compensating controls may be used with the CISO's written approval, and the CISO
  reviews feasibility and effectiveness at least annually.
- **Encryption IN TRANSIT has no compensating-controls route.** The Second Amendment **deleted**
  the provision that used to allow one. §500.15(a) now requires encryption of nonpublic
  information *"both in transit over external networks and at rest"*, full stop. **An in-transit
  exception is not a deviation you can log and compensate — it is non-compliance**, and belongs
  in the §500.17 acknowledgment rather than in this register as a controlled exception.

**Limits, and there are two of them running in opposite directions.**

**Outward** — it binds covered entities in New York financial services and nobody else.

**Inward — §500.19 exempts some covered entities from exactly these sections.** A limit that
only scopes outward is the one this file kept for six releases, and it is why an exempt firm
was told its lawful gap was a compliance failure (BL-188):

- **§500.19(a), the limited exemption** — an entity meeting **any one** of three tests (fewer
  than 20 employees and independent contractors including affiliates; under $7,500,000 gross
  annual revenue in each of the last three fiscal years; under $15,000,000 year-end total
  assets including all affiliates) is exempt from **§500.15 but NOT from §500.12**. The Second
  Amendment **removed §500.12 from this list**, so a limited-exemption entity that was exempt
  from MFA before 1 November 2023 is not exempt now — §500.12 bound it from 1 November 2025
  under the §500.22(d)(4) transition. For such a firm the §500.12(b) compensating-controls
  route above is live and the §500.15(b) one is beside the point.
- **§500.19(c) and (d)** — an entity with no information systems and no nonpublic information,
  and an Insurance Law article 70 entity holding only its parent's or affiliates' information,
  are each exempt from **both §500.12 and §500.15** (and from §500.2, 500.3, 500.4, 500.5,
  500.6, 500.7, 500.8, 500.10, 500.14 and 500.16).
- **§500.19(b), (e) and (g)** exempt from **the whole Part**, §500.17 included.

**Whether a given entity qualifies is a legal determination and this suite does not make it.**
The tests look computable — a headcount, a revenue figure, an asset total — and that is exactly
the trap: affiliate aggregation, what counts as operating under a license, and whether an entity
"otherwise qualifies as a covered entity" are not arithmetic. Record the limb counsel declared,
with who declared it and when, the same way this register records everything else.

**ISO/IEC 27001 Clause 6.1.3 / 8.3** — risk treatment and residual risk acceptance by risk
owners. **Limit:** the standard requires the acceptance, not any particular register format.

Never imply an obligation that is not there, and never present the inventory as compliance
in itself. It is evidence that a process ran.

## The discoverability caveat — read this before selling the inventory

A permanent, queryable, timestamped record of every risk the organisation knowingly accepted
is **discoverable**. It is a governance asset and a litigation exhibit, and which one it turns
out to be depends on whether it agrees with what the organisation said publicly.

Delaware's *Caremark* line — *In re Caremark Int'l Inc. Derivative Litig.*, 698 A.2d 959 (Del.
Ch. 1996), as restated in *Stone v. Ritter*, 911 A.2d 362 (Del. 2006) — rewards a documented
oversight process: a board that can show it received information and acted on it is far better
placed than one that cannot. That is the case for keeping this record. Cite both, not *Caremark*
alone: *Stone* is where the standard a court applies actually lives.

The other half is *SEC v. SolarWinds*: granular internal records that contradicted the
company's public security statements became the evidence. The records were not the problem;
the gap between them and the public statements was.

### ⚠️ The corollary, and it cuts both ways

**Documented board-level process is what earns prong-one protection — and it is simultaneously
the discoverable record that can establish prong-two knowledge.** Not two different records. The
same one.

*Brewer v. Turner* (Regions Financial), C.A. No. 2023-1284-KSJM (Del. Ch. 29 Sep. 2025)
(McCormick, C.), is that in one case, and the opinion is unusually clean about it because the
plaintiff pleaded **both** theories and the court took them in turn.

The information-systems theory *"can be addressed in short order"*: the **§220 documents**
showed multiple Board committees tasked with risk management, and the court concluded there was
*"no straight-faced argument that Regions lacked an information system."* The footnote carrying
that conclusion (n.67) cites Risk Committee minutes, joint Risk-and-Audit Committee minutes, and
**December 2019 and September 2020 Board meeting minutes**.

Those come from **the same §220 production** that shows the board received the whistleblower's
draft complaint and left the practices in place for around twenty months — which is the
red-flags theory that **survived**, and demand was excused as futile. One production, both jobs.

> ⚠️ **Note precisely what that is and is not.** Prong one fell away because the existence of a
> system was **not seriously contestable** — *not* because a court weighed the system and
> pronounced it adequate.
>
> The difference is the whole advice. *"Having a system defeats prong one"* is materially
> different from *"nobody could argue with a straight face that they had none"*, and only the
> second is what the opinion says. **A record good enough to make prong one unarguable buys
> nothing on prong two** — in *Brewer* it supplied the evidence on the other side.

**Why this belongs here rather than in the receipts alone.** This register's whole proposition
is a permanent, queryable record of decisions somebody made. *Brewer* is the case where that
exact artifact does both jobs at once, and a CISO being sold the inventory should hear it in the
same breath as the *Caremark* argument for keeping it — not later, from opposing counsel.

### And the statute is what makes the record reachable

*Brewer*'s §220 production was not an accident of that case. **DGCL § 220** — rewritten by
**Senate Bill 21, signed 25 March 2025** — now enumerates **nine** categories of "books and
records" a stockholder may demand, at **§ 220(a)(1)a.–i.** Two of them are exactly the artifact
this register produces:

- **e.** — minutes of the board and of its committees
- **f.** — materials provided to the board

So the board-level record remains **reachable by a stockholder**, which is the fact this caveat
needs. It is not a novel risk created by keeping a register; it is the ordinary position of
board-level governance records, and it is why *"governance-level, not forensic"* is the rule
above rather than a style preference.

> ⚠️ **§ 220(g) is a three-limb CUMULATIVE test, and it is easy to state as one.** A stockholder
> seeking records *beyond* the enumerated categories must satisfy **all three**:
>
> 1. **(g)(1)** — the demand meets § 220(b);
> 2. **(g)(2)** — a showing of a **compelling need** for the specific records; and
> 3. **(g)(3)** — a demonstration **by clear and convincing evidence** that those specific
>    records are **necessary and essential** to the stated purpose.
>
> Note where the standard attaches: **clear-and-convincing qualifies "necessary and essential",
> not "compelling need"**. Collapsing the three into "you need a compelling need, proved clearly
> and convincingly" states a different — and easier — test than the statute.

> ❌ ***Rutledge* did NOT uphold § 220, and an earlier draft of this passage said it did.**
> *Rutledge v. Dropbox* (Del. No. 248, 2025, 27 Feb. 2026) upheld **SB 21 § 1 (DGCL § 144)** and
> **§ 3 (retroactivity)**. On § 220 the Court was explicit: *"The amendments to § 220 … are **not
> implicated** by the questions the Court of Chancery certified to us."*
>
> The case name, number and date were all correct; **what was wrong was what it held** — the
> most dangerous shape for a citation error, because everything checkable checks out. Narrowed
> to what the Court actually decided, and the § 220 amendments are cited to **the statute
> itself**, which needs no case to be in force.

It is **still an argument for keeping the record.** It is an argument against keeping it
carelessly, which is what the rules below are for.

What follows for how these records should be written:

- **Governance-level, not forensic.** Record the decision, the basis, the approver, the date.
  This is not the place for an engineer's assessment of exploitability.
- **Factual and neutral.** Write what would read the same way to a regulator, a board, and
  opposing counsel, because eventually it may.
- **Aligned to what is disclosed.** An acceptance that contradicts a public statement is a
  problem in one of the two, and the register is where you find that out first — which is an
  argument *for* keeping it, provided the contradiction is then resolved.
- **A decision, not a mention.** *Brewer*'s red flag was a draft complaint that reached the
  board and was investigated without the practices changing. A minute recording that the board
  was *told* something is prong-two evidence with no prong-one benefit; a record of what was
  **decided**, by whom, and on what basis is the one that does both jobs.
- **Counsel in the loop** on anything touching disclosure.

The renderers surface this caveat wherever risk, exception and incident records are linked.
It is not a disclaimer to be dismissed: it is the reason to keep the record *carefully*
rather than the reason not to keep it.

**This is not legal advice.** The register structures and records a decision; it does not
make it, and it is not a substitute for counsel.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
