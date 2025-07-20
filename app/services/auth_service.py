from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import User

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
