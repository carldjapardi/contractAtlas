"""Provider-independent checks for evidence integrity and safe configuration."""

from types import SimpleNamespace
import asyncio
import sys
from unittest.mock import AsyncMock

import pytest

from backend import cognee_adapter as adapter


@pytest.fixture(autouse=True)
def isolated_index(monkeypatch, tmp_path):
    # Tests must never attach to the application's live index or CLI lock.
    monkeypatch.setattr(adapter, "INDEX_PATH", tmp_path / "index.json")


def award(id="award-1"):
    return {
        "id": id, "award_id": "A123", "description": "Identity access management.",
        "agency": "DHS", "sub_agency": None, "recipient_name": "Example Corp",
        "recipient_uei": "UEI123", "parent_name": None, "parent_uei": None,
        "obligation": 10.0, "source_url": "https://www.usaspending.gov/award/A123",
    }


def test_evidence_must_come_from_retrieved_chunks_not_question_or_completion():
    marker = f"[ATLAS_RECORD:{adapter.record_marker('award-1')}]"
    result = [{"user_prompt_result": marker, "text_result": marker, "context_result": marker,
               "objects_result": {"chunks": []}}]
    assert adapter._matched_awards(result, [award()], {"award-1"}) == []


def test_only_known_indexed_sources_are_accepted_and_deduplicated():
    first = adapter.award_document(award())
    excluded = adapter.award_document(award("award-2"))
    unknown = "[ATLAS_RECORD:aaaaaaaaaaaaaaaaaaaaaaaa]"
    result = [{"objects_result": {"chunks": [
        {"payload": {"text": first + excluded + unknown}},
        SimpleNamespace(payload={"text": first}),
    ]}}]
    assert [x["id"] for x in adapter._matched_awards(result, [award(), award("award-2")], {"award-1"})] == ["award-1"]


def test_unknown_result_shapes_fail_closed():
    assert adapter._chunk_texts("model-generated narrative") == []
    assert adapter._chunk_texts([{"objects_result": "unrecognized"}]) == []


def test_document_preserves_source_id_and_financial_semantics():
    document = adapter.award_document(award())
    assert document.count(f"[ATLAS_RECORD:{adapter.record_marker('award-1')}]") == 2
    assert "not fiscal-year-only spending or cash paid" in document
    assert "not reported" in document


def test_openai_alias_is_supported_without_overwriting_explicit_provider_key(monkeypatch):
    monkeypatch.setattr(adapter, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("OPENAI", "alias-test-value")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    adapter.configure_environment()
    assert adapter.os.getenv("LLM_API_KEY") == "alias-test-value"
    monkeypatch.setenv("LLM_API_KEY", "explicit-test-value")
    adapter.configure_environment()
    assert adapter.os.getenv("LLM_API_KEY") == "explicit-test-value"


def test_status_without_package_does_not_import_cognee(monkeypatch):
    monkeypatch.setattr(adapter, "configure_environment", lambda: None)
    monkeypatch.setattr(adapter.importlib.util, "find_spec", lambda _: None)
    assert adapter.get_status()["available"] is False


def test_query_sanitizes_provider_failure(monkeypatch):
    from backend import data

    monkeypatch.setattr(adapter, "get_status", lambda: {"ready": True})
    monkeypatch.setattr(adapter, "_read_manifest", lambda: {
        "snapshot_id": "snapshot-1", "award_ids": ["award-1"], "dataset_name": "test",
    })
    monkeypatch.setattr(data, "load_snapshot", lambda: {
        "metadata": {"snapshot_id": "snapshot-1"}, "awards": [award()],
    })
    fake = SimpleNamespace(
        SearchType=SimpleNamespace(HYBRID_COMPLETION="HYBRID_COMPLETION"),
        search=AsyncMock(side_effect=RuntimeError("provider secret must not escape")),
    )
    monkeypatch.setitem(sys.modules, "cognee", fake)
    with pytest.raises(adapter.CogneeUnavailable) as exc:
        asyncio.run(adapter.query("find cybersecurity awards"))
    assert "secret" not in str(exc.value)
    assert "configuration" in str(exc.value)


def test_status_rejects_a_stale_index(monkeypatch):
    from backend import data

    monkeypatch.setattr(adapter, "configure_environment", lambda: None)
    monkeypatch.setattr(adapter.importlib.util, "find_spec", lambda _: object())
    monkeypatch.setenv("LLM_API_KEY", "test-value")
    monkeypatch.setattr(data, "load_snapshot", lambda: {
        "metadata": {"snapshot_id": "current"}, "awards": [award()],
    })
    monkeypatch.setattr(adapter, "_read_manifest", lambda: {
        "state": "ready", "snapshot_id": "old", "award_ids": ["award-1"],
    })
    status = adapter.get_status()
    assert status["available"] is True
    assert status["ready"] is False
    assert "snapshot changed" in status["reason"]


def test_store_lock_blocks_queries_during_index_and_releases_on_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(adapter, "INDEX_PATH", tmp_path / "index.json")
    assert adapter._index_is_busy() is False
    with pytest.raises(RuntimeError, match="test interruption"):
        with adapter._store_lock(exclusive=True):
            assert adapter._index_is_busy() is True
            with pytest.raises(adapter.CogneeUnavailable):
                with adapter._store_lock(exclusive=False):
                    pass
            raise RuntimeError("test interruption")
    assert adapter._index_is_busy() is False


def test_index_metadata_contains_coverage_without_provider_settings(monkeypatch):
    monkeypatch.setattr(adapter, "_read_manifest", lambda: {
        "state": "ready", "snapshot_id": "s1", "award_ids": ["a1"],
        "LLM_API_KEY": "must-never-return", "cognee_version": "1.6.8",
    })
    metadata = adapter.get_index_metadata()
    assert metadata["award_count"] == 1
    assert metadata["award_ids"] == ["a1"]
    assert "LLM_API_KEY" not in metadata
