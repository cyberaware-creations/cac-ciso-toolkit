#!/usr/bin/env python3
"""Author overlay catalogs + rebuild clean maps from the NIST CSF 2.0 xlsx.

- ISO/CIS labels are CAC-authored paraphrases (never the official titles).
- 800-53 carries verbatim family names and all per-control titles (public domain, NIST SP 800-53 Rev 5).
- Cleans parse artifacts (None tokens, malformed clauses) and whitelists valid ISO clauses.
Edges are facts from the export; labels are ours.
"""
import re, json, os, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
# Build-time only. Reads the vendored export beside this script; writes the bundled
# overlay data into the skill. Lives under tools/ rather than skills/ because
# everything under skills/ ships to users — see tools/README.md.
DATA=os.path.join(HERE,"..","..","skills","nist-csf","references","crosswalks")
SRC=os.path.join(HERE,"_source_csf2.xlsx"); RETRIEVED="2026-07-29"
SUB=re.compile(r'^[A-Z]{2}\.[A-Z]{2}-\d{2}:')


def read_rows(path, sheet):
    """Rows of `sheet` as a dense list of cell strings (blank cells -> "").

    Reuses the stdlib XLSX reader that already ingests this same export for the
    CSF Core, rather than adding openpyxl: tools/ carries no third-party
    dependencies by design (see tools/README.md), and one parser for one file
    format cannot drift from itself.
    """
    src = os.path.join(HERE, "..", "ingest-csf-core.py")
    spec = importlib.util.spec_from_file_location("_ingest_csf_core", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.read_sheet_rows(path, sheet)

# ---- CAC-authored ISO/IEC 27001:2022 Annex A labels (all 93; our own wording) ----
ISO_A={
"A.5.1":"Approved security policy set, communicated","A.5.2":"Security roles and responsibilities defined","A.5.3":"Conflicting duties separated","A.5.4":"Management backs security expectations","A.5.5":"Ties kept with relevant authorities","A.5.6":"Engaged with security interest groups","A.5.7":"Threat intel gathered and used","A.5.8":"Security built into project work","A.5.9":"Assets inventoried with owners","A.5.10":"Acceptable-use rules for assets set","A.5.11":"Assets returned on exit","A.5.12":"Information classified by sensitivity","A.5.13":"Information labelled per classification","A.5.14":"Information transfers protected","A.5.15":"Access control rules established","A.5.16":"Identities managed across lifecycle","A.5.17":"Authentication secrets managed safely","A.5.18":"Access rights provisioned and reviewed","A.5.19":"Security governed in supplier relationships","A.5.20":"Security terms in supplier agreements","A.5.21":"ICT supply-chain security managed","A.5.22":"Supplier services monitored and reviewed","A.5.23":"Cloud service security governed","A.5.24":"Incident response planned and prepared","A.5.25":"Security events assessed and triaged","A.5.26":"Incidents responded to per plan","A.5.27":"Lessons learned from incidents","A.5.28":"Evidence collected and preserved","A.5.29":"Security sustained during disruption","A.5.30":"ICT ready for business continuity","A.5.31":"Legal and contractual duties tracked","A.5.32":"Intellectual property rights respected","A.5.33":"Records protected from loss","A.5.34":"Personal data privacy protected","A.5.35":"Security independently reviewed","A.5.36":"Compliance with security rules checked","A.5.37":"Operating procedures documented",
"A.6.1":"Personnel screened before hire","A.6.2":"Security duties in employment terms","A.6.3":"Staff trained on security","A.6.4":"Disciplinary process for violations","A.6.5":"Duties continue after role change","A.6.6":"Confidentiality agreements in place","A.6.7":"Remote working secured","A.6.8":"Staff report security events",
"A.7.1":"Physical perimeters secured","A.7.2":"Physical entry controlled","A.7.3":"Offices and facilities secured","A.7.4":"Physical spaces monitored","A.7.5":"Guarded against environmental threats","A.7.6":"Secure-area working rules set","A.7.7":"Clear desk and screen enforced","A.7.8":"Equipment sited and protected","A.7.9":"Off-site assets protected","A.7.10":"Storage media managed securely","A.7.11":"Supporting utilities safeguarded","A.7.12":"Cabling protected from interference","A.7.13":"Equipment maintained properly","A.7.14":"Equipment sanitized before reuse/disposal",
"A.8.1":"Endpoint devices protected","A.8.2":"Privileged access rights restricted","A.8.3":"Information access limited by need","A.8.4":"Source-code access controlled","A.8.5":"Strong authentication enforced","A.8.6":"Capacity managed for availability","A.8.7":"Malware defenses maintained","A.8.8":"Technical vulnerabilities managed","A.8.9":"Secure baseline configs set and held","A.8.10":"Information deleted when no longer needed","A.8.11":"Sensitive data masked","A.8.12":"Data leakage prevented","A.8.13":"Backups made and restore-tested","A.8.14":"Processing redundancy provided","A.8.15":"Events logged","A.8.16":"Activity monitored for anomalies","A.8.17":"Clocks synchronized","A.8.18":"Privileged utilities controlled","A.8.19":"Software installs on systems controlled","A.8.20":"Network security managed","A.8.21":"Network service security assured","A.8.22":"Networks segregated","A.8.23":"Web access filtered","A.8.24":"Cryptography applied under policy","A.8.25":"Secure development lifecycle followed","A.8.26":"Application security requirements defined","A.8.27":"Secure architecture principles applied","A.8.28":"Secure coding practiced","A.8.29":"Security testing in development","A.8.30":"Outsourced development overseen","A.8.31":"Dev, test, prod environments separated","A.8.32":"Changes managed and controlled","A.8.33":"Test data protected","A.8.34":"Systems protected during audit testing",
}
# ---- CAC-authored ISO 27001:2022 management-clause labels (4-10) ----
ISO_CL={
"Clause 4.1":"Organization context understood","Clause 4.2":"Interested-party needs identified","Clause 4.3":"ISMS scope determined","Clause 4.4":"ISMS established and maintained",
"Clause 5.1":"Leadership commits to security","Clause 5.2":"Security policy set by leadership","Clause 5.3":"Roles and authorities assigned",
"Clause 6.1":"Risks and opportunities addressed","Clause 6.1.1":"Risk/opportunity planning, general","Clause 6.1.2":"Risk assessment process defined","Clause 6.1.3":"Risk treatment process defined","Clause 6.2":"Security objectives planned","Clause 6.3":"Changes planned deliberately",
"Clause 7.1":"Resources provided","Clause 7.2":"Competence ensured","Clause 7.3":"Staff aware of duties","Clause 7.4":"Communication planned","Clause 7.5":"Documented information controlled",
"Clause 8.1":"Operations planned and controlled","Clause 8.2":"Risk assessments performed","Clause 8.3":"Risk treatment carried out",
"Clause 9.1":"Performance monitored and measured","Clause 9.2":"Internal audits conducted","Clause 9.3":"Management reviews held",
"Clause 10.1":"Continual improvement pursued","Clause 10.2":"Nonconformities corrected",
}
ISO_CLAUSE_WHITELIST=set(ISO_CL)

# ---- CAC-authored CIS v8.1 safeguard labels (referenced set) + control group labels ----
CIS_CTRL={
"CIS-1":"Enterprise asset inventory & control","CIS-2":"Software asset inventory & control","CIS-3":"Data protection","CIS-4":"Secure configuration of assets/software","CIS-5":"Account management","CIS-6":"Access control management","CIS-7":"Continuous vulnerability management","CIS-8":"Audit log management","CIS-9":"Email & web browser protections","CIS-10":"Malware defenses","CIS-11":"Data recovery","CIS-12":"Network infrastructure management","CIS-13":"Network monitoring & defense","CIS-14":"Security awareness & skills training","CIS-15":"Service provider management","CIS-16":"Application software security","CIS-17":"Incident response management","CIS-18":"Penetration testing",
}
CIS_SG={
"CIS 1.1":"Maintain detailed asset inventory","CIS 1.2":"Handle unauthorized assets",
"CIS 2.1":"Maintain software inventory","CIS 2.2":"Keep software supported","CIS 2.3":"Handle unauthorized software","CIS 2.5":"Allowlist authorized software",
"CIS 3.2":"Maintain data inventory","CIS 3.3":"Set data access controls","CIS 3.5":"Dispose of data securely","CIS 3.7":"Maintain data classification scheme","CIS 3.8":"Document data flows","CIS 3.10":"Encrypt data in transit","CIS 3.11":"Encrypt data at rest","CIS 3.12":"Segment data by sensitivity",
"CIS 4.1":"Maintain secure-config process","CIS 4.2":"Secure network device configs",
"CIS 5.1":"Maintain account inventory","CIS 5.6":"Centralize account management",
"CIS 6.1":"Define access-granting process","CIS 6.2":"Define access-revoking process","CIS 6.7":"Centralize access control","CIS 6.8":"Maintain role-based access",
"CIS 7.1":"Maintain vulnerability-management process","CIS 7.2":"Maintain remediation process",
"CIS 8.2":"Collect audit logs","CIS 8.11":"Review audit logs",
"CIS 10.1":"Deploy anti-malware","CIS 10.7":"Use behavior-based anti-malware",
"CIS 11.2":"Automate backups","CIS 11.3":"Protect recovery data","CIS 11.5":"Test recovery",
"CIS 12.2":"Maintain secure network architecture",
"CIS 13.1":"Centralize security-event alerting",
"CIS 14.1":"Run security awareness program","CIS 14.9":"Train role-specific security skills",
"CIS 15.1":"Maintain service-provider inventory","CIS 15.2":"Set provider management policy","CIS 15.3":"Classify service providers","CIS 15.4":"Require security terms in contracts","CIS 15.5":"Assess service providers","CIS 15.6":"Monitor service providers","CIS 15.7":"Decommission providers securely",
"CIS 16.1":"Maintain secure-development process",
"CIS 17.2":"Keep incident reporting contacts","CIS 17.4":"Maintain incident-response process","CIS 17.6":"Define incident comms mechanisms","CIS 17.7":"Run incident-response exercises","CIS 17.8":"Hold post-incident reviews","CIS 17.9":"Set incident thresholds",
}
# ---- 800-53 Rev 5 family names (verbatim; public domain) ----
FAM={"AC":"Access Control","AT":"Awareness and Training","AU":"Audit and Accountability","CA":"Assessment, Authorization, and Monitoring","CM":"Configuration Management","CP":"Contingency Planning","IA":"Identification and Authentication","IR":"Incident Response","MA":"Maintenance","MP":"Media Protection","PE":"Physical and Environmental Protection","PL":"Planning","PM":"Program Management","PS":"Personnel Security","PT":"PII Processing and Transparency","RA":"Risk Assessment","SA":"System and Services Acquisition","SC":"System and Communications Protection","SI":"System and Information Integrity","SR":"Supply Chain Risk Management"}
# ---- SP 800-53 Rev 5 verbatim control titles (public domain; sourced from NIST Rev 5 catalog) ----
TITLES={
"AC-1":"Policy and Procedures","AC-2":"Account Management","AC-3":"Access Enforcement","AC-4":"Information Flow Enforcement","AC-5":"Separation of Duties","AC-6":"Least Privilege","AC-7":"Unsuccessful Logon Attempts","AC-9":"Previous Logon Notification","AC-10":"Concurrent Session Control","AC-12":"Session Termination","AC-14":"Permitted Actions Without Identification or Authentication","AC-16":"Security and Privacy Attributes","AC-17":"Remote Access","AC-18":"Wireless Access","AC-19":"Access Control for Mobile Devices","AC-20":"Use of External Systems","AC-24":"Access Control Decisions",
"AT-1":"Policy and Procedures","AT-2":"Literacy Training and Awareness","AT-3":"Role-based Training",
"AU-1":"Policy and Procedures","AU-2":"Event Logging","AU-3":"Content of Audit Records","AU-6":"Audit Record Review, Analysis, and Reporting","AU-7":"Audit Record Reduction and Report Generation","AU-9":"Protection of Audit Information","AU-11":"Audit Record Retention","AU-12":"Audit Record Generation","AU-13":"Monitoring for Information Disclosure","AU-16":"Cross-organizational Audit Logging",
"CA-1":"Policy and Procedures","CA-2":"Control Assessments","CA-3":"Information Exchange","CA-5":"Plan of Action and Milestones","CA-7":"Continuous Monitoring","CA-8":"Penetration Testing","CA-9":"Internal System Connections",
"CM-1":"Policy and Procedures","CM-2":"Baseline Configuration","CM-3":"Configuration Change Control","CM-4":"Impact Analyses","CM-5":"Access Restrictions for Change","CM-6":"Configuration Settings","CM-7":"Least Functionality","CM-8":"System Component Inventory","CM-9":"Configuration Management Plan","CM-10":"Software Usage Restrictions","CM-11":"User-installed Software","CM-12":"Information Location","CM-13":"Data Action Mapping",
"CM-7(02)":"Least Functionality | Prevent Program Execution","CM-7(04)":"Least Functionality | Unauthorized Software - Deny-by-exception","CM-7(05)":"Least Functionality | Authorized Software - Allow-by-exception","CM-7(09)":"Least Functionality | Prohibiting the Use of Unauthorized Hardware",
"CP-1":"Policy and Procedures","CP-2":"Contingency Plan","CP-4":"Contingency Plan Testing","CP-6":"Alternate Storage Site","CP-7":"Alternate Processing Site","CP-8":"Telecommunications Services","CP-9":"System Backup","CP-10":"System Recovery and Reconstitution",
"CP-2(08)":"Contingency Plan | Identify Critical Assets",
"IA-1":"Policy and Procedures","IA-2":"Identification and Authentication (Organizational Users)","IA-3":"Device Identification and Authentication","IA-4":"Identifier Management","IA-5":"Authenticator Management","IA-6":"Authentication Feedback","IA-7":"Cryptographic Module Authentication","IA-8":"Identification and Authentication (Non-organizational Users)","IA-9":"Service Identification and Authentication","IA-10":"Adaptive Authentication","IA-11":"Re-authentication","IA-12":"Identity Proofing","IA-13":"Identity Providers and Authorization Servers",
"IR-1":"Policy and Procedures","IR-3":"Incident Response Testing","IR-4":"Incident Handling","IR-5":"Incident Monitoring","IR-6":"Incident Reporting","IR-7":"Incident Response Assistance","IR-8":"Incident Response Plan",
"MA-1":"Policy and Procedures","MA-2":"Controlled Maintenance","MA-6":"Timely Maintenance",
"MA-3(06)":"Maintenance Tools | Software Updates and Patches",
"MP-1":"Policy and Procedures","MP-8":"Media Downgrading",
"PE-1":"Policy and Procedures","PE-2":"Physical Access Authorizations","PE-3":"Physical Access Control","PE-4":"Access Control for Transmission","PE-5":"Access Control for Output Devices","PE-6":"Monitoring Physical Access","PE-8":"Visitor Access Records","PE-9":"Power Equipment and Cabling","PE-10":"Emergency Shutoff","PE-11":"Emergency Power","PE-12":"Emergency Lighting","PE-13":"Fire Protection","PE-14":"Environmental Controls","PE-15":"Water Damage Protection","PE-18":"Location of System Components","PE-19":"Information Leakage","PE-20":"Asset Monitoring and Tracking","PE-23":"Facility Location",
"PL-1":"Policy and Procedures","PL-2":"System Security and Privacy Plans","PL-8":"Security and Privacy Architectures",
"PM-1":"Information Security Program Plan","PM-2":"Information Security Program Leadership Role","PM-3":"Information Security and Privacy Resources","PM-4":"Plan of Action and Milestones Process","PM-5":"System Inventory","PM-6":"Measures of Performance","PM-7":"Enterprise Architecture","PM-8":"Critical Infrastructure Plan","PM-9":"Risk Management Strategy","PM-11":"Mission and Business Process Definition","PM-12":"Insider Threat Program","PM-13":"Security and Privacy Workforce","PM-15":"Security and Privacy Groups and Associations","PM-16":"Threat Awareness Program","PM-18":"Privacy Program Plan","PM-19":"Privacy Program Leadership Role","PM-22":"Personally Identifiable Information Quality Management","PM-23":"Data Governance Body","PM-24":"Data Integrity Board","PM-28":"Risk Framing","PM-29":"Risk Management Program Leadership Roles","PM-30":"Supply Chain Risk Management Strategy","PM-31":"Continuous Monitoring Strategy",
"PM-30(01)":"Supply Chain Risk Management Strategy | Suppliers of Critical or Mission-essential Items",
"PS-1":"Policy and Procedures","PS-7":"External Personnel Security","PS-9":"Position Descriptions",
"PT-1":"Policy and Procedures",
"RA-1":"Policy and Procedures","RA-2":"Security Categorization","RA-3":"Risk Assessment","RA-5":"Vulnerability Monitoring and Scanning","RA-7":"Risk Response","RA-8":"Privacy Impact Assessments","RA-9":"Criticality Analysis","RA-10":"Threat Hunting",
"SA-1":"Policy and Procedures","SA-3":"System Development Life Cycle","SA-4":"Acquisition Process","SA-5":"System Documentation","SA-8":"Security and Privacy Engineering Principles","SA-9":"External System Services","SA-10":"Developer Configuration Management","SA-11":"Developer Testing and Evaluation","SA-15":"Development Process, Standards, and Tools","SA-17":"Developer Security and Privacy Architecture and Design","SA-22":"Unsupported System Components",
"SA-10(01)":"Developer Configuration Management | Software and Firmware Integrity Verification","SA-10(03)":"Developer Configuration Management | Hardware Integrity Verification","SA-11(02)":"Developer Testing and Evaluation | Threat Modeling and Vulnerability Analyses","SA-15(07)":"Development Process, Standards, and Tools | Automated Vulnerability Analysis","SA-15(08)":"Development Process, Standards, and Tools | Reuse of Threat and Vulnerability Information","SA-17(06)":"Developer Security and Privacy Architecture and Design | Structure for Testing",
"SC-1":"Policy and Procedures","SC-4":"Information in Shared System Resources","SC-5":"Denial-of-service Protection","SC-6":"Resource Availability","SC-7":"Boundary Protection","SC-8":"Transmission Confidentiality and Integrity","SC-11":"Trusted Path","SC-12":"Cryptographic Key Establishment and Management","SC-13":"Cryptographic Protection","SC-16":"Transmission of Security and Privacy Attributes","SC-24":"Fail in Known State","SC-28":"Protection of Information at Rest","SC-32":"System Partitioning","SC-34":"Non-modifiable Executable Programs","SC-35":"External Malicious Code Identification","SC-36":"Distributed Processing and Storage","SC-39":"Process Isolation","SC-40":"Wireless Link Protection","SC-43":"Usage Restrictions","SC-49":"Hardware-enforced Separation and Policy Enforcement","SC-51":"Hardware-based Protection",
"SC-3(01)":"Security Function Isolation | Hardware Separation","SC-39(01)":"Process Isolation | Hardware Separation",
"SI-1":"Policy and Procedures","SI-2":"Flaw Remediation","SI-3":"Malicious Code Protection","SI-4":"System Monitoring","SI-5":"Security Alerts, Advisories, and Directives","SI-7":"Software, Firmware, and Information Integrity","SI-10":"Information Input Validation","SI-12":"Information Management and Retention","SI-13":"Predictable Failure Prevention","SI-16":"Memory Protection","SI-18":"Personally Identifiable Information Quality Operations",
"SR-1":"Policy and Procedures","SR-2":"Supply Chain Risk Management Plan","SR-3":"Supply Chain Controls and Processes","SR-5":"Acquisition Strategies, Tools, and Methods","SR-6":"Supplier Assessments and Reviews","SR-8":"Notification Agreements","SR-10":"Inspection of Systems or Components","SR-11":"Component Authenticity","SR-12":"Component Disposal",
}

def parse_iso(v):
    v=v.strip(); out=[]
    if v.startswith("Annex A Controls:"):
        n=v.split(":",1)[1].strip()
        if re.match(r'^\d+(\.\d+)?$', n): out.append((f"A.{n}", f"A.{n.split('.')[0]}"))
    elif v.startswith("Mandatory Clause:"):
        body=v.split(":",1)[1]
        for tok in re.findall(r'\d+\.\d+(?:\.\d+)?', body):
            cid=f"Clause {tok}"
            if cid in ISO_CLAUSE_WHITELIST: out.append((cid,"CL"))
    return out
def parse_80053(v):
    m=re.match(r'^([A-Z]{2})-(\d+)(\(.*\))?$', v.strip())
    if not m: return []
    return [(f"{m.group(1)}-{int(m.group(2))}{m.group(3) or ''}", m.group(1))]
def parse_cis(v):
    v=v.strip()
    if re.match(r'^\d+\.\d+$', v): return [(f"CIS {v}", f"CIS-{v.split('.')[0]}")]
    return []

FW={
 '800-53-r5':dict(pre='SP 800-53 Rev 5.1.1',parse=parse_80053,auth='nist-developed',
                  name='NIST SP 800-53 Rev 5',ver='Rev 5',lic='public-domain'),
 'iso-27001-2022':dict(pre='ISO/IEC 27001:2022',parse=parse_iso,auth='mixed-third-party',
                  name='ISO/IEC 27001:2022',ver='2022',lic='iso-copyright'),
 'cis-8.1':dict(pre='CIS Controls v8.1',parse=parse_cis,auth='cis-authored',
                  name='CIS Critical Security Controls v8.1',ver='8.1',lic='cis-cc-by-nc-nd'),
}
rows=read_rows(SRC,'CSF 2.0')
edges={k:set() for k in FW}
cur=None
for r in rows:
    sub=r[2]
    if isinstance(sub,str) and SUB.match(sub): cur=sub.split(':',1)[0].strip()
    else: continue
    cell=r[4]
    if not isinstance(cell,str): continue
    for line in cell.split(chr(10)):
        line=line.strip()
        for k,spec in FW.items():
            if line.startswith(spec['pre']+':'):
                for cid,grp in spec['parse'](line[len(spec['pre'])+1:]):
                    edges[k].add((cur,cid,grp))

def catalog(fid, ctrl_ids):
    spec=FW[fid]; controls=[]; groupings=[]
    if fid=='iso-27001-2022':
        for gid,glab in [("A.5","Organizational controls"),("A.6","People controls"),("A.7","Physical controls"),("A.8","Technological controls"),("CL","ISO 27001 management clauses (4–10)")]:
            groupings.append({"id":gid,"label":glab})
        allids=set(ISO_A)|set(ISO_CL)          # full 93 + clauses -> enables "not covered by CSF" list
        for cid in sorted(allids, key=iso_sort):
            lab=ISO_A.get(cid) or ISO_CL.get(cid)
            grp="CL" if cid.startswith("Clause") else f"A.{cid.split('.')[1] if cid.startswith('A.') else ''}"
            grp=cid.split('.')[0]+'.'+cid.split('.')[1] if False else ("CL" if cid.startswith("Clause") else "A."+cid[2])
            controls.append({"id":cid,"label":lab,"groupingId":grp,"labelSource":"cac-generated","text":None})
    elif fid=='cis-8.1':
        used_groups=sorted({f"CIS-{c.split(' ')[1].split('.')[0]}" for c in ctrl_ids}, key=lambda g:int(g.split('-')[1]))
        for gid in used_groups: groupings.append({"id":gid,"label":CIS_CTRL[gid]})
        for cid in sorted(ctrl_ids, key=lambda s:[int(x) for x in s.replace('CIS ','').split('.')]):
            controls.append({"id":cid,"label":CIS_SG[cid],"groupingId":f"CIS-{cid.split(' ')[1].split('.')[0]}","labelSource":"cac-generated","text":None})
    else:  # 800-53
        used=sorted({g for _,_,g in edges[fid]})
        for g in used: groupings.append({"id":g,"label":FAM[g]})
        for cid in sorted(ctrl_ids, key=nist_sort):
            fam=re.match(r'^([A-Z]{2})',cid).group(1)
            title=TITLES.get(cid)
            controls.append({"id":cid,"label":title or cid,"groupingId":fam,
                             "labelSource":"verbatim-public-domain" if title else "pending-verbatim-title","text":None})
    return {"frameworkId":fid,"name":spec['name'],"version":spec['ver'],"license":spec['lic'],
            "provenance":PROV[fid],"sourceExport":{"tool":"NIST CSF 2.0 Reference Export (xlsx)","retrievedAt":RETRIEVED},
            "groupings":groupings,"controls":controls}

def iso_sort(c):
    if c.startswith("Clause"): return (1,)+tuple(int(x) for x in re.findall(r'\d+',c))
    return (0,)+tuple(int(x) for x in c[2:].split('.'))
def nist_sort(c):
    m=re.match(r'^([A-Z]{2})-(\d+)',c); return (m.group(1),int(m.group(2)),c)

PROV={
"800-53-r5":"NIST-developed CSF→800-53 mapping (public domain). Family names verbatim; per-control titles pending a titles ingest.",
"iso-27001-2022":"Control/clause IDs referenced from NIST's CSF 2.0 informative references (mixed/third-party authority). Labels are CAC paraphrases — ISO/IEC text is copyright; bring your own copy.",
"cis-8.1":"CSF↔CIS relationships are CIS-authored (used as facts, tagged; CIS document not republished). Labels are CAC paraphrases. CIS content is CC BY-NC-ND.",
}
for fid,spec in FW.items():
    es=sorted({(a,b) for a,b,_ in edges[fid]})
    ids={b for _,b in es}
    m={"csfFrameworkId":"csf-2.0","overlayFrameworkId":fid,"direction":"bidirectional",
       "mappingAuthority":spec['auth'],"sourceExport":{"tool":"NIST CSF 2.0 Reference Export (xlsx)","retrievedAt":RETRIEVED},
       "edges":[{"csfSubId":a,"controlId":b,"authority":spec['auth']} for a,b in es]}
    json.dump(m,open(os.path.join(DATA,f"csf-2.0__{fid}.map.json"),"w"),indent=1)
    cat=catalog(fid, ids)
    json.dump(cat,open(os.path.join(DATA,f"{fid}.catalog.json"),"w"),indent=1)
    print(f"{fid}: {len(es)} edges · {len(ids)} mapped ids · catalog {len(cat['controls'])} controls / {len(cat['groupings'])} groups")

# clean up scratch id files + starter demo maps replaced
for f in os.listdir(DATA):
    if f.startswith("_ids_"): os.remove(os.path.join(DATA,f))
print("done")
