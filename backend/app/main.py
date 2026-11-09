"""HTTP API (FastAPI). Запуск: uvicorn app.main:app --reload (из папки backend)."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .bank import (
    figures_dir,
    load_bank,
)
from .config import settings
from .contests import build_contests

log = logging.getLogger("olymp")
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

MAX_BODY_BYTES = 1_000_000


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Слишком большие запросы отклоняем сразу; ответам — стандартные заголовки безопасности."""
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
        return JSONResponse({"detail": "Слишком большой запрос"}, status_code=413)
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    path = request.url.path
    if path.startswith("/api/"):
        resp.headers.setdefault("Cache-Control", "no-store")
    elif path.startswith("/assets/"):
        # В именах собранных файлов есть хэш содержимого — браузер может хранить их хоть год.
        resp.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
    else:
        # index.html и sw.js должны обновляться сразу после выкладки новой версии.
        resp.headers.setdefault("Cache-Control", "no-cache")
    return resp


# Сжатие ответов: список задач ~300 КБ JSON сжимается в несколько раз. Добавляется после
# middleware заголовков, поэтому оборачивает его снаружи и сжимает уже готовый ответ.
app.add_middleware(GZipMiddleware, minimum_size=1000)


# ---------- пользователи ----------
@app.get("/api/health")
def health() -> dict:
    bank = load_bank()
    build_contests(bank)  # прогрев: первый запрос списка олимпиад иначе строит его ~3 с
    return {"ok": True, "problems": len(bank), "app": settings.app_name}


from .common import set_db  # noqa: E402,F401  (нужен тестам)
from .routes import accounts, assistant, olympiads, problems, profile  # noqa: E402

app.include_router(accounts.router)
app.include_router(profile.router)
app.include_router(problems.router)
app.include_router(olympiads.router)
app.include_router(assistant.router)

# ---------- фронтенд (собранный) ----------
_figures = figures_dir()
_figures.mkdir(parents=True, exist_ok=True)
app.mount("/figures", StaticFiles(directory=_figures), name="figures")

_dist = Path(settings.frontend_dist).resolve()
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404, "Нет такого адреса API")
        file = (_dist / path).resolve()
        if path and _dist in file.parents and file.is_file():
            return FileResponse(file)
        return FileResponse(_dist / "index.html")
