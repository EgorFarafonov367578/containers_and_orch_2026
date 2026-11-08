"""Env-контракт бэкенда. Все параметры — переменные окружения."""
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    llm_base_url: str | None  # корень OpenAI API вместе с /v1; None → fallback-режим
    llm_model: str
    llm_connect_timeout: float
    llm_request_timeout: float
    rate_limit_rpm: int
    data_dir: str


def _env(name: str, default: str) -> str:
    """Пустая строка считается «не задано»."""
    value = os.environ.get(name, "").strip()
    return value if value else default


def load_settings() -> Settings:
    base_url = os.environ.get("LLM_BASE_URL", "").strip() or None
    return Settings(
        llm_base_url=base_url,
        llm_model=_env("LLM_MODEL", "qwen3-1.7b"),
        llm_connect_timeout=float(_env("LLM_CONNECT_TIMEOUT", "2.0")),
        llm_request_timeout=float(_env("LLM_REQUEST_TIMEOUT", "30.0")),
        rate_limit_rpm=int(_env("RATE_LIMIT_RPM", "5")),
        data_dir=_env("DATA_DIR", "/data"),
    )
