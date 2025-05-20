import logging
import numpy as np
from asgiref.sync import sync_to_async
from django.db.models import F
from pgvector.django import CosineDistance
from ..models import Message, Chat
from .embeddings import generate_embedding
from agno.agent import Agent
from agno.models.ollama import Ollama

logger = logging.getLogger(__name__)

class ChatHistoryManager:
    """Manages retrieval of chat history using various strategies."""
    
    # Initialize LLM for summarization
    @staticmethod
    async def _get_summarization_agent():
        try:
            llama_model = Ollama(id="llama3.1:8b-instruct-q2_K", provider="Ollama", host="http://localhost:11434")
            agent = Agent(
                name="SummarizationAgent",
                model=llama_model,
            )
            return agent
        except Exception as e:
            logger.error(f"Failed to initialize summarization agent: {e}")
            return None
    
    @staticmethod
    async def get_last_assistant_message(chat_id):
        """Get the last assistant message from the chat."""
        try:
            last = await Message.objects.filter(
                chat_id=chat_id, 
                role="assistant"
            ).order_by('-timestamp').values('content', 'timestamp').afirst()
            
            if last:
                content = last['content']
                logger.debug(f"Found last assistant message: {content[:50]}...")
                
                # Check if message exceeds 300 characters and needs summarization
                if len(content) > 300:
                    logger.info(f"Message length ({len(content)}) exceeds 300 chars, summarizing...")
                    # Use LLM to summarize the message
                    summarized = await ChatHistoryManager.summarize_message(content)
                    return {
                        "text": summarized,
                        "is_user": False,
                        "timestamp": last['timestamp'].isoformat() if last['timestamp'] else "",
                        "summarized": True  # Flag to indicate this is a summary
                    }
                
                return {
                    "text": content,
                    "is_user": False,
                    "timestamp": last['timestamp'].isoformat() if last['timestamp'] else ""
                }
            logger.debug("No last assistant message found")
            return None
        except Exception as e:
            logger.error(f"Error getting last assistant message: {e}")
            return None
    
    @staticmethod
    async def summarize_message(content):
        """Summarize a message using an LLM to capture its essence."""
        try:
            # Get the summarization agent
            agent = await ChatHistoryManager._get_summarization_agent()
            
            if not agent:
                # Fallback to simple truncation if agent initialization fails
                return content[:497] + "..."
            
            # Create a summarization prompt
            prompt = f"""You are an expert summarizer. Your task is to capture the essence of a message 
            while staying under 300 characters. Preserve key information, main points, and the original tone.
            Include critical details and maintain any structured format if present.

            Summarize the following message in under 300 characters while capturing its essence:

            {content}

            Your summary:"""
            
            # Use the arun method directly instead of chat.completions.create
            response = await agent.arun(prompt)
            
            # Extract content from response object
            summary = response.content if hasattr(response, 'content') else str(response)
            summary = summary.strip()
            
            # Double-check length and truncate if still too long
            if len(summary) > 300:
                summary = summary[:497] + "..."
                
            return summary
        except Exception as e:
            logger.error(f"Error using LLM for summarization: {e}")
            # Return truncated original as fallback
            return content[:497] + "..."
    
    @staticmethod
    async def get_last_user_message(chat_id):
        """Get the last user message before the last assistant message."""
        try:
            # First get the timestamp of the last assistant message
            last_assistant = await Message.objects.filter(
                chat_id=chat_id,
                role="assistant"
            ).order_by('-timestamp').values('timestamp').afirst()
            
            # If no assistant message found, just get the last user message
            if not last_assistant:
                last_user = await Message.objects.filter(
                    chat_id=chat_id,
                    role="user"
                ).order_by('-timestamp').values('content', 'timestamp').afirst()
            else:
                # Get the most recent user message that came before the last assistant message
                last_user = await Message.objects.filter(
                    chat_id=chat_id,
                    role="user",
                    timestamp__lt=last_assistant['timestamp']
                ).order_by('-timestamp').values('content', 'timestamp').afirst()
            
            if last_user:
                logger.debug(f"Found last user message: {last_user['content'][:50]}...")
                return {
                    "text": last_user['content'],
                    "is_user": True,
                    "timestamp": last_user['timestamp'].isoformat() if last_user['timestamp'] else ""
                }
            logger.debug("No last user message found")
            return None
        except Exception as e:
            logger.error(f"Error getting last user message: {e}")
            return None
    
    @staticmethod
    async def get_simple_history(chat_id):
        """Get a simple chat history with just the last user and assistant messages."""
        # Get the last user and assistant messages
        last_user = await ChatHistoryManager.get_last_user_message(chat_id)
        last_assistant = await ChatHistoryManager.get_last_assistant_message(chat_id)
        
        # Combine them in chronological order
        result = []
        if last_user:
            result.append(last_user)
        if last_assistant:
            result.append(last_assistant)
            
        logger.info(f"Simple history retrieved {len(result)} messages")
        return result

    @staticmethod
    async def get_last_n_turns(chat_id, n=4):
        """Get the last n messages in the sequence: user, assistant, user, assistant (excluding the latest user prompt). Summarize assistant messages if too long."""
        try:
            # Create a sync function to fetch messages
            @sync_to_async
            def get_messages():
                return list(Message.objects.filter(
                    chat_id=chat_id
                ).order_by('-timestamp').values('content', 'role', 'timestamp')[:n+1])
            
            # Await the sync-to-async wrapped function
            messages = await get_messages()
            
            filtered = []
            user_count = 0
            for msg in messages:
                if msg['role'] == 'user':
                    user_count += 1
                if user_count > 1:
                    continue
                filtered.append(msg)
                if len(filtered) == n:
                    break
            filtered = list(reversed(filtered))
            
            result = []
            for msg in filtered:
                text = msg['content']
                if msg['role'] == 'assistant' and len(text) > 300:
                    # Summarize long assistant messages
                    text = await ChatHistoryManager.summarize_message(text)
                result.append({
                    'text': text,
                    'is_user': msg['role'] == 'user',
                    'timestamp': msg['timestamp'].isoformat() if msg['timestamp'] else ''
                })
            logger.info(f"Last {n} turns retrieved {len(result)} messages (with assistant summarization if needed)")
            return result
        except Exception as e:
            logger.error(f"Error getting last {n} turns: {e}")
            return []