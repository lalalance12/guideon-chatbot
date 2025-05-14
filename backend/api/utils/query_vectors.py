import os
import sys
import numpy as np
import requests
import json
import logging
import time
from asgiref.sync import sync_to_async

# Setup logger
logger = logging.getLogger(__name__)

from api.models import KnowledgeChunk, KnowledgeSource
from pgvector.django import CosineDistance

# --- Configuration ---
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
QUERY_EMBEDDING_MODEL = "bge-m3"  # Use the same model for querying

def generate_embedding(text):
    """Generates a single embedding for query text using the specified model."""
    if not text or text.isspace():
        logger.error("Error: Cannot generate embedding for empty text.")
        return None

    payload = {
        "model": QUERY_EMBEDDING_MODEL,
        "prompt": text
    }

    start_time = time.time()
    try:
        # Use a reasonable timeout for query embedding
        response = requests.post(OLLAMA_EMBED_URL, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        embedding = data.get("embedding")
        
        if not embedding:
            logger.error(f"Error: Received empty embedding from Ollama for model {QUERY_EMBEDDING_MODEL}.")
            return None
            
        embedding_time = time.time() - start_time
        logger.debug(f"Generated embedding in {embedding_time:.2f}s, vector length: {len(embedding)}")
        return embedding
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to Ollama or during request for query embedding: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON response from Ollama: {e} - Response text: {response.text}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during query embedding generation: {e}")
        return None

def search_similar_content(query_text, limit=5, section=None):
    """
    Searches for similar content in the database using vector similarity.

    Args:
        query_text: The text to search for
        limit: Maximum number of results to return
        section: Optional section filter (e.g., "functional_skills", "enabling_skills")
    """
    logger.info(f"Searching for content similar to: '{query_text}'")
    if section:
        logger.info(f"Filtering by section: {section}")
        
    start_time = time.time()
    query_embedding = generate_embedding(query_text)

    if not query_embedding:
        logger.error("Failed to generate embedding for the query")
        return [] 

    try:
        # Perform the vector search using pgvector
        query_embedding_vector = np.array(query_embedding)

        # Start with a broader search to ensure we get enough results
        initial_limit = min(limit * 3, 25)  # Get more results initially for filtering

        # Filter by section if provided
        if section:
            results = KnowledgeChunk.objects.filter(
                metadata__psf_section=section
            ).annotate(
                distance=CosineDistance('embedding', query_embedding_vector)
            ).order_by('distance')[:initial_limit]
        else:
            results = KnowledgeChunk.objects.annotate(
                distance=CosineDistance('embedding', query_embedding_vector)
            ).order_by('distance')[:initial_limit]

        formatted_results = []
        for result in results:
            metadata = result.metadata if isinstance(result.metadata, dict) else {}
            formatted_results.append({
                "text": result.text,
                "metadata": metadata,
                "distance": float(result.distance) if hasattr(result, 'distance') and result.distance is not None else 1.0
            })

        search_time = time.time() - start_time
        logger.info(f"Search completed in {search_time:.2f}s, found {len(formatted_results)} results")
        return formatted_results[:limit]

    except Exception as e:
        logger.error(f"Error during the search process: {e}")
        return {"error": f"An error occurred during search: {e}"}

# New async version of the search function
async def search_similar_content_async(query_text, limit=5, section=None):
    """
    Async version of search_similar_content that properly handles async context.

    Args:
        query_text: The text to search for
        limit: Maximum number of results to return
        section: Optional section filter (e.g., "functional_skills", "enabling_skills")
    """
    logger.info(f"Async searching for content similar to: '{query_text}'")
    if section:
        logger.info(f"Filtering by section: {section}")
        
    start_time = time.time()
    query_embedding = generate_embedding(query_text)

    if not query_embedding:
        logger.error("Failed to generate embedding for the query")
        return [] 

    try:
        # Perform the vector search using pgvector
        query_embedding_vector = np.array(query_embedding)

        # Start with a broader search to ensure we get enough results
        initial_limit = min(limit * 3, 25)  # Get more results initially for filtering

        # Define the query function to be wrapped with sync_to_async
        def perform_vector_search():
            if section:
                return list(KnowledgeChunk.objects.filter(
                    metadata__psf_section=section
                ).annotate(
                    distance=CosineDistance('embedding', query_embedding_vector)
                ).order_by('distance')[:initial_limit])
            else:
                return list(KnowledgeChunk.objects.annotate(
                    distance=CosineDistance('embedding', query_embedding_vector)
                ).order_by('distance')[:initial_limit])

        # Execute the query asynchronously
        results = await sync_to_async(perform_vector_search)()

        formatted_results = []
        for result in results:
            metadata = result.metadata if isinstance(result.metadata, dict) else {}
            formatted_results.append({
                "text": result.text,
                "metadata": metadata,
                "distance": float(result.distance) if hasattr(result, 'distance') and result.distance is not None else 1.0
            })

        search_time = time.time() - start_time
        logger.info(f"Search completed in {search_time:.2f}s, found {len(formatted_results)} results")
        return formatted_results[:limit]

    except Exception as e:
        logger.error(f"Error during the search process: {e}")
        return {"error": f"An error occurred during search: {e}"}

def create_fallback_content(query_text):
    """Provides generic fallback content if vector search fails or yields no results."""
    logger.warning("Providing fallback content for query: {query_text}")
    if any(term in query_text.lower() for term in ["ai", "machine learning", "artificial intelligence", "ml"]):
        return [
            {
                "text": "AI Engineering typically requires skills in machine learning algorithms, data preprocessing, model development, MLOps, and deployment techniques. Key competencies include Python programming, understanding of neural networks, and knowledge of frameworks like TensorFlow and PyTorch.",
                "metadata": {
                    "type": "fallback",
                    "title": "AI Engineering Skills"
                },
                "distance": 0.5  # Default distance for fallback content
            },
            {
                "text": "Career progression in AI often involves starting as a Junior AI Engineer, then moving to AI Engineer, Senior AI Engineer, and eventually AI Architect or AI Research Scientist positions.",
                "metadata": {
                    "type": "fallback",
                    "title": "AI Career Progression"
                },
                "distance": 0.6
            }
        ]
    elif any(term in query_text.lower() for term in ["data science", "data scientist", "analytics"]):
        return [
            {
                "text": "Data Scientists need skills in statistical analysis, machine learning, data visualization, and domain knowledge. They should be proficient in Python, R, SQL, and tools like Tableau or PowerBI.",
                "metadata": {
                    "type": "fallback",
                    "title": "Data Science Skills"
                },
                "distance": 0.5
            },
            {
                "text": "Career paths in data science typically start with Data Analyst roles, progressing to Junior Data Scientist, Data Scientist, Senior Data Scientist, and then to Lead Data Scientist or Data Science Manager.",
                "metadata": {
                    "type": "fallback",
                    "title": "Data Science Career Path"
                },
                "distance": 0.6
            }
        ]
    else:
        return [
            {
                "text": "Technology careers in analytics and AI require a foundation in programming, mathematics, and domain knowledge. Key technical skills include Python, SQL, cloud technologies, and data structures.",
                "metadata": {
                    "type": "fallback",
                    "title": "Tech Career Foundations"
                },
                "distance": 0.5
            },
            {
                "text": "Career progression in tech usually involves moving from junior roles to senior positions, then to lead or architect roles, and potentially into management or executive positions.",
                "metadata": {
                    "type": "fallback",
                    "title": "Tech Career Progression"
                },
                "distance": 0.6
            }
        ]

if __name__ == "__main__":
    # Setup console logging for direct script execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Example usage for testing the search function directly
    test_query = "data science career path"
    search_results = search_similar_content(test_query)

    print(f"\nSearch results for '{test_query}':")
    if isinstance(search_results, dict) and "error" in search_results:
         print(f"  Error: {search_results['error']}")
    elif not search_results:
         print("  No results found.")
    else:
        for i, result in enumerate(search_results):
            title = result.get('metadata', {}).get('title', 'Untitled')
            distance = result.get('distance', 'N/A')
            chunk_type = result.get('metadata', {}).get('type', 'unknown')
            print(f"  {i+1}. Title: {title} (Type: {chunk_type}, Distance: {distance:.4f})")
            print(f"     Text: {result.get('text', '')[:100]}...")