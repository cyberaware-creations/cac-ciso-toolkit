# Assessment & Review — the workflows

Five workflows carry this skill. **0** logs a source the moment it comes up, mid-conversation. **A**
builds or extends a Profile. **B** is the recurring review that keeps it honest. **C0** cold-starts
an empty Profile in nine batched questions rather than 106. **C** works the confirmation queue that
accretes between reviews. Most sessions are A, B, or C; 0 happens inside all of them, whenever a
source comes up.

Every command below is real. If a step here names a flag that `profile_analysis.py` does not
accept, the doc is wrong — fix the doc, not the user's expectations.

---

## Workflow 0 — Record a source

Evidence arrives before anyone has time to decide what it means: a review finishes, a debrief
happens, a document lands. Log it the moment it comes up — this takes seconds and **writes no
ratings**, so it never blocks the conversation it interrupts.

```bash
python3 scripts/profile_analysis.py intake add acme.csfp \
  --label "architecture review with infra team" \
  --subjects ID.AM-01 ID.AM-02 \
  --source-date 2026-03-14 --recorded-by "Darren"
```

`--label` is a note *about* the source, in the user's own words or confirmed by them.
`--source-date` is when the conversation happened, not today. `--subjects` takes every Subcategory
the source bears on — one record per source, not one per Subcategory.

### Getting from a fragment to a record

Fragments arrive as prose: *"just came out of the architecture review — infra reckon they scan for
new kit quarterly, and there's a CMDB but nobody trusts the OT side of it."*

Propose, do not assert:

> That sounds worth logging. Label it *"March architecture review — infra"*? I'd point it at
> **ID.AM-01** (hardware inventory) and **ID.AM-02** (software), since the CMDB and the scans speak
> to both. I'd leave **ID.AM-05** off — criticality didn't come up. Sound right, and when was the
> review?

Three things are happening there, and all three matter:

- **The label is offered, not imposed.** It is a note about the source in the user's own register,
  and they get to rewrite it. Never write an excerpt of what the source said.
- **Subjects are justified individually.** Naming why each id is attached is what lets the user
  strike one. A bare list gets waved through.
- **What was left off is said out loud.** Over-attaching is the failure mode here: every extra id
  becomes evidence-pending, and the queue then promises material that does not exist. Say what you
  excluded and why.

Then, and only then:

```bash
python3 scripts/profile_analysis.py intake add acme.csfp \
  --label "March architecture review — infra" \
  --subjects ID.AM-01 ID.AM-02 \
  --source-date 2026-03-12 --recorded-by "Darren"
```

Ask for the date. `--source-date` defaults to today, which is right for a conversation happening now
and wrong for everything else — and a wrong date silently misreports age and can invert a `revisit`
comparison.

**No rating is discussed at this step.** If the user offers one — *"so that's probably a 2"* — log
the source, then say the rating is a Workflow C decision and let them make it there with the source
in front of them. That is not pedantry: a rating decided in passing, mid-topic, is exactly what the
confirmation session exists to prevent.

---

## Workflow A — Build or extend the Profile

```
- [ ] 1. Scope it before rating anything
- [ ] 2. Initialise the store
- [ ] 3. Rule out what genuinely does not apply
- [ ] 4. Set a baseline Target, then tune it by risk
- [ ] 5. Assess Current, with evidence
- [ ] 6. Characterize Tiers (optional, and separate)
```

### 1. Scope it before rating anything

An unscoped Profile produces numbers nobody can defend. Establish, in the user's words:

- **Purpose** — what decision this Profile informs. "We need a board answer on where we stand" and
  "we're preparing for a customer security review" produce different Targets.
- **Org units** — which parts of the organization are in. A Profile covering "corporate IT" is a
  different artefact from one covering "corporate IT and three plants."
- **Threat types** — what this Profile is oriented against (ransomware, supply chain, insider).
- **Owner** — the accountable role.
- **Assumptions** — anything a reader needs in order to interpret a rating correctly.

Push back on "everything, everywhere." Scope is what makes the ratings mean something.

### 2. Initialise the store

```bash
python3 scripts/profile_analysis.py init \
  --name "Acme Corp — Enterprise Profile" \
  --out acme.csfp \
  --owner "CISO" \
  --purpose "Baseline the programme ahead of the Q4 board review" \
  --org-units "Corporate IT" "Plant OT" \
  --threat-types ransomware "supply chain compromise" \
  --assumptions "Physical security is assessed separately."
```

