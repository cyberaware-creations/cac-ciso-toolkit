{
  "schemaVersion": 1,
  "family": "incident-materiality",
  "meta": {
    "clientName": "Northwind Financial",
    "owner": "CISO",
    "scopeNote": "US-listed registrant with an in-scope EU payments subsidiary.",
    "asOf": "2026-07-31"
  },
  "settings": {
    "holidays": [
      "2026-01-01",
      "2026-01-19",
      "2026-02-16",
      "2026-05-25",
      "2026-06-19",
      "2026-07-03",
      "2026-09-07",
      "2026-11-26",
      "2026-12-25"
    ]
  },
  "incidents": [
    {
      "id": "I-001",
      "title": "Credential-stuffing against the customer portal — first wave",
      "discoveredAt": "2026-03-11",
      "scopeNote": "Automated login attempts from a residential proxy pool. 41 accounts reached.",
      "status": "closed",
      "factors": [
        {
          "key": "financial",
          "assessment": "no-bearing",
          "rationale": "No fraudulent transactions completed. Response absorbed by the retained IR hours.",
          "relatedIncidentIds": [],
          "actor": "d.alleyne",
          "ts": "2026-07-31T20:42:39+00:00"
        },
        {
          "key": "operational",
          "assessment": "no-bearing",
          "rationale": "Portal remained available throughout; rate limiting absorbed the volume.",
          "relatedIncidentIds": [],
          "actor": "d.alleyne",
          "ts": "2026-07-31T20:42:39+00:00"
        },
        {
          "key": "data",
          "assessment": "no-bearing",
          "rationale": "41 accounts reached; profile and order history visible. No payment card or SSN data is held in the portal.",
          "relatedIncidentIds": [],
          "actor": "d.alleyne",
          "ts": "2026-07-31T20:42:39+00:00"
        },
        {
          "key": "regulatory",
          "assessment": "bearing",
          "rationale": "State breach-notice analysis run for the 41 affected accounts; notice sent in two states. No SEC or DORA trigger.",
          "relatedIncidentIds": [],
          "actor": "d.alleyne",
          "ts": "2026-07-31T20:42:39+00:00"
        },
        {
          "key": "reputational",
          "assessment": "no-bearing",
          "rationale": "No press coverage. Two customers contacted support; both retained.",
          "relatedIncidentIds": [],
          "actor": "d.alleyne",
          "ts": "2026-07-31T20:42:39+00:00"
        },
        {
          "key": "aggregation",
          "assessment": "unknown",
          "rationale": "First occurrence of this pattern. Nothing to aggregate yet; revisit if it recurs.",
          "relatedIncidentIds": [],
          "actor": "d.alleyne",
          "ts": "2026-07-31T20:42:39+00:00"
        }
      ],
      "determinations": [
        {
          "state": "not-material",
          "rationale": "41 accounts, no financial impact, no operational disruption, no regulated data beyond the state notices already sent. Not information a reasonable investor would consider important.",
          "decider": "General Counsel",
          "determinedAt": "2026-03-18",
          "ts": "2026-07-31T20:42:39+00:00"
        }
      ],
      "disclosure": {
        "regimes": [
          "sec-1.05"
        ],
        "decision": "no-file",
        "basis": "Determined not material 2026-03-18; state breach notices handled separately under the applicable statutes.",
        "filings": {}
      },
      "anchors": {
        "awareAt": null,
        "classifiedAt": null
      },
      "linkedRiskIds": [],
      "linkedExceptionIds": [],
      "notes": ""
    },
    {
      "id": "I-002",
      "title": "CRM vendor breach — customer records exposed",
      "discoveredAt": "2026-07-06",
      "scopeNote": "Third-party CRM platform, our tenant only. No production system was reachable from it.",
      "status": "open",
      "factors": [
        {
          "key": "data",
          "assessment": "unknown",
          "rationale": "Exfiltration not confirmed as of 9 July. Vendor forensics engaged; the scope of the tenant export is unknown.",
          "relatedIncidentIds": [],
          "actor": "d.alleyne",
          "ts": "2026-07-31T20:42:39+00:00"
        },
        {
          "key": "data",
          "assessment": "bearing",
          "rationale": "Forensics confirmed export of the customer table on 13 July: name, email, postal address and order history for 84,000 customers. Payment card data is tokenised at the gateway and was not in the tenant.",
          "relatedIncidentIds": [],
          "actor": "d.alleyne",
          "ts": "2026-07-31T20:42:39+00:00"
        },
        {
          "key": "financial",
          "assessment": "bearing",
          "rationale": "Notification, call-centre and outside-counsel costs are expected to exceed the retention on the cyber policy. The insurance rider recorded against acceptance A-002 moves the financial loss; it does not move the notification duty or the customer-facing consequence. Range in the finance memo of 14 July.",
          "relatedIncidentIds": [],
          "actor": "d.alleyne",
          "ts": "2026-07-31T20:42:39+00:00"
        },
        {
          "key": "operational",
          "assessment": "no-bearing",
          "rationale": "Order processing continued on the internal system of record throughout. No customer-facing outage and no disruption to fulfilment.",
          "relatedIncidentIds": [],
          "actor": "d.alleyne",
          "ts": "2026-07-31T20:42:39+00:00"
        },
        {
          "key": "regulatory",
          "assessment": "bearing",
          "rationale": "State breach-notice duties in eleven states, and the EU subsidiary's customers bring a GDPR Article 33 assessment running on its own clock. Separate questions from Item 1.05, tracked separately.",
          "relatedIncidentIds": [],
          "actor": "d.alleyne",
          "ts": "2026-07-31T20:42:39+00:00"
        },
        {
          "key": "reputational",
          "assessment": "bearing",
          "rationale": "Two trade outlets contacted us on 13 July. Three enterprise customers invoked the notice clause in their contracts; none has terminated.",
          "relatedIncidentIds": [],
          "actor": "d.alleyne",
          "ts": "2026-07-31T20:42:39+00:00"
        },
        {
          "key": "aggregation",
          "assessment": "no-bearing",
          "rationale": "Considered against I-001 and the May wave: different actor, different vector, different system. Not a related series.",
          "relatedIncidentIds": [],
          "actor": "d.alleyne",
          "ts": "2026-07-31T20:42:39+00:00"
        }
      ],
      "determinations": [
        {
          "state": "assessing",
          "rationale": "Scope not yet established. Vendor forensics engaged 8 July; determination deferred pending the export scope.",
          "decider": "CISO",
          "determinedAt": "2026-07-09",
          "ts": "2026-07-31T20:42:39+00:00"
        },
        {
          "state": "material",
          "rationale": "Export of records for 84,000 customers confirmed 13 July. Notification duties across eleven states and a GDPR assessment, expected costs above the policy retention, and press attention. This is the residual risk the board accepted in October as A-002, and it has now occurred. Determined material by the disclosure committee.",
          "decider": "General Counsel, on the disclosure committee's recommendation",
          "determinedAt": "2026-07-14",
          "ts": "2026-07-31T20:42:40+00:00"
        }
      ],
      "disclosure": {
        "regimes": [
          "sec-1.05"
        ],
        "decision": "file",
        "basis": "Determined material 2026-07-14. Item 1.05 8-K to be filed within four business days; description limited to the material aspects of nature, scope and timing.",
        "filings": {
          "sec-1.05:8-K": "2026-07-17"
        }
      },
      "anchors": {
        "awareAt": null,
        "classifiedAt": null
      },
      "linkedRiskIds": [
        "R-003"
      ],
      "linkedExceptionIds": [
        "A-002"
      ],
      "notes": ""
    },
    {
      "id": "I-003",
      "title": "Card authorisation degradation, EU payments subsidiary",
      "discoveredAt": "2026-07-20",
      "scopeNote": "Authorisation latency above the SLA for 4h12m. EU entity, in DORA scope.",
      "status": "open",
      "factors": [
        {
          "key": "operational",
          "assessment": "bearing",
          "rationale": "Authorisation latency above the SLA for 4h12m across the EU card estate. Classified major under the DORA criteria on 20 July.",
          "relatedIncidentIds": [],
          "actor": "d.alleyne",
          "ts": "2026-07-31T20:42:40+00:00"
        },
        {
          "key": "financial",
          "assessment": "no-bearing",
          "rationale": "SLA credits to three acquirers, quantified at well under the quantitative screen. No lost settlement.",
          "relatedIncidentIds": [],
          "actor": "d.alleyne",
          "ts": "2026-07-31T20:42:40+00:00"
        },
        {
          "key": "data",
          "assessment": "no-bearing",
          "rationale": "Latency only. No data was exposed, altered or made unavailable.",
          "relatedIncidentIds": [],
          "actor": "d.alleyne",
          "ts": "2026-07-31T20:42:40+00:00"
        },
        {
          "key": "regulatory",
          "assessment": "bearing",
          "rationale": "Major under DORA; initial notification and intermediate report submitted to the NCA. Separate from the Item 1.05 question.",
          "relatedIncidentIds": [],
          "actor": "d.alleyne",
          "ts": "2026-07-31T20:42:40+00:00"
        },
        {
          "key": "reputational",
          "assessment": "no-bearing",
          "rationale": "No press coverage. Two acquirers raised it on the weekly call and accepted the remediation plan.",
          "relatedIncidentIds": [],
          "actor": "d.alleyne",
          "ts": "2026-07-31T20:42:40+00:00"
        },
        {
          "key": "aggregation",
          "assessment": "no-bearing",
          "rationale": "Considered against the April capacity incident: same platform, different root cause (a config change, not capacity). Not a related series.",
          "relatedIncidentIds": [],
          "actor": "d.alleyne",
          "ts": "2026-07-31T20:42:40+00:00"
        }
      ],
      "determinations": [
        {
          "state": "not-material",
          "rationale": "Service degradation for 4h12m with no data affected and SLA credits well below any screen. Not information a reasonable investor would consider important.",
          "decider": "General Counsel",
          "determinedAt": "2026-07-24",
          "ts": "2026-07-31T20:42:40+00:00"
        }
      ],
      "disclosure": {
        "regimes": [
          "sec-1.05",
          "dora"
        ],
        "decision": "no-file",
        "basis": "Reported to the NCA under DORA. Not material for Item 1.05: latency only, no data affected, SLA credits immaterial to results.",
        "filings": {
          "dora:initial": "2026-07-20T20:05:00+00:00",
          "dora:intermediate": "2026-07-23T11:30:00+00:00"
        }
      },
      "anchors": {
        "awareAt": "2026-07-20T14:10:00+00:00",
        "classifiedAt": "2026-07-20T17:40:00+00:00"
      },
      "linkedRiskIds": [],
      "linkedExceptionIds": [],
      "notes": ""
    },
    {
      "id": "I-004",
      "title": "Credential-stuffing against the customer portal — third wave",
      "discoveredAt": "2026-07-24",
      "scopeNote": "Same proxy infrastructure as March and May. Volume an order of magnitude higher.",
      "status": "open",
      "factors": [
        {
          "key": "aggregation",
          "assessment": "bearing",
          "rationale": "Third wave from the same infrastructure against the same unremediated weakness. Assessing I-001, the May wave and this one as a series, not as three incidents.",
          "relatedIncidentIds": [
            "I-001"
          ],
          "actor": "d.alleyne",
          "ts": "2026-07-31T20:42:40+00:00"
        },
        {
          "key": "data",
          "assessment": "unknown",
          "rationale": "Account-takeover count not yet established. Log review with the fraud team runs to 3 August.",
          "relatedIncidentIds": [],
          "actor": "d.alleyne",
          "ts": "2026-07-31T20:42:40+00:00"
        }
      ],
      "determinations": [
        {
          "state": "assessing",
          "rationale": "Aggregate scope across the three waves not yet established; determination deferred pending the log review.",
          "decider": "CISO",
          "determinedAt": "2026-07-27",
          "ts": "2026-07-31T20:42:40+00:00"
        }
      ],
      "disclosure": {
        "regimes": [
          "sec-1.05"
        ],
        "decision": "pending",
        "basis": "",
        "filings": {}
      },
      "anchors": {
        "awareAt": null,
        "classifiedAt": null
      },
      "linkedRiskIds": [
        "R-011"
      ],
      "linkedExceptionIds": [],
      "notes": ""
    }
  ],
  "history": [
    {
      "event": "store-created",
      "target": "/Users/darren/Documents/GitHub/cac-ciso-toolkit/skills/incident-materiality/examples/example-incident.inc",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:39+00:00"
    },
    {
      "event": "incident-opened",
      "target": "I-001",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:39+00:00",
      "detail": {
        "title": "Credential-stuffing against the customer portal — first wave",
        "discoveredAt": "2026-03-11",
        "regimes": [
          "sec-1.05"
        ]
      }
    },
    {
      "event": "factor-assessed",
      "target": "I-001",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:39+00:00",
      "detail": {
        "factor": "financial",
        "assessment": "no-bearing"
      }
    },
    {
      "event": "factor-assessed",
      "target": "I-001",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:39+00:00",
      "detail": {
        "factor": "operational",
        "assessment": "no-bearing"
      }
    },
    {
      "event": "factor-assessed",
      "target": "I-001",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:39+00:00",
      "detail": {
        "factor": "data",
        "assessment": "no-bearing"
      }
    },
    {
      "event": "factor-assessed",
      "target": "I-001",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:39+00:00",
      "detail": {
        "factor": "regulatory",
        "assessment": "bearing"
      }
    },
    {
      "event": "factor-assessed",
      "target": "I-001",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:39+00:00",
      "detail": {
        "factor": "reputational",
        "assessment": "no-bearing"
      }
    },
    {
      "event": "factor-assessed",
      "target": "I-001",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:39+00:00",
      "detail": {
        "factor": "aggregation",
        "assessment": "unknown"
      }
    },
    {
      "event": "determination-recorded",
      "target": "I-001",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:39+00:00",
      "detail": {
        "state": "not-material",
        "from": null,
        "determinedAt": "2026-03-18",
        "decider": "General Counsel"
      }
    },
    {
      "event": "disclosure-set",
      "target": "I-001",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:39+00:00",
      "detail": {
        "decision": "no-file",
        "regimes": [
          "sec-1.05"
        ]
      }
    },
    {
      "event": "incident-closed",
      "target": "I-001",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:39+00:00",
      "why": "Credentials reset, rate limiting tightened, state notices completed. Retained as the reference point for later waves."
    },
    {
      "event": "incident-opened",
      "target": "I-002",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:39+00:00",
      "detail": {
        "title": "CRM vendor breach — customer records exposed",
        "discoveredAt": "2026-07-06",
        "regimes": [
          "sec-1.05"
        ]
      }
    },
    {
      "event": "factor-assessed",
      "target": "I-002",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:39+00:00",
      "detail": {
        "factor": "data",
        "assessment": "unknown"
      }
    },
    {
      "event": "factor-assessed",
      "target": "I-002",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:39+00:00",
      "detail": {
        "factor": "data",
        "assessment": "bearing"
      }
    },
    {
      "event": "factor-assessed",
      "target": "I-002",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:39+00:00",
      "detail": {
        "factor": "financial",
        "assessment": "bearing"
      }
    },
    {
      "event": "factor-assessed",
      "target": "I-002",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:39+00:00",
      "detail": {
        "factor": "operational",
        "assessment": "no-bearing"
      }
    },
    {
      "event": "factor-assessed",
      "target": "I-002",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:39+00:00",
      "detail": {
        "factor": "regulatory",
        "assessment": "bearing"
      }
    },
    {
      "event": "factor-assessed",
      "target": "I-002",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:39+00:00",
      "detail": {
        "factor": "reputational",
        "assessment": "bearing"
      }
    },
    {
      "event": "factor-assessed",
      "target": "I-002",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:39+00:00",
      "detail": {
        "factor": "aggregation",
        "assessment": "no-bearing"
      }
    },
    {
      "event": "determination-recorded",
      "target": "I-002",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:39+00:00",
      "detail": {
        "state": "assessing",
        "from": null,
        "determinedAt": "2026-07-09",
        "decider": "CISO"
      }
    },
    {
      "event": "determination-recorded",
      "target": "I-002",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:40+00:00",
      "detail": {
        "state": "material",
        "from": "assessing",
        "determinedAt": "2026-07-14",
        "decider": "General Counsel, on the disclosure committee's recommendation"
      }
    },
    {
      "event": "disclosure-set",
      "target": "I-002",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:40+00:00",
      "detail": {
        "decision": "file",
        "regimes": [
          "sec-1.05"
        ]
      }
    },
    {
      "event": "filing-recorded",
      "target": "I-002",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:40+00:00",
      "detail": {
        "window": "sec-1.05:8-K",
        "at": "2026-07-17"
      }
    },
    {
      "event": "incident-linked",
      "target": "I-002",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:40+00:00",
      "detail": {
        "risk": [
          "R-003"
        ],
        "exception": [
          "A-002"
        ]
      }
    },
    {
      "event": "incident-opened",
      "target": "I-003",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:40+00:00",
      "detail": {
        "title": "Card authorisation degradation, EU payments subsidiary",
        "discoveredAt": "2026-07-20",
        "regimes": [
          "dora"
        ]
      }
    },
    {
      "event": "anchor-set",
      "target": "I-003",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:40+00:00",
      "detail": {
        "awareAt": "2026-07-20T14:10:00+00:00",
        "classifiedAt": "2026-07-20T17:40:00+00:00"
      }
    },
    {
      "event": "filing-recorded",
      "target": "I-003",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:40+00:00",
      "detail": {
        "window": "dora:initial",
        "at": "2026-07-20T20:05:00+00:00"
      }
    },
    {
      "event": "filing-recorded",
      "target": "I-003",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:40+00:00",
      "detail": {
        "window": "dora:intermediate",
        "at": "2026-07-23T11:30:00+00:00"
      }
    },
    {
      "event": "factor-assessed",
      "target": "I-003",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:40+00:00",
      "detail": {
        "factor": "operational",
        "assessment": "bearing"
      }
    },
    {
      "event": "factor-assessed",
      "target": "I-003",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:40+00:00",
      "detail": {
        "factor": "financial",
        "assessment": "no-bearing"
      }
    },
    {
      "event": "factor-assessed",
      "target": "I-003",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:40+00:00",
      "detail": {
        "factor": "data",
        "assessment": "no-bearing"
      }
    },
    {
      "event": "factor-assessed",
      "target": "I-003",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:40+00:00",
      "detail": {
        "factor": "regulatory",
        "assessment": "bearing"
      }
    },
    {
      "event": "factor-assessed",
      "target": "I-003",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:40+00:00",
      "detail": {
        "factor": "reputational",
        "assessment": "no-bearing"
      }
    },
    {
      "event": "factor-assessed",
      "target": "I-003",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:40+00:00",
      "detail": {
        "factor": "aggregation",
        "assessment": "no-bearing"
      }
    },
    {
      "event": "disclosure-set",
      "target": "I-003",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:40+00:00",
      "detail": {
        "decision": "no-file",
        "regimes": [
          "sec-1.05",
          "dora"
        ]
      }
    },
    {
      "event": "determination-recorded",
      "target": "I-003",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:40+00:00",
      "detail": {
        "state": "not-material",
        "from": null,
        "determinedAt": "2026-07-24",
        "decider": "General Counsel"
      }
    },
    {
      "event": "incident-opened",
      "target": "I-004",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:40+00:00",
      "detail": {
        "title": "Credential-stuffing against the customer portal — third wave",
        "discoveredAt": "2026-07-24",
        "regimes": [
          "sec-1.05"
        ]
      }
    },
    {
      "event": "factor-assessed",
      "target": "I-004",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:40+00:00",
      "detail": {
        "factor": "aggregation",
        "assessment": "bearing"
      }
    },
    {
      "event": "factor-assessed",
      "target": "I-004",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:40+00:00",
      "detail": {
        "factor": "data",
        "assessment": "unknown"
      }
    },
    {
      "event": "determination-recorded",
      "target": "I-004",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:40+00:00",
      "detail": {
        "state": "assessing",
        "from": null,
        "determinedAt": "2026-07-27",
        "decider": "CISO"
      }
    },
    {
      "event": "incident-linked",
      "target": "I-004",
      "actor": "d.alleyne",
      "ts": "2026-07-31T20:42:40+00:00",
      "detail": {
        "risk": [
          "R-011"
        ],
        "exception": []
      }
    }
  ],
  "createdAt": "2026-07-31T20:42:39+00:00",
  "updatedAt": "2026-07-31T20:42:40+00:00"
}
