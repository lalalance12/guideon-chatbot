import logging
import json
from asgiref.sync import sync_to_async
from django.db.models import F
from pgvector.django import CosineDistance
from ..models import Message, Chat
from .embeddings import generate_embedding
from agno.agent import Agent
from agno.models.ollama import Ollama

logger = logging.getLogger(__name__)

# Make this a standalone function so it can be imported
async def extract_topics_from_text(text):
    """Extract potential topic mentions from text using LLM."""
    if not text or len(text.strip()) == 0:
        return None
        
    try:
        # Create the LLM agent
        try:
            llama_model = Ollama(id="llama3.1:8b-instruct-q4_1", provider="Ollama", host="http://localhost:11434")
            agent = Agent(
                name="TopicExtractionAgent",
                model=llama_model,
            )
        except Exception as e:
            logger.warning(f"Failed to initialize agent for topic extraction: {e}")
            return None
        
        # Create a topic extraction prompt
        system_prompt = """You are an expert at identifying educational topics in text.
        Your task is to extract all explicit learning topics or skills mentioned in the text.
        Return ONLY a JSON array of topics. If no clear topics are mentioned, return an empty array."""
        
        user_prompt = f"""Extract all learning topics, skills, or subjects that someone might want to take courses about from this text:

{text}

Return ONLY a JSON array of topics like ["topic1", "topic2"]. Include no other text in your response."""
        
        # Get topics from LLM
        response = await agent.arun(user_prompt)
        
        # Extract the response content
        topics_text = response.content if hasattr(response, 'content') else str(response)
        
        # Parse the JSON array
        try:
            # Clean the response text to make sure it's valid JSON
            topics_text = topics_text.strip()
            if topics_text.startswith("```json"):
                topics_text = topics_text[7:]
            if topics_text.endswith("```"):
                topics_text = topics_text[:-3]
            topics_text = topics_text.strip()
            
            topics = json.loads(topics_text)
            if isinstance(topics, list) and topics:
                logger.info(f"Extracted topics using LLM: {topics}")
                return topics
            else:
                logger.info("No topics found in text by LLM")
                return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Raw LLM response: {topics_text}")
            return None
            
    except Exception as e:
        logger.error(f"Error extracting topics with LLM: {e}")
        return None


class ChatHistoryManager:
    """Manages retrieval of chat history using various strategies."""
    
    # Initialize LLM for summarization
    @staticmethod
    async def _get_summarization_agent():
        try:
            llama_model = Ollama(id="llama3.1:8b-instruct-q4_1", provider="Ollama", host="http://localhost:11434")
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
                return message.content
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
                return None
                
            # Implement summarization
            
        except Exception as e:
            logger.error(f"Error summarizing message: {e}")
            return None
        
    @staticmethod
    async def get_last_user_message(chat_id):
        """Get the last user message before the last assistant message."""
        try:
            # Implement last user message retrieval
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
            result.append({"role": "user", "content": last_user})
        
        if last_assistant:
            result.append({"role": "assistant", "content": last_assistant})
            
        logger.info(f"Simple history retrieved {len(result)} messages")
        return result