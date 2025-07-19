from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ConversationCreate(BaseModel):
    title: str

class ConversationRead(BaseModel):
    conversation_id: int
    user_id: int
    title: Optional[str] = None
    summary_text: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {'from_attributes': True}


class ConversationList(BaseModel):
    conversations: List[ConversationRead]
