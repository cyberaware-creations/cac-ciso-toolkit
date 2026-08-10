---
name: ai-register
description: >-
  Maintain a security register of the AI the organisation actually runs — which models and
  products are in use, what each DEPLOYMENT of them touches, how critical it is, what it is
  exposed to under the NIST adversarial machine learning taxonomy (AI 100-2 E2025), and what is
  evidenced about its security. This is the CISO's slice of AI governance and says so: it
  inventories and
  assesses SECURITY, and does not evaluate models, assess bias, perform conformity assessment or
  determine regulatory scope — see references/scope.md, which names those boundaries with their
  sources. Whether the organisation is in scope for the EU AI Act or any other AI regime, and in
  which role — deployer, provider, importer — is DECLARED in the applicability profile that
  business-context owns, on legal advice, and is never inferred here. This skill's regime
  overlays are SELECTED by that declaration rather than a substitute for it, and
  references/regimes.json ships empty on purpose. Risk
  lives in the deployment, not the model: the same LLM drafting copy and screening applicants
  is one system and two entirely different exposures. Exposure classes are DERIVED from
  recorded attributes and there is no command to select them by hand. An attack class has NO
  closed state — no mitigated, resolved or accepted field anywhere — because mitigations are
  empirical and defences have repeatedly been broken; controls are recorded with evidence and
  a date, and an acceptance belongs in exceptions-register. Criticality is derived by tracing
  what a deployment supports back to a business workflow and confirmed by a named person; a
  deployment the trace cannot reach is `untraced`, never `low`. Shadow AI found in a CASB or
  expense review is a real row immediately, unsanctioned, with no staging area. Emits no AI
  risk score, deliberately and under an eval. Use when asked to inventory AI systems or
  agents, record a new AI deployment, work out what an AI deployment is exposed to, log an
  unsanctioned or discovered AI tool, check what evidence covers a model, find AI deployments
  overdue for assessment, or build the AI section of a board pack. NOT for evaluating model
  quality or bias, deciding whether a regime such as the EU AI Act applies or which role the
  organisation holds under it (business-context declares that), accepting a residual
  (exceptions-register), scoring a risk (risk-register), or rating a control (nist-csf).
---

# ai-register

**A security register of the AI the organisation runs.** Not an AI governance programme, not a
model evaluation harness, not a conformity assessment. The security slice, named as such —
`references/scope.md` says what this skill does not own, and cites why.

Three ideas carry it, and each is a refusal as much as a feature.

## 1. Risk lives in the deployment, not the model

The same LLM drafting marketing copy and screening job applicants is **one system and two
exposures**. A register keyed on the model would force one answer, and it would be the wrong
one for whichever deployment mattered more.

| Object | Is | Carries |
|---|---|---|
| `system` (`S-001`) | a model or AI product the organisation has | provider, version, base model where disclosed, hosting, generative or predictive, fine-tuned, retrieval-augmented, provenance, sanction, the `vendor-register` arrangement it comes under |
| `deployment` (`D-001`) | one use of one system | purpose, **owner**, **autonomy**, data classes, connected resources, what it supports, criticality, exposure, evidence, assessments |

`add-system` refuses without a **provider** and a **version**. Without a version nothing can
tell that the model under a deployment changed — the event that silently invalidates every
assessment made against it.

`deploy` refuses without an **owner** and a declared **autonomy**:

| autonomy | means |
|---|---|
| `informs` | it produces output a person reads |
| `recommends` | it proposes an action a person takes |
| `decides` | its output IS the decision — what most regimes call a consequential decision |
| `acts` | it takes actions against connected resources with no person in the loop |

Declared, never inferred. What a deployment is permitted to do is a statement about how it was
wired up and who signed that off, and no attribute of a model implies it. It gates the security
battery and every regulatory question here, so an undeclared one would be assessed anyway,
quietly, at the default.

## 2. An attack class has no closed state

Exposure follows the NIST adversarial ML taxonomy's shape: **availability**, **integrity**,
**privacy**, **misuse**, **supply chain**. `references/nistaml-exposure.md` sets out how each
is derived and what is and is not being claimed about the source.

