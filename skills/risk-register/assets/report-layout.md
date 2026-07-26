# Board PDF Report — Layout

The point-in-time board report, harvested from the Limen Labs web tool's report layout. A4 portrait.
Every deliverable is traceable and carries the disclaimer.

## Structure (in order)

1. **Cover band** — full-width ink (`#14171C`) block at the top. Eyebrow in patina (`#2FA98C`):
   "LIMEN LABS · RISK REGISTER". Client name large in limestone (`#EAE7DF`). Sub-line in limestoneDim
   (`#9AA0A6`): `Assessor · Appetite · Matrix NxN`. For a snapshot-based report, add the snapshot
   label and date so the reader knows the "as of" point.

2. **Executive summary** — total risks; residual band mix (Low / Medium / High / Critical counts);
   over-appetite count; closed count. When `ciso-board-translation` is available, replace the raw
   counts with its board-facing narrative and keep the numbers as support.

3. **Residual heat map** — `matrixSize × matrixSize` grid: impact increasing upward, likelihood
   rightward. Each cell filled by its band color (RAG ramp), showing the count of risks whose
   residual (likelihood, impact) lands there. White text on high/critical cells, ink on low/medium.
   Axis labels: "Likelihood →" and "↑ Impact". Skip residual scores above the current matrix size.

4. **Register table — grouped by the decision needed.** One table, columns: ID · Risk · Theme ·
   Inherent exposure · Response · Residual (exposure + band + velocity) · Owner · Status. Ink header
   row; compact rows. **Every risk appears exactly once**, under one of four section-header rows,
   ranked by residual exposure within its group:

   1. *Above the &lt;appetite&gt; appetite — board decision needed.* Dashed critical rule above it
      (the appetite cut line). Row sub-lines carry the business-impact translation and the treatment
      in place.
   2. *Accepted — standing board approval.* Sub-line carries approver · accepted date · re-validate
      by · expires · flag (acceptance current / due for re-validation / past expiry / incomplete),
      plus the justification. This is the audit-defensible layer the board is standing behind, so it
      belongs in the hand-out.
   3. *Within the &lt;appetite&gt; appetite — under treatment.* Compact rows, no board action sought.
   4. *Closed.* Retained for the audit trail.

   Empty groups are omitted. Do **not** follow the register with separate over-appetite or
   acceptance tables — a risk repeated across three tables reads as three items to a director. The
   grouping *is* the focus list, and the group-specific columns live on the risk's own row.

   Under the table, note the absence a board would otherwise ask about: if nothing is over appetite,
   say so explicitly.

5. **Decisions for the board** — the derived asks (acceptances to re-validate or past expiry, risks
   above appetite, incomplete acceptances, overdue reviews) plus any `decisions` supplied in the
   `ciso-board-translation` sidecar. A report that ends without an ask is a status update.

6. **Footer stamp — every page** — limestoneDim, small: `A Cyber Aware Creation · Not affiliated with
   NIST · <as-of date · source register>`. The stamp makes any handed-out report traceable to the
   exact file and date it came from, and names when the board narrative was not supplied.

## Notes

- Colors come from `assets/brand.md`. Patina is brand/action only — never used to signal "safe."
- The original engine used jsPDF + jspdf-autotable. The skill may render to PDF via any available
  tool (e.g. an HTML→PDF path) as long as the structure, colors, and footer stamp match this spec.
- Prefer generating the self-contained HTML dashboards (`references/dashboards.md`) for on-screen
  review; use this PDF layout for the artifact a CISO hands to the board.
