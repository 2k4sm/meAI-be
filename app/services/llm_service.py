from typing import List, AsyncGenerator, Optional, Dict, Any
from langchain.chat_models import init_chat_model
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage, AIMessage
from app.utils.message_utils import get_last_n_messages
from app.utils.embedding_utils import add_message_embedding, query_similar_messages
from chromadb.api.types import QueryResult
from app.models.message import Message
from app.models.conversation import Conversation
from app.utils.type_utils import safe_str, safe_int
from app.constants import SYSTEM_PROMPT, N_CONTEXT_MESSAGES
from sqlalchemy.orm import Session
from app.config import settings
from langchain_core.messages import ToolMessage
from app.services.composio_service import composio_service
import logging

composio = composio_service.composio
logger = logging.getLogger(__name__)

def get_model_and_embeddings():
    """
    Initialize and return the chat model and embeddings based on the settings.model value.
    """
    model_name = settings.model.lower()
    if model_name == "gemini":
        chat_model = init_chat_model("google_genai:gemini-2.0-flash")
        embedding_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-exp-03-07")
    elif model_name == "openai":
        chat_model = init_chat_model("openai:gpt-4o-mini")
        embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")
    else:
        raise ValueError(f"Invalid model: {settings.model}")
    return chat_model, embedding_model

model, embeddings = get_model_and_embeddings()


async def get_embedding(text: str) -> List[float]:
    return embeddings.embed_query(safe_str(text))

async def get_semantic_context(user_message: str, conversation_id: int, top_k: int = 10) -> List[str]:
    embedding = await get_embedding(user_message)
    results: QueryResult = query_similar_messages(embedding, conversation_id, top_k=top_k)  # type: ignore
    docs: List[str] = []
    documents = results.get('documents')
    if isinstance(documents, list) and len(documents) > 0 and isinstance(documents[0], list):
        docs = documents[0]
    return [safe_str(doc) for doc in docs]

async def get_context_with_summary(db: Session, conversation_id: int, user_message: str, semantic_k: int = 10) -> List[str]:
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
    try:
        embedding = await get_embedding(content)
        add_message_embedding(message_id, content, embedding, conversation_id)
    except Exception as embed_error:
        logger.error(f"Embedding error for message {message_id} in conversation {conversation_id}: {embed_error}")