This seeds all 106 Subcategories as **unrated and untargeted** — deliberately. A fresh Profile
reports *no coverage figure at all*, which is the truth, rather than 0% or 100%, which are both
lies.

### 3. Rule out what genuinely does not apply

Rare, and always justified. Out-of-scope is not a rating:

```bash
python3 scripts/profile_analysis.py set acme.csfp DE.AE-02 \
  --applicability not-applicable \
  --rationale "Event analysis is contracted to an MSSP and assessed under their profile."
```

Be sceptical here. "We don't do that" usually means *the outcome is not achieved* — rating `0` —
not that the outcome does not apply. Reserve `not-applicable` for outcomes genuinely outside the
scope you set in step 1. The rationale is required because an auditor will ask.

### 4. Set a baseline Target, then tune it by risk

```bash
python3 scripts/profile_analysis.py quickstart-target acme.csfp
```

Defaults every in-scope Target to **level 2 (Largely Achieved)** — a defensible baseline, not a
maximum. Re-running at the same level is a true no-op, so it is safe to repeat.

Then **tune**, which is the part that carries the judgment:

```bash
# Raise where risk warrants it
python3 scripts/profile_analysis.py set acme.csfp PR.AA-01 --target 3 \
  --rationale "Identity is the primary control for the ransomware scenario this Profile targets."

# Lower where it does not
python3 scripts/profile_analysis.py set acme.csfp PR.DS-02 --target 1 \
  --rationale "Data in transit is limited to a segmented plant network; proportionate at level 1."
```

> A Profile where every Target is 3 is not a Target Profile — it is a wish list. NIST is explicit
> that Targets reflect risk-based prioritization. If the user wants everything at maximum, ask what
> they would fund first; the answer *is* the prioritization.

Also set priority, which weights the gap ranking:

```bash
python3 scripts/profile_analysis.py set acme.csfp GV.RM-01 --priority critical
```

### 5. Assess Current, with evidence

The core of the work. A Current rating needs a recorded source first — see Workflow 0 — then a
decision:

```bash
python3 scripts/profile_analysis.py intake add acme.csfp \
  --label "IAM policy review and a sample of 20 OT accounts" --subjects PR.AA-01 \
  --source-date 2026-07-20 --recorded-by "Darren"

python3 scripts/profile_analysis.py set acme.csfp PR.AA-01 \
  --current 1 \
  --source in-0001 --confirmed-by "Darren" \
  --evidence "iam-policy-v4.pdf" "ticket:SEC-2211" \
  --notes "SSO covers corporate apps; plant OT still uses local accounts." \
  --rationale "Assessed against the IAM policy and a sample of 20 OT accounts."
```

`--current` **refuses without both `--source` and `--confirmed-by`.** A rating is the claim the
whole report rests on, so it does not exist without a named source and a named person attached to
it. Never fill either flag with a guess to get past the refusal — if there is no recorded source yet,
that is Workflow 0, not a reason to invent one.

Rating guidance, using the default scale:

| Rating | Means | The test |
|---|---|---|
| 0 | Not Achieved | Nothing meaningful in place. |
| 1 | Partially Achieved | Exists somewhere, inconsistently, or for some assets only. |
| 2 | Largely Achieved | Works as intended in most of the scope, with known gaps. |
| 3 | Fully Achieved | Consistent across scope, and you could show evidence today. |

Ask "what would you show an auditor?" A rating with no answer to that is a 1, not a 3.

Use the Implementation Examples as the prompt — `analyze` attaches them to every gap row, and all
106 Subcategories have at least one. They turn "we're weak on PR.AA-01" into a concrete next step.

### 6. Characterize Tiers (optional, and separate)

Tiers are set on the Profile, not per Subcategory. They characterize the **rigor** of risk
governance and management practices — read the verbatim NIST text in the Core's `tiers` block with
the user and let them place themselves, then record the judgment:

```bash
python3 scripts/profile_analysis.py set-tier acme.csfp --overall 2 --function GV=3 PR=2 \
  --rationale "Board review: governance is repeatable; delivery is inconsistent across units."
```

Use the command, never a hand edit. `set-tier` requires `--rationale`, refuses a fractional Tier,
and appends a history event — the three things that make a Tier a recorded judgment rather than a
number that appeared in the file. It never reads the ratings; there is no code path from coverage to
a Tier, by design.

