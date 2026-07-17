from fastapi.testclient import TestClient

from live_api.app.main import app


def test_healthz():
    with TestClient(app) as client:
        res = client.get("/healthz")
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        assert body["provider"] == "mock"
        assert "OGDC" in body["symbols"]


def test_quotes_returns_all_default_symbols():
    with TestClient(app) as client:
        res = client.get("/api/v1/quotes")
        assert res.status_code == 200
        body = res.json()
        assert body["delayed"] is True
        assert body["provider"] == "mock"
        returned_symbols = {q["symbol"] for q in body["quotes"]}
        assert returned_symbols == {"OGDC", "PPL", "HBL", "ENGRO", "LUCK"}


def test_quotes_respects_symbols_query_param():
    with TestClient(app) as client:
        res = client.get("/api/v1/quotes", params={"symbols": "OGDC,PPL"})
        assert res.status_code == 200
        returned_symbols = {q["symbol"] for q in res.json()["quotes"]}
        assert returned_symbols == {"OGDC", "PPL"}


def test_meta_endpoint():
    with TestClient(app) as client:
        res = client.get("/api/v1/meta")
        assert res.status_code == 200
        body = res.json()
        assert body["provider"] == "mock"
        assert "market_open" in body
        assert isinstance(body["symbols"], list)


def test_admin_refresh_requires_auth():
    with TestClient(app) as client:
        res = client.post("/admin/refresh")
        assert res.status_code == 401


def test_admin_refresh_rejects_bad_token():
    with TestClient(app) as client:
        res = client.post("/admin/refresh", headers={"Authorization": "Bearer wrong-token"})
        assert res.status_code == 401
