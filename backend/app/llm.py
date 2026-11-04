"""Слой работы с языковыми моделями.

Цепочка провайдеров (LLM_CHAIN): если модель перегружена (429/503) или
недоступна, запрос автоматически уходит следующей. Сейчас поддерживаются
Gemini (Google AI Studio) и OpenRouter (открытые модели: Nemotron, Gemma и др.).

Ключи берутся из GEMINI_API_KEY / OPENROUTER_API_KEY. Если ключа нет,
запрос всё равно отправляется: в облачном окружении ключ подставляет прокси.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from dataclasses import dataclass

import httpx

from .config import settings

log = logging.getLogger("llm")

RETRYABLE = {408, 429, 500, 502, 503, 504}
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMError(RuntimeError):
    pass


@dataclass
class Image:
    data: bytes
    mime: str = "image/jpeg"


@dataclass
class LLMResult:
    text: str
    model: str  # "provider:model"


def _gemini_request(model: str, system: str, prompt: str, json_mode: bool, image: Image | None):
    parts: list[dict] = [{"text": prompt}]
    if image:
        parts.append(
            {"inline_data": {"mime_type": image.mime, "data": base64.b64encode(image.data).decode()}}
        )
    body: dict = {
        "contents": [{"role": "user", "parts": parts}],
        "systemInstruction": {"parts": [{"text": system}]},
        "generationConfig": {"temperature": 0.4},
    }
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"
    headers = {"Content-Type": "application/json"}
    if settings.gemini_api_key:
        headers["x-goog-api-key"] = settings.gemini_api_key
    return GEMINI_URL.format(model=model), headers, body


def _gemini_text(data: dict) -> str:
    cands = data.get("candidates") or []
    if not cands:
        raise LLMError(f"Пустой ответ Gemini: {str(data)[:200]}")
    parts = cands[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    if not text.strip():
        raise LLMError("Gemini вернул пустой текст")
    return text


def _openrouter_request(model: str, system: str, prompt: str, json_mode: bool, image: Image | None):
    content: list[dict] | str = prompt
    if image:
        b64 = base64.b64encode(image.data).decode()
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{image.mime};base64,{b64}"}},
        ]
    body = {
        "model": model,
        "temperature": 0.4,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
    }
    headers = {"Content-Type": "application/json", "X-Title": settings.app_name}
    if settings.openrouter_api_key:
        headers["Authorization"] = f"Bearer {settings.openrouter_api_key}"
    return OPENROUTER_URL, headers, body


def _openrouter_text(data: dict) -> str:
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"Неожиданный ответ OpenRouter: {str(data)[:200]}") from exc
    if not text or not text.strip():
        raise LLMError("OpenRouter вернул пустой текст")
    return text


async def _anthropic_complete(model: str, system: str, prompt: str, image: Image | None) -> str:
    """Claude через официальный SDK. PDF и картинки передаются блоками document/image."""
    import anthropic

    content: list[dict] = []
    if image:
        b64 = base64.b64encode(image.data).decode()
        kind = "document" if image.mime == "application/pdf" else "image"
        content.append({"type": kind, "source": {"type": "base64", "media_type": image.mime, "data": b64}})
    content.append({"type": "text", "text": prompt})
    client = anthropic.AsyncAnthropic(timeout=settings.llm_timeout_s * 4, max_retries=2)
    try:
        async with client.messages.stream(
            model=model,
            max_tokens=32000,
            system=system,
            messages=[{"role": "user", "content": content}],
        ) as stream:
            message = await stream.get_final_message()
    except anthropic.RateLimitError as exc:
        raise LLMError("Claude: превышен лимит запросов") from exc
    except anthropic.AuthenticationError as exc:
        raise LLMError("Claude: нет или неверный ANTHROPIC_API_KEY") from exc
    except anthropic.APIStatusError as exc:
        raise LLMError(f"Claude: HTTP {exc.status_code}") from exc
    except anthropic.APIConnectionError as exc:
        raise LLMError("Claude: нет соединения") from exc
    if message.stop_reason == "refusal":
        raise LLMError("Claude отказался отвечать на запрос")
    text = "".join(b.text for b in message.content if b.type == "text")
    if not text.strip():
        raise LLMError("Claude вернул пустой текст")
    return text


_PROVIDERS = {
    "gemini": (_gemini_request, _gemini_text),
    "openrouter": (_openrouter_request, _openrouter_text),
}


async def complete(
    prompt: str,
    system: str = "Ты помощник для подготовки школьников к олимпиадам.",
    *,
    json_mode: bool = False,
    image: Image | None = None,
    chain: list[str] | None = None,
    client: httpx.AsyncClient | None = None,
) -> LLMResult:
    """Отправить запрос первой доступной модели из цепочки."""
    chain = chain or settings.llm_chain
    errors: list[str] = []
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=settings.llm_timeout_s)
    try:
        for entry in chain:
            provider, _, model = entry.strip().partition(":")
            if provider == "anthropic":
                try:
                    return LLMResult(await _anthropic_complete(model, system, prompt, image), entry)
                except LLMError as exc:
                    errors.append(f"{entry}: {exc}")
                    log.warning("LLM %s недоступна (%s), пробую следующую", entry, exc)
                    continue
            if provider not in _PROVIDERS:
                errors.append(f"{entry}: неизвестный провайдер")
                continue
            build, parse = _PROVIDERS[provider]
            url, headers, body = build(model, system, prompt, json_mode, image)
            for attempt in range(2):
                try:
                    resp = await client.post(url, headers=headers, json=body)
                except httpx.HTTPError as exc:
                    errors.append(f"{entry}: {type(exc).__name__}")
                    break
                if resp.status_code == 200:
                    try:
                        return LLMResult(text=parse(resp.json()), model=entry)
                    except (LLMError, ValueError) as exc:
                        errors.append(f"{entry}: {exc}")
                        break
                errors.append(f"{entry}: HTTP {resp.status_code}")
                if resp.status_code in RETRYABLE and attempt == 0:
                    await asyncio.sleep(1.0)
                    continue
                break
            log.warning("LLM %s недоступна (%s), пробую следующую", entry, errors[-1] if errors else "?")
    finally:
        if own_client:
            await client.aclose()
    raise LLMError("Все модели недоступны: " + "; ".join(errors))


def extract_json(text: str) -> dict:
    """Достать JSON-объект из ответа модели (с ```json ... ``` или без)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else text
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end == -1:
        raise LLMError("В ответе модели нет JSON")
    try:
        return json.loads(candidate[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"Модель вернула некорректный JSON: {exc}") from exc


async def complete_json(prompt: str, system: str, **kwargs) -> tuple[dict, str]:
    """Запрос с ответом в JSON. Если модель ответила мусором — пробуем следующую."""
    remaining = [c.strip() for c in (kwargs.pop("chain", None) or settings.llm_chain)]
    last: Exception = LLMError("Пустая цепочка моделей")
    while remaining:
        res = await complete(prompt, system, json_mode=True, chain=remaining, **kwargs)
        try:
            return extract_json(res.text), res.model
        except LLMError as exc:
            last = exc
            remaining = remaining[remaining.index(res.model) + 1 :]
    raise LLMError(str(last))
