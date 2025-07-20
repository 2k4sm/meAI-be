from fastapi import APIRouter, Depends, status, WebSocket, WebSocketDisconnect
from app.utils.auth_utils import verify_token
from app.services.auth_service import get_user_by_email
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.conversation import ConversationRead, ConversationCreate, ConversationList
from app.schemas.message import MessageList, MessageCreate
from app.services import conversation_service
from app.services.llm_service import stream_llm_response, store_message_embedding, get_context_with_summary
from app.models.message import MessageType
from app.utils.embedding_utils import delete_message_embedding, delete_conversation_embeddings

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
            if message_in.type in [MessageType.HUMAN, MessageType.AI]:
                await store_message_embedding(message_obj, conversation_id)
            try:
                context = await get_context_with_summary(db, conversation_id, user_message)
                
                llm_response = ""
                tool_messages = []
                
                async for chunk in stream_llm_response(user_message, context, db, user_id):
                    if chunk["type"] == "ai":
                        await websocket.send_json({"role": "assistant", "content": chunk["content"]})
                        llm_response += chunk["content"]
                    elif chunk["type"] in ["tool_start", "tool_success", "tool_error"]:
                        await websocket.send_json({"role": "tool", "content": chunk["content"]})

                        tool_content = chunk["content"]
                        if chunk["type"] == "tool_success" and "tool_result" in chunk:
                            tool_content += f"\nResult: {chunk['tool_result']}"
                        elif chunk["type"] == "tool_error" and "error" in chunk:
                            tool_content += f"\nError: {chunk['error']}"
                        
                        tool_messages.append({
                            "tool_name": chunk["tool_name"],
                            "content": tool_content,
                            "type": chunk["type"]
                        })

                reply_in = MessageCreate(
                    conversation_id=conversation_id,
                    type=MessageType.AI,
                    content=llm_response
                )
                reply_message_obj = await conversation_service.add_message(db, reply_in, user_id)
                if reply_in.type in [MessageType.HUMAN, MessageType.AI]:
                    await store_message_embedding(reply_message_obj, conversation_id)
                
                for tool_msg in tool_messages:
                    tool_message_in = MessageCreate(
                        conversation_id=conversation_id,
                        type=MessageType.TOOL,
                        content=f"[{tool_msg['tool_name']}] {tool_msg['content']}"
                    )
                    tool_message_obj = await conversation_service.add_message(db, tool_message_in, user_id)
                    # Do NOT store embedding for tool messages
                    
            except Exception as e:
                error_message = f"Error processing request: {str(e)}"
                await websocket.send_json({"role": "assistant", "content": error_message})
                
                reply_in = MessageCreate(
                    conversation_id=conversation_id,
                    type=MessageType.AI,
                    content=error_message
                )
                reply_message_obj = await conversation_service.add_message(db, reply_in, user_id)
                if reply_in.type in [MessageType.HUMAN, MessageType.AI]:
                    await store_message_embedding(reply_message_obj, conversation_id)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
