from typing import List, AsyncGenerator, Optional, Dict, Any
from langchain.chat_models import init_chat_model
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI, HarmCategory, HarmBlockThreshold
from langchain_openai import OpenAIEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage, AIMessage, ToolMessage
from app.utils.message_utils import get_last_n_messages
from app.utils.embedding_utils import add_message_embedding, query_similar_messages
from chromadb.api.types import QueryResult
from app.models.message import Message
from app.models.conversation import Conversation
from app.utils.type_utils import safe_str, safe_int
from app.constants import SYSTEM_PROMPT, N_CONTEXT_MESSAGES
from sqlalchemy.orm import Session
from app.config import settings
from app.services.composio_service import composio_service
import logging
import json


composio = composio_service.composio
logger = logging.getLogger(__name__)

def build_system_prompt(db: Session, user_id: int) -> str:
    """
    Returns the system prompt with AvailableToolkits and AllToolkits appended.
    """
    enabled_toolkits = composio_service.get_user_enabled_toolkits(db, user_id)
    prompt = SYSTEM_PROMPT.strip()
    prompt += f"\n\nAvailableToolkits: {enabled_toolkits}"
    return prompt

def get_model_and_embeddings():
    """
    Initialize and return the chat model and embeddings based on the settings.model value.
    """
    model_name = settings.model.lower()
    if model_name == "gemini":
        chat_model = init_chat_model("google_genai:gemini-2.0-flash")
        embedding_model = GoogleGenerativeAIEmbeddings(model="models/embedding-001", task_type="SEMANTIC_SIMILARITY")
    elif model_name == "openai":
        chat_model = init_chat_model("openai:gpt-4.1-mini")
        embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")
    else:
        raise ValueError(f"Invalid model: {settings.model}")
    return chat_model, embedding_model

model, embeddings = get_model_and_embeddings()
summary_model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    safety_settings={
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
)

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
    from app.schemas.message import MessageType
    message_id = safe_int(getattr(message, 'message_id', None))
    content = safe_str(getattr(message, 'content', None))
    msg_type = getattr(message, 'type', None)
    if msg_type not in [MessageType.HUMAN, MessageType.AI]:
        print(f"Skipping embedding for message {message_id} in conversation {conversation_id} of type {msg_type}")
        return
    try:
        embedding = await get_embedding(content)
        add_message_embedding(message_id, content, embedding, conversation_id)
    except Exception as embed_error:
        logger.error(f"Embedding error for message {message_id} in conversation {conversation_id}: {embed_error}")

async def generate_summary_with_llm(messages: List[Message], previous_summary: Optional[str] = None, db: Optional[Session] = None, user_id: Optional[int] = None) -> str:
    """
    Use the LLM to generate a summary of the provided messages, optionally including the previous summary.
    """
    formatted = "\n".join([f"{msg.type}: {msg.content}" for msg in messages])
    if previous_summary:
        prompt = (
            f"""
            Previous summary: {previous_summary}

            Update this summary with new content while preserving key context and ongoing threads. Prioritize new developments, remove outdated details, consolidate repetitive information, and maintain only essential context. 175 words maximum.
            """
        )
    else:
        prompt = (
            f"""
            Summarize this conversation's context, purpose, and key points in 175 maximum. Prioritize essential information, eliminate redundancy, and use concise language for efficient storage.
            """
        )

    llm_messages: List[BaseMessage] = [SystemMessage(content=prompt), HumanMessage(content=formatted)]
    response = await summary_model.ainvoke(llm_messages)
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


async def classify_tool_intent_with_llm(user_message: str, conversation_summary: str = "", last_messages: str = "", semantic_results: str = "") -> list:
    """
    Use the LLM to classify the user message into one or more of the allowed tool intent slugs.
    Returns a list of slugs as strings (e.g., ["GOOGLETASKS", "GMAIL"]).
    Now includes conversation_summary, last_messages, and semantic_results in the prompt.
    """
    allowed_slugs = composio_service.get_supported_toolkits()
    allowed_slugs_str = " ".join(allowed_slugs)
    prompt = (
        f"""
        Determine which tools are needed to fulfill the user's request from: {allowed_slugs_str}, NOTOOL, SEARCH
        **Context**: 
            
            - Conversation flow: {conversation_summary}
            - Past Interactions: {last_messages}
            
            - Semantic Results: {semantic_results}
        
        **Tool mappings**:

            - SLACKBOT: Slack messaging, channels, workspace
            - GOOGLECALENDAR: Calendar, scheduling, meetings
            - GMAIL: Email sending, reading, management
            - GOOGLETASKS: Tasks, todos, reminders
            - NOTION: Notes, docs, pages, databases
            - TWITTER: Social posts, tweets
            - SEARCH: Web search, information lookup, news search
            - NOTOOL: General chat, no tool needed

        **Rules**:

            - Use conversation context to resolve ambiguous requests
            
            - Return multiple tools if needed (comma-separated)
            
            - Consider implicit intents (e.g., "remind me" = GOOGLETASKS)
            
            - Default to NOTOOL only when clearly no tools apply

        Return only tool slug(s). No explanation.
        """
    )

    print(f"[classify_tool_intent_with_llm] prompt: {prompt}")
    llm_messages: List[BaseMessage] = [SystemMessage(content=prompt), HumanMessage(content=user_message)]
    response = await summary_model.ainvoke(llm_messages)
    if isinstance(response, AIMessage):
        slug_str = str(response.content).strip()
    elif hasattr(response, "content"):
        slug_str = str(response.content).strip()
    elif isinstance(response, str):
        slug_str = response.strip()
    else:
        slug_str = str(response).strip()
    print(f"[classify_tool_intent_with_llm] result slug(s): {slug_str}")
    slugs = [s.strip() for s in slug_str.split(",") if s.strip()]
    return slugs

