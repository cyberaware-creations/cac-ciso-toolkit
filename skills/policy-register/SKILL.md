---
name: policy-register
description: >-
  Keep a defensible register of the organisation's security policies — what exists, who owns
  it, what version, who approved it on what date, when it is next reviewed, and which
  requirement each document is aimed at — persisted in a local file, so the question every
  auditor asks every CISO every year can be answered from a record rather than from memory.
  Grounded in the Policy and Procedures control in each NIST SP 800-53 Rev. 5 family and in
  NIST CSF 2.0 GV.PO-01 and GV.PO-02, both shipped with the skill so nothing needs
  downloading. Refuses to record a policy as approved without a named approver and a date,
  and refuses to say a requirement is met, covered, satisfied or compliant because a policy
  maps to it — a mapping records that a document exists and what it is aimed at, nothing
  more. Reports counts, never percentages. Supersedes and never deletes, because the audit
  question is what was in force on the date of the incident. A requirement with no policy
  reads not declared rather than absent, and an overdue review flags without blocking
  anything. Use when asked which policies exist, who approved one and when, what a policy is
  aimed at, which requirements have no document behind them, what is overdue for review, or
  to produce the policy inventory an auditor or a regulator asks for. Carries a kind field
  reserved for plans and playbooks; only policies behave in this release.
---

# Policy Register

*"Show me your policies, and which requirement each one satisfies."*

Every auditor asks it. Most organisations answer it from a shared drive, a spreadsheet that
went stale in March, and somebody's memory of who signed what. This skill answers it from a
record: what exists, who owns it, what version, who approved it on what date, when it is next
reviewed, and what each document is aimed at.

It stands alone. No other skill needs to have been run, no other store needs to exist, and an
empty register is a normal state rather than a fault.

## The refusal is the product

**A mapped policy is never evidence that a requirement is met.**

That sentence is the whole reason this is a skill and not a spreadsheet. *"We have a policy
for that"*, accepted as *"that risk is controlled"*, is the most common quiet untruth in this
industry — and a register that permitted the slide would make a CISO **less** defensible for
having used it, because a register looks like a system.

So a policy record supports exactly one claim:

> a document exists, a named person approved it on a date, and it is aimed at these
> requirements.

There is no state meaning covered, met, satisfied or compliant. There is no percentage. The
four things a requirement row can say all describe the **documents**, never the requirement:

| State | What it says |
|---|---|
| `not-declared` | Nothing in this register names this requirement. **Not** a finding that no policy exists — many organisations hold one omnibus policy across several control families. |
| `draft-only` | Every document mapped here is still a draft. Nobody has approved one. |
| `superseded-only` | Every document mapped here has been superseded and nothing approved replaced it. The state that most often goes unnoticed. |
| `approved-policy` | At least one approved document is aimed at this requirement. A document exists and a named person approved it. It does not say the requirement is met, and this register cannot tell you whether it is. |

`evals/no-coverage-claim.sh` and `evals/no-coverage-percentage.sh` prove both rules by
mutation on every run. Adding a fifth state called `covered` is a one-line change that
nothing else in the codebase would object to; those two guards are what object.

## Approved means a name and a date

```bash
python3 scripts/policy_register.py approve register.pol --id P-001 \
    --by "The Board" --on 2026-01-15
```

Both are required, and the refusal names every missing field at once, before the file is
opened — so a rejected command leaves the register byte-identical.

CSF GV.PO-01 asks the organisation to *"require approval from senior management on policy"*.
A record that says `approved` with nobody named records the opposite of that, and it is
worse than no record, because it will be produced in evidence.

**The refusal is write-time only.** A file that already carries `approved` with no approver
still loads, and `analyze` reports the state rather than hiding it. Refusing to *read* it
would strand the one person who needs to see it.

## Supersession, never deletion

There is no delete command, and there is not going to be one. The audit question is never
*what is your policy on this* — it is *what was in force on the date of the incident*, and a
register that can only answer for today answers the wrong question with complete confidence.

```bash
python3 scripts/policy_register.py supersede register.pol --id P-005 \
    --on 2026-09-01 --why "Replaced by the 3.0 issue after the KMS migration."
```

The record stays in the file, stays in the CSV an auditor is handed, and stays on the page,
marked as superseded. `--by-policy` is optional, because withdrawing a document without a
replacement is a real act — and it is the one that goes quietly wrong, so the requirement
view surfaces it as `superseded-only` instead of letting the row fall silent.

`evals/no-deletion.sh` counts the records after every mutation of a full lifecycle and scans
for any code path that shortens the list.

## Review is an act, not a timer

```bash
python3 scripts/policy_register.py review register.pol --id P-001 \
    --on 2026-05-12 --next 2027-05-12 \
    --why "Reviewed with the risk committee alongside the risk appetite statement; no change."
```

`--why` is required. GV.PO-01 asks that policy be *"periodically reviewed"*; a clock that
resets itself is evidence that somebody ran a script.

