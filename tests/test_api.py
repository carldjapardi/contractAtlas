from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_health_does_not_expose_configuration_values():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert set(response.json()) == {"status", "cognee"}
    assert set(response.json()["cognee"]) >= {"available", "ready", "reason"}


def test_reject_invalid_queries_and_bounds():
    for payload in [
        {"question": "   "},
        {"question": "hello", "mode": "invented"},
        {"question": "x" * 1501},
    ]:
        assert client.post("/api/query", json=payload).status_code == 422
    assert client.get("/api/graph?limit=10000").status_code == 422
    assert client.get("/api/awards?limit=-1").status_code == 422


def test_unavailable_cognee_is_explicit(monkeypatch):
    from backend import cognee_adapter

    async def unavailable(question):
        raise cognee_adapter.CogneeUnavailable("Cognee index is not ready.")

    monkeypatch.setattr(cognee_adapter, "query", unavailable)
    response = client.post("/api/query", json={"question": "Find awards", "mode": "cognee"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Cognee index is not ready."


def test_provider_error_details_are_redacted(monkeypatch):
    from backend import cognee_adapter

    async def broken(question):
        raise RuntimeError("secret-provider-credential")

    monkeypatch.setattr(cognee_adapter, "query", broken)
    response = client.post("/api/query", json={"question": "Find awards", "mode": "cognee"})
    assert response.status_code == 502
    assert "secret-provider-credential" not in response.text


def test_unknown_api_route_is_not_spa_html():
    assert client.get("/api/unknown").status_code == 404
