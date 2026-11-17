"""Build the approved, isolated source expansion; never mutate the active corpus.

CSV files are machine-readable ingestion fixtures, generated from the same JSON
records as the source documents. No spreadsheet formulas or inferred contacts.
Public HTML/PDF captures are retained, hashed, and fetched only with --refresh-public.
Run PDF extraction with a Python environment containing pypdf.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess

from scripts.collect_team_sources import award_source, extract_main_text

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/expansion"
PUBLIC = {
    "deloitte_identity.html": "https://www.deloitte.com/us/en/services/consulting/services/cyber-identity.html",
    "accenture_federal_cyber.html": "https://www.accenture.com/en-us/industries/accenture-federal-services/cybersecurity",
    "cisa_zero_trust_v2.pdf": "https://www.cisa.gov/sites/default/files/2023-04/zero_trust_maturity_model_v2_508.pdf",
}
# Manual, reviewable subject selection. Identity relevance is not implied by inclusion.
CANDIDATES = {
    "LEIDOS, INC.": "SOC and cybersecurity operations",
    "ACCENTURE FEDERAL SERVICES LLC": "Vulnerability management support",
    "DELOITTE & TOUCHE LLP": "SOC security engineering",
    "BOOZ ALLEN HAMILTON INC": "Cybersecurity exercises and support",
    "INFORMATION TECHNOLOGY COMPANY, L.L.C.": "Cybersecurity support; scope needs verification",
    "SYNERGIST JV LLC": "Information system security and program support",
    "SOFITC3, LLC": "Cybersecurity assessments and awareness",
    "Z, INC.": "Vulnerability analysis and reporting",
    "IDEMIA IDENTITY & SECURITY USA LLC": "Credential-authentication equipment cybersecurity; enterprise IAM fit unknown",
    "SOLUTIONS3 LLC": "Cyber defense training; operational delivery fit unknown",
    "ACADEMY OF APPLIED TECHNOLOGY, LLC": "Cybersecurity training; operational delivery fit unknown",
    "THE MITRE CORPORATION": "Research and systems engineering; teaming suitability needs separate review",
}
TOPICS = [r"identity", r"access management", r"security operations", r"\bsoc\b", r"zero[ -]?trust", r"vulnerability", r"cyber.?security", r"cyber defense"]


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def norm(text):
    return " ".join(text.split())


def score(award):
    return sum(bool(re.search(p, award["description"], re.I)) for p in TOPICS)


def curate(snapshot):
    rows, supporting = [], {}
    for name, lane in CANDIDATES.items():
        matches = [a for a in snapshot["awards"] if a["recipient_name"] == name and score(a)]
        matches.sort(key=lambda a: (-score(a), a["id"]))
        if not matches:
            raise ValueError(f"No description-supported candidate: {name}")
        # One exact source identity per row. Same-name entities are never merged.
        entity = matches[0]["recipient_id"]
        evidence = [a for a in matches if a["recipient_id"] == entity][:3]
        source_ids = []
        for a in evidence:
            source = award_source(a, snapshot["metadata"]["retrieved_at"])
            supporting[source["id"]] = source
            source_ids.append(source["id"])
        rows.append({
            "candidate_id": "public:" + entity, "recipient_name": name,
            "recipient_id": entity, "recipient_uei": evidence[0].get("recipient_uei") or "unknown",
            "research_lane": lane, "evidence_status": "real_derived",
            "snapshot_id": snapshot["metadata"]["snapshot_id"],
            "snapshot_retrieved_at": snapshot["metadata"]["retrieved_at"],
            "selected_award_count": len(evidence),
            "award_ids": [a["id"] for a in evidence],
            "source_ids": source_ids, "source_urls": [a["source_url"] for a in evidence],
            "award_descriptions": [a["description"] for a in evidence],
            "contact_name": "unknown", "contact_role": "unknown",
            "teaming_interest": "unknown", "current_capacity": "unknown",
            "staffed_coverage": "unknown", "eligibility": "unknown",
            "qualification_status": "research_candidate_only",
        })
    return rows, list(supporting.values())


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v for k, v in row.items()})


class VisibleText(HTMLParser):
    """Publisher-specific fallback: skip script/style, then use an exact heading boundary."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1

    def handle_data(self, value):
        if not self.skip and value.strip():
            self.parts.append(norm(value))


