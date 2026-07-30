# CAC Label Style — ISO & CIS control labels

We never reproduce ISO's or CIS's official control titles or normative text. For every mapped
ISO 27001:2022 and CIS v8.1 control we author an **original short label** that conveys the
control's intent in our own words. 800-53 needs none (public domain — verbatim title used).

## Rules
- **≤ 8 words**, outcome-phrased, our own phrasing — not the standard's wording.
- Describe the *intent* of the control, enough for a CISO to recognize it by its ID.
- No verbs/nouns lifted verbatim from the official title where avoidable.
- One label per control ID; `labelSource: "cac-generated"`.
- Keep IDs exact (they're references, not creative content).

## Worked examples (IDs verified; labels are CAC-original)

Identifier and our label only. An earlier draft of this file carried a third column of the
**official** titles, headed "for our internal keying" — an authoring aid that had no business
shipping, and that contradicted the first line of this document. Read a label against the official
wording in your own licensed copy of the standard; that comparison is not ours to publish.

### ISO/IEC 27001:2022 Annex A
| ID | CAC label |
|---|---|
| A.5.1 | Approved security policy set, communicated |
| A.5.7 | Threat intel gathered and acted on |
| A.5.23 | Cloud service security governed end-to-end |
| A.6.3 | Staff trained on security duties |
| A.7.2 | Physical entry controlled and monitored |
| A.8.9 | Secure baseline configs set and held |
| A.8.13 | Backups made, protected, restore-tested |
| A.8.24 | Cryptography applied under a clear policy |

### CIS Controls v8.1
| ID | CAC label |
|---|---|
| CIS 1 | Know and control every connected asset |
| CIS 4 | Harden and maintain secure configs |
| CIS 4.1 | Documented secure-config process kept current |
| CIS 6 | Grant, review, revoke access deliberately |
| CIS 8 | Collect and retain useful audit logs |
| CIS 11 | Recoverable backups, tested on a schedule |

These are the style target for any label authored later. Note that the CIS catalogue covers only
the Safeguards the NIST CSF export references — see `README.md` for why the remainder are not
enumerated here.
