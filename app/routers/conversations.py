from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.conversation import Conversation, ConversationCreate, ConversationList
from app.schemas.message import Message, MessageList
from app.services import conversation_service

router = APIRouter(prefix="/conversations", tags=["conversations"])

@router.get("/", response_model=ConversationList)
def list_conversations(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    conversations = conversation_service.get_conversations(db, user_id=current_user.user_id)
    return {"conversations": conversations}

@router.post("/", response_model=Conversation)
def create_conversation(conversation_in: ConversationCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    conversation = conversation_service.create_conversation(db, user_id=current_user.user_id, conversation_in=conversation_in)
    return conversation

@router.get("/{conversation_id}/messages", response_model=MessageList)
def get_conversation_messages(conversation_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    messages = conversation_service.get_messages(db, conversation_id=conversation_id, user_id=current_user.user_id)
    return {"messages": messages}
