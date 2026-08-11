# CAC-PI-1 — the document intake contract

A CISO with a shelf of policies had nowhere to put them. This is where they go — and the shape
of it is forced by a property of the product that is worth stating before the schema.

---

## The engine cannot open a document, and it must not learn how

**The agent extracts. The engine ingests structured JSON. The human declares.**

Verified across the whole repository before this was designed: there is no `pypdf`, `PyPDF2`,
`pdfplumber`, `pdfminer`, `fitz` or `python-docx`; no OCR; no `pandoc` or `pdftotext`; no
`subprocess` in any shipped script; and no `urllib`, `requests` or `http.client` in any engine.
Every engine here is **stdlib-only and offline**, and `SKILL.md` states that as a property of
the product rather than an accident of what nobody has needed yet.

So extraction happens **outside**: by an agent, or by the `pdf` / `docx` skills on the machine.
The result reaches `policy_register.py` as JSON on stdin or a file.

> **Do not put a parser in the engine.** It would break the offline guarantee for every user, to
> save one step for the user who happened to have a PDF. This paragraph exists so the next
> person does not have to rediscover why.

### And we ingest assertions ABOUT a document, never its text

`SKILL.md`'s stated non-goal: *"Store or render policy text. This is not a document management
system."* A **citation** is what makes a proposal reviewable — somebody can go and read the same
words. The words themselves stay in the document.

---

## The payload

```json
{
  "contractVersion": "CAC-PI-1",
  "documents": [
    {
      "title": "Access Control Policy",
      "owner": "Head of Security",
      "version": "3.0",
      "citation": "s 4.2, p. 11",
      "note": "optional — what the extraction wants the reviewer to know",
      "mappedTo": [
        { "requirement": "AC-1", "citation": "s 4.2.1, p. 12" },
        { "requirement": "IA-2", "citation": "s 5.1, p. 15" }
      ]
    }
  ]
}
```

| field | required | notes |
|---|---|---|
| `contractVersion` | **yes** | Must be exactly `CAC-PI-1`. A mismatch is refused, not read leniently. |
| `title`, `owner` | **yes** | The same two `add` requires. |
| `citation` | **yes** | Page, section or heading. |
| `version` | no | Defaults to `1.0`. |
| `note` | no | Free text for the reviewer. |
| `mappedTo[].requirement` | **yes** if present | |
| `mappedTo[].citation` | **yes** if present | Its own citation — see below. |

**A filename is not a citation.** It says *which* document, not *where in it*. The refusal says
so, because "ACP-v3.pdf" is the answer somebody will reach for first.

**Every mapping carries its own citation**, separately from the document's. The document-level
one says which document; the mapping-level one says where in it the aim is evidenced. They are
different questions, and a confirmed mapping with no page is a claim nobody can check.

### Refused by name

`state` · `approval` · `approvedBy` · `supersededOn` · `supersededBy` · `supersedes`

Each is a way of asking the import to put a document in force without a person. Refused
individually, naming the act that does it instead.

---

## Nothing changes until a person assesses

```bash
policy_register.py ingest  store.pol payload.json --actor claude   # proposals only
policy_register.py proposals store.pol                             # what is waiting
policy_register.py assess  store.pol --id PR-001 --by 'General Counsel'
policy_register.py assess  store.pol --id PR-002 --by 'CISO' --reject --why '...'
```

**Ingesting a hundred documents moves nothing** — no requirement state, no count, no rendered
page. The acceptance test is borrowed verbatim from `vendor-register`:

> *"ask → 7 open ← the reading layer changed NOTHING… If proposing ever moves the count,
> something is wrong."*

`evals/intake-proposes-only.sh` asserts the **whole read model byte-identical** across an
ingest. *(One field is excluded: `analyze` stamps `generatedAt` with wall-clock time, so a naive
compare differs always, for a reason that has nothing to do with the register. Excluded by name;
everything else is compared exactly.)*

**`assess` is the only act that creates a record.** `--by` is required — *derivation and reading
both propose; only a person confirms* — and `--reject` requires `--why`, because a rejection with
no reason is indistinguishable from an oversight to the next reader. **Rejected proposals are
retained** and excluded from the working view: *"we looked and said no"* is a different fact from
*"nobody looked"*.

Confirming goes through **`add_policy`**, so it faces every refusal a hand-entered record faces:
`REQUIRED_ADD` still applies, `kind` must still be `policy`, and `plan`/`playbook` are still
refused. **An intake is not a side door.**

### `viaProposal` — where the row came from

A confirmed record carries the proposal id, the citation, who confirmed it and when, plus a
citation per mapping. An auditor asking *"where did this row come from"* gets **a document and a
page**, not the word "an import".

---

## ⚠️ The supersession rule: intake creates DRAFTS, and only drafts

**Decided (T5): drafts-only.**

The register answers *"what was in force on the date of the incident"* from `approval.on`,
`supersededOn` and the `supersedes`/`supersededBy` chain. There is no delete command and never
will be.

A batch import creating a v3.0 record without superseding v2.0 would put **two approved
documents in force for the same requirements** with nothing recording which governs — the exact
state `approve` already refuses. So intake cannot reach it: **a confirmed proposal becomes a
`draft`**, and a draft is not in force. Approving and superseding stay human acts, in that
order, by somebody who has read both documents.

The property is **structural rather than checked** — there is no rule to get wrong, because the
state that would breach it is never written. `intake-proposes-only.sh` registers a mutation that
confirms straight to `approved` precisely to show the structure is load-bearing rather than
incidental.

The alternative was to resolve `--supersedes` targets at import and refuse the unresolvable
ones. It was not chosen: it puts a resolution step nobody reviewed in front of the one property
this register is for.

---

## ⚠️ A proposed mapping is not a coverage claim, and the source document will say otherwise

`REQUIREMENT_STATES` is the complete vocabulary a requirement row may carry, and **every state
describes the DOCUMENTS, never the requirement**. There is no state meaning *covered*, *met*,
*satisfied* or *compliant*.

The extraction will carry sentences like *"this policy addresses access control"* — because that
is how policy documents are written. **This is the most likely place in the product to breach
that boundary.** A mapping proposed here means *this document is aimed at that requirement*, and
confirming it still says only that **a document exists, a named person approved it on a date,
and it is aimed at these requirements.**

`no-coverage-claim.sh` and `no-coverage-percentage.sh` guard the vocabulary, and
`intake-proposes-only.sh` asserts it on the intake surfaces too — a state invented at intake
time is not something a static scan of the shipped engine would see.

---

## Noted, not settled

`policy-register` does not adopt CAC-AP-1, and `SKILL.md` records that as **undecided rather than
an oversight**. Intake does not settle it and adds no `--context` flag. If intake later makes the
case for one, that is its own item.
