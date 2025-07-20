from typing import Optional, List, Dict, Any
from pydantic import BaseModel, field_serializer, field_validator
from datetime import datetime
from app.models.user_toolkit_connection import ConnectionStatus



class ConnectionRequest(BaseModel):
    connection_request_id: str
    redirect_url: Optional[str] = None
    status: str



class ToolsResponse(BaseModel):
    tools: List[Any]
    toolkit_slugs: List[str]
    user_id: int
    
    @field_serializer('tools')
    def serialize_tools(self, tools: List[Any]) -> List[Dict[str, Any]]:
        """Serialize tools to a format that can be JSON serialized."""
        serialized_tools = []
        for tool in tools:
            try:
                tool_dict = {
                    "name": getattr(tool, 'name', str(tool)),
                    "description": getattr(tool, 'description', None),
                    "type": type(tool).__name__,
                    "toolkit": getattr(tool, 'toolkit', None)
                }
                serialized_tools.append(tool_dict)
            except Exception:
                serialized_tools.append({
                    "name": str(tool),
                    "description": None,
                    "type": type(tool).__name__,
                    "toolkit": None
                })
        return serialized_tools


class MessageResponse(BaseModel):
    message: str


class ToolkitConnection(BaseModel):
    connection_id: int
    user_id: int
    toolkit_slug: str
    connection_status: ConnectionStatus
    connected_account_id: Optional[str] = None
    auth_config_id: Optional[str] = None
    connection_request_id: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_validator('connection_status', mode='before')
    def validate_connection_status(cls, v):
        if v is not None and not isinstance(v, ConnectionStatus):
            try:
                return ConnectionStatus(v)
            except Exception:
                return None
        return v

    @field_validator('last_synced_at', 'created_at', 'updated_at', mode='before')
    def validate_datetimes(cls, v):
        if v is not None and not isinstance(v, datetime):
            try:
                return datetime.fromisoformat(str(v))
            except Exception:
                return None
        return v

    class Config:
        from_attributes = True


class ToolkitConnectionList(BaseModel):
    connections: List[ToolkitConnection]
    total_count: int


class ConnectionSyncRequest(BaseModel):
    connection_request_id: str



class ConnectionSyncResponse(BaseModel):
    success: bool
    message: str
    connection_status: Optional[ConnectionStatus] = None
    last_synced_at: Optional[datetime] = None


class ToolkitDiscovery(BaseModel):
    slug: str
    name: str
    description: Optional[str] = None
    logo: Optional[str] = None
    categories: Optional[List[str]] = None
    is_connected: bool = False
    connection_status: Optional[str] = None


class ToolkitDiscoveryList(BaseModel):
    toolkits: List[ToolkitDiscovery]
    total_count: int
