import asyncio
import json
import httpx
import pytest
from app.llm import LLMUnavailable, generate_greeting

URL = "http://model:8080/v1"


def _handler(content: str):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        body = json.loads(request.content)
        assert body["model"] == "qwen3-1.7b"
        assert any(m["role"] == "system" for m in body["messages"])
        return httpx.Response(200, json={"choices": [
            {"message": {"role": "assistant", "content": content}}]})
    return handler


def test_returns_content_and_strips_think():
    h = _handler("  <think>размышления</think>\nТёплое поздравление!  ")
    out = asyncio.run(generate_greeting(URL, "qwen3-1.7b", 2.0, 30.0, "привет",
                                        transport=httpx.MockTransport(h)))
    assert out == "Тёплое поздравление!"


def test_connect_error_raises_unavailable():
    def handler(request):
        raise httpx.ConnectError("нет модели")
    with pytest.raises(LLMUnavailable):
        asyncio.run(generate_greeting(URL, "qwen3-1.7b", 2.0, 30.0, "привет",
                                      transport=httpx.MockTransport(handler)))


def test_http_500_raises_unavailable():
    with pytest.raises(LLMUnavailable):
        asyncio.run(generate_greeting(
            URL, "qwen3-1.7b", 2.0, 30.0, "привет",
            transport=httpx.MockTransport(lambda r: httpx.Response(500))))


def test_empty_content_raises_unavailable():
    with pytest.raises(LLMUnavailable):
        asyncio.run(generate_greeting(
            URL, "qwen3-1.7b", 2.0, 30.0, "привет",
            transport=httpx.MockTransport(_handler(""))))


def test_non_json_200_raises_unavailable():
    # 200 с HTML-мусором (например, страница авторизации прокси) — не 500, а fallback
    with pytest.raises(LLMUnavailable):
        asyncio.run(generate_greeting(
            URL, "qwen3-1.7b", 2.0, 30.0, "привет",
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, text="<html>proxy auth</html>"))))
