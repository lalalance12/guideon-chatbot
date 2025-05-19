import os
import sys
import numpy as np
import requests
import json
import logging
import time
from asgiref.sync import sync_to_async
from typing import List, Dict, Any, Optional

# Setup logger
logger = logging.getLogger(__name__)

from api.models import KnowledgeChunk, KnowledgeSource
from pgvector.django import CosineDistance
from django.db.models import Q

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

def search_similar_content(query_text, limit=5, section=None, entity_type=None):
    """
    Searches for similar content in the database using vector similarity.

    Args:
        query_text: The text to search for
        limit: Maximum number of results to return
        section: Optional section filter (e.g., "functional_skills", "enabling_skills")
        entity_type: Optional entity type filter (e.g., "job_role", "functional_skill")
    """
    logger.info(f"Searching for content similar to: '{query_text}'")
    if section:
        logger.info(f"Filtering by section: {section}")
    if entity_type:
        logger.info(f"Filtering by entity type: {entity_type}")
        
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

        # Build query with filters
        query = KnowledgeChunk.objects.all()
        
        # Apply filters if provided
        if section:
            query = query.filter(metadata__psf_section=section)
        
        if entity_type:
            query = query.filter(metadata__entity_type=entity_type)
        
        # Execute the vector search
        results = query.annotate(
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

# Async version of the search function
async def search_similar_content_async(query_text, limit=5, section=None, entity_type=None):
    """
    Async version of search_similar_content that properly handles async context.

    Args:
        query_text: The text to search for
        limit: Maximum number of results to return
        section: Optional section filter (e.g., "functional_skills", "enabling_skills")
        entity_type: Optional entity type filter (e.g., "job_role", "functional_skill")
    """
    logger.info(f"Async searching for content similar to: '{query_text}'")
    if section:
        logger.info(f"Filtering by section: {section}")
    if entity_type:
        logger.info(f"Filtering by entity type: {entity_type}")
        
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
            query = KnowledgeChunk.objects.all()
            
            # Apply filters if provided
            if section:
                query = query.filter(metadata__psf_section=section)
            
            if entity_type:
                query = query.filter(metadata__entity_type=entity_type)
            
            # Execute the vector search
            return list(query.annotate(
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

async def get_related_content_by_id(content_id, relation_type='all', limit=5):
    """
    Retrieves content related to a specific item by ID through explicit relationships.
    
    Args:
        content_id: The ID of the content item to find relations for
        relation_type: Type of relationship to follow ('skills', 'roles', 'all')
        limit: Maximum number of results to return
    """
    try:
        # Define the query function to be wrapped with sync_to_async
        def get_source_item():
            return list(KnowledgeChunk.objects.filter(
                metadata__id=content_id
            ))
            
        # Execute query asynchronously
        source_item = await sync_to_async(get_source_item)()
        
        if not source_item:
            logger.warning(f"No item found with ID: {content_id}")
            return []
            
        source_metadata = source_item[0].metadata
        source_type = source_metadata.get('type', '')
        source_entity_type = source_metadata.get('entity_type', '')
        
        related_ids = []
        
        # Extract related IDs based on relationship type
        if (source_type == 'whole_role' or source_entity_type == 'job_role') and relation_type in ['skills', 'all']:
            # Get IDs of skills required for this role
            for skill in source_metadata.get('functional_skills', []):
                related_ids.append(skill.get('id'))
            for skill in source_metadata.get('enabling_skills', []):
                related_ids.append(skill.get('id'))
                
        elif (source_type in ['fs_complete_overview', 'esc_complete_overview'] or 
              source_entity_type in ['functional_skill', 'enabling_skill']) and relation_type in ['roles', 'all']:
            # Get IDs of roles that require this skill
            for role in source_metadata.get('required_by_roles', []):
                related_ids.append(role.get('id'))
        
        # Filter out None values
        related_ids = [rid for rid in related_ids if rid]
        
        if not related_ids:
            logger.info(f"No related items found for ID: {content_id}")
            return []
            
        # Get the related items
        def get_related_items():
            return list(KnowledgeChunk.objects.filter(
                metadata__id__in=related_ids
            ).values('text', 'metadata')[:limit])
            
        related_items = await sync_to_async(get_related_items)()
        
        # Format results
        formatted_results = []
        for item in related_items:
            formatted_results.append({
                "text": item['text'],
                "metadata": item['metadata'],
                "relation_type": "related_by_explicit_reference"
            })
            
        return formatted_results
            
    except Exception as e:
        logger.error(f"Error retrieving related content: {e}")
        return []

async def get_skill_levels(skill_id, limit=6):
    """
    Retrieves all proficiency levels for a given skill.
    
    Args:
        skill_id: The ID of the skill to find levels for
        limit: Maximum number of levels to return
    """
    try:
        def get_levels():
            return list(KnowledgeChunk.objects.filter(
                Q(metadata__parent_skill_id=skill_id) &
                (Q(metadata__type='fs_complete_level') | Q(metadata__type='esc_complete_level'))
            ).order_by('metadata__level').values('text', 'metadata')[:limit])
            
        level_items = await sync_to_async(get_levels)()
        
        if not level_items:
            logger.info(f"No skill levels found for skill ID: {skill_id}")
            return []
            
        # Format results
        formatted_results = []
        for item in level_items:
            formatted_results.append({
                "text": item['text'],
                "metadata": item['metadata'],
                "relation_type": "skill_level"
            })
            
        return formatted_results
            
    except Exception as e:
        logger.error(f"Error retrieving skill levels: {e}")
        return []

async def get_career_progression(role_id):
    """
    Retrieves career progression paths for a given role.
    
    Args:
        role_id: The ID of the role to find career paths for
    """
    try:
        # First find the role to get its details
        def get_role():
            return list(KnowledgeChunk.objects.filter(
                metadata__id=role_id,
                metadata__entity_type='job_role'
            ).values('text', 'metadata'))
            
        role_items = await sync_to_async(get_role)()
        
        if not role_items:
            logger.warning(f"No role found with ID: {role_id}")
            return []
            
        role_title = role_items[0]['metadata'].get('title', '')
        
        # Then find career map domains that include this role
        def get_domains():
            return list(KnowledgeChunk.objects.filter(
                metadata__type='career_map_domain',
                metadata__roles__contains=[{"name": role_title}]  # This is a simplification, may need adjustment
            ).values('text', 'metadata'))
            
        domain_items = await sync_to_async(get_domains)()
        
        if not domain_items:
            logger.info(f"No career domains found for role: {role_title}")
            return []
            
        # Format results
        formatted_results = []
        for item in domain_items:
            formatted_results.append({
                "text": item['text'],
                "metadata": item['metadata'],
                "relation_type": "career_path"
            })
            
        return formatted_results
            
    except Exception as e:
        logger.error(f"Error retrieving career progression: {e}")
        return []

async def comprehensive_search(query_text, include_related=True, limit=5):
    """
    Performs a comprehensive search that includes both vector similarity and relationship traversal.
    
    Args:
        query_text: The text to search for
        include_related: Whether to include related items through relationships
        limit: Maximum number of initial results to return
    """
    try:
        # First do a regular vector search
        vector_results = await search_similar_content_async(query_text, limit)
        
        if not vector_results or not include_related:
            return vector_results
            
        # Extract the first result's ID to find related content
        if isinstance(vector_results, list) and len(vector_results) > 0:
            primary_result = vector_results[0]
            primary_id = primary_result.get('metadata', {}).get('id')
            
            if primary_id:
                # Get related content based on first result's ID
                related_results = await get_related_content_by_id(primary_id, limit=3)
                
                if related_results:
                    # Add a separator to distinguish vector results from related content
                    vector_results.append({
                        "text": "--- Related Content ---",
                        "metadata": {"type": "separator"},
                        "is_separator": True
                    })
                    
                    # Add related content
                    vector_results.extend(related_results)
        
        return vector_results
        
    except Exception as e:
        logger.error(f"Error during comprehensive search: {e}")
        return []

def create_fallback_content(query_text):
    """Provides generic fallback content if vector search fails or yields no results."""
    logger.warning(f"Providing fallback content for query: {query_text}")
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