Two rules hold this together, and both are checked rather than remembered.

**Exposure is DERIVED, never selected.** There is no command to mark a class applicable or
inapplicable. A hand-selectable list becomes a list somebody trims when it is inconvenient, and
the class most likely to be trimmed is the one that took longest to explain. Change the
attributes and the exposure recomputes; the record says *why* each class applies, from
something declared.

**There is no closed state.** No `mitigated`, `resolved`, `closed` or `accepted` field on a
class, and no command that sets one. NIST's position is that adversarial ML mitigations are
empirical rather than guaranteed, that published defences have repeatedly been broken by
adaptive attacks, and that the problem remains open. A register that let somebody tick a class
as handled would assert exactly what the source declines to.

Controls are recorded **with evidence and a date**. A class with controls reads as *controls
applied*, never as resolved. Wanting to accept the residual is legitimate — and it is an
**acceptance**, which needs an approver, a justification, an expiry and a re-validation act.
The refusal names `exceptions-register`, because a refusal with nowhere to go gets worked
around.

## 3. This is the CISO's slice

The skill supplies an inventory and a security assessment to whoever owns AI governance. It
does not evaluate models, assess bias, or determine regulatory scope. `references/regimes.json`
ships **empty**: the mechanism is there, the content is not, because a tool asserting an
obligation it cannot cite to primary text is worse than one that stays quiet.
`references/regimes.md` sets out what a verification pass has to do.

---

## Criticality, mirrored from `vendor-register`

Same word, same properties, same refusals — a CISO who learned this vocabulary once must not
meet a second one for it.

- **Derivation proposes; a named person assigns.** `--confirm` without `--by` is refused.
- **`untraced` is a value, not a gap.** It means the walk ran and did not reach a workflow with
  a declared criticality. It is never `low`, never a member of the scale, and
  `criticality_rank` **raises** rather than ordering it.
- **A truncated walk returns `untraced` AND `truncated`** — never a confident level from an
  unfinished walk.
- With no `--context`, everything derives `untraced`. Loud and correct.

## The Layer A / Layer B boundary

Reading **proposes**; only a named person **confirms**.

- `propose` refuses without a **citation**. A proposal with no citation is an opinion.
- `propose` refuses to cite **T3 or T4 at all**.
- `assess` refuses without `--by`, and `--reject` refuses without `--why`.

**A model card is T3.** It is the most substantive-looking artifact in the whole AI supply
chain — structured, technical, full of measured numbers, often the only thing a provider
publishes — and nobody independent produced it, nothing in it is an obligation with a remedy
behind it, and the evaluations it reports were chosen by the party being evaluated. `ingest`
refuses to record one above T3. It is genuinely useful for working out what to **ask**, and it
is never a reason to stop asking.

| tier | is | may close a requirement |
|---|---|---|
| T1 | an audited artifact — an independent evaluation, a third-party red-team report, a penetration test of the deployment | yes |
| T2 | a contractual commitment — an executed DPA, a signed no-training clause | yes |
| T3 | an assertion by the party described — model card, system card, provider evaluation, our own DPIA | **no** |
| T4 | public copy — a trust page, a product blog | **no** |

## Escalations

`subjectKind: "deployment"`. Derived every run, never stored, and nothing blocks.

| trigger | fires when |
|---|---|
| `unclassified` / `untraced` | same vocabulary as `vendor-register` |
| `attack-class-uncontrolled` | an applicable class with no control recorded |
| `model-changed` | model, version or hosting changed since the last assessment |
| `base-model-changed` | the disclosed base model changed — **even when the product version did not** |
| `autonomy-increased` | autonomy rose, or connected resources grew, since the last assessment |
| `assessment-overdue` | beyond cadence for its confirmed criticality |
| `unowned` | no owner |
| `provider-arrangement-missing` | SaaS-hosted with no `arrangementRef` |
| `unsanctioned-in-use` | an unsanctioned system with a live deployment |

