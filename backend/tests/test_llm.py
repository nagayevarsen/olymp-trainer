"""Цепочка моделей: при перегрузке одной запрос уходит следующей. Сеть не используется."""

import asyncio

import httpx
import pytest

from app.llm import LLMError, complete, complete_json, extract_json


def run(coro):
    return asyncio.run(coro)


def gemini_ok(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def openrouter_ok(text):
    return {"choices": [{"message": {"content": text}}]}


def client_with(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_first_model_answers(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _nosleep)
    calls = []

    def handler(req):
        calls.append(str(req.url))
        return httpx.Response(200, json=gemini_ok("42"))

    res = run(complete("q", chain=["gemini:m1", "openrouter:m2"], client=client_with(handler)))
    assert res.text == "42" and res.model == "gemini:m1" and len(calls) == 1


def test_fallback_on_overload(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _nosleep)

    def handler(req):
        if "googleapis" in str(req.url):
            return httpx.Response(503, json={"error": "busy"})
        return httpx.Response(200, json=openrouter_ok("ok"))

    res = run(complete("q", chain=["gemini:m1", "openrouter:m2"], client=client_with(handler)))
    assert res.model == "openrouter:m2"


def test_all_fail(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _nosleep)
    handler = lambda req: httpx.Response(429)  # noqa: E731
    with pytest.raises(LLMError):
        run(complete("q", chain=["gemini:a", "openrouter:b"], client=client_with(handler)))


def test_json_fallback_on_garbage(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _nosleep)

    def handler(req):
        if "googleapis" in str(req.url):
            return httpx.Response(200, json=gemini_ok("не json"))
        return httpx.Response(200, json=openrouter_ok('```json\n{"a": 1}\n```'))

    data, model = run(
        complete_json("q", "s", chain=["gemini:a", "openrouter:b"], client=client_with(handler))
    )
    assert data == {"a": 1} and model == "openrouter:b"


def test_extract_json():
    assert extract_json('Вот ответ: {"x": [1, 2]} готово') == {"x": [1, 2]}
    with pytest.raises(LLMError):
        extract_json("нет json")


async def _nosleep(_):
    return None
