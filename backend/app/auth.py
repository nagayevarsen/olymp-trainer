"""Минимальный аккаунт: уникальный ник + пароль. Ни почты, ни телефона, ни настоящего имени.

Пароль хранится только как хэш scrypt с солью (стандартная библиотека Python).
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

NICK_RE = re.compile(r"^[A-Za-zА-Яа-яЁё0-9_.-]{3,20}$")
MIN_PASSWORD = 6
MAX_PASSWORD = 64
_N, _R, _P = 2**14, 8, 1


class AuthError(ValueError):
    pass


def check_nick(nick: str) -> str:
    nick = nick.strip()
    if not NICK_RE.fullmatch(nick):
        raise AuthError("Ник: 3–20 символов — буквы, цифры, точка, дефис, подчёркивание")
    return nick


def check_password(password: str) -> None:
    if not (MIN_PASSWORD <= len(password) <= MAX_PASSWORD):
        raise AuthError(f"Пароль: от {MIN_PASSWORD} до {MAX_PASSWORD} символов")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, n, r, p, salt, digest = stored.split("$")
        got = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=32
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got.hex(), digest)
