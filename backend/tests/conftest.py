import pytest

from app import ratelimit


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Лимиты частоты запросов живут в памяти процесса — между тестами их сбрасываем."""
    ratelimit.reset()
    yield
    ratelimit.reset()
