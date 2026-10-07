"""رمزنگاری رمز عبور (argon2)، JWT و Fernet برای توکن بات."""

import base64
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        # API: verify(hash, password)
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
        return str(payload.get("sub")) or None
    except jwt.PyJWTError:
        return None


def _fernet() -> Fernet | None:
    key = get_settings().fernet_key
    if not key:
        return None
    raw = key.strip().encode()
    # کلید ۳۲ بایتی base64 است؛ اگر کاربر کلید خام داد، خودمان تبدیل می‌کنیم
    try:
        return Fernet(raw)
    except Exception:
        return Fernet(base64.urlsafe_b64encode(raw.ljust(32)[:32]))


def encrypt_secret(plaintext: str) -> str:
    f = _fernet()
    if f is None:
        # در dev بدون کلید؛ هرگز در prod این‌طور نکنید
        return "plain:" + plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    f = _fernet()
    if f is None:
        return ciphertext.removeprefix("plain:")
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        return ""