> **Never** compute a Tier from the ratings, average Tiers, trend them as a maturity score, or
> report "Tier 2.4". NIST calls Table 2 a *notional illustration*. Conflating Tiers with maturity is
> the single most recognizable tell that a CSF report was not written by someone who reads NIST.

---

## Workflow B — The assessment review

The recurring ritual. Its value compounds: what moved, when, and **why**.

```
- [ ] 1. Diff against the last review
- [ ] 2. Update Current where reality moved — with reasons
- [ ] 3. Work the attention lists
- [ ] 4. Turn gaps into owned, dated actions
- [ ] 5. Snapshot
- [ ] 6. Report
```

### 1. Diff against the last review

Open with what changed, not with the current state:

```bash
python3 scripts/profile_analysis.py diff acme.csfp
```

### 2. Update Current where reality moved

```bash
python3 scripts/profile_analysis.py set acme.csfp PR.AA-01 --current 2 \
  --source in-0001 --confirmed-by "Darren" \
  --rationale "OT identities migrated to the corporate IdP in October; 40 local accounts remain."
```

`--source` must name a real `intake` record — log the review or conversation this decision is drawn
from first (Workflow 0) if it isn't recorded yet.

When you checked and nothing changed, say so explicitly — "reviewed, no change" is a finding, and
it is the only thing that stops a stale rating from looking fresh:

```bash
python3 scripts/profile_analysis.py set acme.csfp GV.OC-01 --reviewed
```

`lastReviewed` moves only on a Current change or an explicit `--reviewed`. Editing notes does not
reset staleness, by design.

### 3. Work the attention lists

```bash
python3 scripts/profile_analysis.py analyze acme.csfp --today 2026-10-01 --top 10 > analysis.json
```

`analyze` surfaces six lists. Each has a question attached to it:

| List | The question to ask |
|---|---|
| **Largest gaps** (by prioritized score) | Is anything being done about the top five? |
| **Never reviewed** | Why has nobody looked at these at all? |
| **Stalest** | Is this rating still true, or just old? |
| **Unowned actions** | Who owns this? An action without an owner is a wish. |
| **Past-due actions** | Slipped, or abandoned? Re-date it or close it honestly. |
| **Accepted gaps** | Is the acceptance still valid, and who re-affirms it? |

Accepted gaps deserve particular attention. A gap accepted eighteen months ago under different
circumstances, never revisited, is how organizations end up surprised.

### 4. Turn gaps into owned, dated actions

A gap that does not become owned work will be on the same list next quarter:

```bash
python3 scripts/profile_analysis.py action add acme.csfp \
  --title "Decommission remaining local OT accounts" \
  --linked PR.AA-01 PR.AA-05 \
  --owner "Head of Infrastructure" \
  --milestone "Q1 2027" \
  --target-date 2027-01-31

python3 scripts/profile_analysis.py action close acme.csfp A-003 \
  --rationale "Threat intel feed live and integrated with the SIEM since 12 Sept."
```

Closure requires a rationale — it is a completion claim.

### 5. Snapshot

Freeze the review so the next one has something to diff against:

```bash
python3 scripts/profile_analysis.py snapshot acme.csfp \
  --label "Q3 2026 Assessment" \
  --note "Post-remediation review; board pack issued 2026-10-15."
```

Snapshots freeze assessments, action items, and computed rollups. Do this **after** the updates and
**before** reporting, so the report and the snapshot agree.

### 6. Report

See SKILL.md for the reporting path. In short:

```bash
# Operational (CISO and team)
python3 scripts/profile_analysis.py analyze acme.csfp --today 2026-10-01 \
  | python3 renderers/render_operational.py --out coverage.html

# Executive (board) — translations composed via ciso-board-translation
python3 scripts/profile_analysis.py analyze acme.csfp --today 2026-10-01 \
  | python3 renderers/render_executive.py --translations translations.json --out board.html
```

---

## Workflow C0 — Cold start

A Profile with nothing in it does not need 106 questions. It needs nine, each of which resolves
several Subcategories at once.

```bash
python3 scripts/profile_analysis.py elicit acme.csfp
```

Three questions per batch by default; the full bank is roughly a twenty-minute conversation. The
questions and what to listen for live in `references/elicitation.json` — read the `listenFor` line
before asking, because it names the parts of an answer that usually go unsaid ("we have a SIEM"
answers none of the four detection Subcategories on its own).

