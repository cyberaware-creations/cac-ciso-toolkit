# CAC-HO-1 — how a document reaches this repo

**Applies to:** every document written outside this repo that repo content will cite
**Implemented by:** nothing. **This standard has no guard and cannot have one** — see the last section.
**In force since:** v0.119.0
**Sibling standards:** [CAC-RW-1](sources-schema.md) · [CAC-GP-1](guard-proof-standard.md) · [CAC-LE-1](eval-lint-standard.md)

---

## The problem, stated exactly

Research and design documents are written in one place and cited from another. Twice, shipped
content cited a document that the session which had to read it **could not open**:

- **RW-001**, the Reference Watch dossier, was cited as authority by **six shipped files** for two
  days. Its only location was a Claude Project workspace.
- **Three board-outcome grounding documents** were cited by a shipped plan for three days. Same
  cause.

**Both were found by somebody going to read the source.** That is the expensive way to find it —
the citation had already shipped, and in RW-001's case three recorded decisions rested on a file
nobody could open.

Then the fix failed twice more, which is the part worth writing down.

---

## HO-1.1 A hand-off names the surface, and the surface has a direction

**"Attached to this session" is not a surface.** Cowork and Claude Code do not share a filesystem.
`SendUserFile` delivers a file into the maintainer's conversation; it does not touch the machine Code runs
on. Two briefs said "attached" meaning that, and nothing arrived either time.

**Naming the surface is necessary and it is not sufficient.** On the third attempt the surface was
named precisely — Notion file attachments on the citing item — and it still did not work, for a
new reason:

> `notion-download-attachment` requires the attachment to **belong to the requesting integration**.
> The uploads were made by one integration; Code reads with another, in the same workspace. Code
> can read the page, the file block and the filename. It cannot read the bytes.

Four routes were tried and all four are dead: the attachment UUID from the `file://` src (404), the
file **block** id (returns the title and "this page is blank"), the attachment UUID as a page id
(404), and the tool's own suggested fallback of "the signed file URL returned when reading the
containing page" — the page returns internal `file://` refs carrying encoded JSON, not signed HTTPS
URLs.

**So a surface must be stated with the direction it works in.** As measured on 2026-08-11:

| surface | Cowork → it | Code → it |
|---|---|---|
| A path under `~/Documents` | ⚠️ only with a granted folder (device bridge); ✗ otherwise | ✅ reads directly |
| A commit on a branch in this repo | ✅ if it has git or GitHub API access | ✅ |
| A Notion attachment on the citing item | ✅ writes fine | ⛔ **404 — integration-scoped** |
| Notion **page body** text | ✅ | ✅ — but Markdown rendering reflows tables and blockquotes, so **byte-exactness is lost** |
| "Attached to this session" | — | ⛔ not a surface at all |

> ⭐ **The durable fix for this whole class is the first row, and it is a permission rather than a
> procedure.** Granting the repo folder to the writing session — the desktop bridge exposes
> `device_commit_files`, which writes straight into any folder that has been granted — lets
> research documents be written into `docs/research/` **directly**. No attachment, no download, no
> human step, and **HO-1.1's problem stops existing** rather than being routed around.
>
> That row reads ⚠️ rather than ✅ only because the grant dialog has timed out twice with no
> response. **A route that is unavailable is a different fact from a route that is impossible**, and
> the difference is the whole reason this row is not marked ✗.

⚠️ **For a verbatim research document the last row of that table matters more than it looks.** The
entire value of these documents is that they are byte-exact; a blockquote silently reflowed is a
document that no longer says what it said. Pasting into a page body is a working transport for
*content* and a broken one for *provenance*.

**The route that works today** for a Code-bound document is a human step: download it from Notion in
a browser and save it under `~/Documents`, or commit it to a branch.

## HO-1.2 A research document that shipped code cites lives in `docs/research/`

**Before the citation is written, not after.**

`docs/research/` sits beside `docs/superpowers/`. The reasoning is BL-227's own: *they are cited BY
the repo, so a location the repo can name is worth something.* A citation that resolves inside the
same tree cannot drift out of reach the way RW-001 did.

**Notion carries a document across; the repo is where it lives.** Those are different jobs and
conflating them is what produced both failures.

> ⚠️ **This does not relocate everything.** The three board-outcome documents keep their
> `docs/superpowers/specs/` and `docs/superpowers/notes/` destinations, because that split comes
> from how `plans/2026-08-08-board-outcome-plan.md` cites them, not from this rule.

## HO-1.3 The transport's limits, so nobody rediscovers them

- **The Cowork container cannot reach `api.notion.com` directly** (`CONNECT tunnel failed, 403`), so
  a document has to pass through the attachment API's inline `content` parameter.
- **That parameter caps at 200 KiB.** Fine for a research document. **Useless for a PDF.**
- **The IR 8286A r1 PDF cannot come across this way** — it is 3.1 MB against a 200 KiB cap.

> ⚠️ **CORRECTION, same day, v0.121.0 — the sentence that used to follow that bullet was wrong.**
>
> It read: *"…which is why BL-94 C1 and BL-54 T4's remaining scenarios stay blocked."* **The first
> clause is true and the inference is not.** Those items never needed this transport. **IR 8286A r1
> is a public NIST publication**, free of charge at
> `https://nvlpubs.nist.gov/nistpubs/ir/2025/NIST.IR.8286Ar1.pdf` (DOI `10.6028/NIST.IR.8286Ar1`) —
> fetchable directly and readable page by page. Verified by fetching it and reading page 1:
> *NIST Interagency Report NIST IR 8286Ar1 — Identifying and Estimating Cybersecurity Risk for
> Enterprise Risk Management.*
>
> **The error was reasoning from the transport's limit to the items' status** without checking
> whether those items needed the transport at all. Both had been recorded as PDF-blocked for weeks,
> and this standard restated that as settled instead of testing it — which is precisely the failure
> **CAC-RW-1.14** names: *a correction is a claim and gets checked like one.* Filed as **BL-255**.
>
> ⛔ **This does not license writing §2.2.2.4 from memory.** It means the section can now be *read*,
> which is the only thing that was ever missing. Whoever picks up BL-94 C1 opens the document.

**The general point survives the correction, and is worth keeping separate from it:** a source that
is *published* needs no hand-off at all. This standard is about documents that exist only where
somebody wrote them. **Check which kind you have before treating a hand-off as the blocker** — the
cheapest unblocking move is often discovering the document was never private.

---

## Why this standard has no guard, and why that is not a gap

Every other standard here is enforced by a script. This one cannot be, and pretending otherwise
would be worse than leaving it prose.

**A guard would have to know what a citation points at outside the repo**, which is exactly the
information that goes missing. `check-sources.py` can already tell you a `usedFor` path is not in
the tree — that is CAC-RW-1 C4, and it is the closest thing to enforcement available. What it
cannot tell you is that a document *named in prose* in a plan's header lives somewhere the next
session cannot reach.

**The failure this standard describes is a failure of the hand-off, and the hand-off happens
between two humans-with-agents twice a week.** ⛔ **Do not build tooling for it.** A script that
automates a twice-weekly exchange is a maintenance burden bought to avoid reading two paragraphs.

The record is the enforcement. That is weaker than a check, and it is stated here so nobody mistakes
it for one.
