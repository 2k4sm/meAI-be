from app.models.message import Message
from sqlalchemy.orm import Session
from typing import List

def get_last_n_messages(db: Session, conversation_id: int, n: int) -> List[Message]:
    return db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.desc()).limit(n).all()[::-1] 