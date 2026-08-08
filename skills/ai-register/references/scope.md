# What this skill does not own

A register that quietly widens is worse than a narrow one, because the widening happens in the
reader's head rather than in the code. This page names the boundaries and says where each one
comes from, so the line is defensible rather than asserted.

The short version: **this is the security slice.** It inventories AI deployments, derives what
each is exposed to under an adversarial-ML taxonomy, records what is evidenced about its
security, and escalates what has gone stale or changed. Everything below is a real and
necessary activity that belongs to somebody else.

## The frame this sits inside

NIST's AI Risk Management Framework describes trustworthy AI through **seven characteristics**:
valid and reliable; **safe**; **secure and resilient**; **accountable and transparent**;
**explainable and interpretable**; **privacy-enhanced**; and **fair, with harmful bias
managed**.

Security is *one* of them. A tool that inventories AI and then reports on all seven is
implicitly claiming a competence its evidence does not support — and, worse, gives an
organisation a page that looks like AI governance while covering a seventh of it.

So the register covers **secure and resilient**, touches **privacy** only where an attack
class does (data recovered from a model, or reached through it), and stays out of the rest.

*Source: NIST AI 100-1, the AI Risk Management Framework, §3. Read the primary text before
relying on any characterisation of it here.*

## Not model evaluation

The register does not run, commission, score or interpret an evaluation of a model's outputs.
It records **that** an evaluation exists, at what tier, covering what scope, over what period —
and treats a provider's own evaluation as a T3 assertion, because the party being evaluated
chose what to evaluate.

Why not: evaluating a model is a discipline with its own methods, its own failure modes and its
own people. A security register that produced an accuracy figure would be putting a number
nobody here computed next to numbers this register refuses to compute at all.

**Whose it is:** the team that owns the model or the product, working with whoever the
organisation has for evaluation.

## Not bias or fairness assessment

There is no field for disparate impact, no fairness metric, no protected-attribute analysis.

Why not: this is the boundary most likely to be crossed by accident, because a deployment that
`decides` about people is obviously *somebody's* problem and this is the register that knows
about it. But bias assessment requires access to outcomes data, a legal view on which
attributes are protected in which jurisdiction, and a methodology this tool has none of. A
`biasChecked: true` field would be the most dangerous boolean in the suite: cheap to set, and
read by everyone downstream as though the work had been done.

What the register *does* do is make the deployment visible, name its owner, record that it
decides about people, and put the question in front of whoever owns it.

**Whose it is:** legal, HR or the product function, depending on the use.

## Not conformity assessment or regulatory scope

The register does not determine whether an organisation is a provider or a deployer under any
regime, does not assess conformity, and does not produce a declaration or technical
documentation. `references/regimes.json` ships with no regime content at all — see
`references/regimes.md` for why, and for what a verification pass would have to do.

Why not: role determination is a legal question whose answer changes every obligation that
follows, and getting it backwards fills a register with duties that are real and are somebody
else's.

**Whose it is:** legal, with qualified advice.

## Not an AI policy, and not procurement

No approval workflow, no intake form, no policy text, no "approved tools" list to maintain
alongside the register. `sanction` records a decision somebody made, with their name and their
reason; it does not make one, and it is not a gate anything has to pass through.

Why not: a register that becomes an approval workflow acquires a queue, and the failure mode of
shadow AI is a queue people route around. A discovered system is a real row the moment it is
found, precisely so that nothing has to wait for a process.

**Whose it is:** whoever owns technology procurement and the AI use policy.

## Not incident response, risk scoring, or acceptance

Each of these has a register in this suite already, and the boundary is the same in all three
cases — one exposure recorded in two systems of record is how the two come to disagree.

| activity | where it belongs |
|---|---|
| scoring a finding under likelihood × impact | `risk-register`, via `export-findings` |
| accepting a residual exposure, with an approver and an expiry | `exceptions-register` |
| determining whether an incident is material or disclosable | `incident-materiality` |
| rating a control's maturity against a framework outcome | `nist-csf` |
| writing what a board is told | `ciso-board-translation` |

## What was considered and rejected

Recorded so the next person can see the argument rather than re-run it.

- **A maturity or readiness score for the AI programme.** Rejected: the same objection as every
  score in this suite, plus a specific one — the inputs would be counts of classes and
  controls, and turning "three of five classes have a control recorded" into a number implies
  the other two are a shortfall against a target. There is no target. A class is not something
  you finish.
- **A `mitigated` flag on an exposure class.** Rejected, and guarded two ways. See
  `references/nistaml-exposure.md` §4.
- **A hand-selectable exposure list, "for flexibility".** Rejected: the class most likely to be
  deselected is the one that took longest to explain.
- **Model-keyed rather than deployment-keyed.** Rejected: it forces one answer for two
  different uses of the same model, and it would be the wrong one for whichever mattered more.
- **A staging area for discovered systems.** Rejected: it is a queue, and a queue is where a
  shadow-AI finding goes to be forgotten.
- **Prompt or output logging content in the register.** Rejected: the register records *that*
  logging exists and who can read it. Holding the content would make this store a target with
  the same data the deployment has, and none of its controls.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
