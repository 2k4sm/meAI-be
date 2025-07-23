from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from app.config import settings

def create_session_token(payload: Dict[str, Any]) -> str:
    """Create a session token that will be stored in a cookie"""
    to_encode = payload.copy()
    expire = datetime.now(timezone.utc) + timedelta(seconds=settings.cookie_max_age)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def verify_session_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify a session token from a cookie"""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None 