from pathlib import Path

from backend import team_memory as team


def test_source_document_preserves_provenance_and_source_category():
    source = {"id": "agency:cisa", "title": "Guidance", "kind": "agency_guidance",
              "url": "https://www.cisa.gov/example", "retrieved_at": "2026-11-16", "text": "Real source text", "notes": []}
    text = team._source_document(source)
    assert text.count("[TEAM_SOURCE:agency:cisa]") == 2
    assert "Real source text" in text
    assert "not live solicitations" in text


def test_evidence_mapping_rejects_unknown_ids_and_echoed_prompts():
    rows = team._chunk_rows([{"user_prompt_result": "[TEAM_SOURCE:known]", "objects_result": []}])
    assert rows == []
    row = {"text": "[TEAM_SOURCE:known] [TEAM_SOURCE:invented]"}
    assert team._ids_from_row(row, {}, {"known"}) == ["known"]


def test_filename_mapping_retains_source_identity_when_chunk_lacks_marker():
    manifest = {"document_names": {"abc.txt": "vendor:example"}}
    assert team._ids_from_row({"text": "middle chunk", "document_name": "/tmp/abc.txt"}, manifest, {"vendor:example"}) == ["vendor:example"]


def test_source_fingerprint_changes_when_content_changes():
    assert team._source_fingerprint([{"id": "a", "text": "first"}]) != team._source_fingerprint([{"id": "a", "text": "second"}])


def test_unconfigured_status_does_not_import_provider(monkeypatch, tmp_path):
    monkeypatch.setattr(team, "_cloud_enabled", lambda: False)
    monkeypatch.setattr(team, "_runtime_config", lambda: None)
    monkeypatch.setattr(team, "SOURCE_PATH", tmp_path / "missing.json")
    monkeypatch.setattr(team, "MANIFEST_PATH", tmp_path / "manifest.json")
    monkeypatch.setattr(team.importlib.util, "find_spec", lambda _: None)
    status = team.get_status()
    assert status["runtime_mode"] == "local"
    assert status["ready"] is False
    assert status["available"] is False
