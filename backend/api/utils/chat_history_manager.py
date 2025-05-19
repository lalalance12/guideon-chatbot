import logging
import re
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
            async for message in Message.objects.filter(
                chat_id=chat_id, 
                role='assistant'
            ).order_by('-timestamp')[:1]:
                # Return as dictionary with content renamed to text for consistency
                return {
                    "is_user": False,
                    "text": message.content,  # Use content field from Message model
                    "timestamp": message.timestamp.isoformat(),
                    "previous_topic": ChatHistoryManager._extract_topic_from_text(message.content)
                }
            return None
        except Exception as e:
            logger.error(f"Error retrieving last assistant message: {e}")
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
            
            # Use the arun method directly instead of chat.completions.create
            response = await agent.arun(user_prompt)
            
            # Extract the summary text from the response
            summary = response.content if hasattr(response, 'content') else str(response)
            
            # Clean up the summary
            summary = summary.strip()
            
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
            # Get the latest user message that isn't the current one
            # (filter for messages older than 30 seconds to avoid the current one)
            import datetime
            cutoff_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=30)
            
            async for message in Message.objects.filter(
                chat_id=chat_id, 
                role='user',
                timestamp__lt=cutoff_time  # Only get messages older than cutoff
            ).order_by('-timestamp')[:1]:
                return {
                    "is_user": True,
                    "text": message.content,  # Use content field from Message model
                    "timestamp": message.timestamp.isoformat()
                }
            return None
        except Exception as e:
            logger.error(f"Error retrieving last user message: {e}")
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
            result.append({
                "is_user": True,
                "text": last_user.get("content", ""),
                "timestamp": last_user.get("timestamp", None)
            })
        if last_assistant:
            result.append({
                "is_user": False,
                "text": last_assistant.get("content", ""),
                "timestamp": last_assistant.get("timestamp", None),
                # Extract any topic mentions for context reference resolution
                "previous_topic": ChatHistoryManager._extract_topic_from_text(last_assistant.get("content", ""))
            })
            
        logger.info(f"Simple history retrieved {len(result)} messages")
        return result

    # New helper method to extract topics from text
    @staticmethod
    def _extract_topic_from_text(text):
        """Extract potential topic mentions from text for context resolution."""
        try:
            if not text:
                return None
                
            # Extract topics using regex patterns
            topic_patterns = [
                # Look for "about X" pattern
                r'about\s+([a-zA-Z\s]+(?:programming|development|science|learning|analytics|visualization|statistics))',
                # Look for skill names
                r'(data\s+science|machine\s+learning|artificial\s+intelligence|programming|python|r\s+programming|statistics|data\s+visualization|data\s+analytics)',
                # Look for "X skills" pattern
                r'([a-zA-Z\s]+)\s+skills',
            ]
            
            for pattern in topic_patterns:
                matches = re.findall(pattern, text.lower())
                if matches:
                    # Return the first match
                    return matches[0].strip()
            
            return None
        except Exception as e:
            logger.error(f"Error extracting topic from text: {e}")
            return None