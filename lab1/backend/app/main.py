"""Бэкенд «поздравлялки»: /api/greeting с rate limit, LLM и историей."""
import datetime
from typing import Callable

import httpx
from fastapi import FastAPI, HTTPException, Request

from . import dates
from .config import Settings, load_settings
from .history import append_record
from .llm import LLMUnavailable, generate_greeting
from .ratelimit import SlidingWindowRateLimiter


def create_app(settings: Settings | None = None,
               http_transport: httpx.AsyncBaseTransport | None = None,
               today_fn: Callable[[], datetime.date] | None = None) -> FastAPI:
    settings = settings or load_settings()
    limiter = SlidingWindowRateLimiter(settings.rate_limit_rpm)
    get_today = today_fn or (lambda: dates.today(settings.tz))
    app = FastAPI(title="Поздравлялка")

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/api/greeting")
    async def greeting(request: Request) -> dict:
        ip = request.client.host if request.client else "unknown"
        if not limiter.check(ip):
            raise HTTPException(status_code=429,
                                detail="Слишком много запросов — попробуйте позже")
        d = get_today()
        holiday, _seasonal = dates.describe_date(d)
        source = "fallback"
        text: str
        if settings.llm_base_url:
            try:
                text = await generate_greeting(
                    settings.llm_base_url, settings.llm_model,
                    settings.llm_connect_timeout, settings.llm_request_timeout,
                    dates.build_prompt(d), transport=http_transport)
                source = "llm"
            except LLMUnavailable:
                pass
        if source == "fallback":
            text = dates.greeting_phrase(d)
        append_record(settings.data_dir, {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "ip": ip, "date": d.isoformat(), "holiday": holiday,
            "source": source, "greeting": text,
        })
        return {"date": d.isoformat(), "holiday": holiday,
                "greeting": text, "source": source}

    return app


app = create_app()
