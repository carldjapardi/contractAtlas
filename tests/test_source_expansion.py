"""Validate real provenance, fictional identity separation, and feedback isolation."""
import csv
import hashlib
import json
from pathlib import Path

from scripts.build_source_expansion import curate

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/expansion"


def read_csv(path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def test_curated_rows_match_exact_snapshot_entities_and_award_fields():
    snapshot = json.loads((ROOT / "data/snapshot.json").read_text())
    by_id = {a["id"]: a for a in snapshot["awards"]}
    rows = read_csv(BUNDLE / "candidate_partners.csv")
    assert len(rows) == 12
    assert len({r["candidate_id"] for r in rows}) == len(rows)
    for row in rows:
        ids = json.loads(row["award_ids"])
        assert len(ids) == int(row["selected_award_count"])
        assert json.loads(row["award_descriptions"]) == [by_id[i]["description"] for i in ids]
        assert json.loads(row["source_urls"]) == [by_id[i]["source_url"] for i in ids]
        for aid in ids:
            a = by_id[aid]
            assert a["recipient_id"] == row["recipient_id"]
            assert a["recipient_name"] == row["recipient_name"]
            assert a["recipient_uei"] == row["recipient_uei"]
        for field in ["contact_name", "contact_role", "teaming_interest", "current_capacity", "staffed_coverage", "eligibility"]:
            assert row[field] == "unknown"


def test_same_name_recipient_identities_are_not_combined():
    snapshot = json.loads((ROOT / "data/snapshot.json").read_text())
    leidos = [a for a in snapshot["awards"] if a["recipient_name"] == "LEIDOS, INC."]
    assert len({a["recipient_id"] for a in leidos}) > 1
    rows, _ = curate(snapshot)
    chosen = next(r for r in rows if r["recipient_name"] == "LEIDOS, INC.")
    source = {a["id"]: a for a in leidos}
    assert {source[i]["recipient_id"] for i in chosen["award_ids"]} == {chosen["recipient_id"]}


def test_public_captures_and_preserved_checkpoint_match_manifest():
    manifest = json.loads((BUNDLE / "manifest.json").read_text())
    assert hashlib.sha256((ROOT / "data/team_sources.json").read_bytes()).hexdigest() == manifest["baseline_sha256"]
    for capture in manifest["public_captures"]:
        assert hashlib.sha256((BUNDLE / capture["file"]).read_bytes()).hexdigest() == capture["sha256"]
        assert capture["url"].startswith("https://")
        assert capture["retrieved_at"]


def test_synthetic_relationships_have_only_fictional_identities_and_valid_sources():
    rows = read_csv(BUNDLE / "synthetic/relationships.csv")
    sources = json.loads((BUNDLE / "team_sources.expanded.json").read_text())["sources"]
    source_map = {s["id"]: s for s in sources}
    assert len(rows) == 6
    assert len({r["record_id"] for r in rows}) == len(rows)
    for row in rows:
        assert row["evidence_status"] == "synthetic_demo"
        assert row["organization_id"].startswith("demo:")
        assert row["organization_uei"] == "not_applicable_fictional"
        assert row["real_company_match"] == "none"
        for sid in json.loads(row["source_ids"]):
            assert "SYNTHETIC DEMO" in source_map[sid]["text"]


def test_review_and_evaluation_answers_are_not_in_initial_memory():
    expanded = json.loads((BUNDLE / "team_sources.expanded.json").read_text())
    sources = expanded["sources"]
    assert len({s["id"] for s in sources}) == len(sources)
    assert len(sources) == 68
    text = "\n".join(s["text"] for s in sources)
    assert "demo:review-01" not in text
    assert "Accepted feedback candidate" not in text
    assert "held_out_readiness" not in text
    assert "comparison_protocol" not in text
    assert sum(s["id"].startswith("demo:meeting-") for s in sources) == 3
    original = json.loads((ROOT / "data/team_sources.json").read_text())["sources"]
    by_id = {s["id"]: s for s in sources}
    for source in original:
        assert by_id[source["id"]] == source
    capability_sources = [s for s in sources if s["kind"] == "company_capability"]
    assert len(capability_sources) == 4
    assert all(len(s["text"].split()) <= 185 for s in capability_sources)
    guidance = by_id["guidance_cisa_identity_table2_v2"]
    assert "maturity: Optimal" in guidance["text"]
    assert "not universal procurement requirements" in guidance["text"]


def test_csv_cells_cannot_be_interpreted_as_formulas():
    for path in [BUNDLE / "candidate_partners.csv", BUNDLE / "synthetic/relationships.csv"]:
        for row in read_csv(path):
            assert all(not value.lstrip().startswith(("=", "+", "-", "@")) for value in row.values())