**One answer becomes one intake record.** This is the rule the whole workflow turns on:

```bash
# They answered q1. Attach only what the answer actually spoke to.
python3 scripts/profile_analysis.py intake add acme.csfp \
  --label "cold-start walkthrough: how we know what's on the network" \
  --subjects ID.AM-01 ID.AM-02 \
  --source-date 2026-07-28 --recorded-by "Darren"
```

Four Subcategories' worth of material gathered in one question is a saving on *evidence
collection*. It is not a saving on *decisions* — those are still four separate ratings, made
deliberately in Workflow C with the source in front of them.

A question drops out of `elicit` once every Subcategory it resolves is settled: rated, scoped out,
or already carrying recorded material. So a cold-start session naturally hands over to `queue` — the
material you just collected is what the queue's first band is made of.

Do not run the whole bank and then rate 37 Subcategories in one sitting. That is the rubber-stamping
failure with extra steps.

---

## Workflow C — Confirm from the queue

Intake accretes between reviews — sources get logged (Workflow 0) faster than anyone has time to
decide what they mean. This workflow is where that backlog gets worked, in its own session,
deliberately separate from the pace evidence arrives at.

```bash
python3 scripts/profile_analysis.py queue acme.csfp
```

Ranked in three bands, in this order: **evidence-pending** (material already recorded, nothing
decided yet), then **revisit** (a confirmed rating that cannot be shown to predate material
recorded against it — either the material is newer, or the rating carries no confirmation date
to compare against), then
**cold-start** (nothing recorded at all, ordered by `references/cold-start-rank.json`). Material you
already have beats material you have to go find; a rating newer evidence has called into question
beats one nobody has looked at yet.

Confirm one at a time:

```bash
python3 scripts/profile_analysis.py set acme.csfp ID.AM-01 --current 2 \
  --source in-0001 --confirmed-by "Darren" \
  --rationale "Asset inventory reviewed against the March architecture review; 40 servers untracked."
```

### What a good presentation looks like

A queue row carries a source, a date, and an outcome. Present those, then ask:

> **ID.AM-01** — *Inventories of hardware managed by the organization are maintained.*
> One source bears on it: **in-0001**, *"March architecture review — infra"*, 12 March.
> What's Current, 0 to 3?

And not:

> **ID.AM-01** — the March review mentions quarterly scans and a CMDB, so this looks like a **2**.
> Confirm?

The second version writes the model's inference into the file under the user's name. It will be
accepted most of the time, which is precisely the problem — a number offered for confirmation is not
a number anyone decided.

Work batches of **at most five** (`queue`'s own default, and `analyze`'s `--queue-top`):

```bash
python3 scripts/profile_analysis.py queue acme.csfp --top 3
```

### When the material is thin

Sometimes the honest answer to a queue row is that nobody knows yet. Do not rate it. Record what
needs asking, so it is tracked rather than remembered:

```bash
python3 scripts/profile_analysis.py action add acme.csfp \
  --title "Confirm whether OT assets are in the CMDB or only corporate IT" \
  --linked ID.AM-01 --owner "Infra lead" --target-date 2026-08-15
```

The Subcategory stays evidence-pending and stays in the queue. That is a **result**, not a failure to
reach one — an unrated Subcategory with a dated question against it is worth more than a rating
nobody can defend.

---

## Handing gaps to the risk register

The two skills share the CSF Subcategory ID space. When a framework gap needs to be *scored and
tracked as a risk* — with likelihood, impact, and appetite — export it:

```bash
python3 scripts/profile_analysis.py export-gaps acme.csfp --out gaps.csv

python3 ../risk-register/scripts/score_register.py import-gaps gaps.csv --into acme-register.rr
```

The import dedupes on `csfSubcategoryId`, so re-exporting after a review **updates** the matching
risks instead of creating duplicates.

> **Column-name caveat.** That CSV contract names its rating columns `current_tier` and
> `target_tier`. They carry per-Subcategory **achievement ratings (0–3), not CSF Tiers** — the
> importer's naming predates this skill. Do not let the column name leak into anything a reader
> sees; renaming it across both skills is a v2 change.

**Which skill answers which question:** framework completeness and coverage → this skill. A specific
risk, its likelihood and impact, and whether it sits within appetite → `risk-register`. A CSF gap
becoming a scored risk crosses the seam above.