def public_sources():
    sources, captures = [], []
    for filename, url in PUBLIC.items():
        path = BUNDLE / "public" / filename
        raw = path.read_bytes()
        retrieved = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
        capture = {"file": "public/" + filename, "url": url, "retrieved_at": retrieved,
                   "sha256": hashlib.sha256(raw).hexdigest()}
        captures.append(capture)
        if filename.endswith(".pdf"):
            from pypdf import PdfReader
            reader = PdfReader(path)
            page_texts = {str(i + 1): reader.pages[i].extract_text() for i in [12, 13, 14]}
            dump(BUNDLE / "public/cisa_identity_pages.json", page_texts)
            intro = norm(page_texts["13"].split("5.1 Identity", 1)[1].split("Table 2 lists", 1)[0])
            # Explicit row/column labels avoid flattening a table into false assertions.
            cells = [
                ("13", "Authentication", "Optimal", "Agency continuously validates identity with phishing-resistant MFA, not just when access is initially granted."),
                ("14", "Identity Stores", "Optimal", "Agency securely integrates their identity stores across all partners and environments as appropriate."),
                ("14", "Access Management (New Function)", "Optimal", "Agency uses automation to authorize just-in-time and just-enough access tailored to individual actions and individual resource needs."),
                ("15", "Visibility and Analytics Capability", "Optimal", "Agency maintains comprehensive visibility and situational awareness across enterprise by performing automated analysis over user activity log types, including behavior-based analytics."),
            ]
            for page, _, _, text in cells:
                if text not in norm(page_texts[page]):
                    raise ValueError("CISA table content changed; inspect the complete PDF pages")
            text = "Section 5.1 Identity, page 13 (verbatim prose, whitespace normalized):\n" + intro
            text += "\n\nTable 2 selected cells. These describe OPTIMAL maturity, not universal procurement requirements."
            for page, function, stage, cell in cells:
                text += f"\nPage {page}; function: {function}; maturity: {stage}; source cell: {cell}"
            sources.append({"id": "guidance_cisa_identity_table2_v2", "title": "CISA Zero Trust Maturity Model v2: Identity, section 5.1 and Table 2", "kind": "agency_guidance", "url": url + "#page=13", "retrieved_at": retrieved, "text": text, "notes": ["Real official guidance, April 2023, pages 13-15. Selected cells visually checked against rendered pages.", "Not a solicitation. Optimal maturity examples are not blanket mandatory requirements.", "Original PDF and full extracted page text retained; excerpt labels preserve table row and column meaning."]})
            continue
        if filename.startswith("deloitte"):
            parser = VisibleText()
            parser.feed(raw.decode())
            full = "\n".join(parser.parts)
            start, stop = "Digital Identity +", "Privileged Account Management"
            excerpt = full[full.index(start):full.index(stop)]
            sid, title = "capability_deloitte_identity", "Deloitte: Cyber Identity (self-reported excerpt)"
            note = "Brand-level service page. Do not infer which Deloitte legal entity delivers each service or transfer eligibility between entities."
        else:
            full = extract_main_text(raw.decode())
            start, stop = "Adaptive security operations & MxDR", "Execution-ready cyber capabilities"
            excerpt = full[full.index(start):full.index(stop)]
            sid, title = "capability_accenture_federal_cyber", "Accenture Federal Services: Cybersecurity (self-reported excerpt)"
            note = "Federal-services publisher page; availability, specific awards, and eligibility require separate evidence."
        excerpt = " ".join(excerpt.split()[:185])
        if len(excerpt) < 150:
            raise ValueError("Insufficient actual capability content")
        (BUNDLE / "public" / filename.replace(".html", ".txt")).write_text(full)
        sources.append({"id": sid, "title": title, "kind": "company_capability", "url": url,
                        "retrieved_at": retrieved, "text": excerpt, "notes": ["Real retrieved publisher HTML; bounded verbatim excerpt, whitespace normalized.", "Self-reported claims, not independently verified past performance or operational readiness.", note]})
    return sources, captures


def relationship_rows():
    common = {"evidence_status": "synthetic_demo", "scenario_as_of": "2026-11-16",
              "organization_uei": "not_applicable_fictional", "real_company_match": "none"}
    records = [
        ("demo:harbor-signal", "Harbor Signal (fictional)", "Rowan Hale", "Partnerships manager", "Maya Chen", "2026-11-09", "discovery_completed", "Delivery qualification; no teaming commitment", "2026-11-12", ["demo:meeting-01"], "historical"),
        ("demo:harbor-signal", "Harbor Signal (fictional)", "Alex Rivera", "Delivery lead", "Imani Cole", "2026-11-12", "technical_coverage_clarified", "Weekday triage only; verify staffing evidence", "2026-11-18", ["demo:meeting-02"], "current_coverage_capacity_superseded"),
        ("demo:harbor-signal", "Harbor Signal (fictional)", "Alex Rivera", "Delivery lead", "Maya Chen", "2026-11-16", "capacity_unavailable_for_december", "Recheck provisional January 18 capacity", "2026-11-23", ["demo:meeting-03"], "current"),
        ("demo:cedar-response", "Cedar Response (fictional)", "Sam Okafor", "Operations lead", "Noah Reed", "2026-11-12", "evidence_requested", "Request coverage roster and escalation matrix; 24/7 claim unverified", "2026-11-18", ["demo:meeting-02"], "current"),
        ("demo:cedar-response", "Cedar Response (fictional)", "Sam Okafor", "Operations lead", "Imani Cole", "2026-11-12", "technical_review_pending", "Assess promised evidence when received; no response ownership agreed", "2026-11-18", ["demo:meeting-02"], "current"),
        ("demo:harbor-signal", "Harbor Signal (fictional)", "Alex Rivera", "Delivery lead", "Imani Cole", "2026-11-16", "eligibility_unverified", "Obtain eligibility evidence before any procurement-specific recommendation", "unknown", ["demo:meeting-02", "demo:meeting-03"], "current"),
    ]
    fields = ["organization_id", "organization_name", "contact_name", "contact_role", "internal_owner", "interaction_date", "status", "next_action", "due_date", "source_ids", "record_state"]
    return [dict(record_id=f"demo:relationship-{i:02}", **dict(zip(fields, row)), **common) for i, row in enumerate(records, 1)]


