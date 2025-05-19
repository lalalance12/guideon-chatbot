import logging
from asgiref.sync import sync_to_async
from django.db.models import F
import numpy as np
from pgvector.django import CosineDistance
from ..models import Message, Chat
from .embeddings import generate_embedding

logger = logging.getLogger(__name__)

class ChatHistoryManager:
    """Manages retrieval of chat history using various strategies."""
    
    @staticmethod
    async def get_last_assistant_message(chat_id):
        """Get the last assistant message from the chat."""
        try:
            last = await Message.objects.filter(
                chat_id=chat_id, 
                role="assistant"
            ).order_by('-timestamp').values('content', 'timestamp').afirst()
            
            if last:
                logger.debug(f"Found last assistant message: {last['content'][:50]}...")
                return {
                    "text": last['content'],
                    "is_user": False,
                    "timestamp": last['timestamp'].isoformat() if last['timestamp'] else ""
                }
            logger.debug("No last assistant message found")
            return None
        except Exception as e:
            logger.error(f"Error getting last assistant message: {e}")
            return None
    
    @staticmethod
    async def get_semantic_history(chat_id, query, k=5):
        """Retrieve semantically similar messages from chat history."""
        try:
            # Get query embedding
            query_embedding = await generate_embedding(query)
            if not query_embedding:
                logger.warning("Could not generate embedding for query")
                return []
                
            # Convert to numpy array for vector operations
            query_embedding_vector = np.array(query_embedding)
            
            # Define the query function to be wrapped with sync_to_async
            @sync_to_async
            def get_similar_messages():
                # Find semantically similar messages using cosine distance
                return list(Message.objects.filter(
                    chat_id=chat_id, 
                    embedding__isnull=False  # Only include messages with embeddings
                ).annotate(
                    similarity=CosineDistance('embedding', query_embedding_vector)
                ).order_by('similarity')[:k].values('content', 'role', 'timestamp'))
            
            # Execute the query asynchronously
            similar_messages = await get_similar_messages()
            
            # Convert to the expected format
            return [{
                "text": msg['content'],
                "is_user": msg['role'] == "user",
                "timestamp": msg['timestamp'].isoformat() if msg['timestamp'] else ""
            } for msg in similar_messages]
            
        except Exception as e:
            logger.error(f"Error in semantic history retrieval: {e}")
            return []
    
    @staticmethod
    async def get_hybrid_history(chat_id, query, k=9):
        """
        Get hybrid chat history that combines:
        1. The last assistant message (for continuity)
        2. Top-k semantically similar messages (for relevance)
        """
        # 1) Get last assistant turn
        last = await ChatHistoryManager.get_last_assistant_message(chat_id)
        base = [last] if last else []
        
        # 2) Get top-k semantically similar messages
        sem = await ChatHistoryManager.get_semantic_history(chat_id, query, k=k)
        
        # 3) Merge, preserving the last-turn first and deduplicating
        seen = {m["text"] for m in base}
        result = base + [m for m in sem if m["text"] not in seen]
        
        logger.info(f"Hybrid history retrieved {len(result)} messages: 1 last + {len(sem)} semantic - {len(seen)} duplicates")
        return result