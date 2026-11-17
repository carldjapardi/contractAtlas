import json
import sys

import pytest

from backend import baseline, data
from scripts.ingest import normalize
from scripts import ingest


def source_row(award_id="ONE", recipient_uei="UEI1", amount=10.25):
    return {"generated_internal_id": f"CONT_AWD_{award_id}", "Award ID": award_id,
            "Recipient UEI": recipient_uei, "Recipient Name": "SAME NAME LLC",
            "recipient_id": "source-recipient-id", "Award Amount": amount,
            "Awarding Agency": "Department of Homeland Security",
            "Description": "Identity and access management"}


@pytest.fixture
def frozen_snapshot(tmp_path, monkeypatch):
    awards = [normalize(source_row("ONE", "UEI1", 10.25), {"recipient": {
                  "parent_recipient_uei": "PARENT", "parent_recipient_name": "Parent Group"}}),
              normalize(source_row("TWO", "UEI2", -2.10), {"recipient": {
                  "parent_recipient_uei": "PARENT", "parent_recipient_name": "Parent Group"}}),
              normalize(source_row("THREE", "UEI3", 100))]
    awards[1]["description"] = "Cybersecurity monitoring"
    awards[2]["description"] = "Office chairs"
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps({"metadata": {"name": "test", "truncated": True}, "awards": awards}))
    monkeypatch.setenv("ATLAS_SNAPSHOT_PATH", str(path))
    return awards


def test_stable_award_and_recipient_identity_is_not_name_based():
    first = normalize(source_row("ONE", "UEI1"))
    second = normalize(source_row("TWO", "UEI2"))
    assert first["id"] != second["id"]
    assert first["recipient_id"] != second["recipient_id"]
    assert first["recipient_name"] == second["recipient_name"]
    with pytest.raises(ValueError):
        normalize({"Award ID": "AMBIGUOUS"})


def test_missing_parent_is_unknown():
    award = normalize(source_row())
    assert award["parent_uei"] is None
    assert all(node["type"] != "parent" for node in data.build_graph([award])["nodes"])


def test_graph_deduplicates_awards_and_has_evidence_for_every_reported_edge(frozen_snapshot):
    graph = data.build_graph(frozen_snapshot + frozen_snapshot)
    assert len([n for n in graph["nodes"] if n["type"] == "award"]) == 3
    assert len([n for n in graph["nodes"] if n["type"] == "recipient"]) == 3
    assert len([n for n in graph["nodes"] if n["type"] == "parent"]) == 1
    node_ids = {n["id"] for n in graph["nodes"]}
    for edge in graph["edges"]:
        assert edge["source"] in node_ids and edge["target"] in node_ids
        assert edge["origin"] == "reported"
        assert edge["award_ids"]


def test_graph_limit_declares_truncation(frozen_snapshot):
    graph = data.build_graph(frozen_snapshot, limit=1)
    assert graph["truncated"]
    assert len([n for n in graph["nodes"] if n["type"] == "award"]) == 1


def test_graph_reuses_exact_uei_recipient_for_reported_parent_role(frozen_snapshot):
    frozen_snapshot[0]["parent_uei"] = frozen_snapshot[1]["recipient_uei"]
    frozen_snapshot[0]["parent_name"] = frozen_snapshot[1]["recipient_name"]
    graph = data.build_graph(frozen_snapshot)
    ids = {node["id"] for node in graph["nodes"]}
    assert "parent:UEI2" not in ids
    parent = next(node for node in graph["nodes"] if node["id"] == "recipient:UEI2")
    assert parent["type"] == "recipient"
    assert "reported ultimate parent" in parent["sublabel"]
    assert set(parent["award_ids"]) == {"CONT_AWD_ONE", "CONT_AWD_TWO"}
    edge = next(edge for edge in graph["edges"] if edge["source"] == "recipient:UEI2" and edge["target"] == "recipient:UEI1")
    assert edge["relationship"] == "reported parent of"
    assert edge["origin"] == "reported"
    assert edge["award_ids"] == ["CONT_AWD_ONE"]


