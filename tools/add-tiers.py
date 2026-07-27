"""
T0b — inject verbatim CSF Tier text (NIST CSWP 29, Appendix B, Table 2) into the Core JSON.

Runs once, out-of-band; only its output ships. Every transcribed paragraph is verified
as a substring of the PDF's own extracted text before anything is written, so a typo or
a dropped clause fails loudly rather than shipping as "verbatim".

STRUCTURE NOTE: Table 2 has TWO dimensions — Cybersecurity Risk Governance and
Cybersecurity Risk Management. The design spec assumed three, adding "Third-Party
Cybersecurity Risk Management"; that came from csf-assessment's paraphrase, which split
supplier/third-party language out. In the source, that language sits INSIDE the
Cybersecurity Risk Management column. We follow the source.
"""
import json
import re
import sys
import unicodedata

CORE = sys.argv[1]
SOURCE_TXT = sys.argv[2]

# ---------------------------------------------------------------------------
# Verbatim transcription of Table 2. Paragraph breaks preserved as list items.
# Typographic apostrophes are normalised to ASCII; no other character changes.
# ---------------------------------------------------------------------------
LEVELS = [
    {
        "tier": 1,
        "name": "Partial",
        "label": "Tier 1: Partial",
        "oneLine": "Ad hoc, reactive practice with limited organizational awareness of cybersecurity risk.",
        "governance": [
            "Application of the organizational cybersecurity risk strategy is managed in an ad hoc manner.",
            "Prioritization is ad hoc and not formally based on objectives or threat environment.",
        ],
        "riskManagement": [
            "There is limited awareness of cybersecurity risks at the organizational level.",
            "The organization implements cybersecurity risk management on an irregular, case-by-case basis.",
            "The organization may not have processes that enable cybersecurity information to be shared within the organization.",
            "The organization is generally unaware of the cybersecurity risks associated with its suppliers and the products and services it acquires and uses.",
        ],
    },
    {
        "tier": 2,
        "name": "Risk Informed",
        "label": "Tier 2: Risk Informed",
        "oneLine": "Risk awareness exists and management approves practices, but they are not yet organization-wide policy.",
        "governance": [
            "Risk management practices are approved by management but may not be established as organization-wide policy.",
            "The prioritization of cybersecurity activities and protection needs is directly informed by organizational risk objectives, the threat environment, or business/mission requirements.",
        ],
        "riskManagement": [
            "There is an awareness of cybersecurity risks at the organizational level, but an organization-wide approach to managing cybersecurity risks has not been established.",
            "Consideration of cybersecurity in organizational objectives and programs may occur at some but not all levels of the organization. Cyber risk assessment of organizational and external assets occurs but is not typically repeatable or reoccurring.",
            "Cybersecurity information is shared within the organization on an informal basis.",
            "The organization is aware of the cybersecurity risks associated with its suppliers and the products and services it acquires and uses, but it does not act consistently or formally in response to those risks.",
        ],
    },
    {
        "tier": 3,
        "name": "Repeatable",
        "label": "Tier 3: Repeatable",
        "oneLine": "Formally approved policy applied organization-wide, with consistent methods and regular review.",
        "governance": [
            "The organization's risk management practices are formally approved and expressed as policy.",
            "Risk-informed policies, processes, and procedures are defined, implemented as intended, and reviewed.",
            "Organizational cybersecurity practices are regularly updated based on the application of risk management processes to changes in business/mission requirements, threats, and technological landscape.",
        ],
        "riskManagement": [
            "There is an organization-wide approach to managing cybersecurity risks. Cybersecurity information is routinely shared throughout the organization.",
            "Consistent methods are in place to respond effectively to changes in risk. Personnel possess the knowledge and skills to perform their appointed roles and responsibilities.",
            "The organization consistently and accurately monitors the cybersecurity risks of assets. Senior cybersecurity and non-cybersecurity executives communicate regularly regarding cybersecurity risks. Executives ensure that cybersecurity is considered through all lines of operation in the organization.",
            "The organization risk strategy is informed by the cybersecurity risks associated with its suppliers and the products and services it acquires and uses. Personnel formally act upon those risks through mechanisms such as written agreements to communicate baseline requirements, governance structures (e.g., risk councils), and policy implementation and monitoring. These actions are implemented consistently and as intended and are continuously monitored and reviewed.",
        ],
    },
    {
        "tier": 4,
        "name": "Adaptive",
        "label": "Tier 4: Adaptive",
        "oneLine": "Continuous improvement driven by lessons learned and real-time information, embedded in the organizational culture.",
        "governance": [
            "There is an organization-wide approach to managing cybersecurity risks that uses risk-informed policies, processes, and procedures to address potential cybersecurity events. The relationship between cybersecurity risks and organizational objectives is clearly understood and considered when making decisions. Executives monitor cybersecurity risks in the same context as financial and other organizational risks. The organizational budget is based on an understanding of the current and predicted risk environment and risk tolerance. Business units implement executive vision and analyze system-level risks in the context of the organizational risk tolerances.",
            "Cybersecurity risk management is part of the organizational culture. It evolves from an awareness of previous activities and continuous awareness of activities on organizational systems and networks. The organization can quickly and efficiently account for changes to business/mission objectives in how risk is approached and communicated.",
        ],
        "riskManagement": [
            "The organization adapts its cybersecurity practices based on previous and current cybersecurity activities, including lessons learned and predictive indicators. Through a process of continuous improvement that incorporates advanced cybersecurity technologies and practices, the organization actively adapts to a changing technological landscape and responds in a timely and effective manner to evolving, sophisticated threats.",
            "The organization uses real-time or near real-time information to understand and consistently act upon the cybersecurity risks associated with its suppliers and the products and services it acquires and uses.",
            "Cybersecurity information is constantly shared throughout the organization and with authorized third parties.",
        ],
    },
]


