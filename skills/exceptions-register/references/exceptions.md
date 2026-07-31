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
at an objective the standard abandoned. **NIST SP 800-63B** moved off user-chosen complexity
years ago in favour of length, screening against breached-password corpora, and no forced
rotation. Exhorting users toward "strong" passwords asks them to do the thing the guidance
stopped asking for — so the measure is not merely weak, it is pointed at the wrong target.

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

**NYDFS Part 500 §500.12 / §500.15** — where MFA or encryption is not implemented as
specified, a written approval of compensating controls is required, reviewed at least
annually. **Limit:** it binds covered entities in New York financial services and nobody else.

**ISO/IEC 27001 Clause 6.1.3 / 8.3** — risk treatment and residual risk acceptance by risk
owners. **Limit:** the standard requires the acceptance, not any particular register format.

Never imply an obligation that is not there, and never present the inventory as compliance
in itself. It is evidence that a process ran.

## The discoverability caveat — read this before selling the inventory

A permanent, queryable, timestamped record of every risk the organisation knowingly accepted
is **discoverable**. It is a governance asset and a litigation exhibit, and which one it turns
out to be depends on whether it agrees with what the organisation said publicly.

Delaware's *Caremark* line rewards a documented oversight process: a board that can show it
received information and acted on it is far better placed than one that cannot. That is the
case for keeping this record.

The other half is *SEC v. SolarWinds*: granular internal records that contradicted the
company's public security statements became the evidence. The records were not the problem;
the gap between them and the public statements was.

What follows for how these records should be written:

- **Governance-level, not forensic.** Record the decision, the basis, the approver, the date.
  This is not the place for an engineer's assessment of exploitability.
- **Factual and neutral.** Write what would read the same way to a regulator, a board, and
  opposing counsel, because eventually it may.
- **Aligned to what is disclosed.** An acceptance that contradicts a public statement is a
  problem in one of the two, and the register is where you find that out first — which is an
  argument *for* keeping it, provided the contradiction is then resolved.
- **Counsel in the loop** on anything touching disclosure.

The renderers surface this caveat wherever risk, exception and incident records are linked.
It is not a disclaimer to be dismissed: it is the reason to keep the record *carefully*
rather than the reason not to keep it.

**This is not legal advice.** The register structures and records a decision; it does not
make it, and it is not a substitute for counsel.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
