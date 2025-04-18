# filepath: c:\Users\Asus\Desktop\guideon-chatbot\backend\api\utils\query_vectors.py
import os
import sys
import numpy as np
import requests
import json
# Remove F if not used directly here after refactoring
# from django.db.models import F

# Add project root and backend directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../../..'))
backend_dir = os.path.abspath(os.path.join(current_dir, '../..'))

if project_root not in sys.path:
    sys.path.append(project_root)
if backend_dir not in sys.path:
    sys.path.append(backend_dir)


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.backend.settings')
import django
django.setup()

from api.models import Pathway
from pgvector.django import CosineDistance # Import CosineDistance here

# --- Configuration ---
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
QUERY_EMBEDDING_MODEL = "bge-m3" # Use the same model for querying

def generate_embedding(text):
    """Generates a single embedding for query text using the specified model."""
    if not text or text.isspace():
        print("Error: Cannot generate embedding for empty text.")
        return None

    payload = {
        "model": QUERY_EMBEDDING_MODEL,
        "prompt": text
    }

    try:
        # Use a reasonable timeout for query embedding
        response = requests.post(OLLAMA_EMBED_URL, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        embedding = data.get("embedding")
        if not embedding:
            print(f"Error: Received empty embedding from Ollama for model {QUERY_EMBEDDING_MODEL}.")
            return None
        return embedding
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Ollama or during request for query embedding: {e}")
        return None
    except json.JSONDecodeError as e:
         print(f"Error decoding JSON response from Ollama: {e} - Response text: {response.text}")
         return None
    except Exception as e:
        print(f"An unexpected error occurred during query embedding generation: {e}")
        return None

def search_similar_content(query_text, limit=5):
    """Searches for similar content in the database using vector similarity."""
    print(f"\nSearching for content similar to: '{query_text}'")
    query_embedding = generate_embedding(query_text)

    if not query_embedding:
        # Return an error structure consistent with expected API responses perhaps
        return {"error": "Failed to generate embedding for the query."}

    try:
        # Check if there's any data to search
        pathway_count = Pathway.objects.count()
        if pathway_count == 0:
            print("Database is empty. Returning fallback content.")
            # Consider if fallback is appropriate or if an empty list/error is better
            return create_fallback_content(query_text) # Or return []

        # Perform the vector search using pgvector
        try:
            # pgvector expects a list or numpy array
            query_embedding_vector = np.array(query_embedding) # Convert if needed

            # Perform the cosine distance search
            # Adjust filtering as needed (e.g., remove metadata filter if not applicable)
            results = Pathway.objects.annotate(
                distance=CosineDistance('embedding', query_embedding_vector)
            ).order_by('distance')[:limit]
            # Example filter (if metadata structure supports it):
            # ).filter(
            #     metadata__type__in=['role', 'functional_skill', 'enabling_skill']
            # ).order_by('distance')[:limit]


            formatted_results = []
            for result in results:
                # Safely access metadata, default to empty dict
                metadata = result.metadata if isinstance(result.metadata, dict) else {}
                formatted_results.append({
                    "text": result.text,
                    "metadata": metadata,
                    # Ensure distance is available and convert to float
                    "distance": float(result.distance) if hasattr(result, 'distance') and result.distance is not None else 1.0
                })

            if not formatted_results:
                print("Vector search returned no results. Returning fallback content.")
                return create_fallback_content(query_text) # Or return []
            else:
                print(f"Found {len(formatted_results)} similar items.")
                return formatted_results

        except Exception as e:
            # Catch specific pgvector or DB errors if possible
            print(f"Vector search database query failed: {e}")
            # Fallback might hide underlying DB issues, consider returning error
            # return create_fallback_content(query_text)
            return {"error": f"Database search failed: {e}"}

    except Exception as e:
        # Catch broader errors like DB connection issues
        print(f"Error during the search process (e.g., checking count): {e}")
        return {"error": f"An error occurred during search: {e}"}


def create_fallback_content(query_text):
    """Provides generic fallback content if vector search fails or yields no results."""
    # (Fallback content remains the same as provided previously)
    print("Providing fallback content.")
    if any(term in query_text.lower() for term in ["ai", "machine learning", "artificial intelligence", "ml"]):
        return [
            {
                "text": "AI Engineering typically requires skills in machine learning algorithms, data preprocessing, model development, MLOps, and deployment techniques. Key competencies include Python programming, understanding of neural networks, and knowledge of frameworks like TensorFlow and PyTorch.",
                "metadata": {
                    "type": "fallback",
                    "title": "AI Engineering Skills"
                }
            },
            {
                "text": "Career progression in AI often involves starting as a Junior AI Engineer, then moving to AI Engineer, Senior AI Engineer, and eventually AI Architect or AI Research Scientist positions.",
                "metadata": {
                    "type": "fallback",
                    "title": "AI Career Progression"
                }
            }
        ]
    elif any(term in query_text.lower() for term in ["data science", "data scientist", "analytics"]):
        return [
            {
                "text": "Data Scientists need skills in statistical analysis, machine learning, data visualization, and domain knowledge. They should be proficient in Python, R, SQL, and tools like Tableau or PowerBI.",
                "metadata": {
                    "type": "fallback",
                    "title": "Data Science Skills"
                }
            },
            {
                "text": "Career paths in data science typically start with Data Analyst roles, progressing to Junior Data Scientist, Data Scientist, Senior Data Scientist, and then to Lead Data Scientist or Data Science Manager.",
                "metadata": {
                    "type": "fallback",
                    "title": "Data Science Career Path"
                }
            }
        ]
    else:
        return [
            {
                "text": "Technology careers in analytics and AI require a foundation in programming, mathematics, and domain knowledge. Key technical skills include Python, SQL, cloud technologies, and data structures.",
                "metadata": {
                    "type": "fallback",
                    "title": "Tech Career Foundations"
                }
            },
            {
                "text": "Career progression in tech usually involves moving from junior roles to senior positions, then to lead or architect roles, and potentially into management or executive positions.",
                "metadata": {
                    "type": "fallback",
                    "title": "Tech Career Progression"
                }
            }
        ]

if __name__ == "__main__":
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
            print(f"  {i+1}. Title: {title} (Distance: {distance:.4f})")
            print(f"     Text: {result.get('text', '')[:100]}...")