async def stream_llm_response(prompt: str, context: List[str], db: Session, user_id: int, slugs: List[str]) -> AsyncGenerator[Dict[str, Any], None]:
    enabled_toolkits = composio_service.get_user_enabled_toolkits(db, user_id)
    tools_list = []
    for slug in slugs:
        if slug != "NOTOOL" and slug in enabled_toolkits:
            toolkit_tools = composio.tools.get(user_id=str(user_id), toolkits=[slug])
            if toolkit_tools:
                tools_list.extend(toolkit_tools)

        if slug == "SEARCH":
            tools_list.extend(composio.tools.get(user_id=str(user_id), tools=["COMPOSIO_SEARCH_NEWS_SEARCH"]))
            tools_list.extend(composio.tools.get(user_id=str(user_id), tools=["COMPOSIO_SEARCH_SEARCH"]))
            tools_list.extend(composio.tools.get(user_id=str(user_id), tools=["COMPOSIO_SEARCH_FINANCE_SEARCH"]))
            enabled_toolkits.append("COMPOSIO_SEARCH_NEWS_SEARCH")
            enabled_toolkits.append("COMPOSIO_SEARCH_SEARCH")
            enabled_toolkits.append("COMPOSIO_SEARCH_FINANCE_SEARCH")

    model_with_tools = model
    if tools_list:
        model_with_tools = model.bind_tools(tools_list)
    print(f"[stream_llm_response] enabled_toolkits: {enabled_toolkits}")
    print(f"[stream_llm_response] tools_list: {tools_list}")
    messages: List[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
    if context:
        messages.append(SystemMessage(content="\n Past Context: \n".join(context)))
        messages.append(SystemMessage(content="\n Available Toolkits: \n".join([str(t) for t in enabled_toolkits] if enabled_toolkits else [])))
    messages.append(HumanMessage(content=prompt))

    while True:
        first_chunk = None
        result = model_with_tools.invoke(messages)

        first_chunk = result

        if not first_chunk:
            break

        tool_calls = []
        if hasattr(first_chunk, "additional_kwargs") and "tool_calls" in first_chunk.additional_kwargs:
            tool_calls = first_chunk.additional_kwargs["tool_calls"]

        elif hasattr(first_chunk, "model_dump"):
            response_dict = first_chunk.model_dump()
            tool_calls = response_dict.get("tool_calls", [])

        if tool_calls:
            tool_results = []
            for tool_call in tool_calls:
                tool_name = tool_call.get("name") or tool_call.get("function", {}).get("name")
                tool_args = tool_call.get("args") or tool_call.get("function", {}).get("arguments")
                tool_call_id = tool_call.get("id")
                
                if isinstance(tool_args, str):
                    tool_args = json.loads(tool_args)
                yield {
                    "type": "tool_start",
                    "tool_name": tool_name,
                    "content": f"\n\n**Executing {tool_name}**\n\n"
                }
                try:
                    tool_result = composio.tools.execute(
                        tool_name,
                        tool_args,
                        user_id=str(user_id)
                    )
                    tool_results.append({
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": str(tool_result)
                    })
                    yield {
                        "type": "tool_success",
                        "tool_name": tool_name,
                        "content": f"**{tool_name} execution completed**\n\n"
                    }
                except Exception as e:
                    tool_results.append({
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": f"Error executing tool: {str(e)}"
                    })
                    yield {
                        "type": "tool_error",
                        "tool_name": tool_name,
                        "content": f"**{tool_name} failed.**\n\n"
                    }
            messages.append(first_chunk)
            for tool_result in tool_results:
                messages.append(ToolMessage(
                    content=tool_result["content"],
                    tool_call_id=tool_result["tool_call_id"]
                ))
            continue

        async for chunk in model_with_tools.astream(messages):
            if hasattr(chunk, "content"):
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
            else:
                yield {"type": "ai", "content": str(chunk)}
        break
