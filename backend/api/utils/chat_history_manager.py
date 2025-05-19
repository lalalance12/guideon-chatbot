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
            llama_model = Ollama(id="llama3.1:8b-instruct-q8_0", provider="Ollama", host="http://localhost:11434")
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
                
                # Check if message exceeds 500 characters and needs summarization
                if len(content) > 500:
                    logger.info(f"Message length ({len(content)}) exceeds 500 chars, summarizing...")
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
            system_prompt = """You are an expert summarizer. Your task is to capture the essence of a message 
            while staying under 500 characters. Preserve key information, main points, and the original tone.
            Include critical details and maintain any structured format if present."""
            
            user_prompt = f"""Summarize the following message in under 500 characters while capturing its essence:

{content}

Your summary:"""
            
            # Get response from the LLM
            response = await agent.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=250  # Limiting tokens to ensure we stay under character limit
            )
            
            summary = response.choices[0].message.content.strip()
            
            # Double-check length and truncate if still too long
            if len(summary) > 500:
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