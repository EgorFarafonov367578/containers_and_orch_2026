import datetime
import json
import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def _settings(**kw) -> Settings:
    base = dict(llm_base_url=None, llm_model="qwen3-1.7b",
                llm_connect_timeout=2.0, llm_request_timeout=30.0,
                rate_limit_rpm=5, data_dir="/tmp/test-greetings-data")
    base.update(kw)
    return Settings(**base)


def test_healthz(tmp_path):
    client = TestClient(create_app(_settings(data_dir=str(tmp_path))))
    assert client.get("/healthz").json() == {"status": "ok"}


def test_greeting_fallback(tmp_path):
    client = TestClient(create_app(_settings(data_dir=str(tmp_path))))
    r = client.get("/api/greeting")
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "fallback" and body["holiday"] is None
    assert body["greeting"] and body["date"]


def test_greeting_on_holiday(tmp_path):
    app = create_app(_settings(data_dir=str(tmp_path)),
                     today_fn=lambda: datetime.date(2027, 1, 1))
    body = TestClient(app).get("/api/greeting").json()
    assert body["holiday"] == "Новый год"


def test_rate_limit(tmp_path):
    client = TestClient(create_app(_settings(rate_limit_rpm=1,
                                             data_dir=str(tmp_path))))
    assert client.get("/api/greeting").status_code == 200
    assert client.get("/api/greeting").status_code == 429


def test_llm_path(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {
            "role": "assistant", "content": "С праздником, друг!"}}]})
    app = create_app(_settings(llm_base_url="http://model:8080/v1",
                               data_dir=str(tmp_path)),
                     http_transport=httpx.MockTransport(handler))
    body = TestClient(app).get("/api/greeting").json()
    assert body["source"] == "llm" and body["greeting"] == "С праздником, друг!"


def test_llm_down_falls_back(tmp_path):
    def handler(request):
        raise httpx.ConnectError("нет модели")
    app = create_app(_settings(llm_base_url="http://model:8080/v1",
                               data_dir=str(tmp_path)),
                     http_transport=httpx.MockTransport(handler))
    body = TestClient(app).get("/api/greeting").json()
    assert body["source"] == "fallback"


def test_history_written(tmp_path):
    client = TestClient(create_app(_settings(data_dir=str(tmp_path))))
    client.get("/api/greeting")
    line = json.loads((tmp_path / "history.jsonl").read_text().splitlines()[0])
    assert "greeting" in line and line["source"] == "fallback"


def test_api_alive_when_data_dir_unwritable(tmp_path):
    blocker = tmp_path / "занят"
    blocker.write_text("файл вместо каталога")
    client = TestClient(create_app(_settings(data_dir=str(blocker))))
    assert client.get("/api/greeting").status_code == 200
