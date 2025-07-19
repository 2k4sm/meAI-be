from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from app.routers.auth import verify_token, get_user_by_email
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.conversation import ConversationRead, ConversationCreate, ConversationList
from app.schemas.message import MessageRead, MessageList, MessageCreate
from app.services import conversation_service
from app.services.llm_service import stream_llm_response, store_message_embedding, get_context_with_summary
from app.models.message import MessageType

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

@router.websocket("/{conversation_id}/stream")
async def conversation_ws(websocket: WebSocket, conversation_id: int, db: Session = Depends(get_db)):
    await websocket.accept()
    try:
        token = websocket.headers.get('authorization')
        if not token or not token.lower().startswith('bearer '):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        token_value = token[7:]
        payload = verify_token(token_value)
        if not payload:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        user = get_user_by_email(db, payload["sub"])
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        user_id = user.user_id

        conversation = conversation_service.get_conversation(db, conversation_id, user_id)
        if not conversation:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        while True:
            data = await websocket.receive_json()
            user_message = data.get('content')
            if not user_message:
                continue
            message_in = MessageCreate(
                conversation_id=conversation_id,
                type=MessageType.HUMAN,
                content=user_message
            )
            message_obj = await conversation_service.add_message(db, message_in, user_id)
            await store_message_embedding(message_obj, conversation_id)
            context = await get_context_with_summary(db, conversation_id, user_message)
            llm_response = ""
            async for chunk in stream_llm_response(user_message, context):
                await websocket.send_json({"role": "assistant", "content": chunk})
                llm_response += chunk

            reply_in = MessageCreate(
                conversation_id=conversation_id,
                type=MessageType.AI,
                content=llm_response
            )
            reply_message_obj = await conversation_service.add_message(db, reply_in, user_id)
            await store_message_embedding(reply_message_obj, conversation_id)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
