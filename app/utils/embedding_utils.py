from chromadb.api.types import QueryResult
from typing import List
import chromadb
from datetime import datetime
import logging
from app.config import settings

logger = logging.getLogger(__name__)

chroma_client = chromadb.HttpClient(
    host=settings.chroma_host,
    port=settings.chroma_port
)

collection = chroma_client.get_or_create_collection('messages')

def add_message_embedding(message_id: int, content: str, embedding: List[float], conversation_id: int):
    timestamp = datetime.now().isoformat()
    collection.add(
        ids=[str(message_id)],
        embeddings=[embedding],
        metadatas=[{
            "message_id": message_id, 
            "conversation_id": conversation_id,
            "timestamp": timestamp
        }],
        documents=[content],
    )
    logger.info(f"Added embedding for message {message_id} in conversation {conversation_id}")

def query_similar_messages(query_embedding: List[float], conversation_id: int, top_k: int = 10) -> QueryResult:
    SIMILARITY_THRESHOLD = 0.80
    DISTANCE_THRESHOLD = 1 - SIMILARITY_THRESHOLD

    raw_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"conversation_id": conversation_id},
        include=["documents", "metadatas", "distances"],
    )

    documents = raw_results["documents"][0]
    metadatas = raw_results["metadatas"][0]
    distances = raw_results["distances"][0]

    filtered_results = [
        {"document": doc, "metadata": meta, "distance": dist}
        for doc, meta, dist in zip(documents, metadatas, distances)
        if dist <= DISTANCE_THRESHOLD
    ]

    return filtered_results


def delete_conversation_embeddings(conversation_id: int) -> bool:
    """
    Delete all embeddings for a specific conversation.
    
    Args:
        conversation_id: The ID of the conversation to delete
        
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        collection.delete(where={"conversation_id": conversation_id})
        logger.info(f"Deleted all embeddings for conversation {conversation_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete embeddings for conversation {conversation_id}: {str(e)}")
        return False

def delete_message_embedding(message_id: int) -> bool:
    """
    Delete a specific message embedding.
    
    Args:
        message_id: The ID of the message to delete
        
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        collection.delete(ids=[str(message_id)])
        logger.info(f"Deleted embedding for message {message_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete embedding for message {message_id}: {str(e)}")
        return False
