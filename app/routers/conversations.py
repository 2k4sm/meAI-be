from fastapi import APIRouter, Depends, status, WebSocket, WebSocketDisconnect, Cookie
from typing import Optional
from app.utils.auth_utils import verify_session_token
from app.services.auth_service import get_user_by_email
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.conversation import ConversationRead, ConversationCreate, ConversationList
from app.schemas.message import MessageList, MessageCreate
from app.services import conversation_service
from app.services.llm_service import stream_llm_response, store_message_embedding, get_context_with_summary, classify_tool_intent_with_llm
from app.models.message import MessageType
from app.utils.embedding_utils import delete_message_embedding, delete_conversation_embeddings
from app.config import settings

router = APIRouter(prefix="/conversations", tags=["conversations"])

@router.get("/", response_model=ConversationList)
def list_conversations(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    conversations = conversation_service.get_conversations(db, user_id=current_user.user_id)
    return {"conversations": conversations}

@router.post("/", response_model=ConversationRead)
def create_conversation(conversation_in: ConversationCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    conversation = conversation_service.create_conversation(db, user_id=current_user.user_id, conversation_in=conversation_in)
    return conversation

@router.get("/{conversation_id}/messages", response_model=MessageList)
def get_conversation_messages(conversation_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    messages = conversation_service.get_messages(db, conversation_id=conversation_id, user_id=current_user.user_id)
    return {"messages": messages}

@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    try:
        conversation = conversation_service.get_conversation(db, conversation_id, current_user.user_id)
        if not conversation:
            return {"error": "Conversation not found"}, 404
        
        conversation_service.delete_conversation(db, conversation_id, current_user.user_id)
        delete_conversation_embeddings(conversation_id)
        
        return {"message": "Conversation deleted successfully"}
    except Exception as e:
        return {"error": f"Failed to delete conversation: {str(e)}"}, 500

@router.delete("/{conversation_id}/messages/{message_id}")
def delete_message(conversation_id: int, message_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    try:
        message = conversation_service.get_message(db, message_id, conversation_id, current_user.user_id)
        if not message:
            return {"error": "Message not found"}, 404
        
        conversation_service.delete_message(db, message_id, conversation_id, current_user.user_id)
        delete_message_embedding(message_id)
        
        return {"message": "Message deleted successfully"}
    except Exception as e:
        return {"error": f"Failed to delete message: {str(e)}"}, 500
