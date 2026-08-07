# `GV.SC` and `SR` — where each part of this skill has a home

Every structural element of `vendor-register` maps to an outcome already bundled in this
repository. The mapping is the design, not a retrofit.

## CSF 2.0 `GV.SC` — the outcomes

Quoted concepts from `skills/nist-csf/references/nist-csf-2.0-core.json`, which ships here.

| Subcategory | Becomes |
|---|---|
| `GV.SC-01` — programme, strategy, policies established | Register `settings`: the scale, the cadences, the declared approach |
| `GV.SC-02` — roles and responsibilities for suppliers | The owner on every arrangement. **Refused without one** |
| `GV.SC-03` — C-SCRM integrated into enterprise risk | The one-way bridge to `risk-register` *(Plan 2)* |
| `GV.SC-04` — suppliers known and prioritized by criticality | **The criticality walk** — the whole conditional engine |
| `GV.SC-05` — requirements integrated into contracts | `review-requirements`, and its refusal without an evidence reference |
| `GV.SC-06` — due diligence before entering relationships | The `assess` act, pre-contract *(Plan 2)* |
| `GV.SC-07` — risks recorded, assessed, responded to, monitored | The arrangement record and its history |
| `GV.SC-08` — suppliers included in incident planning | Link to `incident-materiality` *(Plan 2)* |
| `GV.SC-09` — performance monitored through the lifecycle | Cadence by criticality, and the triggers that fire regardless |
| `GV.SC-10` — provisions for after the agreement ends | `exit` (documented **and** tested, separately), and `retire` with data return and confirmed deletion |

## SP 800-53r5 `SR` — the controls

| Control | Where it lands |
|---|---|
| `SR-1` Policy and Procedures | Register `settings` |
| `SR-2` Supply Chain Risk Management Plan | The declared approach; the bridge to `risk-register` |
| `SR-3` Supply Chain Controls and Processes | Requirement coverage, monitoring |
| `SR-5` Acquisition Strategies, Tools, and Methods | Pre-contract assessment *(Plan 2)* |
| **`SR-6` Supplier Assessments and Reviews** | **The skill's core act** — at contract and on cadence |
| `SR-8` Notification Agreements | Incident-notification requirements |
| `SR-10` Inspection of Systems or Components | Evidence verification *(Plan 2)* |
| `SR-11` Component Authenticity | Provenance questions — the reason `--layer component` survives *(Plan 2)* |
| `SR-12` Component Disposal | `retire` — data return and confirmed deletion |

## `SR-4`, `SR-7` and `SR-9`: absent from the *mapping*, not from 800-53

The plan left this open, and it is answerable from this repository rather than from an external
source. **They are absent from the CSF→800-53 mapping, not from SP 800-53 itself.**

The bundled catalogue says so in its own words. `skills/nist-csf/references/crosswalks/800-53-r5.catalog.json`
declares:

```json
"catalogueScope": {
  "coverage": "referenced-subset",
  "note": "Holds the controls the NIST CSF export references, not all of SP 800-53 Rev 5. An
           empty outside-CSF list therefore means nothing further is catalogued here, not that
           CSF reaches every 800-53 control."
}
```

So the `SR` controls this repository can reach are exactly those the NIST-published CSF mapping
references — `SR-1, 2, 3, 5, 6, 8, 10, 11, 12`. The three that are missing are missing because
the mapping does not reach them, and a reader should not infer that the gap was a judgement made
here about their relevance.

**What that means in practice:** if your organisation assesses against 800-53 directly, `SR-4`,
`SR-7` and `SR-9` are yours to handle outside the crosswalk. This skill will record an arbitrary
`--sr` reference on an arrangement, so nothing stops you citing them; what it cannot do is
project them back through a crosswalk that does not contain them.

---

*A Cyber Aware Creation · Not affiliated with NIST. Crosswalks are derived projections, never an
audit or a certification.*
