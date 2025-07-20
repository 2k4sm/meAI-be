from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.tool import ToolkitInfo, ConnectionRequest, ConnectionStatus, ToolsResponse, MessageResponse
from app.services.composio_service import composio_service

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("/", response_model=ToolsResponse)
async def get_tools_for_user(
    filter: Optional[bool] = Query(None, description="Filter by enabled toolkits"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get tools for the current user, optionally filtered by toolkit."""
    toolkit_slugs = []
    if filter:
        toolkit_slugs = composio_service.get_user_enabled_toolkits(db, current_user.user_id)
    
    tools = composio_service.get_tools_for_user(str(current_user.user_id), toolkit_slugs)
    return ToolsResponse(
        tools=tools,
        toolkit_slugs=toolkit_slugs,
        user_id=current_user.user_id
    )


@router.post("/connect/{toolkit_slug}", response_model=ConnectionRequest)
async def initiate_toolkit_connection(
    toolkit_slug: str,
    redirect_url: Optional[str] = Query(None, description="Optional redirect URL after OAuth"),
    current_user: User = Depends(get_current_user)
):
    """Initiate OAuth connection for a toolkit."""
    try:
        connection_request = composio_service.initiate_connection(
            toolkit_slug, str(current_user.user_id), redirect_url
        )
    
        return ConnectionRequest(
            connection_request_id=connection_request.id,
            redirect_url=connection_request.redirect_url,
            status="pending"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate connection: {str(e)}")

@router.post("/enable/{toolkit_slug}", response_model=MessageResponse)
async def enable_toolkit(
    toolkit_slug: str,
    current_user: User = Depends(get_current_user),
    redirect_url: Optional[str] = Query(None, description="Optional redirect URL after OAuth"),
    db: Session = Depends(get_db)
):
    """Enable a toolkit for the current user."""
    success = composio_service.enable_toolkit_for_user(db, current_user.user_id, toolkit_slug)
    
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to enable toolkit")
    
    if redirect_url:
        return RedirectResponse(url=redirect_url)
    
    return MessageResponse(message=f"Toolkit {toolkit_slug} enabled successfully")


@router.delete("/disable/{toolkit_slug}", response_model=MessageResponse)
async def disable_toolkit(
    toolkit_slug: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disable a toolkit for the current user."""
    success = composio_service.disable_toolkit_for_user(db, current_user.user_id, toolkit_slug)
    
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to disable toolkit")
    return MessageResponse(message=f"Toolkit {toolkit_slug} disabled successfully")
