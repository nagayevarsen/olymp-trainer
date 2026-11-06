"""Минимальный аккаунт: уникальный ник + пароль. Ни почты, ни телефона, ни настоящего имени.

Пароль хранится только как хэш scrypt с солью (стандартная библиотека Python).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets

NICK_RE = re.compile(r"^[A-Za-zА-Яа-яЁё0-9_.-]{3,20}$")
MIN_PASSWORD = 8
MAX_PASSWORD = 64
# Проверка по базе утёкших паролей (Have I Been Pwned, k-анонимность: уходят только 5 символов SHA-1).
PWNED_CHECK = os.environ.get("PWNED_CHECK", "1") != "0"
COMMON_PASSWORDS = {
    "12345678", "123456789", "1234567890", "password", "password1", "qwertyui", "qwerty123", "11111111",
    "00000000", "1q2w3e4r", "1qaz2wsx", "iloveyou", "asdfghjk", "zxcvbnm1", "abcd1234", "qwertyuiop",
    "йцукенгш", "пароль123", "87654321", "aa123456", "12341234", "password123",
}  # fmt: skip
_N, _R, _P = 2**14, 8, 1


class AuthError(ValueError):
    pass


def check_nick(nick: str) -> str:
    nick = nick.strip()
    if not NICK_RE.fullmatch(nick):
        raise AuthError("Ник: 3–20 символов — буквы, цифры, точка, дефис, подчёркивание")
    return nick


def check_password(password: str, nick: str = "") -> None:
    if not (MIN_PASSWORD <= len(password) <= MAX_PASSWORD):
        raise AuthError(f"Пароль: от {MIN_PASSWORD} до {MAX_PASSWORD} символов")
    if password.lower() in COMMON_PASSWORDS or (nick and password.lower() == nick.lower()):
        raise AuthError("Этот пароль слишком простой — придумай другой")
    if PWNED_CHECK and password_leaked(password):
        raise AuthError("Этот пароль уже утекал с других сайтов и известен взломщикам — придумай другой")


def password_leaked(password: str) -> bool:
    """Есть ли пароль в базе утечек Have I Been Pwned. На сервис уходят только первые 5 символов
    SHA-1 хэша (k-анонимность), сам пароль никуда не отправляется. Сервис недоступен — не блокируем."""
    import httpx

    digest = hashlib.sha1(password.encode()).hexdigest().upper()
    prefix, rest = digest[:5], digest[5:]
    try:
        r = httpx.get(
            f"https://api.pwnedpasswords.com/range/{prefix}",
            headers={"Add-Padding": "true", "User-Agent": "OlympTrainer"},
            timeout=3,
        )
        r.raise_for_status()
    except httpx.HTTPError:
        return False
    for line in r.text.splitlines():
        suffix, _, count = line.partition(":")
        if suffix.strip() == rest and count.strip() not in ("", "0"):
            return True
    return False


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
