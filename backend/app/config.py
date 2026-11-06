"""Настройки приложения из переменных окружения."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Минимальная загрузка backend/.env (без внешних зависимостей)."""
    env_file = BACKEND_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

DEFAULT_CHAIN = ",".join(
    [
        "gemini:gemini-3.5-flash",
        "gemini:gemini-3.8-flash",
        "gemini:gemini-flash-latest",
        "gemini:gemini-3.5-flash-lite",
        "openrouter:nvidia/nemotron-3-ultra-550b-a55b:free",
        "openrouter:google/gemma-4-31b-it:free",
    ]
)

# Для перекрёстной проверки берём модели другого производителя первыми.
DEFAULT_CROSSCHECK_CHAIN = ",".join(
    [
        "openrouter:nvidia/nemotron-3-ultra-550b-a55b:free",
        "gemini:gemini-3.8-flash",
        "openrouter:google/gemma-4-31b-it:free",
    ]
)


@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "Olymp Trainer")
    data_dir: str = os.getenv("DATA_DIR", str(BACKEND_DIR / "data"))
    db_path: str = os.getenv("DB_PATH", str(BACKEND_DIR / "data" / "app.db"))
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or None
    openrouter_api_key: str | None = os.getenv("OPENROUTER_API_KEY") or None
    llm_chain: list[str] = field(default_factory=lambda: os.getenv("LLM_CHAIN", DEFAULT_CHAIN).split(","))
    crosscheck_chain: list[str] = field(
        default_factory=lambda: os.getenv("CROSSCHECK_CHAIN", DEFAULT_CROSSCHECK_CHAIN).split(",")
    )
    llm_timeout_s: float = float(os.getenv("LLM_TIMEOUT_S", "90"))
    cors_origins: list[str] = field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    )
    frontend_dist: str = os.getenv("FRONTEND_DIST", str(BACKEND_DIR.parent / "frontend" / "dist"))
    # За обратным прокси (Render и т. п.) включить, чтобы IP брался из X-Forwarded-For.
    trust_proxy: bool = os.getenv("TRUST_PROXY", "").lower() in ("1", "true", "yes")
    # Сколько запросов к ИИ (чат + проверка решений) всего за день на весь сервер — защита бюджета.
    ai_global_daily_limit: int = int(os.getenv("AI_GLOBAL_DAILY_LIMIT", "3000"))
    # Сколько новых аккаунтов в час с одного IP (у школы может быть один IP на класс).
    signups_per_ip_hour: int = int(os.getenv("SIGNUPS_PER_IP_HOUR", "40"))
    session_days: int = int(os.getenv("SESSION_DAYS", "180"))
    # Sonnet в чате — только для трудных задач, когда Haiku не справляется. Он в ~20 раз дороже.
    strong_per_user_daily: int = int(os.getenv("STRONG_PER_USER_DAILY", "5"))
    strong_global_daily: int = int(os.getenv("STRONG_GLOBAL_DAILY", "150"))


settings = Settings()
