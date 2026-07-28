# Assessment & Review — the workflows

Four workflows carry this skill. **0** logs a source the moment it comes up, mid-conversation. **A**
builds or extends a Profile. **B** is the recurring review that keeps it honest. **C** works the
confirmation queue that accretes between reviews. Most sessions are A, B, or C; 0 happens inside all
of them, whenever a source comes up.

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

`--label` is a note *about* the source, in the user's own words or confirmed by them — never
something generated on their behalf, and never an excerpt from whatever the source actually was.
`--source-date` is when the conversation happened, not today; it defaults to today only if omitted,
which is rarely what you want for anything discussed after the fact. `--subjects` takes every
Subcategory the source bears on — one record per source, not one per Subcategory.

Nothing here decides a rating. That happens later, deliberately, in Workflow C.

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

Tiers are set on the Profile, not per Subcategory, by editing `profile.tier` (`overall`, and
optionally `byFunction`). They characterize the **rigor** of risk governance and management
practices — read the verbatim NIST text in the Core's `tiers` block with the user and let them
place themselves.

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

## Workflow C — Confirm from the queue

Intake accretes between reviews — sources get logged (Workflow 0) faster than anyone has time to
decide what they mean. This workflow is where that backlog gets worked, in its own session,
deliberately separate from the pace evidence arrives at.

```bash
python3 scripts/profile_analysis.py queue acme.csfp
```

Ranked in three bands, in this order: **evidence-pending** (material already recorded, nothing
decided yet), then **revisit** (a confirmed rating with newer material against it), then
**cold-start** (nothing recorded at all, ordered by `references/cold-start-rank.json`). Material you
already have beats material you have to go find; a rating newer evidence has called into question
beats one nobody has looked at yet.

Confirm one at a time:

```bash
python3 scripts/profile_analysis.py set acme.csfp ID.AM-01 --current 2 \
  --source in-0001 --confirmed-by "Darren" \
  --rationale "Asset inventory reviewed against the March architecture review; 40 servers untracked."
```

A queue row shows the source and the date and **never a proposed rating** — presenting a conclusion
and asking for confirmation is how inference gets laundered as judgment, and a rubber-stamped rating
is worse than an unrated one because it looks like evidence.

Work batches of **at most five** by default (`queue`'s own cap, and `analyze`'s `--queue-top`) — a
long confirmation run is exactly where rubber-stamping happens. Where the material on a row is thin,
the right outcome is **a question to go ask**, not a rating: leave it in the queue and log what you
still need with Workflow 0 once you have it.

```bash
python3 scripts/profile_analysis.py queue acme.csfp --top 3
```

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
