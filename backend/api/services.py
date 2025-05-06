import requests
import logging
import json
import time
from .models import Chat, Message
from agno.agent import RunResponse
from .agents.career_agent import career_agent, knowledge_base_tool
from .utils.intent_classifier import classify_intent

logger = logging.getLogger(__name__)

OLLAMA_API_URL = "http://localhost:11434/api/generate"

def build_prompt(user_prompt: str, chat_history=None) -> str:
    """
    Builds a prompt with context and chat history for the Ollama model
    """
    system_prompt = """You are Guideon, a specialist in the Philippine Skills Framework for Analytics & AI (PSF-AAI).
You provide guidance on the PSF-AAI framework, which defines skills, roles, and proficiency levels for analytics and AI careers in the Philippines.
When asked about topics outside the PSF-AAI framework, explain that you specialize in this framework and suggest related topics within it.
The PSF-AAI framework was developed by the Analytics & AI Association of the Philippines (AAP) and the Department of Information and Communications Technology (DICT)."""

    # If we have chat history, include it in the prompt
    history_text = ""
    if chat_history and len(chat_history) > 0:
        logger.debug(f"Building prompt with {len(chat_history)} historical messages")
        for message in chat_history:
            if message.role == 'user':
                history_text += f"User: {message.content}\n"
            else:
                history_text += f"Guideon: {message.content}\n"
    
    # Combine system prompt, history, and current user prompt
    if history_text:
        full_prompt = f"{system_prompt}\n\nPrevious conversation:\n{history_text}\n\nUser: {user_prompt}\nGuideon:"
        return full_prompt
    else:
        simple_prompt = f"{system_prompt}\n\nUser: {user_prompt}\nGuideon:"
        return simple_prompt


def query_with_agent(user_prompt: str, chat_id=None) -> str:
    logger.info(f"===== PROCESSING NEW QUERY =====")
    logger.info(f"User prompt: {user_prompt[:50]}..." if len(user_prompt) > 50 else user_prompt)
    start_time = time.time()
    
    # 1. Gather chat history for Phidata AND internal use
    chat_history = []
    phidata_history = []
    if chat_id:
        try:
            chat = Chat.objects.get(id=chat_id)
            phidata_history = []
            logger.debug(f"Loading chat history for chat ID: {chat_id}")
            for msg in chat.messages.all().order_by('timestamp'):
                chat_history.append(msg)
                role = "user" if msg.role == "user" else "assistant"
                phidata_history.append({"role": role, "content": msg.content})
            logger.debug(f"Loaded {len(chat_history)} messages from history")
        except Chat.DoesNotExist:
            logger.warning(f"Chat with id {chat_id} not found")

    # 2. Classify intent
    intent = None
    confidence = 0.0
    try:
        logger.debug("Classifying intent...")
        intent_enum, confidence = classify_intent(user_prompt, chat_history)
        intent = intent_enum.value
        logger.info(f"✅ Query intent classified as: {intent} (confidence: {confidence:.2f})")
    except Exception as e:
        logger.error(f"❌ Intent classification failed: {e}")

    # 3. Call the agent with proper try/fallback
    try:
        logger.debug(f"Calling career agent with intent: {intent}")
        logger.debug(f"Passing conversation history with {len(phidata_history) if phidata_history else 0} messages")
        
        run_resp = career_agent.run(
            user_prompt,
            session_id=str(chat_id) if chat_id else None,
            conversation_history=phidata_history or None,
            intent=intent,
            intent_confidence=confidence,
        )
        
        processing_time = time.time() - start_time
        logger.info(f"✅ Agent response generated successfully in {processing_time:.2f}s")
        return run_resp.content

    except Exception as agent_error:
        logger.error(f"❌ Agent execution failed: {agent_error}")

        if hasattr(agent_error, "run_log"):
            logger.error(f"Last run-log:\n{agent_error.run_log}")
        
        logger.info("Attempting fallback...")
        # Try fallback or return PSF-AAI info
        try:
            return fallback_query_ollama(user_prompt, chat_id)
        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {fallback_error}")
            return """
I apologize for the technical issue. I specialize in the Philippine Skills Framework for Analytics & Artificial Intelligence (PSF-AAI), a structured competency map developed by the Analytics & AI Association of the Philippines (AAP) and the Department of Information and Communications Technology (DICT).

The PSF-AAI defines career roles, functional skills with proficiency levels 1-6, and enabling skills for the analytics and AI sector in the Philippines.

Would you like to know about specific analytics or AI skills, career roles, or progression paths in the PSF-AAI framework?
"""

def fallback_query_ollama(user_prompt: str, chat_id=None) -> str:
    """
    Original Ollama query function, kept as fallback
    """
    try:
        # Get chat history if chat_id is provided
        chat_history = []
        if chat_id:
            try:
                chat = Chat.objects.get(id=chat_id)
                chat_history = chat.messages.all().order_by('timestamp')
                logger.info(f"Retrieved {len(chat_history)} messages for chat_id {chat_id}")
            except Chat.DoesNotExist:
                logger.warning(f"Chat with id {chat_id} not found")
        
        headers = {"Content-Type": "application/json"}
        prompt = build_prompt(user_prompt, chat_history)
        
        data = {
            "model": "llama3.1:8b-instruct-q4_1",
            "prompt": prompt,
            "stream": False,
        }

        logger.info("Sending request to Ollama API")
        
        response = requests.post(OLLAMA_API_URL, json=data, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"Ollama API error: {response.status_code}")
            return "Error getting response from language model."
        
        try:
            response_data = response.json()
            return response_data["response"]
        except Exception as json_error:
            logger.error(f"Error parsing JSON response: {json_error}")
            return "Error parsing response from Ollama."
            
    except requests.RequestException as e:
        logger.error(f"Error querying Ollama: {e}")
        return "I'm having trouble connecting to my knowledge base right now. Please try again later."

def query_ollama(user_prompt: str, chat_id=None) -> str:
    """
    Main entry point for query processing
    """
    return query_with_agent(user_prompt, chat_id)