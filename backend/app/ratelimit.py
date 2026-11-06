"""Ограничение частоты запросов (в памяти процесса).

Защищает от подбора паролей, массового создания аккаунтов, перебора ответов и от того, чтобы
кто-то потратил весь бюджет на ИИ. Окно «скользящее»: считаются события за последние window_s секунд.
Состояние живёт в памяти одного процесса — для одного сервера этого достаточно.
"""

from __future__ import annotations

import threading
import time
from collections import deque

from fastapi import HTTPException, Request

from .config import settings

_lock = threading.Lock()
_events: dict[tuple[str, str], deque[float]] = {}
_MAX_KEYS = 100_000


def _prune(now: float) -> None:
    """Если ключей слишком много — выбросить те, где все события давно прошли."""
    if len(_events) < _MAX_KEYS:
        return
    for k in [k for k, q in _events.items() if not q or now - q[-1] > 86_400]:
        del _events[k]


def allow(bucket: str, key: str, limit: int, window_s: float, *, count: bool = True) -> bool:
    """Можно ли ещё одно событие. count=False — только проверить, не засчитывая."""
    now = time.monotonic()
    with _lock:
        _prune(now)
        q = _events.setdefault((bucket, key), deque())
        while q and now - q[0] > window_s:
            q.popleft()
        if len(q) >= limit:
            return False
        if count:
            q.append(now)
        return True


def hit(bucket: str, key: str) -> None:
    """Засчитать событие без проверки (например, неудачный вход)."""
    with _lock:
        _events.setdefault((bucket, key), deque()).append(time.monotonic())


def enforce(bucket: str, key: str, limit: int, window_s: float, message: str) -> None:
    if not allow(bucket, key, limit, window_s):
        raise HTTPException(429, message)


def reset() -> None:
    """Для тестов."""
    with _lock:
        _events.clear()


def client_ip(request: Request) -> str:
    """IP клиента. За прокси (Render и т. п.) — последний адрес из X-Forwarded-For, который добавил
    сам прокси; первые адреса клиент может подделать. Без TRUST_PROXY заголовок игнорируется."""
    if settings.trust_proxy:
        fwd = request.headers.get("x-forwarded-for", "")
        parts = [p.strip() for p in fwd.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return request.client.host if request.client else "unknown"
