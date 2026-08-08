# NISTAML exposure — the taxonomy as implemented, and the rule that governs it

## 1. What is being claimed about the source, said plainly

The five classes below follow the **shape** of NIST's work on adversarial machine learning
(the AI 100-2 series): a taxonomy of attacks on AI systems organised by what the attacker is
trying to achieve, split between predictive and generative systems.

**That publication is not bundled in this repository**, the way the CSF 2.0 Core and the
800-53 crosswalk are. This file describes what the engine implements. It does not quote the
publication, it does not reproduce its attack taxonomy, and **nothing here should be relied on
as a citation without checking the source.** Where this document characterises NIST's position
— particularly in §4 — that characterisation is a summary written from reading, and the
primary text is the authority.

The class identifiers `NISTAML.01` … `NISTAML.05` are **this tool's own labels**. They are not
NIST identifiers, and no publication numbers its attack categories this way. They exist so
that a store, a page and a board pack can refer to the same thing unambiguously.

## 2. The five classes, and what derives each

| id | name | the concern | derived when |
|---|---|---|---|
| `NISTAML.01` | availability | an attacker degrading the service the deployment provides | always |
| `NISTAML.02` | integrity | an attacker causing the deployment to produce the output they choose | always |
| `NISTAML.03` | privacy | an attacker recovering data the deployment was trained on or has access to | it handles declared data classes, **or** the model was fine-tuned, **or** retrieval puts organisation data in its context, **or** it reaches connected resources |
| `NISTAML.04` | misuse | an attacker using the deployment's own generative capability for their ends | the system is **generative** |
| `NISTAML.05` | supply chain | compromise reaching the deployment through the model or its supply chain | the provider is **external** |

Two of these discriminate, and the discrimination is the point.

**Misuse is a generative concern.** A predictive classifier has no generative capability for an
attacker to borrow. Asking about it would be noise in a register whose whole value is that
every question in it is live.

**Supply chain applies wherever the model comes from outside**, which is the join to
`vendor-register`. It is why `arrangementRef` exists on a system, and why
`provider-arrangement-missing` escalates a SaaS system with no arrangement recorded: the
contractual questions that class raises — incident notice, subprocessors, exit — are asked
there, of the provider, not here.

Availability and integrity apply to everything. A model that can be degraded or steered is
every model; the only question is what that costs *here*, which is what criticality answers.

## 3. Derived, never selected

**There is no command to mark a class applicable or inapplicable.** Not in the CLI, not in the
module. `evals/exposure.sh` checks for the absence, because an absence grows back.

The reason is not that hand-selection is unthinkable; it is that a hand-selectable list becomes
a list somebody trims when it is inconvenient, and **the class most likely to be trimmed is the
one that took longest to explain**. Every class carries a `because` string built from something
declared on the record, so a reader can always ask "why is this here" and get an answer that is
not "somebody ticked it".

Change the attributes and the exposure recomputes. Recomputing **preserves controls**: a
control recorded against integrity is still a control that was applied, even if the class
stopped being derivable, and a class in that state is kept and marked `noLongerDerived` rather
than deleted. Deleting it would throw away evidence somebody produced; pretending it were still
applicable would be a different lie.

## 4. There is no closed state — the rule, and why

**No `mitigated`, `resolved`, `closed`, `accepted`, `remediated` or `handled` field exists on
an exposure class, and no command sets one.** There are exactly two states:

```
no-controls-recorded    controls-recorded
```

and there is no third.

The reason is what the adversarial-ML literature says about its own mitigations. NIST's
position, as this project reads it: mitigations in this space tend to be **empirical and
limited in nature** rather than offering information-theoretic guarantees; published defences
have **repeatedly been broken by adaptive attacks**; detecting adversarial examples is about as
hard as defending against them; and the problem **remains open**. *That is a summary. Check
the primary text.*

A register that let somebody tick a class as handled would assert exactly what the source
declines to assert. And the assertion would not stay in the store — it would reach a board
page, where "mitigated" ends a conversation.

So: controls are recorded **with evidence and a date**. `record-control` refuses without both.
A class with three controls against it reports as `controls-recorded`, which says what
happened — somebody recorded a control — and stops there.

### Where the legitimate need goes

Wanting to accept a residual exposure is entirely reasonable, and it is a real act with a real
shape: an approver, a justification, an expiry, a re-validation. `accept_exposure` exists in
the module **only to refuse**, and the refusal names `exceptions-register`, because a refusal
with nowhere to go just gets worked around.

### How the rule is held

Four ways, because it is the rule most likely to be relaxed later — its absence looks like a
gap rather than a decision, and restoring it is a one-line change nothing else would object to.

1. `evals/no-closed-state.sh`, **behavioural**: nothing inside a real store's exposure block,
   at any depth, in a key or a value, matches the closed-state pattern.
2. The same eval, **static**: no shipped `.py` assigns such a field, writes one through
   `setdefault`, or defines a function named for closing a class that does not refuse.
3. `evals/board-safety.sh`, **on the page**: no closure vocabulary in the rendered HTML, and no
   green fill, tick or completion ratio on an exposure class. A green chip says "done" to every
   reader in the room faster than any sentence undoes it.
4. Both mutation-tested inside the suites themselves, so a guard nobody has watched fail is
   never trusted.

## 5. What an exposure class is not

- **Not a finding.** `export-findings` carries requirements a named person recorded as not met.
  An uncontrolled class is a fact about something with no closed state; a risk in
  `risk-register` has one, and exporting a class would defeat this rule one hop away and out of
  sight.
- **Not a severity.** There is no ranking among the five, and no arithmetic over them. Counting
  classes with no control recorded is a count; averaging it against criticality would be the AI
  risk score arriving through a side door, and `evals/no-ai-score.sh` reads the arithmetic to
  make sure it does not.
- **Not a control framework.** The class says what the deployment is exposed to. What to do
  about it is a control question, and controls are rated in `nist-csf`.

---

*A Cyber Aware Creation · Not affiliated with NIST, and not endorsed by it. Not legal advice.*
