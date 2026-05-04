import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import fetch_one, get_connection, init_db, utcnow_iso

JWT_SECRET = os.getenv("APP_JWT_SECRET", "dev-insecure-secret-change-me")
JWT_ALG = "HS256"
JWT_EXPIRE_DAYS = 7
DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo"

security = HTTPBearer(auto_error=False)


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
    return f"pbkdf2_sha256${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored.split("$", 2)
    except ValueError:
        return False
    expected = bytes.fromhex(digest_hex)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 120000)
    return hmac.compare_digest(expected, actual)


def create_access_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=JWT_EXPIRE_DAYS)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def ensure_demo_user() -> None:
    init_db()
    with get_connection() as conn:
        user = fetch_one(conn, "SELECT * FROM users WHERE email = ?", (DEMO_EMAIL,))
        if user:
            return
        conn.execute(
            "INSERT INTO users (id, email, password_hash, display_name, is_demo, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), DEMO_EMAIL, _hash_password(DEMO_PASSWORD), "Demo User", 1, utcnow_iso()),
        )
        conn.commit()


def register_user(email: str, password: str, display_name: str) -> dict:
    if len(password) < 3:
        raise HTTPException(status_code=400, detail="Password must contain at least 3 characters.")
    with get_connection() as conn:
        existing = fetch_one(conn, "SELECT id FROM users WHERE email = ?", (email.lower(),))
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered.")
        user_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO users (id, email, password_hash, display_name, is_demo, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, email.lower(), _hash_password(password), display_name.strip() or email, 0, utcnow_iso()),
        )
        conn.commit()
        return get_user_by_id(user_id)


def login_user(email: str, password: str) -> dict:
    with get_connection() as conn:
        user = fetch_one(conn, "SELECT * FROM users WHERE email = ?", (email.lower(),))
    if not user or not _verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    return user


def demo_login() -> dict:
    ensure_demo_user()
    return login_user(DEMO_EMAIL, DEMO_PASSWORD)


def get_user_by_id(user_id: str) -> dict:
    with get_connection() as conn:
        user = fetch_one(conn, "SELECT * FROM users WHERE id = ?", (user_id,))
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


def user_public(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "is_demo": bool(user["is_demo"]),
    }


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token.") from exc


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization required.")
    payload = _decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload.")
    return get_user_by_id(user_id)
