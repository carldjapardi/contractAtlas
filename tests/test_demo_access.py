from fastapi.testclient import TestClient

from backend.app import app


def test_hosted_paid_actions_fail_closed_without_configured_code(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("ATLAS_DEMO_ACCESS_CODE", raising=False)
    with TestClient(app) as client:
        assert client.get("/api/access").json() == {"required": True, "authorized": False}
        response = client.post("/api/team/runs", json={"question": "Research identity partners", "profile": "Small cybersecurity contractor"})
        assert response.status_code == 503


def test_access_cookie_authorizes_without_exposing_demo_code(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("ATLAS_DEMO_ACCESS_CODE", "example-private-demo-code")
    with TestClient(app, base_url="https://testserver") as client:
        assert client.post("/api/access", json={"code": "wrong"}).status_code == 401
        response = client.post("/api/access", json={"code": "example-private-demo-code"})
        assert response.status_code == 200
        cookie = response.headers["set-cookie"]
        assert "example-private-demo-code" not in cookie
        assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie
        assert client.get("/api/access").json()["authorized"] is True


def test_invalid_cookie_cannot_unlock_paid_action(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("ATLAS_DEMO_ACCESS_CODE", "example-private-demo-code")
    with TestClient(app, base_url="https://testserver") as client:
        client.cookies.set("atlas_demo_access", "forged")
        assert client.post("/api/query", json={"question": "Find identity work"}).status_code == 401
