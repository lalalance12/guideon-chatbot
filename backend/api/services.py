import requests
import logging
import json
from .models import Chat, Message

logger = logging.getLogger(__name__)

OLLAMA_API_URL = "http://localhost:11434/api/generate"

def build_prompt(user_prompt: str, chat_history=None) -> str:
    """
    Builds a prompt with context and chat history for the Ollama model
    """
    system_prompt = """You are Guideon, a helpful AI assistant focused on education and learning.
You provide guidance on courses, learning paths, and educational resources.
You're friendly, supportive, and knowledgeable about various academic subjects.
You help students, scholars, and lifelong learners achieve their educational goals."""

    # If we have chat history, include it in the prompt
    history_text = ""
    if chat_history and len(chat_history) > 0:
        logger.info(f"Building prompt with {len(chat_history)} historical messages")
        for message in chat_history:
            if message.role == 'user':
                history_text += f"User: {message.content}\n"
            else:
                history_text += f"Guideon: {message.content}\n"
        logger.info(f"Chat history incorporated into prompt, history length: {len(history_text)} chars")
    else:
        logger.info("No chat history to incorporate into prompt")
    
    # Combine system prompt, history, and current user prompt
    if history_text:
        full_prompt = f"{system_prompt}\n\nPrevious conversation:\n{history_text}\n\nUser: {user_prompt}\nGuideon:"
        logger.info(f"Built prompt with history. Total length: {len(full_prompt)} chars")
        # Log a preview of the prompt
        logger.info(f"Prompt preview: {full_prompt[:200]}... [truncated] ...{full_prompt[-100:]}")
        return full_prompt
    else:
        simple_prompt = f"{system_prompt}\n\nUser: {user_prompt}\nGuideon:"
        logger.info(f"Built prompt without history. Total length: {len(simple_prompt)} chars")
        return simple_prompt

def query_ollama(user_prompt: str, chat_id=None) -> str:
    """
    Sends a query to the locally running Ollama model
    """
    try:
        # Get chat history if chat_id is provided
        chat_history = []
        if chat_id:
            try:
                chat = Chat.objects.get(id=chat_id)
                # Exclude the current message which hasn't been processed yet
                chat_history = chat.messages.all().order_by('timestamp')
                logger.info(f"Retrieved {len(chat_history)} messages for chat_id {chat_id}")
                
                # Log the messages being used for context
                for idx, msg in enumerate(chat_history):
                    logger.info(f"History message {idx+1}: {msg.role} - {msg.content[:30]}...")
                
            except Chat.DoesNotExist:
                logger.warning(f"Chat with id {chat_id} not found")
        else:
            logger.info("No chat_id provided, proceeding without chat history")
        
        headers = {"Content-Type": "application/json"}
        prompt = build_prompt(user_prompt, chat_history)
        
        data = {
            "model": "llama3.2",  # Using the specified model
            "prompt": prompt,
            "stream": False,  # Not streaming responses
        }

        logger.info(f"Sending request to Ollama API: {OLLAMA_API_URL}")
        
        response = requests.post(OLLAMA_API_URL, json=data, headers=headers)
        
        logger.info(f"Response status code: {response.status_code}")
        
        # For debugging, log the full response
        try:
            response_data = response.json()
            logger.info(f"Response received, length: {len(response_data.get('response', ''))} chars")
            return response_data["response"]
        except Exception as json_error:
            logger.error(f"Error parsing JSON response: {json_error}")
            logger.error(f"Raw response: {response.text}")
            return "Error parsing response from Ollama."
            
    except requests.RequestException as e:
        logger.error(f"Error querying Ollama: {e}")
        return "I'm having trouble connecting to my knowledge base right now. Please try again later." 