def test_equal_parent_name_without_equal_uei_does_not_merge(frozen_snapshot):
    frozen_snapshot[0]["parent_name"] = frozen_snapshot[1]["recipient_name"]
    graph = data.build_graph(frozen_snapshot)
    assert {"parent:PARENT", "recipient:UEI2"} <= {n["id"] for n in graph["nodes"]}


def test_award_filter_combines_search_and_entity_identity(frozen_snapshot):
    assert data.get_awards(search="access", recipient_id="UEI1")["total"] == 1
    assert data.get_awards(search="access", recipient_id="UEI2")["total"] == 0
    assert data.get_awards(limit=1)["total"] == 3
    assert len(data.get_awards(limit=1)["awards"]) == 1


def test_financial_summary_includes_negative_amounts_and_lifetime_label(frozen_snapshot):
    result = baseline.query("Show all awards")
    assert "$108.15" in result["answer"]
    assert "lifetimes" in result["answer"]
    assert result["matched_count"] == 3


def test_lexical_retrieval_does_not_invent_synonym_matches(frozen_snapshot):
    result = baseline.query("identity access management")
    assert [e["id"] for e in result["evidence"]] == ["CONT_AWD_ONE"]
    assert baseline.query("zero trust orchestration")["evidence"] == []


def test_shared_parent_requires_distinct_identifiers(frozen_snapshot):
    result = baseline.query("Which recipients share a parent?")
    assert "Parent Group" in result["answer"]
    assert {e["id"] for e in result["evidence"]} == {"CONT_AWD_ONE", "CONT_AWD_TWO"}
    assert "CONT_AWD_THREE" not in result["graph"]["nodes"]


def test_parent_lookup_scopes_to_exact_recipient_identifier(frozen_snapshot):
    result = baseline.query("Who is the parent of UEI1?")
    assert [e["id"] for e in result["evidence"]] == ["CONT_AWD_ONE"]
    assert "Parent Group" in result["answer"]


def test_source_award_identifier_lookup_is_exact(frozen_snapshot):
    assert [e["id"] for e in baseline.query("Find award TWO")["evidence"]] == ["CONT_AWD_TWO"]


def test_common_question_words_do_not_match_the_in_recipient_name(frozen_snapshot):
    frozen_snapshot[2]["recipient_name"] = "THE UNIVERSITY OF TEXAS"
    assert not baseline._entity_matches("Who is the parent of LEIDOS?", frozen_snapshot)


def test_rare_topic_word_does_not_force_recipient_name_routing(frozen_snapshot):
    frozen_snapshot[0]["recipient_name"] = "ADVANCED COMPUTER CONCEPTS LLC"
    frozen_snapshot[0]["description"] = "Office supplies"
    frozen_snapshot[1]["description"] = "Computer network defense services"
    assert baseline._entity_matches("Find computer network defense services", frozen_snapshot) == []
    assert {a["id"] for a in baseline.retrieve("computer network defense", frozen_snapshot)} == {
        "CONT_AWD_ONE", "CONT_AWD_TWO"}


def test_complete_recipient_name_can_omit_legal_suffix(frozen_snapshot):
    frozen_snapshot[0]["recipient_name"] = "A DISTINCT COMPANY LLC"
    frozen_snapshot[1]["recipient_name"] = "UNRELATED CORPORATION"
    frozen_snapshot[2]["recipient_name"] = "A THIRD COMPANY"
    assert [a["id"] for a in baseline._entity_matches("Find awards for A DISTINCT", frozen_snapshot)] == ["CONT_AWD_ONE"]


@pytest.mark.parametrize("question", ["Which contractors committed fraud?", "How much cash was paid?",
                                     "Which projects were successful?", "Who wins across agencies?",
                                     "Did these contracts prevent cyber attacks?"])
