from pydantic import BaseModel
from typing import List
from datetime import datetime
from app.models.message import MessageType

class MessageCreate(BaseModel):
    content: str
    type: MessageType
    conversation_id: int

class MessageRead(BaseModel):
    message_id: int
    conversation_id: int
    user_id: int
    type: MessageType
    content: str
    created_at: datetime

    model_config = {'from_attributes': True}


class MessageList(BaseModel):
    messages: List[MessageRead]
