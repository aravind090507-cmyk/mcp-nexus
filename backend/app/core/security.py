import hashlib
import os
import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from jose import jwt, JWTError
from app.core.config import settings

logger = logging.getLogger(__name__)

# Enterprise-grade PBKDF2-HMAC-SHA256 password hashing for guaranteed zero-dependency cross-platform stability
def get_password_hash(password: str) -> str:
    salt = os.urandom(16).hex()
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return f"{salt}${key}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password or '$' not in hashed_password:
        return False
    salt, key = hashed_password.split('$', 1)
    new_key = hashlib.pbkdf2_hmac(
        'sha256',
        plain_password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return hmac.compare_digest(key, new_key)

def create_access_token(subject: Any, expires_delta: Optional[timedelta] = None) -> str:
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "exp": expire,
        "iat": now,
        "iss": "mcp-nexus-auth",
        "aud": "mcp-nexus-api",
        "sub": str(subject)
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            issuer="mcp-nexus-auth",
            audience="mcp-nexus-api"
        )
        return payload
    except JWTError as e:
        logger.warning(f"JWT verification failure: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected token decoding error: {e}")
        return None