def build():
    snapshot = json.loads((ROOT / "data/snapshot.json").read_text())
    base = json.loads((ROOT / "data/team_sources.json").read_text())
    rows, award_sources = curate(snapshot)
    write_csv(BUNDLE / "candidate_partners.csv", rows)
    relations = relationship_rows()
    write_csv(BUNDLE / "synthetic/relationships.csv", relations)
    extra, captures = public_sources()
    # Fixed scenario date is distinct from actual creation/retrieval timestamps.
    created = datetime.now(timezone.utc).isoformat()
    docs = []
    for filename, sid in [("company_profile.md", "demo:company-profile"), ("meeting_01_discovery.md", "demo:meeting-01"), ("meeting_02_technical.md", "demo:meeting-02"), ("meeting_03_update.md", "demo:meeting-03")]:
        text = (BUNDLE / "synthetic" / filename).read_text()
        docs.append({"id": sid, "title": text.splitlines()[0].lstrip("# "), "kind": "internal_brief", "url": None, "retrieved_at": created, "text": text, "notes": ["SYNTHETIC DEMO. All organizations, people, relationships and dialogue are fictional.", "Not evidence about any real public contractor. Fictional IDs must not be resolved to real UEIs.", "Meeting statements are attributed claims. Promised evidence is pending, and explicit later updates supersede only the specified fields."]})
    for filename, records, status in [("candidate_partners.csv", rows, "REAL DERIVED PUBLIC DATA"), ("synthetic/relationships.csv", relations, "SYNTHETIC DEMO")]:
        for row in records:
            key = row.get("candidate_id") or row["record_id"]
            docs.append({"id": "curated:" + key, "title": status + ": " + str(row.get("recipient_name") or row["record_id"]), "kind": "internal_brief", "url": None, "retrieved_at": created, "text": status + "\n" + json.dumps(row, ensure_ascii=False, indent=2), "notes": ["Structured curation from " + filename + "; underlying source IDs and original evidence are retained.", "Real candidates have unknown contacts, availability, interest, coverage and eligibility. Synthetic records describe fictional organizations only."]})
    sources = {s["id"]: s for s in base["sources"]}
    for source in award_sources + extra + docs:
        if source["id"] not in sources:
            sources[source["id"]] = source
    expanded = {"version": 1, "sources": list(sources.values()), "notes": base["notes"] + ["Approved expansion 1-7: real-derived candidate CSV, four companies' capability evidence, synthetic profile/relationships/three meetings, separate synthetic review input, focused official guidance.", "Synthetic review meeting and evaluation expectations are deliberately excluded from initial ingestion. No GitHub repository or procurement notice was added."]}
    dump(BUNDLE / "team_sources.expanded.json", expanded)
    manifest = {"version": 1, "created_at": created, "active_corpus_unchanged": True,
                "baseline_sha256": hashlib.sha256((ROOT / "data/team_sources.json").read_bytes()).hexdigest(),
                "snapshot_id": snapshot["metadata"]["snapshot_id"], "public_captures": captures,
                "candidate_rows": len(rows), "relationship_rows": len(relations),
                "initial_source_count": len(sources), "review_input": "synthetic/review_meeting.md",
                "excluded_from_initial_ingestion": ["synthetic/review_meeting.md", "evaluation_cases.json"],
                "capability_companies": ["Leidos", "GuidePoint Security", "Deloitte", "Accenture Federal Services"]}
    dump(BUNDLE / "manifest.json", manifest)
    print(json.dumps({k: manifest[k] for k in ["candidate_rows", "relationship_rows", "initial_source_count"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-public", action="store_true")
    args = parser.parse_args()
    if args.refresh_public:
        for filename, url in PUBLIC.items():
            target = BUNDLE / "public" / filename
            temporary = target.with_suffix(target.suffix + ".download")
            subprocess.run(["curl", "-fLsS", "--max-time", "60", "--user-agent", "Mozilla/5.0", url, "-o", str(temporary)], check=True)
            temporary.replace(target)
    build()


if __name__ == "__main__":
    main()