def test_unanswerable_questions_abstain(frozen_snapshot, question):
    result = baseline.query(question)
    assert not result["evidence"]
    assert "cannot establish" in result["answer"]


def test_missing_snapshot_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_SNAPSHOT_PATH", str(tmp_path / "missing.json"))
    assert data.get_metadata()["status"] == "empty"
    assert baseline.query("Show awards")["matched_count"] == 0


def test_ingestion_keeps_page_size_constant_when_limit_is_not_page_multiple(tmp_path, monkeypatch):
    requests = []

    def fake_request(client, method, url, **kwargs):
        payload = kwargs["json"]
        requests.append(payload)
        start = (payload["page"] - 1) * payload["limit"]
        stop = min(start + payload["limit"], 180)
        return {"results": [source_row(str(i)) for i in range(start, stop)],
                "page_metadata": {"hasNext": stop < 180}}

    monkeypatch.setattr(ingest, "ROOT", tmp_path)
    monkeypatch.setattr(ingest, "request_json", fake_request)
    monkeypatch.setattr(sys, "argv", ["ingest", "--limit", "150", "--skip-details"])
    ingest.main()
    snapshot = json.loads((tmp_path / "data/snapshot.json").read_text())
    assert [request["limit"] for request in requests] == [100, 100]
    assert len(snapshot["awards"]) == 150
    assert snapshot["metadata"]["truncated"]
    assert snapshot["metadata"]["raw_path"].startswith("data/raw/")
    assert (tmp_path / snapshot["metadata"]["raw_path"] / "requests.json").exists()


@pytest.mark.parametrize("bad_amount", [None, True, "NaN", "Infinity", "-Infinity", "1e10000", "not-a-number"])
def test_missing_or_nonfinite_amount_never_becomes_a_published_obligation(bad_amount):
    with pytest.raises(ValueError):
        normalize(source_row(amount=bad_amount))


@pytest.mark.parametrize("response", [{}, {"results": []}, {"results": [], "page_metadata": {}},
                                     {"results": [], "page_metadata": {"hasNext": "false"}},
                                     {"results": [], "page_metadata": {"hasNext": True}},
                                     {"results": [source_row(amount="NaN")], "page_metadata": {"hasNext": False}}])
def test_malformed_or_stalled_ingestion_preserves_snapshot_and_old_raw(tmp_path, monkeypatch, response):
    existing = {"metadata": {}, "awards": [normalize(source_row())]}
    path = tmp_path / "data/snapshot.json"
    path.parent.mkdir()
    original = json.dumps(existing)
    path.write_text(original)
    old_raw = tmp_path / "data/raw/old-run"
    old_raw.mkdir(parents=True)
    (old_raw / "search-page-1.json").write_text("old source evidence")
    monkeypatch.setattr(ingest, "ROOT", tmp_path)
    monkeypatch.setattr(ingest, "request_json", lambda *args, **kwargs: response)
    monkeypatch.setattr(sys, "argv", ["ingest", "--skip-details"])
    with pytest.raises(ValueError):
        ingest.main()
    assert path.read_text() == original
    assert (old_raw / "search-page-1.json").read_text() == "old source evidence"


def test_empty_replacement_requires_explicit_cli_flag(tmp_path, monkeypatch):
    path = tmp_path / "data/snapshot.json"
    path.parent.mkdir()
    original = json.dumps({"metadata": {}, "awards": [normalize(source_row())]})
    path.write_text(original)
    monkeypatch.setattr(ingest, "ROOT", tmp_path)
    monkeypatch.setattr(ingest, "request_json", lambda *args, **kwargs: {"results": [], "page_metadata": {"hasNext": False}})
    monkeypatch.setattr(sys, "argv", ["ingest", "--skip-details"])
    with pytest.raises(ValueError, match="allow-empty"):
        ingest.main()
    assert path.read_text() == original
    monkeypatch.setattr(sys, "argv", ["ingest", "--skip-details", "--allow-empty"])
    ingest.main()
    assert json.loads(path.read_text())["awards"] == []
