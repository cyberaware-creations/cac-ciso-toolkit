# The policy record, and where its shape comes from

The fields in this register are not designed. They are read off the implementation examples
NIST publishes under CSF 2.0 GV.PO-01 and GV.PO-02, which ship with this toolkit in
`skills/nist-csf/references/nist-csf-2.0-core.json`. Every field below names the example it
exists to serve, so a reader can check the reasoning rather than take it.

| Field | The example it comes from |
|---|---|
| `title`, `owner`, `version` | *"Create, disseminate, and maintain an understandable, usable risk management policy with statements of management intent, expectations, and direction"* (GV.PO-01) |
| `approval.by`, `approval.on` | *"Require approval from senior management on policy"* (GV.PO-01) |
| `review.intervalDays`, `review.lastOn`, `review.nextOn` | *"Periodically review policy and supporting processes and procedures…"* (GV.PO-01) and *"Provide a timeline for reviewing changes to the organization's risk environment…"* (GV.PO-02) |
| `acknowledgement.required`, `acknowledgement.cadence` | *"Require personnel to acknowledge receipt of policy when first hired, annually, and whenever policy is updated"* (GV.PO-01) — which is exactly the three cadences the field accepts |
| `mappedTo` | The requirement spine below. GV.PO-02 asks that policy be updated *"to reflect changes in legal and regulatory requirements"*, which presumes somebody knows which requirements a document is aimed at |
| `state`, `supersededOn`, `supersededBy`, `supersedes` | Not from an example. From the audit question — see *Supersession* below |

`acknowledgement` records **that acknowledgement is required and how often**. It does not
record who acknowledged what: that is an HR or LMS system, and a register that held a
half-populated list of names would be worse than one that holds none, because somebody would
report from it.

## The requirement spine

NIST publishes **nothing dedicated to security policy management**, and the two anchors that
do exist are both already in this toolkit:

* the **Policy and Procedures** control in each SP 800-53 Rev. 5 family — twenty of them,
  `AC-1` through `SR-1`
* **CSF 2.0 GV.PO-01 and GV.PO-02**

The join between them is NIST's, not this project's: the CSF Core's own informative
references for GV.PO-01 and GV.PO-02 list all twenty, `AC-01` through `SR-01`.

The list is vendored into `requirements.json` rather than read from `nist-csf`, because every
shipped script here must run from its own directory with nothing else installed. Vendoring
costs exactly one thing — two copies that can silently disagree — and
`evals/requirement-drift.sh` regenerates the file from the `nist-csf` artifacts on every run
and compares all 112 fields.

**Two things this list is not.** It is not the organisation's obligations, which is why this
skill reports counts and refuses proportions. And it is not a closed set: an id outside it can
be mapped and gets its own section on the page, because dropping a true statement because the
spine is NIST-shaped would be an absence that looks like a clean result.

## Supersession, and why there is no delete

The audit question is not *what is your policy on this*. It is *what was in force on the date
of the incident* — and a register that can only answer for today answers the wrong question
with complete confidence, which is worse than not answering.

So a document leaves force exactly one way, and stays in the file afterwards:

```bash
python3 scripts/policy_register.py supersede register.pol --id P-005 \
    --on 2026-09-01 --why "Withdrawn during the KMS migration; the replacement is in drafting."
```

`--by-policy` names the replacement and is **optional**, because withdrawing a document with
nothing to replace it is a real act rather than an error. It is also the state that goes
quietly wrong — the register still looks populated and the requirement has nothing in force —
so the requirement view surfaces it as `superseded-only` and escalates it high.

## Revision returns a document to draft

`revise` sets a new version and clears the approval, because the approved text and the new
text are not the same document. The prior approval stays in `history`, where it belongs: it
records something that really happened, on a date, to a version that really existed.

The requirement that document was aimed at drops back to `draft-only` until somebody approves
the new version — which is the honest answer to *"is there an approved policy for this?"*
during a rewrite, and the answer most registers get wrong.

## What the four requirement states mean

See the table in `SKILL.md`. The property worth restating here is the one the guards enforce:
**every state describes the documents, and none describes the requirement.** This register has
no way to determine whether a requirement is met — it cannot see whether anybody follows the
policy, whether the control exists, or whether it works — and it will not imply otherwise in
a word, a number, or a colour.

For whether a control is actually in place, use `nist-csf`. For a risk knowingly accepted
against a standard, use `exceptions-register`. Those are different questions and different
skills, and the separation is the point.

This document is not legal advice.
