import asyncio
import json

import pytest

from scripts import evaluate


@pytest.fixture
def evaluation_context(monkeypatch, tmp_path):
    root = tmp_path / "project"
    (root / "data").mkdir(parents=True)
    (root / "data/evaluation_cases.json").write_text(json.dumps({
        "description": "Exploratory checks", "cases": [{
            "id": "lookup", "category": "structured", "question": "Find award A123",
            "expected_award_ids": ["A123"],
        }],
    }))
    snapshot = {"metadata": {"snapshot_id": "current"}, "awards": [{"id": "record-1", "award_id": "A123"}]}
    monkeypatch.setattr(evaluate, "ROOT", root)
    monkeypatch.setattr(evaluate.data, "load_snapshot", lambda: snapshot)
    index = tmp_path / "index.json"
    monkeypatch.setattr(evaluate.cognee_adapter, "INDEX_PATH", index)
    return snapshot, index


def test_partial_corpus_never_produces_comparison_metrics(evaluation_context, monkeypatch):
    _, index = evaluation_context
    index.write_text(json.dumps({"state": "ready", "snapshot_id": "current", "award_ids": []}))

    async def forbidden(question):
        raise AssertionError("Provider must not be called for an incomparable corpus")

    monkeypatch.setattr(evaluate.cognee_adapter, "query", forbidden)
    result = asyncio.run(evaluate.run(["cognee"]))
    assert result["corpus_comparable"] is False
    assert result["summary"][0]["completed"] == 0
    assert result["summary"][0]["mean_recall"] is None
    assert result["cases"][0]["results"][0]["status"] == "unavailable"


def test_missing_anchor_is_skipped_instead_of_scored(evaluation_context, monkeypatch):
    snapshot, _ = evaluation_context
    snapshot["awards"][0]["award_id"] = "DIFFERENT"

    def forbidden(question):
        raise AssertionError("Unavailable expected source must be skipped")

    monkeypatch.setattr(evaluate.baseline, "query", forbidden)
    result = asyncio.run(evaluate.run(["baseline"]))
    assert result["cases"][0]["results"][0]["status"] == "skipped"
    assert result["summary"][0]["mean_recall"] is None


def test_provider_failure_is_not_written_into_results(evaluation_context, monkeypatch):
    _, index = evaluation_context
    index.write_text(json.dumps({"state": "ready", "snapshot_id": "current", "award_ids": ["record-1"]}))

    async def broken(question):
        raise RuntimeError("credential-bearing-provider-exception")

    monkeypatch.setattr(evaluate.cognee_adapter, "query", broken)
    result = asyncio.run(evaluate.run(["cognee"]))
    assert result["cases"][0]["results"][0]["status"] == "error"
    assert "credential-bearing" not in json.dumps(result)


def test_empty_snapshot_cannot_be_evaluated(evaluation_context):
    snapshot, _ = evaluation_context
    snapshot["awards"] = []
    with pytest.raises(ValueError, match="real snapshot"):
        asyncio.run(evaluate.run(["baseline"]))