**`model-changed`, `base-model-changed` and `unsanctioned-in-use` fire at every criticality
level, including the lowest.** `low` has no cadence by design, and a silent model swap is
exactly the event that makes a low-criticality deployment stop being low.

## Shadow AI

`intake-discovered` refuses without a **source** and a **found-on date**, and then makes the
system a real row immediately — unsanctioned, incomplete, and *in* the register where it can
escalate. There is no staging area, deliberately: the failure mode of shadow AI is a finding
that lives in a spreadsheet, an email thread or a CASB console until somebody remembers to
promote it.

## What crosses to other skills

| to | what | shape |
|---|---|---|
| `risk-register` | `export-findings` — requirements a named person recorded NOT met | one-way, idempotent, **no likelihood, impact or score**; attack classes are not exported, because a class has no closed state and a risk does |
| `nist-csf` | `export-signal` — counts only | evidence for the Cyber AI Profile scoping question, never an answer to it |
| `board-pack` | the `ai` section, item key `deployments` | additive within `contractVersion: 1` |
| `exceptions-register` | where an acceptance belongs | named in the refusal |

No skill imports another. Every transport is data (CAC-AP-1 §2.6).

## Commands

```bash
python3 scripts/ai_register.py init acme.air --org "Acme Manufacturing"
python3 scripts/ai_register.py add-system acme.air --name "Contoso Assist" \
    --provider Contoso --version 2026.4 --base-model GPT-cx-2 --retrieval-augmented \
    --arrangement VA-001 --by CISO
python3 scripts/ai_register.py deploy acme.air --system S-001 \
    --purpose "screening job applicants" --owner "HR Director" --autonomy decides \
    --data-class "applicant personal data" --supports "Applicant tracking" \
    --consequential --by CISO
python3 scripts/ai_register.py classify acme.air --deployment D-001 --context ctx.json \
    --confirm high --by "R. Calder" --basis "a decision about a person"
python3 scripts/ai_register.py ask acme.air --deployment D-001 --context ctx.json
python3 scripts/ai_register.py ingest acme.air --deployment D-001 --kind red-team-report \
    --tier T1 --source "Fabrikam Security, engagement 41" \
    --scope "the chat surface; EXCLUDES tool calling" \
    --period-start 2026-01-06 --period-end 2026-03-27 --by CISO
python3 scripts/ai_register.py propose acme.air --deployment D-001 \
    --requirement adversarial-testing.red-team --evidence EV-001 \
    --citation "section 4.2" --by "Security Analyst"
python3 scripts/ai_register.py assess acme.air --deployment D-001 --by CISO --confirm PR-001
python3 scripts/ai_register.py record-control acme.air --deployment D-001 \
    --class NISTAML.02 --control "untrusted-content filter" \
    --evidence "config export NW-CFG-118" --on 2026-03-30 --by "Head of Security"
python3 scripts/ai_register.py analyze acme.air --context ctx.json --out analysis.json
python3 scripts/ai_register.py export-findings acme.air --out findings.json
python3 scripts/ai_register.py export-signal acme.air --out signal.json
python3 scripts/ai_register.py self-test
```

Rendering:

```bash
cd renderers && python3 render_operational.py --in ../analysis.json --out operational.html
```

```bash
cd renderers && python3 render_board.py --in ../analysis.json \
    --translations ai.board.json --out board.html
```

## What this will not do

- **No AI risk score.** Not a posture grade, not a readiness index, not a coverage percentage.
  A generated number looks like an assessment, is irreproducible, and disagrees with the
  register that actually owns scoring. Enforced by `evals/no-ai-score.sh`, behaviourally and
  statically — a score renamed `attentionIndex` escapes only the first.
- **No way to close an attack class.** Enforced by `evals/no-closed-state.sh`, and by
  `evals/board-safety.sh` on the rendered page: no green fill, no tick, no "3 of 5 covered".
- **No model evaluation, bias assessment or conformity assessment.** See
  `references/scope.md`.
- **No regulatory scope determination.** `references/regimes.json` is empty on purpose.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
