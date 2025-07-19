from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from app.config import settings
from app.models.user import User


def create_access_token(payload: Dict[str, Any], expires_in: Optional[int] = None) -> str:
    """Create access token with specified expiration in minutes"""
    if expires_in is None:
        expires_in = settings.access_token_expire_minutes
    
    to_encode = payload.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_in)
    to_encode.update({"exp": expire})
    
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(payload: Dict[str, Any], expires_in: Optional[int] = None) -> str:
    """Create refresh token with specified expiration in days"""
    if expires_in is None:
        expires_in = settings.refresh_token_expire_days
    
    to_encode = payload.copy()
    expire = datetime.utcnow() + timedelta(days=expires_in)
    to_encode.update({"exp": expire})
    
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify JWT token and return payload or None"""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None


def get_or_create_user(db: Session, userinfo: dict) -> User:
    """Get existing user or create new user from Google OAuth data"""
    email = userinfo.get("email")
    if not email:
        raise ValueError("Email is required from Google OAuth")
    
    user = db.query(User).filter(User.email == email).first()
    
    if user:
        user.name = userinfo.get("name", user.name)
        user.avatar_url = userinfo.get("picture", user.avatar_url)
        setattr(user, 'last_login', datetime.utcnow())
        setattr(user, 'auth_method', "google")
        return user
    
    user = User(
        email=email,
        name=userinfo.get("name", ""),
        avatar_url=userinfo.get("picture"),
        auth_method="google",
        last_login=datetime.utcnow()
    )
    db.add(user)
    return user


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email"""
    return db.query(User).filter(User.email == email).first()
