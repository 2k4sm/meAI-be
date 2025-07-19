from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: str
    name: str
    avatar_url: Optional[str] = None
    auth_method: str

class UserRead(UserBase):
    user_id: int
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None
    
    model_config = {'from_attributes': True}
