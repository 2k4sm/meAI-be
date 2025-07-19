from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ConversationBase(BaseModel):
    title: Optional[str] = None

class ConversationCreate(ConversationBase):
    pass

class ConversationInDBBase(ConversationBase):
    conversation_id: int
    user_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class Conversation(ConversationInDBBase):
    pass

class ConversationList(BaseModel):
    conversations: List[Conversation]
