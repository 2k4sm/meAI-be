from pydantic import BaseModel
from typing import Optional, Any, List
from datetime import datetime

class ToolCallBase(BaseModel):
    tool_name: str
    input_params: Optional[Any] = None
    tool_response: Optional[Any] = None

class ToolCallCreate(ToolCallBase):
    message_id: int

class ToolCallInDBBase(ToolCallBase):
    tool_call_id: int
    message_id: int
    executed_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class ToolCall(ToolCallInDBBase):
    pass

class ToolCallList(BaseModel):
    tool_calls: List[ToolCall]
