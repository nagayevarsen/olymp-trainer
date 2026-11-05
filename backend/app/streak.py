"""Серия дней («стрик») и задача дня.

- Каждый день у ученика своя задача дня средней сложности (5–7 баллов из 10), из ещё не решённых.
- Решил задачу дня — серия +1. Пропустил день — серия гаснет.
- Если пропущен ровно один день, серию можно восстановить: 3 восстановления в месяц,
  пополняются 1-го числа.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, timedelta

RESTORES_PER_MONTH = 3
DAILY_POINTS = (5, 7)


@dataclass
class StreakState:
    count: int = 0
    last_day: date | None = None  # последний день, когда решена задача дня
    restores_left: int = RESTORES_PER_MONTH
    restores_month: str = ""  # «2026-11»: месяц, к которому относится restores_left

    def refill(self, today: date) -> None:
        month = today.strftime("%Y-%m")
        if self.restores_month != month:
            self.restores_month = month
            self.restores_left = RESTORES_PER_MONTH

    def status(self, today: date) -> str:
        """done_today | active (вчера решил, сегодня ещё нет) | restorable | broken | new"""
        if self.last_day is None:
            return "new"
        if self.last_day == today:
            return "done_today"
        if self.last_day == today - timedelta(days=1):
            return "active"
        if self.last_day == today - timedelta(days=2) and self.restores_left > 0:
            return "restorable"
        return "broken"

    def visible_count(self, today: date) -> int:
        return self.count if self.status(today) in ("done_today", "active", "restorable") else 0

    def complete(self, today: date) -> None:
        """Задача дня решена."""
        st = self.status(today)
        if st == "done_today":
            return
        self.count = self.count + 1 if st == "active" else 1
        self.last_day = today

    def restore(self, today: date) -> bool:
        """Восстановить серию после одного пропущенного дня."""
        self.refill(today)
        if self.status(today) != "restorable":
            return False
        self.restores_left -= 1
        self.last_day = today - timedelta(days=1)
        return True


def pick_daily(user_id: str, today: date, candidates: list[str]) -> str | None:
    """Задача дня: одна и та же для ученика весь день."""
    if not candidates:
        return None
    ids = sorted(candidates)
    h = int(hashlib.sha256(f"{user_id}:{today.isoformat()}".encode()).hexdigest(), 16)
    return ids[h % len(ids)]
