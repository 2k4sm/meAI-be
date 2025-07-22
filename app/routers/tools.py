from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.user_toolkit_connection import UserToolkitConnection
from app.schemas.tool import (
    ConnectionRequest, ToolkitResponse, MessageResponse,
    ToolkitConnection, ToolkitConnectionList, ConnectionSyncResponse,
)
from app.services.composio_service import composio_service

router = APIRouter(prefix="/toolkits", tags=["tools"])


@router.get("/", response_model=ToolkitResponse)
async def get_tools_for_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get supported toolkits."""
   
    toolkits = composio_service.get_supported_toolkits()
    
    return ToolkitResponse(
        toolkits=toolkits,
        user_id=current_user.user_id
    )


@router.post("/connect/{toolkit_slug}", response_model=ConnectionRequest)
async def initiate_toolkit_connection(
    toolkit_slug: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Initiate OAuth connection for a toolkit."""
    try:
        connection_request = composio_service.initiate_connection_with_db_update(
            db, toolkit_slug, str(current_user.user_id)
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


@router.get("/connections", response_model=ToolkitConnectionList)
async def get_user_connections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all toolkit connections for the current user."""
    connections = composio_service.get_user_connections(db, current_user.user_id)
    toolkit_connections = [ToolkitConnection.model_validate(conn) for conn in connections]
    return ToolkitConnectionList(
        connections=toolkit_connections,
        total_count=len(toolkit_connections)
    )


@router.get("/connections/{toolkit_slug}", response_model=ToolkitConnection)
async def get_connection_status(
    toolkit_slug: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get connection status for a specific toolkit."""
    connection = composio_service.get_connection_status(db, current_user.user_id, toolkit_slug)
    if not connection:
        raise HTTPException(status_code=404, detail=f"No connection found for toolkit {toolkit_slug}")
    
    return ToolkitConnection.model_validate(connection)



@router.post("/connections/sync/{connection_request_id}", response_model=ConnectionSyncResponse)
async def sync_connection_by_request_id(
    connection_request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Sync connection using connection_request_id from Composio."""
    try:
        success = composio_service.sync(db, connection_request_id)
        
        connection = db.query(UserToolkitConnection).filter(
            UserToolkitConnection.connection_request_id == connection_request_id
        ).first()
        
        if not connection:
            return ConnectionSyncResponse(
                success=False,
                message=f"No connection found for request_id: {connection_request_id}",
                connection_status=None,
                last_synced_at=None
            )
        
        toolkit_connection = ToolkitConnection.model_validate(connection)
        connection_status = toolkit_connection.connection_status
        last_synced = toolkit_connection.last_synced_at
        
        if success:
            return ConnectionSyncResponse(
                success=True,
                message=f"Connection synced successfully for request_id: {connection_request_id}",
                connection_status=connection_status,
                last_synced_at=last_synced
            )
        else:
            return ConnectionSyncResponse(
                success=False,
                message=f"Failed to sync connection for request_id: {connection_request_id}",
                connection_status=connection_status,
                last_synced_at=last_synced
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync connection: {str(e)}")

