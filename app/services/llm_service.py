import os
from typing import List, AsyncGenerator
from chromadb.api.types import QueryResult
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from app.services.embedding_service import query_similar_messages, add_message_embedding
from app.models.message import Message
from app.config import settings

SYSTEM_PROMPT = "You are a helpful AI assistant."

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    convert_system_message_to_human=True
)
embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-exp-03-07")

def _safe_str(val) -> str:
    return str(val) if val is not None else ""

def _safe_int(val) -> int:
    try:
        return int(val)
    except Exception:
        return 0

async def get_embedding(text: str) -> List[float]:
    return embeddings.embed_query(_safe_str(text))

async def get_context(user_message: str, conversation_id: int, top_k: int = 5) -> List[str]:
    embedding = await get_embedding(user_message)
    results: QueryResult = query_similar_messages(embedding, conversation_id, top_k=top_k)  # type: ignore
    docs: List[str] = []
    documents = results.get('documents')
    if isinstance(documents, list) and len(documents) > 0 and isinstance(documents[0], list):
        docs = documents[0]
    return [_safe_str(doc) for doc in docs]

async def store_message_embedding(message: Message, conversation_id: int):
    message_id = _safe_int(getattr(message, 'message_id', None))
    content = _safe_str(getattr(message, 'content', None))
    embedding = await get_embedding(content)
    add_message_embedding(message_id, content, embedding, conversation_id)

async def stream_llm_response(prompt: str, context: List[str]) -> AsyncGenerator[str, None]:
    messages: List[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
    if context:
        messages.append(HumanMessage(content="\n".join(context)))
    messages.append(HumanMessage(content=prompt))
    async for chunk in llm.astream(messages):
        if isinstance(chunk.content, str):
            yield chunk.content
        elif isinstance(chunk.content, list):
            for part in chunk.content:
                if isinstance(part, str):
                    yield part
                elif isinstance(part, dict) and "text" in part:
                    yield part["text"]
