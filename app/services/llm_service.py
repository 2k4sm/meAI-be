from typing import List, AsyncGenerator, Optional, Dict, Any
from langchain.chat_models import init_chat_model
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage, AIMessage
from app.utils.message_utils import get_last_n_messages
from app.utils.embedding_utils import add_message_embedding, query_similar_messages
from app.models.message import Message
from app.models.conversation import Conversation
from app.utils.type_utils import safe_str, safe_int
from app.constants import SYSTEM_PROMPT, N_CONTEXT_MESSAGES
from sqlalchemy.orm import Session
from app.services.composio_service import composio_service

model = init_chat_model("google_genai:gemini-2.0-flash")
composio = composio_service.composio

embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-exp-03-07")

async def get_embedding(text: str) -> List[float]:
    return embeddings.embed_query(safe_str(text))

async def get_semantic_context(user_message: str, conversation_id: int, top_k: int = 5) -> List[str]:
    embedding = await get_embedding(user_message)
    results: QueryResult = query_similar_messages(embedding, conversation_id, top_k=top_k)  # type: ignore
    docs: List[str] = []
    documents = results.get('documents')
    if isinstance(documents, list) and len(documents) > 0 and isinstance(documents[0], list):
        docs = documents[0]
    return [safe_str(doc) for doc in docs]

async def get_context_with_summary(db: Session, conversation_id: int, user_message: str, semantic_k: int = 5) -> List[str]:
    """
    Returns a list of context strings: the latest summary (if any), the last N messages, and semantic search results.
    """
    conversation = db.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
    summary_text = conversation.summary_text if conversation and conversation.summary_text else None
    messages = get_last_n_messages(db, conversation_id, N_CONTEXT_MESSAGES)
    semantic_context = await get_semantic_context(user_message, conversation_id, top_k=semantic_k)
    context = []
    if summary_text:
        context.append(f"Summary: {summary_text}")
    for msg in messages:
        context.append(f"{msg.type}: {msg.content}")
    if semantic_context:
        context.append("Relevant past messages:")
        context.extend(semantic_context)
    return context

async def store_message_embedding(message: Message, conversation_id: int):
    message_id = safe_int(getattr(message, 'message_id', None))
    content = safe_str(getattr(message, 'content', None))
    embedding = await get_embedding(content)
    add_message_embedding(message_id, content, embedding, conversation_id)

async def stream_llm_response(prompt: str, context: List[str], db: Session, user_id: int) -> AsyncGenerator[str, None]:
    enabled_toolkits = composio_service.get_user_enabled_toolkits(db, user_id)
    tools_list = composio.tools.get(user_id=str(user_id), toolkits=enabled_toolkits)
    
    model_with_tools = model
    if tools_list:
        model_with_tools = model.bind_tools(tools_list)
    
    messages: List[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
    if context:
        messages.append(HumanMessage(content="\n".join(context)))
    messages.append(HumanMessage(content=prompt))
    
    first_chunk = None
    async for chunk in model_with_tools.astream(messages):
        first_chunk = chunk
        break
    
    if first_chunk:
        try:
            response_dict = first_chunk.dict() if hasattr(first_chunk, 'dict') else {}
            tool_calls = response_dict.get('tool_calls', [])
            
            if tool_calls:
                tool_results = []
                for tool_call in tool_calls:
                    try:
                        tool_result = composio.tools.execute(
                            tool_call['name'],
                            tool_call['args'],
                            user_id=str(user_id)
                        )
                        tool_results.append({
                            "tool_call_id": tool_call.get("id"),
                            "name": tool_call["name"],
                            "content": str(tool_result)
                        })
                    except Exception as e:
                        tool_results.append({
                            "tool_call_id": tool_call.get("id"),
                            "name": tool_call["name"],
                            "content": f"Error executing tool: {str(e)}"
                        })
                
                messages.append(first_chunk)
                for tool_result in tool_results:
                    from langchain_core.messages import ToolMessage
                    messages.append(ToolMessage(
                        content=tool_result["content"],
                        tool_call_id=tool_result["tool_call_id"]
                    ))
                
                async for chunk in model_with_tools.astream(messages):
                    if isinstance(chunk.content, str):
                        yield chunk.content
                    elif isinstance(chunk.content, list):
                        for part in chunk.content:
                            if isinstance(part, str):
                                yield part
                            elif isinstance(part, dict) and "text" in part:
                                yield part["text"]
                    else:
                        yield str(chunk.content)
                return
        except Exception as e:
            print(f"Error in stream_llm_response: {str(e)}")
    
    async for chunk in model_with_tools.astream(messages):
        if isinstance(chunk.content, str):
            yield chunk.content
        elif isinstance(chunk.content, list):
            for part in chunk.content:
                if isinstance(part, str):
                    yield part
                elif isinstance(part, dict) and "text" in part:
                    yield part["text"]
        else:
            yield str(chunk.content)

async def generate_summary_with_llm(messages: List[Message], previous_summary: Optional[str] = None) -> str:
    """
    Use the LLM to generate a summary of the provided messages, optionally including the previous summary.
    """
    formatted = "\n".join([f"{msg.type}: {msg.content}" for msg in messages])
    if previous_summary:
        prompt = (
            "Given the previous summary and the following new messages, create an updated concise summary that captures the main points and context for future reference. "
            f"Previous summary:\n{previous_summary}\n\nNew messages:\n{formatted}"
        )
    else:
        prompt = (
            "Summarize the following conversation messages in a concise way, capturing the main points and context for future reference. "
        )
    llm_messages: List[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
    response = await model.ainvoke(llm_messages)
    if isinstance(response, AIMessage):
        return str(response.content)
    elif isinstance(response, list):
        parts = []
        for part in response:
            if isinstance(part, str):
                parts.append(part)
            elif hasattr(part, "content") and not isinstance(part, tuple):
                parts.append(str(part.content))
        return " ".join(parts)
    elif hasattr(response, "content"):
        return str(response.content)
    return str(response)
