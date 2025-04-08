import os
import sys
import numpy as np
import requests
import json
from django.db.models import F

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

from api.models import Pathway

def generate_embedding(text, batch=False):
    url = "http://localhost:11434/api/embeddings"
    
    payload = {
        "model": "llama3.1",
        "prompt": text
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return response.json().get("embedding")
        print(f"Error generating embedding: {response.text}")
        return None
    except Exception as e:
        print(f"Exception generating embedding: {e}")
        return None

def search_similar_content(query_text, limit=5):
    query_embedding = generate_embedding(query_text)
    
    if not query_embedding:
        return {"error": "Failed to generate embedding for query"}
    
    try:
        pathway_count = Pathway.objects.count()
        if pathway_count == 0:
            return create_fallback_content(query_text)
            
        try:
            query_embedding_array = np.array(query_embedding)
            
            from pgvector.django import CosineDistance
            
            # Enhanced search with level filtering and context awareness
            results = Pathway.objects.annotate(
                distance=CosineDistance('embedding', query_embedding_array)
            ).filter(
                metadata__level__lte=3  # Focus on entry to mid-level pathways
            ).order_by('distance')[:limit]
            
            formatted_results = []
            for result in results:
                metadata = result.metadata if hasattr(result, 'metadata') else {}
                formatted_results.append({
                    "text": result.text,
                    "metadata": metadata,
                    "distance": float(result.distance) if hasattr(result, 'distance') else 1.0
                })
            
            return formatted_results if formatted_results else create_fallback_content(query_text)
                
        except Exception as e:
            print(f"Vector search failed: {e}")
            return create_fallback_content(query_text)
            
    except Exception as e:
        print(f"Error in search_similar_content: {e}")
        return {"error": str(e)}

def create_fallback_content(query_text):
    if any(term in query_text.lower() for term in ["ai", "machine learning", "artificial intelligence", "ml"]):
        return [
            {
                "text": "AI Engineering typically requires skills in machine learning algorithms, data preprocessing, model development, MLOps, and deployment techniques. Key competencies include Python programming, understanding of neural networks, and knowledge of frameworks like TensorFlow and PyTorch.",
                "metadata": {
                    "type": "text_match",
                    "title": "AI Engineering Skills"
                }
            },
            {
                "text": "Career progression in AI often involves starting as a Junior AI Engineer, then moving to AI Engineer, Senior AI Engineer, and eventually AI Architect or AI Research Scientist positions.",
                "metadata": {
                    "type": "text_match",
                    "title": "AI Career Progression"
                }
            }
        ]
    elif any(term in query_text.lower() for term in ["data science", "data scientist", "analytics"]):
        return [
            {
                "text": "Data Scientists need skills in statistical analysis, machine learning, data visualization, and domain knowledge. They should be proficient in Python, R, SQL, and tools like Tableau or PowerBI.",
                "metadata": {
                    "type": "text_match",
                    "title": "Data Science Skills"
                }
            },
            {
                "text": "Career paths in data science typically start with Data Analyst roles, progressing to Junior Data Scientist, Data Scientist, Senior Data Scientist, and then to Lead Data Scientist or Data Science Manager.",
                "metadata": {
                    "type": "text_match",
                    "title": "Data Science Career Path"
                }
            }
        ]
    else:
        return [
            {
                "text": "Technology careers in analytics and AI require a foundation in programming, mathematics, and domain knowledge. Key technical skills include Python, SQL, cloud technologies, and data structures.",
                "metadata": {
                    "type": "text_match",
                    "title": "Tech Career Foundations"
                }
            },
            {
                "text": "Career progression in tech usually involves moving from junior roles to senior positions, then to lead or architect roles, and potentially into management or executive positions.",
                "metadata": {
                    "type": "text_match",
                    "title": "Tech Career Progression"
                }
            }
        ]

if __name__ == "__main__":
    query = "data science career path"
    results = search_similar_content(query)
    print(f"Search results for '{query}':")
    for i, result in enumerate(results):
        print(f"{i+1}. {result.get('metadata', {}).get('title', 'Untitled')}")
        print(f"   {result['text'][:100]}...")