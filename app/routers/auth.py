from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request
from app.config import settings
from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import get_or_create_user, get_user_by_email
from app.schemas.user import UserRead
from app.utils.auth_utils import create_session_token, verify_session_token
from typing import Optional

router = APIRouter(prefix="/auth", tags=["authentication"])

oauth = OAuth()
oauth.register(
    name='google',
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={"scope": "openid email profile"},
)

async def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Get current user from session cookie"""
    session_token = request.cookies.get(settings.cookie_name)
    if not session_token:
        return None
    
    payload = verify_session_token(session_token)
    if not payload:
        return None
    
    return get_user_by_email(db, payload["sub"])

@router.get("/google")
async def google(request: Request):
    """Initiate Google OAuth flow"""
    redirect_uri = request.url_for('google_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """Handle Google OAuth callback"""
    try:
        token = await oauth.google.authorize_access_token(request)
        userinfo = token.get("userinfo")
        if not userinfo:
            raise HTTPException(status_code=400, detail="Invalid Google response")

        user = get_or_create_user(db, userinfo)
        session_token = create_session_token({"sub": user.email})
        
        response = RedirectResponse(url=settings.frontend_url)
        response.set_cookie(
            key=settings.cookie_name,
            value=session_token,
            max_age=settings.cookie_max_age,
            path=settings.cookie_path,
            domain=settings.cookie_domain,
            secure=settings.cookie_secure,
            httponly=settings.cookie_httponly,
            samesite=settings.cookie_samesite
        )
        
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")

@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)):
    """Get current user information"""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return UserRead.model_validate(user)

@router.post("/logout")
async def logout():
    """Logout user by clearing the session cookie"""
    response = JSONResponse({"message": "Successfully logged out"})
    response.delete_cookie(
        key=settings.cookie_name,
        path=settings.cookie_path,
        domain=settings.cookie_domain,
    )
    return response
