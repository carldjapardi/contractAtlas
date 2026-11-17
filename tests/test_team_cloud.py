import asyncio
import json

import httpx
import pytest

from backend import team_cloud as cloud
from backend import team_memory as team


def test_lesson_identity_does_not_depend_on_retrieval_order():
    first = "# Session learning (session a)\n\nValidate award scope before claiming fit. (Reviewed evidence.)"
    second = "# Session learning (session b)\n\nKeep vendor claims separate. (Accepted review.)"
    forward = {item["id"] for item in cloud.lesson_excerpts(first + "\n\n" + second)}
    reverse = {item["id"] for item in cloud.lesson_excerpts(second + "\n\n" + first)}
    assert forward == reverse
    assert len(forward) == 2


def test_unknown_lesson_format_does_not_count_as_learning():
    assert cloud.lesson_excerpts("The model says it remembered a lesson") == []


def test_cloud_config_rejects_non_cognee_destinations(monkeypatch):
    monkeypatch.setattr(cloud, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("COGNEE_API_KEY", "unit-test-key")
    monkeypatch.setenv("COGNEE_SERVICE_URL", "https://elsewhere.example")
    with pytest.raises(team.TeamMemoryUnavailable):
        cloud.config()


def test_cloud_provider_error_body_never_escapes(monkeypatch):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(cloud, "config", lambda: ("https://test.cognee.ai", "unit-test-key"))
    transport = httpx.MockTransport(lambda req: httpx.Response(400, json={"error": "private-provider-body"}))
    monkeypatch.setattr(cloud.httpx, "AsyncClient", lambda **kwargs: real_client(transport=transport, **kwargs))
    with pytest.raises(team.TeamMemoryUnavailable) as exc:
        asyncio.run(cloud.request("POST", "/api/v1/recall", json={"query": "test"}))
    assert "HTTP 400" in str(exc.value)
    assert "private-provider-body" not in str(exc.value)


def test_ingestion_poll_accepts_native_status_shape_without_wrong_pipeline_filter(monkeypatch):
    async def completed(method, path, **kwargs):
        assert "pipeline" not in kwargs["params"]
        return {"dataset-id": {"status": "DATASET_PROCESSING_COMPLETED", "reason": None, "error": None}}
    monkeypatch.setattr(cloud, "request", completed)
    asyncio.run(cloud._wait_ingestion("dataset-id"))


def test_ingestion_failure_is_explicit(monkeypatch):
    async def failed(*args, **kwargs):
        return {"dataset-id": {"status": "DATASET_PROCESSING_ERRORED"}}
    monkeypatch.setattr(cloud, "request", failed)
    with pytest.raises(team.TeamMemoryUnavailable):
        asyncio.run(cloud._wait_ingestion("dataset-id"))


def test_source_retrieval_ignores_session_echoes_and_unknown_markers(monkeypatch):
    async def recalled(method, path, **kwargs):
        assert kwargs["json"]["nodeName"] == ["team_sources"]
        return [{"source": "session", "text": "[TEAM_SOURCE:known]"},
                {"source": "graph", "text": "[TEAM_SOURCE:known] Actual record. [TEAM_SOURCE:unknown]"}]
    monkeypatch.setattr(cloud, "request", recalled)
    monkeypatch.setattr(team, "_sources", lambda: [{"id": "known"}])
    text, ids, lessons = asyncio.run(cloud._retrieve("question", {"dataset_name": "test"}))
    assert ids == ["known"]
    assert lessons == []
    assert "Actual record" in text


def test_tenant_operation_lock_releases_after_exception(monkeypatch, tmp_path):
    monkeypatch.setattr(cloud, "MANIFEST", tmp_path / "manifest.json")
    assert cloud.is_busy() is False
    with pytest.raises(ValueError):
        with cloud.operation():
            assert cloud.is_busy() is True
            raise ValueError("simulated failure")
    assert cloud.is_busy() is False
