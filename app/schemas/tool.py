from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, field_serializer


class ToolkitInfo(BaseModel):
    slug: str
    name: str
    description: Optional[str] = None
    logo: Optional[str] = None
    categories: Optional[List[str]] = None
    is_enabled: bool = False



class ConnectionRequest(BaseModel):
    connection_request_id: str
    redirect_url: Optional[str] = None
    status: str


class ConnectionStatus(BaseModel):
    status: str
    connected_account_id: Optional[str] = None
    toolkit: Optional[str] = None
    error: Optional[str] = None


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
