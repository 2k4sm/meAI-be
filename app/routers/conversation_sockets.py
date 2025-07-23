import http.cookies
from app.db.session import SessionLocal
from app.main import sio
from app.config import settings
from app.services.auth_service import get_user_by_email
from app.services import conversation_service
from app.schemas.message import MessageCreate, MessageType
from app.services.llm_service import stream_llm_response, store_message_embedding, get_context_with_summary, classify_tool_intent_with_llm, get_semantic_context
from app.utils.auth_utils import verify_session_token
from sqlalchemy.orm import Session
from app.utils.message_utils import get_last_n_messages

def get_cookie_from_environ(environ, cookie_name):
    cookie_header = environ.get('HTTP_COOKIE')
    if not cookie_header:
        return None
    cookies = http.cookies.SimpleCookie()
    cookies.load(cookie_header)
    return cookies.get(cookie_name).value if cookie_name in cookies else None

@sio.event(namespace='/conversations/stream')
async def connect(sid, environ):
    print(f"[connect] sid={sid}")
    session_cookie = get_cookie_from_environ(environ, settings.cookie_name)
    if not session_cookie:
        print(f"[connect] Missing session_cookie.")
        return False  # Refuse connection
    payload = verify_session_token(session_cookie)
    if not payload:
        print(f"[connect] Invalid session token: {session_cookie}")
        return False  # Refuse connection
    user = get_user_by_email(SessionLocal(), payload["sub"])
    if not user:
        print(f"[connect] User not found for email: {payload['sub']}")
        return False  # Refuse connection
    user_id = user.user_id
    await sio.save_session(sid, {'user_id': user_id}, namespace='/conversations/stream')
    print(f"[connect] User {user_id} connected.")

@sio.on('join_conversation', namespace='/conversations/stream')
async def join_conversation(sid, data):
    print(f"[join_conversation] sid={sid}, data={data}")
    session = await sio.get_session(sid, namespace='/conversations/stream')
    user_id = session.get('user_id') if session else None
    conversation_id = data.get('conversation_id')
    if not user_id or not conversation_id:
        print(f"[join_conversation] Missing user_id or conversation_id. user_id={user_id}, conversation_id={conversation_id}")
        await sio.emit('error', {'error': 'Unauthorized or missing conversation_id'}, room=sid, namespace='/conversations/stream')
        await sio.disconnect(sid, namespace='/conversations/stream')
        return
    conversation = conversation_service.get_conversation(SessionLocal(), conversation_id, user_id)
    if not conversation:
        print(f"[join_conversation] Conversation not found: {conversation_id} for user_id: {user_id}")
        await sio.emit('error', {'error': 'Conversation not found'}, room=sid, namespace='/conversations/stream')
        await sio.disconnect(sid, namespace='/conversations/stream')
        return
    await sio.save_session(sid, {'user_id': user_id, 'conversation_id': conversation_id}, namespace='/conversations/stream')
    await sio.enter_room(sid, str(conversation_id), namespace='/conversations/stream')
    print(f"[join_conversation] User {user_id} joined conversation {conversation_id}")
    await sio.emit('joined', {'message': f'Joined conversation {conversation_id}'}, room=sid, namespace='/conversations/stream')

@sio.on('message', namespace='/conversations/stream')
async def handle_message(sid, data):
    print(f"[handle_message] sid={sid}, data={data}")
    session = await sio.get_session(sid, namespace='/conversations/stream')
    user_id = session.get('user_id')
    conversation_id = session.get('conversation_id')
    if user_id is None or conversation_id is None:
        print(f"[handle_message] Missing user_id or conversation_id in session.")
        await sio.emit('error', {'error': 'Not joined to a conversation.'}, room=sid, namespace='/conversations/stream')
        return
    db: Session = SessionLocal()
    user_message = data.get('content')
    if not user_message:
        print(f"[handle_message] No user_message provided.")
        return
    conversation = db.query(conversation_service.Conversation).filter(conversation_service.Conversation.conversation_id == conversation_id).first()
    conversation_summary = conversation.summary_text if conversation and conversation.summary_text else ""
    
    last_msgs = get_last_n_messages(db, conversation_id, 4)
    last_messages = "\n".join([f"{msg.type}: {msg.content}" for msg in last_msgs])
    semantic_context = await get_semantic_context(user_message, conversation_id, top_k=3)
    semantic_results = "\n".join(semantic_context)
    slug = await classify_tool_intent_with_llm(user_message, conversation_summary, last_messages, semantic_results)
    print(f"[handle_message] slug={slug}")
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
        print(f"[handle_message] context={context}")
        llm_response = ""
        tool_messages = []
        try:
            async for chunk in stream_llm_response(user_message, context, db, user_id, slug):
                print(f"[handle_message] chunk={chunk}")
                if chunk["type"] == "ai":
                    await sio.emit('assistant', {"role": "assistant", "content": chunk["content"]}, room=sid, namespace='/conversations/stream')
                    llm_response += chunk["content"]
                elif chunk["type"] in ["tool_start", "tool_success", "tool_error"]:
                    await sio.emit('tool', {"role": "tool", "content": chunk["content"]}, room=sid, namespace='/conversations/stream')
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
        except Exception as stream_error:
            error_message = f"Error streaming LLM/tool response: {str(stream_error)}"
            print(f"[handle_message] Stream Exception: {error_message}")
            await sio.emit('assistant', {"role": "assistant", "content": error_message}, room=sid, namespace='/conversations/stream')
            return
        await sio.emit('last_chunk', {"last_chunk": True}, room=sid, namespace='/conversations/stream')
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
            await conversation_service.add_message(db, tool_message_in, user_id)
    except Exception as e:
        error_message = f"Error processing request: {str(e)}"
        print(f"[handle_message] Exception: {error_message}")
        await sio.emit('assistant', {"role": "assistant", "content": error_message}, room=sid, namespace='/conversations/stream')
        reply_in = MessageCreate(
            conversation_id=conversation_id,
            type=MessageType.AI,
            content=error_message
        )
        reply_message_obj = await conversation_service.add_message(db, reply_in, user_id)
        if reply_in.type in [MessageType.HUMAN, MessageType.AI]:
            await store_message_embedding(reply_message_obj, conversation_id)