def normalize(text: str) -> str:
    """Collapse to a comparable form: NFKD, ASCII quotes, no whitespace, no hyphens.

    Hyphens are dropped because pdftotext silently de-hyphenates words broken across a
    line ('organization-wide' extracts as 'organizationwide'). Whitespace is dropped
    because the PDF's column layout wraps every cell.
    """
    text = unicodedata.normalize("NFKD", text)
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-")
    return re.sub(r"[\s\-]+", "", text).lower()


source = normalize(open(SOURCE_TXT, encoding="utf-8").read())

failures = []
checked = 0
for level in LEVELS:
    for dim in ("governance", "riskManagement"):
        for para in level[dim]:
            checked += 1
            if normalize(para) not in source:
                failures.append(f"Tier {level['tier']} {dim}: {para[:90]}...")

if failures:
    print(f"TRANSCRIPTION FAILED — {len(failures)} of {checked} paragraphs not found in the source PDF:")
    for f in failures:
        print("  - " + f)
    sys.exit(1)

core = json.load(open(CORE, encoding="utf-8"))
core["tiers"] = {
    "dimensions": [
        {"key": "governance", "label": "Cybersecurity Risk Governance", "appliesTo": ["GV"]},
        {
            "key": "riskManagement",
            "label": "Cybersecurity Risk Management",
            "appliesTo": ["ID", "PR", "DE", "RS", "RC"],
        },
    ],
    "levels": LEVELS,
    "source": {
        "publication": "NIST CSWP 29 — The NIST Cybersecurity Framework (CSF) 2.0",
        "date": "February 26, 2024",
        "location": "Appendix B, Table 2. Notional Illustration of the CSF Tiers",
        "url": "https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf",
        "verbatim": True,
        "transcriptionNote": (
            "governance and riskManagement text is verbatim from Table 2; typographic "
            "apostrophes normalised to ASCII, no other character changes. Each paragraph "
            "is verified as a substring of the published PDF at ingest time. 'oneLine' is "
            "OUR paraphrase for chips and tooltips, not NIST text."
        ),
    },
    # Two audiences, two strings. `guardrail` instructs the model and must never be
    # rendered: a board deck that tells its own reader what "must never be rendered" is
    # talking to itself in front of the client. `readerNote` says the same thing to the
    # person holding the report, in their language.
    "guardrail": (
        "MODEL-FACING — do not render. NIST presents Table 2 as a NOTIONAL ILLUSTRATION. "
        "Tiers characterize the rigor of cybersecurity risk governance (GOVERN) and risk "
        "management (IDENTIFY, PROTECT, DETECT, RESPOND, RECOVER) practices. They are NOT a "
        "maturity score, and must never be rendered, averaged, or trended as one. Per CSWP 29 "
        "Sec. 3.2, Tiers complement a risk management methodology rather than replace it, and "
        "progression to higher Tiers is encouraged only when risks or mandates are greater, or "
        "when a cost-benefit analysis indicates a feasible and cost-effective reduction of "
        "negative risk. Use `readerNote` for anything a human will see."
    ),
    "readerNote": (
        "Tiers describe how rigorous this organisation's approach to cybersecurity risk is — "
        "how risk decisions get made, and how consistently. They are a considered judgment, "
        "not a score calculated from the ratings in this report, and a higher Tier is not "
        "automatically better: NIST recommends moving up only when the risks you face or the "
        "obligations you carry justify the cost."
    ),
}
core["notes"]["tiers"] = (
    "Verbatim from NIST CSWP 29 Appendix B, Table 2 — two dimensions, not three. "
    "Supplier/third-party language sits inside the Cybersecurity Risk Management dimension "
    "in the source; it is not a separate column."
)

with open(CORE, "w", encoding="utf-8") as fh:
    json.dump(core, fh, indent=2, ensure_ascii=False)
    fh.write("\n")

print(f"OK — {checked}/{checked} transcribed paragraphs verified against the published PDF")
print(f"  tiers      {len(LEVELS)} ({', '.join(l['label'] for l in LEVELS)})")
print(f"  dimensions {len(core['tiers']['dimensions'])} ({', '.join(d['label'] for d in core['tiers']['dimensions'])})")
print(f"  -> {CORE}")
