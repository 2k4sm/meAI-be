from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.message import MessageType

class MessageBase(BaseModel):
    content: str
    type: MessageType

class MessageCreate(MessageBase):
    conversation_id: int
    user_id: Optional[int] = None

class MessageInDBBase(MessageBase):
    message_id: int
    conversation_id: int
    user_id: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class Message(MessageInDBBase):
    pass

class MessageList(BaseModel):
    messages: List[Message]
