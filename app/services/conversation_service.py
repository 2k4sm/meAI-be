from sqlalchemy.orm import Session
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.conversation import ConversationCreate, ConversationRead
from app.schemas.message import MessageCreate, MessageRead
from typing import List, Optional
from app.services.llm_service import generate_summary_with_llm
from app.utils.message_utils import get_last_n_messages
from app.constants import M_SUMMARY_INTERVAL

def get_conversations(db: Session, user_id: int) -> List[ConversationRead]:
    conversations = db.query(Conversation).filter(Conversation.user_id == user_id).order_by(Conversation.created_at.desc()).all()
    return [ConversationRead.model_validate(c) for c in conversations]

def create_conversation(db: Session, user_id: int, conversation_in: ConversationCreate) -> ConversationRead:
    conversation = Conversation(user_id=user_id, title=conversation_in.title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return ConversationRead.model_validate(conversation)

def get_conversation(db: Session, conversation_id: int, user_id: int) -> Optional[ConversationRead]:
    conversation = db.query(Conversation).filter(Conversation.conversation_id == conversation_id, Conversation.user_id == user_id).first()
    return ConversationRead.model_validate(conversation) if conversation else None

def get_messages(db: Session, conversation_id: int, user_id: int) -> List[MessageRead]:
    conversation = db.query(Conversation).filter(Conversation.conversation_id == conversation_id, Conversation.user_id == user_id).first()
    if not conversation:
        return []
    messages = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()).all()
    return [MessageRead.model_validate(m) for m in messages]

async def add_message(db: Session, message_in: MessageCreate, user_id: int) -> Message:
    message = Message(
        conversation_id=message_in.conversation_id,
        user_id=user_id,
        type=message_in.type,
        content=message_in.content
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    message_count = db.query(Message).filter(Message.conversation_id == message.conversation_id).count()
    if message_count % M_SUMMARY_INTERVAL == 0:
        last_msgs = get_last_n_messages(db, message.conversation_id, M_SUMMARY_INTERVAL)
        conversation = db.query(Conversation).filter(Conversation.conversation_id == message.conversation_id).first()
        if conversation:
            prev_summary = conversation.summary_text if conversation.summary_text else None
            filtered_msgs = [m for m in last_msgs if m.type in ("Human", "AI")]
            summary_text = await generate_summary_with_llm(filtered_msgs, previous_summary=prev_summary)
            conversation.summary_text = summary_text
            db.flush()
            db.commit()

    return message

def get_message(db: Session, message_id: int, conversation_id: int, user_id: int) -> Optional[MessageRead]:
    message = db.query(Message).join(Conversation).filter(
        Message.message_id == message_id,
        Message.conversation_id == conversation_id,
        Conversation.user_id == user_id
    ).first()
    return MessageRead.model_validate(message) if message else None

def delete_message(db: Session, message_id: int, conversation_id: int, user_id: int) -> bool:
    message = db.query(Message).join(Conversation).filter(
        Message.message_id == message_id,
        Message.conversation_id == conversation_id,
        Conversation.user_id == user_id
    ).first()
    if message:
        db.delete(message)
        db.commit()
        return True
    return False

def delete_conversation(db: Session, conversation_id: int, user_id: int) -> bool:
    conversation = db.query(Conversation).filter(
        Conversation.conversation_id == conversation_id,
        Conversation.user_id == user_id
    ).first()
    if conversation:
        db.query(Message).filter(Message.conversation_id == conversation_id).delete()
        db.delete(conversation)
        db.commit()
        return True
    return False
