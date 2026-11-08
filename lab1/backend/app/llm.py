"""Клиент OpenAI-совместимого API модели (llama.cpp llama-server).

LLM_BASE_URL — корень API вместе с /v1 (например http://greetings-model:8080/v1),
клиент дописывает только /chat/completions. Любая ошибка → LLMUnavailable,
вызывающий код отдаёт fallback-поздравление.
"""
import re
import httpx

SYSTEM_PROMPT = ("Ты — дружелюбный ассистент, который пишет короткие "
                 "поздравления на русском языке (1–3 предложения), "
                 "без markdown и без вступлений.")

_THINK_RE = re.compile(r"<think>.*?</think>", re.S)


class LLMUnavailable(Exception):
    """Модель недоступна или вернула пустой/битый ответ."""


def _clean(content: str) -> str:
    # Qwen3 может прислать блок размышлений даже с --reasoning off
    return _THINK_RE.sub("", content).strip()


async def generate_greeting(base_url: str, model: str, connect_timeout: float,
                            request_timeout: float, prompt: str,
                            transport: httpx.AsyncBaseTransport | None = None) -> str:
    timeout = httpx.Timeout(connect=connect_timeout, read=request_timeout,
                            write=10.0, pool=connect_timeout)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.8,
        "max_tokens": 200,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
            response = await client.post(f"{base_url}/chat/completions", json=payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise LLMUnavailable(f"модель недоступна: {exc}") from exc
    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        # ValueError покрывает json.JSONDecodeError — 200 с битым/HTML-телом
        raise LLMUnavailable("неожиданный формат ответа модели") from exc
    cleaned = _clean(content or "")
    if not cleaned:
        raise LLMUnavailable("модель вернула пустой ответ")
    return cleaned
