import importlib

import pytest


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "test-chat")
    monkeypatch.setenv("WEBHOOK_SECRET", "test-secret")
    import app
    importlib.reload(app)
    app.app.config["TESTING"] = True
    return app.app.test_client()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["configured"] is True


def test_missing_secret_rejected(client):
    response = client.post("/webhook", json={"signal": "BUY"})
    assert response.status_code == 401


def test_invalid_secret_rejected(client):
    response = client.post(
        "/webhook", json={"signal": "BUY"}, headers={"X-Webhook-Secret": "wrong"}
    )
    assert response.status_code == 401


def test_non_json_rejected(client):
    response = client.post(
        "/webhook", data="bad", headers={"X-Webhook-Secret": "test-secret"}
    )
    assert response.status_code == 415


def test_valid_signal_sends_telegram(client, monkeypatch):
    import app

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"ok": True}

    captured = {}

    def fake_post(url, json, timeout):
        captured.update(url=url, payload=json, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(app.requests, "post", fake_post)
    response = client.post(
        "/webhook",
        json={"signal": "BUY", "symbol": "XAUUSD", "entry": "4000"},
        headers={"X-Webhook-Secret": "test-secret"},
    )
    assert response.status_code == 200
    assert "SIGNAL: BUY" in captured["payload"]["text"]
    assert captured["timeout"] == 10


def test_telegram_failure_returns_error(client, monkeypatch, caplog):
    import app
    import requests

    def fail(*args, **kwargs):
        raise requests.Timeout("https://api.telegram.org/bottest-token/sendMessage")

    monkeypatch.setattr(app.requests, "post", fail)
    response = client.post(
        "/webhook", json={"signal": "BUY"}, headers={"X-Webhook-Secret": "test-secret"}
    )
    assert response.status_code == 502

    assert "Telegram delivery failed" in caplog.text
    assert "test-token" not in caplog.text