async def stream_llm_response(prompt: str, context: List[str], db: Session, user_id: int, slugs: list[str]) -> AsyncGenerator[Dict[str, Any], None]:
    enabled_toolkits = composio_service.get_user_enabled_toolkits(db, user_id)
    tools_list = []
    for slug in slugs:
        if slug != "NOTOOL":
            toolkit_tools = composio.tools.get(user_id=str(user_id), toolkits=[slug])
            if toolkit_tools:
                tools_list.extend(toolkit_tools)
    tools_list.extend(composio.tools.get(user_id=str(user_id), tools=["COMPOSIO_SEARCH_DUCK_DUCK_GO_SEARCH"]))
    tools_list.extend(composio.tools.get(user_id=str(user_id), tools=["COMPOSIO_SEARCH_EXA_SIMILARLINKS"]))
    tools_list.extend(composio.tools.get(user_id=str(user_id), tools=["COMPOSIO_SEARCH_NEWS_SEARCH"]))
    tools_list.extend(composio.tools.get(user_id=str(user_id), tools=["COMPOSIO_SEARCH_SEARCH"]))
    model_with_tools = model
    if tools_list:
        model_with_tools = model.bind_tools(tools_list)
    print(f"enabled_toolkits: {enabled_toolkits}")
    print(f"tools_list: {tools_list}")

    messages: List[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
    if context:
        messages.append(HumanMessage(content="\n".join(context)))
    messages.append(HumanMessage(content=prompt))
    max_tool_llm_cycles = 5
    cycles = 0
    tool_call_history = set()
    while cycles < max_tool_llm_cycles:
        cycles += 1
        first_chunk = None
        async for chunk in model_with_tools.astream(messages):
            first_chunk = chunk
            break
        if not first_chunk:
            break
        try:
            response_dict = first_chunk.model_dump()
            tool_calls = response_dict.get('tool_calls', [])
            if tool_calls:
                tool_call = tool_calls[0]
                tool_name = tool_call["name"]
                tool_args = str(tool_call.get("args", {}))
                tool_call_key = (tool_name, tool_args)
                if tool_call_key in tool_call_history:
                    messages.append(HumanMessage(content=f"The tool call '{tool_name}' with these arguments has already been executed. Please move to the next tool call or provide a final answer."))
                    continue 
                tool_call_history.add(tool_call_key)
                yield {
                    "type": "tool_start",
                    "tool_name": tool_name,
                    "content": f"\n\n**Executing {tool_name}...**\n\n"
                }
                try:
                    tool_result = composio.tools.execute(
                        tool_call['name'],
                        tool_call['args'],
                        user_id=str(user_id)
                    )
                    messages.append(ToolMessage(
                        content=str(tool_result),
                        tool_call_id=tool_call.get("id")
                    ))
                    messages.append(HumanMessage(content=f"The tool call '{tool_name}' has been completed. The response is available above. Please move to the next tool call or provide a final answer."))
                except Exception as e:
                    messages.append(ToolMessage(
                        content=f"Error executing tool: {str(e)}",
                        tool_call_id=tool_call.get("id")
                    ))
                    messages.append(HumanMessage(content=f"The tool call '{tool_name}' failed with an error. The error is available above. Please move to the next tool call or provide a final answer."))
                continue
            else:
                messages.append(first_chunk)
                if hasattr(first_chunk, "content"):
                    if isinstance(first_chunk.content, str):
                        yield {"type": "ai", "content": first_chunk.content}
                    elif isinstance(first_chunk.content, list):
                        for part in first_chunk.content:
                            if isinstance(part, str):
                                yield {"type": "ai", "content": part}
                            elif isinstance(part, dict) and "text" in part:
                                yield {"type": "ai", "content": part["text"]}
                    else:
                        yield {"type": "ai", "content": str(first_chunk.content)}
                async for chunk in model_with_tools.astream(messages):
                    if isinstance(chunk.content, str):
                        yield {"type": "ai", "content": chunk.content}
                    elif isinstance(chunk.content, list):
                        for part in chunk.content:
                            if isinstance(part, str):
                                yield {"type": "ai", "content": part}
                            elif isinstance(part, dict) and "text" in part:
                                yield {"type": "ai", "content": part["text"]}
                    else:
                        yield {"type": "ai", "content": str(chunk.content)}
                return
        except Exception as e:
            logger.error(f"Error in stream_llm_response: {str(e)}")
            break
    yield {"type": "ai", "content": "Sorry, I was unable to complete your request due to too many tool steps or an internal error."}

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


async def classify_tool_intent_with_llm(user_message: str, db: Session, user_id: int) -> list[str]:
    """
    Use the LLM to classify the user message into all relevant enabled tool intent slugs for the user.
    Returns a list of slugs (e.g., ["GOOGLETASKS", "NOTION"]).
    """
    enabled_slugs = [slug.upper() for slug in composio_service.get_user_enabled_toolkits(db, user_id)]
    allowed_slugs = enabled_slugs + ["NOTOOL"]
    allowed_slugs_str = ", ".join(allowed_slugs)
    prompt = (
        f"Classify the following user message into all relevant enabled intent slugs: "
        f"{allowed_slugs_str}. If none are appropriate, return NOTOOL. "
        f"Return a comma-separated list of slugs, nothing else. Slugs must be UPPERCASE.\n\n"
        f"User message: {user_message}"
    )
    llm_messages: List[BaseMessage] = [SystemMessage(content=prompt), HumanMessage(content=user_message)]
    response = await model.ainvoke(llm_messages)
    if isinstance(response, AIMessage):
        slug_str = str(response.content).strip().upper()
    elif hasattr(response, "content"):
        slug_str = str(response.content).strip().upper()
    elif isinstance(response, str):
        slug_str = response.strip().upper()
    else:
        slug_str = str(response).strip().upper()
    slugs = [s.strip() for s in slug_str.split(",") if s.strip()]
    valid_slugs = [s for s in slugs if s in allowed_slugs]
    if not valid_slugs or "NOTOOL" in valid_slugs:
        return ["NOTOOL"]
    return valid_slugs
