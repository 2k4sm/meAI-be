from sqlalchemy.orm import Session
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.conversation import ConversationCreate
from app.schemas.message import MessageCreate
from typing import List, Optional

def get_conversations(db: Session, user_id: int) -> List[Conversation]:
    return db.query(Conversation).filter(Conversation.user_id == user_id).order_by(Conversation.created_at.desc()).all()

def create_conversation(db: Session, user_id: int, conversation_in: ConversationCreate) -> Conversation:
    conversation = Conversation(user_id=user_id, **conversation_in.model_dump())
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation

def get_conversation(db: Session, conversation_id: int, user_id: int) -> Optional[Conversation]:
    return db.query(Conversation).filter(Conversation.conversation_id == conversation_id, Conversation.user_id == user_id).first()

def get_messages(db: Session, conversation_id: int, user_id: int) -> List[Message]:
    conversation = db.query(Conversation).filter(Conversation.conversation_id == conversation_id, Conversation.user_id == user_id).first()
    if not conversation:
        return []
    return db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()).all()

def add_message(db: Session, message_in: MessageCreate) -> Message:
    message = Message(**message_in.model_dump())
    db.add(message)
    db.commit()
    db.refresh(message)
    return message
