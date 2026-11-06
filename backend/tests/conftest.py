import pytest

from app import ratelimit


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Лимиты частоты запросов живут в памяти процесса — между тестами их сбрасываем."""
    ratelimit.reset()
    yield
    ratelimit.reset()


@pytest.fixture(autouse=True)
def _no_network_password_check(monkeypatch):
    """Тесты не ходят в Have I Been Pwned."""
    from app import auth

    monkeypatch.setattr(auth, "PWNED_CHECK", False)