**An overdue review flags and never blocks.** The document stays approved, stays in every
view, and stays against its requirement — because it is still the policy in force, and
hiding it would be the opposite of what the flag is for. The flag is derived on every read
and stored nowhere, so it clears the moment the review is recorded.

## The requirement spine, and why it is only twenty-two

NIST publishes nothing dedicated to security policy management. The legitimate anchors are
the **Policy and Procedures control in each SP 800-53 Rev. 5 family** — `AC-1`, `AT-1`,
`AU-1`, `CA-1`, `CM-1`, `CP-1`, `IA-1`, `IR-1`, `MA-1`, `MP-1`, `PE-1`, `PL-1`, `PM-1`,
`PS-1`, `PT-1`, `RA-1`, `SA-1`, `SC-1`, `SI-1`, `SR-1` — and **CSF 2.0 GV.PO-01 and
GV.PO-02**.

The join is not this project's invention: the CSF Core's own informative references for
GV.PO-01 and GV.PO-02 name all twenty of those controls.

Both anchors ship with the toolkit, so nothing is downloaded and no licence is involved. The
list is **vendored** into `references/requirements.json` so this skill runs from its own
directory with nothing else installed; `evals/requirement-drift.sh` regenerates it from the
`nist-csf` artifacts on every run and fails on any difference.

**Twenty-two requirements are the NIST policy spine, not your obligations.** That is exactly
why this skill reports counts and refuses proportions: a percentage of this list is a
completeness figure for a catalogue nobody claimed was complete.

An id outside the spine — `PCI DSS 12.8.1`, a contractual clause, your own control
framework — can be mapped and is **shown in its own section**, never dropped. Discarding it
because the spine is NIST-shaped would be an absence that looks exactly like a clean result.

## Commands

```bash
python3 scripts/policy_register.py init register.pol --org "Northwind Logistics" \
    --owner "Head of Information Security"

python3 scripts/policy_register.py add register.pol \
    --title "Information Security Policy" --owner "Head of Information Security" \
    --version 3.1 --map PM-1 --map GV.PO-01 --acknowledge "on-hire,annual,on-update"

python3 scripts/policy_register.py approve  register.pol --id P-001 --by "The Board" --on 2025-11-04
python3 scripts/policy_register.py revise   register.pol --id P-001 --version 4.0 --why "..."
python3 scripts/policy_register.py review   register.pol --id P-001 --on .. --next .. --why "..."
python3 scripts/policy_register.py supersede register.pol --id P-005 --on .. --why "..."
python3 scripts/policy_register.py map      register.pol --id P-001 --requirement AT-1
python3 scripts/policy_register.py unmap    register.pol --id P-001 --requirement AT-1 --why "..."

python3 scripts/policy_register.py requirements register.pol      # the auditor's view
python3 scripts/policy_register.py analyze      register.pol --out analysis.json
python3 scripts/policy_register.py export       register.pol --format csv --out policies.csv
python3 scripts/policy_register.py self-test
```

The page:

```bash
cd renderers && python3 render_requirements.py --in ../analysis.json \
    --out policy-requirements.html --offline
```

`--offline` emits no external request, because these artifacts are opened in a room, on a
laptop, with no network. `--brand` takes a client palette and is refused rather than
approximated if any pairing falls below its contrast floor.

**The colours are deliberately not RAG.** `approved-policy` and `not-declared` take neutral
chips, because neither is a verdict; only `draft-only` and `superseded-only` take the
attention palette, because both describe a document problem this register can actually see.
Painting the first green would make the coverage claim in colour that the guards forbid in
words — and colour is what a board reads first.

## Entry anywhere, and a partial programme is normal

No other skill has to have been run. No store this skill wants to read has to exist. Every
mutation leaves a schema-valid file, so stopping half way through leaves a legible partial
state rather than wreckage. An empty register analyses cleanly, reports twenty-two
requirements as not declared, and raises nothing — **an absent register is not a fault, and
this skill does not nag.**

## What it deliberately does not do

- **Store or render policy text.** This is not a document management system.
- **Track individual acknowledgements.** That is an HR or LMS system. The register records
  that acknowledgement is *required* and at what cadence — which is what GV.PO-01's
  implementation examples ask for.
- **Generate policy text, or judge whether a policy is any good.**
- **Behave for `kind: plan` or `kind: playbook`.** The field ships so a store written today
  needs no migration when they land; recording one now is refused, with that reason.
- **Produce a board section.** Deliberately deferred.
- **Carry ISO 27001 or CIS identifiers** in the requirement view.

## Reading

- `references/policy.md` — the record shape, read off the GV.PO implementation examples
- `references/schema.md` — the `.pol` file, field by field
- `references/requirements.json` — the vendored spine
- `examples/example.pol` — a worked register with a superseded document and two overdue reviews

This skill is not legal advice.
