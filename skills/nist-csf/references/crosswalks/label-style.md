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

### ISO/IEC 27001:2022 Annex A (93 controls · 4 themes: 5 Org / 6 People / 7 Physical / 8 Tech)
| ID | (official topic, for our internal keying) | CAC label |
|---|---|---|
| A.5.1 | Policies for information security | Approved security policy set, communicated |
| A.5.7 | Threat intelligence | Threat intel gathered and acted on |
| A.5.23 | Information security for use of cloud services | Cloud service security governed end-to-end |
| A.6.3 | Information security awareness, education, training | Staff trained on security duties |
| A.7.2 | Physical entry | Physical entry controlled and monitored |
| A.8.9 | Configuration management | Secure baseline configs set and held |
| A.8.13 | Information backup | Backups made, protected, restore-tested |
| A.8.24 | Use of cryptography | Cryptography applied under a clear policy |

### CIS Controls v8.1 (18 Controls · 153 Safeguards)
| ID | (official topic, for our internal keying) | CAC label |
|---|---|---|
| CIS 1 | Inventory and Control of Enterprise Assets | Know and control every connected asset |
| CIS 4 | Secure Configuration of Enterprise Assets and Software | Harden and maintain secure configs |
| CIS 4.1 | Establish and maintain a secure configuration process | Documented secure-config process kept current |
| CIS 6 | Access Control Management | Grant, review, revoke access deliberately |
| CIS 8 | Audit Log Management | Collect and retain useful audit logs |
| CIS 11 | Data Recovery | Recoverable backups, tested on a schedule |

These are the style target for the full generation pass (labels for every control ID that
appears in the CSF crosswalk once the export is ingested).
