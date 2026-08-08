# `.air` store schema

`schemaVersion: 1`, `family: "ai-register"`. JSON, written atomically, human-readable on
purpose: a register somebody can only read through the tool is a register nobody audits.

`load()` refuses a store whose `family` is not `ai-register`, naming the file extensions that
belong to the sibling skills. Validation guards **writes**; a store already carrying a bad
value still opens, because refusing to open it would strand whoever has to fix it.

## Top level

```jsonc
{
  "schemaVersion": 1,
  "family": "ai-register",
  "meta":     { "orgName": "", "preparedBy": "", "scopeNote": "", "asOf": "YYYY-MM-DD" },
  "settings": { ... },
  "systems":     [ ... ],
  "deployments": [ ... ],
  "history":   [ ... ],     // append-only
  "snapshots": [ ... ],
  "createdAt": "…", "updatedAt": "…"
}
```

## `settings`

| key | default | meaning |
|---|---|---|
| `criticalityScale` | `["low","moderate","high"]` | lowest first. `untraced` and `unclassified` may never be members — `set_scale` refuses. |
| `scaleVersion` | `"v1"` | stamped onto every confirmed level, so a level read a year later can still be interpreted |
| `cadenceDays` | `{"high": 365, "moderate": 730}` | `low` has **no** cadence, deliberately: the always-fire triggers are what catch it |
| `traceMaxHops` | `2` | bounded walk; beyond it the result is `untraced` **and** `truncated` |
| `evidenceGraceDays` | `365` | measured from the end of an artifact's period |
| `proposalStaleDays` | `30` | how long a reading may sit un-assessed |
| `consolidation` | absent | `{declaredBy, basis}`; required before a multi-entity register renders as one view |

## `systems[]` — `S-001`

| field | notes |
|---|---|
| `name`, `provider`, `version` | **provider and version are required.** Without a version nothing can tell that the model under a deployment changed. |
| `family` | the product line, where it differs from the name |
| `baseModel` | **where disclosed only.** Left empty rather than guessed — `base-model-changed` would otherwise fire against a guess. |
| `hosting` | `self-hosted` \| `saas` \| `hybrid` |
| `genAI` | generative, or predictive when false. Gates `NISTAML.04` and the adversarial battery. |
| `fineTuned`, `retrievalAugmented` | both feed `NISTAML.03` |
| `vendorRef`, `arrangementRef` | the `vendor-register` `V-` / `VA-` ids. Data, never a lookup. |
| `chainNote` | free text, deliberately: the chain behind a model is often several parties deep and partly undisclosed, and a structured field would imply a completeness nobody has |
| `provenance` | `declared` \| `discovered` |
| `sanction` | `sanctioned` \| `unsanctioned` \| `under-review`, with `sanctionBy`, `sanctionOn`, `sanctionWhy` |
| `discoveredVia`, `discoveredOn` | present only on a discovered system; both required at intake |

## `deployments[]` — `D-001`

**This is where risk lives.** One system may carry many.

| field | notes |
|---|---|
| `systemRef` | refused if it names a system not in the inventory |
| `entityRef` | defaults to the org name; drives the multi-entity check |
| `purpose`, `owner` | both required |
| `autonomy` | `informs` \| `recommends` \| `decides` \| `acts`. **Required**, declared, never inferred. |
| `autonomyDeclaredBy`, `autonomyDeclaredOn` | carried into any skip record, per CAC-AP-1 §2.4 |
| `declares` | `{flag: {value, declaredBy, declaredOn, basis}}`. §2.3: outranks the org profile in both directions. Absence is not a declaration. |
| `dataClasses[]`, `connectedResources[]` | both feed `NISTAML.03`; connected resources also feed `autonomy-increased` |
| `consequentialDecision` | a flag, checked against autonomy by `autonomy_warnings` |
| `supports` | the workflow name the criticality walk starts from |
| `addedOn` | where the cadence clock starts when nothing has ever been assessed |
| `criticality` | see below |
| `exposure` | see below |
| `evidence[]`, `proposals[]`, `requirements[]`, `assessments[]` | the assessment layer |
| `retired` | null, or a record; retired deployments escalate nothing |

### `criticality`

```jsonc
{
  "derived": "high" | "untraced",
  "derivedOn": "YYYY-MM-DD",
  "trace": ["Applicant tracking", "CRM"],
  "truncated": false,
  "confirmed": {
    "value": "high", "by": "R. Calder", "on": "YYYY-MM-DD",
    "basis": "…", "scaleVersion": "v1", "againstDerived": "moderate"
  }
}
```

`confirmed` is `null` until a named person assigns. `againstDerived` records what the walk said
at the time, so a later disagreement escalates as a finding rather than silently overwriting.

### `exposure`

Keyed by class id. **Derived from attributes; there is no command to select an entry.**

```jsonc
{
  "NISTAML.02": {
    "class": "NISTAML.02",
    "name": "integrity",
    "concern": "an attacker causing the deployment to produce the output they choose",
    "because": "…, from something declared on the record",
    "controls": [
      { "control": "…", "evidence": "…", "on": "YYYY-MM-DD", "by": "Head of Security" }
    ],
    "noLongerDerived": true   // only when the class stopped deriving and carries controls
  }
}
```

**There is no `mitigated`, `resolved`, `closed` or `accepted` key here, and there never will
be.** See `nistaml-exposure.md` §4. Two states are computed from this block —
`no-controls-recorded` and `controls-recorded` — and there is no third.

### `evidence[]` — `EV-001`

`kind`, `tier` (`T1`–`T4`), `source`, `scope`, `periodStart`, `periodEnd`, `url`,
`retrievedOn`, `ingestedOn`, `ingestedBy`.

- **T1 requires `scope` and a period.** An artifact whose limits are not written down gets read
  as though it had none, and a report with no period cannot expire.
- **A `url` requires `retrievedOn`.**
- A known kind cannot be recorded above its ceiling: a **model card is T3**, a trust page T4.

### `proposals[]` — `PR-001`

`requirement`, `evidenceRef`, `citation`, `note`, `status` (`proposed` → `confirmed` |
`rejected`), and the who/when of each transition. **A proposal satisfies nothing.** `propose`
refuses without a citation, and refuses to cite T3 or T4 at all.

### `requirements[]`

`requirement` (a `battery.question` key), `met`, `evidenceRef` or `evidence`, `citation`,
`checkedOn`, `checkedBy`, `viaProposal`. A row with `met: false` and a `checkedBy` is what
`export-findings` carries to `risk-register`.

### `assessments[]`

`on`, `by`, `confirmed[]`, `rejected[]`, `note` — and, importantly, **what it was assessed
against**:

```jsonc
{
  "againstSystem": { "systemRef": "S-001", "version": "2026.4",
                     "baseModel": "GPT-cx-2", "hosting": "saas" },
  "againstAutonomy": "decides",
  "againstConnectedResources": ["endpoint management", "the service desk"]
}
```

This is what makes `model-changed`, `base-model-changed` and `autonomy-increased` possible.
Comparing today's system against the one the assessor actually had in front of them is the only
way to notice a silent swap.

## `history[]`

Append-only: `{event, target, actor, ts, why?, detail?}`. Never rewritten, never pruned by the
engine.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
