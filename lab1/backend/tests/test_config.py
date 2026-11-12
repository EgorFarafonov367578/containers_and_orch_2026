import os
from app.config import load_settings


def test_defaults(monkeypatch):
    for var in ("LLM_BASE_URL", "LLM_MODEL", "LLM_CONNECT_TIMEOUT",
                "LLM_REQUEST_TIMEOUT", "RATE_LIMIT_RPM", "DATA_DIR", "APP_TZ"):
        monkeypatch.delenv(var, raising=False)
    s = load_settings()
    assert s.llm_base_url is None
    assert s.llm_model == "qwen3-1.7b"
    assert s.llm_connect_timeout == 2.0
    assert s.llm_request_timeout == 30.0
    assert s.rate_limit_rpm == 5
    assert s.data_dir == "/data"
    assert s.tz == "Europe/Moscow"


def test_env_override(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://model:8080/v1")
    monkeypatch.setenv("RATE_LIMIT_RPM", "3")
    monkeypatch.setenv("DATA_DIR", "/tmp/x")
    s = load_settings()
    assert s.llm_base_url == "http://model:8080/v1"
    assert s.rate_limit_rpm == 3
    assert s.data_dir == "/tmp/x"


def test_empty_base_url_means_disabled(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "")
    assert load_settings().llm_base_url is None
