"""Tokens de un solo uso (hasheados) para invitación y reset de contraseña."""
import hashlib
import secrets
import uuid
from datetime import datetime, timezone, timedelta

TOKEN_TTL_HOURS = 48


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_token(db, user_id: str, purpose: str, created_by_id: str) -> str:
    """Invalida tokens previos no usados del usuario y crea uno nuevo. Devuelve el token en claro (solo para el email)."""
    now = datetime.now(timezone.utc)
    await db.password_tokens.update_many(
        {"user_id": user_id, "used_at": None},
        {"$set": {"used_at": now.isoformat(), "superseded": True}}
    )
    token = secrets.token_urlsafe(32)
    await db.password_tokens.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "token_hash": _hash(token),
        "purpose": purpose,
        "expires_at": (now + timedelta(hours=TOKEN_TTL_HOURS)).isoformat(),
        "used_at": None,
        "created_by": created_by_id,
        "created_at": now.isoformat(),
    })
    return token


async def validate_token(db, token: str):
    """Devuelve el doc del token si es válido (no usado, no expirado); None si no."""
    doc = await db.password_tokens.find_one({"token_hash": _hash(token)}, {"_id": 0})
    if not doc or doc.get("used_at"):
        return None
    expires_at = datetime.fromisoformat(doc["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None
    return doc


async def consume_token(db, token: str):
    await db.password_tokens.update_one(
        {"token_hash": _hash(token)},
        {"$set": {"used_at": datetime.now(timezone.utc).isoformat()}}
    )
