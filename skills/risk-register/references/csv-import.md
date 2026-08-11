# CSV intake — bringing a CISO's own spreadsheet in

`import-csv` exists so that a CISO with thirty risks in a spreadsheet does not have to retype
them. It is the answer to *"meet me where I am"*, and where most CISOs are is a spreadsheet.

```bash
python3 scripts/score_register.py import-csv rows.csv --into register.rr \
    --from-operator --operator 'Head of Security'          # preview, writes nothing
python3 scripts/score_register.py import-csv rows.csv --into register.rr --write \
    --from-operator --operator 'Head of Security'          # applies the merge
```

---

## ⚠️ `export-csv` is NOT a round-trip format, and this is where you find that out

If you are here because you exported the register, edited it, and expected to import it back:
**you cannot, and the reason is not an oversight.**

**Five exported columns are DERIVED, not stored.** `inherentExposure`, `inherentBand`,
`residualExposure`, `residualBand` and `overAppetite` come out of `score_register()`. They are
*outputs* — the matrix multiplied, banded against this register's own thresholds, and compared
to its appetite. Accepting them as inputs would let a spreadsheet assert a band that disagrees
with the matrix that produced it, and then two things in the same file would claim to be the
severity of one risk.

So they are **refused by name**, never ignored. A silently dropped `residualBand` is a user
believing they set something, and they do not find out until a board asks why the register
disagrees with their spreadsheet.

**`description` is required here and is absent from the export entirely** — as are `notes`,
`acceptance` and `analysisMethod`. An export shaped for a reader and an import shaped for the
engine are different documents, and pretending otherwise would make one of them worse.

> ❗ A note on counts, because an earlier plan for this feature got it wrong and the mistake is
> instructive. Ten export columns have no stored top-level key of that name — but only **five**
> are derived. The other five (`inherentL`, `inherentI`, `residualL`, `residualI`, `cost`) are
> **flattenings** of stored nested objects, and they are exactly the columns an importer needs.
> Treating all ten as derived would have thrown away the score columns this feature exists to
> accept.

---

## The columns

| | columns |
|---|---|
| **Required** | `title`, `description`, `category`, `owner`, `response` |
| **Scores** (see provenance) | `inherentL`, `inherentI`, `residualL`, `residualI` |
| **Optional** | `id`, `theme`, `responseDescription`, `cost`, `reviewDate`, `csfSubcategoryId`, `notes`, `references`, `sourceRef`, `status` |
| **Refused by name** | `inherentExposure`, `inherentBand`, `residualExposure`, `residualBand`, `overAppetite`, `outOfRange`, `provisionalTitle`, `provisionalScore` |

Headers are matched **case- and space-insensitively**, and common spellings are aliased —
`Residual L`, `residual_l` and `residualL` are one column. Spreadsheets arrive from Excel,
Sheets and Numbers and none of them agree about spacing; refusing a file over a header space
would fail the exact user this feature is for. Unrecognised columns are reported and ignored.

**`description` is required for the same reason `add` requires it.** A one-word noun scored out
of 25 is not a risk, and the register refuses to hold one however it arrived.

**`provisionalTitle` and `provisionalScore` are refused although they are stored.** They record
what this tool has not yet had a human confirm; a spreadsheet clearing them would erase that
record rather than earn it. `set-text` and `set-score` clear them, and only those.

**`references` is multi-value on the newline convention** — the inverse of what `export-csv`
writes, and the only separator that works, because the field is free text and any printable one
could occur inside a value. See `schema.md`.

---

## Provenance decides whether the scores survive

**Exactly one of `--from-sibling` or `--from-operator` is required. There is no default.**

| flag | scores | why |
|---|---|---|
| `--from-sibling` | **refused by name** | Another tool's export. A scoring key arriving from another register means that register started scoring — the one thing the bridge exists to prevent. |
| `--from-operator --operator 'Name'` | **accepted, attributed** | Your own spreadsheet. |

The distinction is about **machine** provenance, and that is the whole point. `import-findings`
refuses any scoring key because *"a scoring key reaching here means the other register started
scoring."* That reason does not reach an operator: **a human bringing their own spreadsheet is
this register's owner, not a second register.** They are not forming a competing opinion; they
are entering theirs for the first time.

There is no default because the two answers differ in whether the numbers in the file are usable
at all. Guessing one would guess the answer to the question the flag exists to ask.

`--from-operator` **requires** `--operator 'Name'`. Scores arriving that way are somebody's
assessment, and an unattributed assessment is what this register refuses everywhere else. The
attribution is stored on each scored risk as `scoreProvenance`, in the `{value, declaredBy,
declaredOn, basis}` shape `business-context` and `vendor-register` also use.

---

## What it does, and what it will not do

**Preview by default; `--write` commits.** The preview *is* the review step. An import that
wrote on sight would turn every refusal below into a finding after the fact.

**Refusal is per ROW, not per file.** One bad row is reported by row number and skipped; the
other twenty-nine still land. Every row faces the same refusals a hand-entered risk faces —
`exceptions-register` states the rule this follows: **an import is not a side door.**

**It merges through `merge_import`**, the same function `import-gaps` and `import-findings` use,
rather than a second matching implementation. Two merge paths would be two sets of rules about
when a human-authored title may be overwritten, and only one of them would get the next fix.

### ⚠️ Re-running a file is NOT idempotent unless the rows carry a match key

`merge_import` matches on `csfSubcategoryId` and `sourceRef` **and on nothing else.** A row
carrying neither has no match key and is **added again** on a re-run.

This is stated loudly by the command itself, counting the affected rows, because the natural
assumption is the opposite one and it is wrong destructively: fixing two rows and re-running a
thirty-row file would otherwise leave sixty risks. **Give rows a `sourceRef`** — any stable
identifier from the spreadsheet they came from — if you expect to re-import.

*(Whether the optional `id` column should also match is an open question and is filed, not
guessed: honouring it would arguably be the second merge path this design avoids.)*

---

## Not legal advice, and not an assessment

An imported score is a record of what somebody asserted, attributed to them. It is not this
tool's opinion of the risk, and importing a file has never been a substitute for assessing one.
