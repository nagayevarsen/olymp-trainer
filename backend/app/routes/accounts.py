"""Аккаунты: регистрация, вход, выход, аватарка, удаление."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from .. import ratelimit as rl
from ..auth import AuthError, check_nick, check_password, hash_password, verify_password
from ..common import _bearer, _signup_guard, current_user, get_db
from ..db import DB

log = logging.getLogger("olymp")
router = APIRouter()


# ---------- схемы запросов ----------
class NewUser(BaseModel):
    # Имя гостя видно в рейтинге: только буквы, цифры, пробел, точка, дефис.
    name: str = Field(min_length=1, max_length=20, pattern=r"^[\w .\-]+$")
    grade: int | None = Field(default=None, ge=1, le=12)


@router.post("/api/users")
def create_user(body: NewUser, request: Request, db: DB = Depends(get_db)) -> dict:
    """Профиль-гость без пароля (оставлен для совместимости; прогресс живёт только в этом браузере)."""
    _signup_guard(request)
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Пустое имя")
    uid = db.create_user(name, body.grade)
    return {"id": uid, "name": name, "grade": body.grade, "token": db.create_session(uid)}


# ---------- аккаунт: ник + пароль, без почты и телефона ----------
class Register(BaseModel):
    nick: str = Field(max_length=40)
    password: str = Field(max_length=200)
    grade: int | None = Field(default=None, ge=1, le=12)
    accept_terms: bool = False


class Login(BaseModel):
    nick: str = Field(max_length=40)
    password: str = Field(max_length=200)


def _account_fields(nick: str, password: str) -> tuple[str, str]:
    try:
        nick = check_nick(nick)
        check_password(password, nick)
    except AuthError as exc:
        raise HTTPException(400, str(exc)) from exc
    return nick, hash_password(password)


@router.get("/api/nick-available")
def nick_available(nick: str, db: DB = Depends(get_db)) -> dict:
    try:
        nick = check_nick(nick)
    except AuthError as exc:
        return {"available": False, "reason": str(exc)}
    taken = db.nick_taken(nick)
    return {"available": not taken, "reason": "Такой ник уже занят" if taken else None}


@router.post("/api/register")
def register(body: Register, request: Request, db: DB = Depends(get_db)) -> dict:
    if not body.accept_terms:
        raise HTTPException(400, "Нужно согласиться с условиями использования")
    nick, pass_hash = _account_fields(body.nick, body.password)
    _signup_guard(request)
    uid = db.create_account(nick, pass_hash, body.grade)
    if uid is None:
        raise HTTPException(409, "Такой ник уже занят")
    return {"id": uid, "name": nick, "grade": body.grade, "token": db.create_session(uid)}


LOGIN_FAILS_PER_NICK = 10  # за 15 минут
LOGIN_FAILS_PER_IP = 50


@router.post("/api/login")
async def login(body: Login, request: Request, db: DB = Depends(get_db)) -> dict:
    nick_key, ip = body.nick.strip().lower(), rl.client_ip(request)
    if not (
        rl.allow("login-nick", nick_key, LOGIN_FAILS_PER_NICK, 900, count=False)
        and rl.allow("login-ip", ip, LOGIN_FAILS_PER_IP, 900, count=False)
    ):
        raise HTTPException(429, "Слишком много неудачных попыток входа. Подожди 15 минут.")
    user = db.user_by_nick(body.nick.strip())
    ok = bool(user) and await asyncio.to_thread(verify_password, body.password, user["pass_hash"])
    if not ok:
        rl.hit("login-nick", nick_key)
        rl.hit("login-ip", ip)
        await asyncio.sleep(0.5)  # замедляем подбор пароля, не блокируя сервер
        raise HTTPException(401, "Неверный ник или пароль")
    return {
        "id": user["id"],
        "name": user["name"],
        "grade": user["grade"],
        "token": db.create_session(user["id"]),
    }


@router.post("/api/logout")
def logout(authorization: str = Header(default=""), db: DB = Depends(get_db)) -> dict:
    if token := _bearer(authorization):
        db.delete_session(token)
    return {"ok": True}


@router.post("/api/me/account")
def attach_account(body: Login, user: dict = Depends(current_user), db: DB = Depends(get_db)) -> dict:
    """Гость задаёт ник и пароль — прогресс сохраняется и становится доступен с других устройств."""
    if user.get("pass_hash"):
        raise HTTPException(400, "У профиля уже есть ник и пароль")
    nick, pass_hash = _account_fields(body.nick, body.password)
    if not db.attach_account(user["id"], nick, pass_hash):
        raise HTTPException(409, "Такой ник уже занят")
    return {"id": user["id"], "name": nick}


class AvatarBody(BaseModel):
    kind: Literal["pixel", "photo"]
    seed: int | None = Field(default=None, ge=0, le=2**31)
    data_url: str | None = Field(default=None, max_length=60_000)


JPEG_PREFIX = "data:image/jpeg;base64,"
JPEG_MAGIC = bytes([0xFF, 0xD8, 0xFF])


@router.get("/api/me/avatar")
def get_avatar(user: dict = Depends(current_user)) -> dict:
    """Аватарка видна только владельцу: в рейтинге и других местах она не показывается."""
    raw = user.get("avatar")
    return {"avatar": json.loads(raw) if raw else None}


@router.put("/api/me/avatar")
def put_avatar(body: AvatarBody, user: dict = Depends(current_user), db: DB = Depends(get_db)) -> dict:
    if body.kind == "pixel":
        if body.seed is None:
            raise HTTPException(422, "Нужен seed")
        value = {"kind": "pixel", "seed": body.seed}
    else:
        url = body.data_url or ""
        try:
            ok = (
                url.startswith(JPEG_PREFIX)
                and base64.b64decode(url[len(JPEG_PREFIX) :], validate=True)[:3] == JPEG_MAGIC
            )
        except ValueError:
            ok = False
        if not ok:
            raise HTTPException(422, "Нужна картинка JPEG")
        value = {"kind": "photo", "dataUrl": url}
    db.set_avatar(user["id"], json.dumps(value))
    return {"avatar": value}


@router.delete("/api/me")
def delete_me(user: dict = Depends(current_user), db: DB = Depends(get_db)) -> dict:
    db.delete_user(user["id"])
    return {"deleted": True}
