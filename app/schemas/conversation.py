from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ConversationBase(BaseModel):
    title: Optional[str] = None

class ConversationCreate(ConversationBase):
    pass

class ConversationInDBBase(ConversationBase):
    conversation_id: Optional[int] = None
    user_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class Conversation(ConversationInDBBase):
    pass

class ConversationList(BaseModel):
    conversations: List[Conversation]
