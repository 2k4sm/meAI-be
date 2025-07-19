from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request
from app.config import settings
from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import create_access_token, create_refresh_token, verify_token, get_or_create_user, get_user_by_email

router = APIRouter(prefix="/api/auth", tags=["authentication"])

oauth = OAuth()
oauth.register(
    name='google',
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={"scope": "openid email profile"},
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

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
        
        refresh_token = create_refresh_token({"sub": user.email})
        setattr(user, 'refresh_token', refresh_token)
        db.commit()

        access_token = create_access_token({"sub": user.email})
        return JSONResponse({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")

@router.get("/me")
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Get current user information"""
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = get_user_by_email(db, payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return {
        "user_id": user.user_id,
        "email": user.email, 
        "name": user.name, 
        "avatar_url": user.avatar_url,
        "auth_method": user.auth_method,
        "last_login": user.last_login,
        "created_at": user.created_at
    }

@router.post("/refresh")
async def refresh_token(request: Request, db: Session = Depends(get_db)):
    """Refresh access token using refresh token"""
    try:
        data = await request.json()
        token = data.get("refresh_token")
        if not token:
            raise HTTPException(status_code=400, detail="Refresh token required")
        
        payload = verify_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        user = db.query(User).filter(User.email == payload["sub"], User.refresh_token == token).first()
        if not user:
            raise HTTPException(status_code=401, detail="Token revoked")
        
        access_token = create_access_token({"sub": user.email})
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token refresh failed: {str(e)}")

@router.post("/logout")
async def logout(request: Request,db: Session = Depends(get_db),token: str = Depends(oauth2_scheme)):
    """Logout user by invalidating refresh token"""
    try:
        payload = verify_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid access token")
        
        data = await request.json()
        refresh_token = data.get("refresh_token")
        if not refresh_token:
            raise HTTPException(status_code=400, detail="Refresh token required for logout")
        
        refresh_payload = verify_token(refresh_token)
        if not refresh_payload:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        if payload["sub"] != refresh_payload["sub"]:
            raise HTTPException(status_code=401, detail="Token subject mismatch")
        
        user = get_user_by_email(db, payload["sub"])
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        if user.refresh_token != refresh_token:
            raise HTTPException(status_code=401, detail="Refresh token does not match")
        
        setattr(user, 'refresh_token', None)
        db.commit()
        
        return {"message": "Successfully logged out"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Logout failed: {str(e)}")
