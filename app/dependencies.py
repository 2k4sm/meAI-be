from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import get_user_by_email
from app.utils.auth_utils import verify_session_token
from app.config import settings

async def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user from session cookie"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    
    try:
        session_token = request.cookies.get(settings.cookie_name)
        if not session_token:
            raise credentials_exception
        
        payload = verify_session_token(session_token)
        if not payload:
            raise credentials_exception
        
        user = get_user_by_email(db, payload["sub"])
        if not user:
            raise credentials_exception
        
        return user
    except Exception:
        raise credentials_exception
