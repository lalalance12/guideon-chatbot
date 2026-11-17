import logging
import requests
import numpy as np

logger = logging.getLogger(__name__)

# Constants - using the same model as in query_vectors.py
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "bge-m3"  # Using the same model as your other code

async def generate_embedding(text):
    """Generate embedding for a text using Ollama's API."""
    if not text or isinstance(text, str) and text.isspace():
        logger.error("Cannot generate embedding for empty text")
        return None

    payload = {
        "model": EMBEDDING_MODEL,
        "prompt": text
    }

    try:
        response = requests.post(OLLAMA_EMBED_URL, json=payload, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        embedding = data.get("embedding")
        
        if not embedding:
            logger.error(f"Received empty embedding from Ollama for model {EMBEDDING_MODEL}")
            return None
            
        logger.debug(f"Generated embedding with vector length: {len(embedding)}")
        return embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return None