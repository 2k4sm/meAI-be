from chromadb.api.types import QueryResult
from typing import List
import chromadb
from app.config import settings

chroma_client = chromadb.HttpClient(
    host=settings.chroma_host,
    port=settings.chroma_port
)

collection = chroma_client.get_or_create_collection('messages')

def add_message_embedding(message_id: int, content: str, embedding: List[float], conversation_id: int):
    collection.add(
        ids=[str(message_id)],
        embeddings=[embedding],
        metadatas=[{"message_id": message_id, "conversation_id": conversation_id}],
        documents=[content],
    )

def query_similar_messages(query_embedding: List[float], conversation_id: int, top_k: int = 10) -> QueryResult:
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"conversation_id": conversation_id},
        include=["documents", "metadatas", "distances"],
    )
    return results 