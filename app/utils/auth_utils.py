from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from app.config import settings
from datetime import timezone
def create_access_token(payload: Dict[str, Any], expires_in: Optional[int] = None) -> str:
    if expires_in is None:
        expires_in = settings.access_token_expire_minutes
    to_encode = payload.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_in)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def create_refresh_token(payload: Dict[str, Any], expires_in: Optional[int] = None) -> str:
    if expires_in is None:
        expires_in = settings.refresh_token_expire_days
    to_encode = payload.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=expires_in)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None 