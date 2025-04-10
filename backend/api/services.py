import requests
import logging
import json

logger = logging.getLogger(__name__)

OLLAMA_API_URL = "http://localhost:11434/api/generate"

def build_prompt(user_prompt: str) -> str:
    """
    Builds a prompt with context for the Ollama model
    """
    return f"""You are Guideon, a helpful AI assistant focused on education and learning.
You provide guidance on courses, learning paths, and educational resources.
You're friendly, supportive, and knowledgeable about various academic subjects.
You help students, scholars, and lifelong learners achieve their educational goals.

{user_prompt}"""

def query_ollama(user_prompt: str) -> str:
    """
    Sends a query to the locally running Ollama model
    """
    try:
        headers = {"Content-Type": "application/json"}
        data = {
            "model": "llama3.2",  # Using the specified model
            "prompt": build_prompt(user_prompt),
            "stream": False,  # Not streaming responses
        }

        logger.info(f"Sending request to Ollama API: {OLLAMA_API_URL}")
        logger.info(f"Request data: {json.dumps(data)}")
        
        response = requests.post(OLLAMA_API_URL, json=data, headers=headers)
        
        logger.info(f"Response status code: {response.status_code}")
        
        # For debugging, log the full response
        try:
            response_data = response.json()
            logger.info(f"Response data: {json.dumps(response_data)}")
            return response_data["response"]
        except Exception as json_error:
            logger.error(f"Error parsing JSON response: {json_error}")
            logger.error(f"Raw response: {response.text}")
            return "Error parsing response from Ollama."
            
    except requests.RequestException as e:
        logger.error(f"Error querying Ollama: {e}")
        return "I'm having trouble connecting to my knowledge base right now. Please try again later." 