import os
import sys
import numpy as np
import requests
import json
import logging
import time
from asgiref.sync import sync_to_async
from collections import defaultdict
from itertools import chain
import time
from django.db.models import F, Q

# Setup logger
logger = logging.getLogger(__name__)

from api.models import KnowledgeChunk, KnowledgeSource
from pgvector.django import CosineDistance

# --- Enhanced Configuration ---
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
QUERY_EMBEDDING_MODEL = "bge-m3"

# Enhanced Constants for search configuration
SIMILARITY_THRESHOLD = 0.78
CHUNK_TYPE_WEIGHTS = {
    "fs_complete_overview": 1.1,
    "esc_complete_overview": 1.1,
    "whole_role": 1.15,             # Boost comprehensive role descriptions
    "career_progression_path": 1.1, # Boost career progression chunks
    "fs_complete_level": 1.05,
    "esc_complete_level": 1.05,
    "role_description": 1.0,
    "career_map_domain": 1.0,
    "career_map_grade": 1.0,
    "fs_overview": 0.95,
    "esc_overview": 0.95,
}

# Enhanced connection-based boosting
CONNECTIVITY_BOOST = {
    "high_connectivity": 0.05,      # Chunks with connectivity_score > 3
    "has_career_progression": 0.03, # Chunks with career progression info
    "has_role_connections": 0.03,   # Chunks with role connections
    "skill_mappings": 0.02          # Chunks with skill-role mappings
}

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

def detect_query_intent(query_text):
    """Enhanced query intent detection for connectivity-aware search"""
    query_lower = query_text.lower()
    
    intent_patterns = {
        "career_progression": ["career path", "progression", "next role", "advancement", "promote", "move up"],
        "skill_requirements": ["skills for", "skills needed", "requirements", "competencies"],
        "role_connections": ["roles that use", "jobs requiring", "positions with"],
        "domain_exploration": ["domain", "field", "area", "specialization"],
        "grade_information": ["grade", "level", "seniority", "junior", "senior"],
        "general_search": []  # Default fallback
    }
    
    for intent, patterns in intent_patterns.items():
        if any(pattern in query_lower for pattern in patterns):
            return intent
    
    return "general_search"

async def search_similar_content_async(query_text, limit=5, section=None, extra_keywords=""):
    """
    Enhanced async search leveraging enriched metadata for better connectivity.
    """
    logger.info(f"Enhanced search for: '{query_text}{' '+extra_keywords if extra_keywords else ''}'")
    
    # Detect query intent for enhanced search strategy
    query_intent = detect_query_intent(query_text)
    logger.debug(f"Detected query intent: {query_intent}")
    
    # Append extra keywords for better semantic search
    search_text = query_text
    if extra_keywords:
        search_text = f"{query_text} {extra_keywords}"
    
    # Generate embedding for search query
    start_time = time.time()
    embedding = generate_embedding(search_text)
    if not embedding:
        logger.error("Failed to generate embedding for search query")
        return await sync_to_async(create_fallback_content)(query_text)
        
    logger.debug(f"Generated embedding in {time.time() - start_time:.2f}s")
    
    try:
        # Enhanced search with connectivity-aware filtering
        queryset = KnowledgeChunk.objects.all()
        
        # Apply section filter if specified
        if section:
            queryset = queryset.filter(metadata__psf_section=section)
        
        # Intent-based query enhancement
        if query_intent == "career_progression":
            # Prefer chunks with career progression info
            queryset = queryset.extra(
                select={
                    'has_progression': "CASE WHEN metadata->>'has_career_progression' = 'true' THEN 1 ELSE 0 END"
                }
            )
        elif query_intent == "skill_requirements":
            # Prefer chunks with role-skill mappings
            queryset = queryset.extra(
                select={
                    'has_skill_mapping': "CASE WHEN metadata->>'has_role_connections' = 'true' THEN 1 ELSE 0 END"
                }
            )
        
        # Enhanced search with metadata-based boosting
        results = await sync_to_async(list)(
            queryset.annotate(
                embedding_distance=CosineDistance('embedding', embedding)
            ).filter(
                embedding_distance__lte=SIMILARITY_THRESHOLD
            ).order_by('embedding_distance')[:limit * 2]  # Get more results for post-processing
        )
        
        if not results:
            logger.warning(f"No similar content found for query: {query_text}")
            return await try_query_expansion(query_text, limit, section)
        
        # Enhanced post-processing with metadata awareness
        processed_results = await sync_to_async(post_process_results_enhanced)(results, limit, query_text, query_intent)
        
        logger.info(f"Found {len(processed_results)} enhanced results for query: {query_text}")
        return format_results_enhanced(processed_results, query_text, query_intent)
        
    except Exception as e:
        logger.error(f"Error during enhanced search: {e}")
        return await sync_to_async(create_fallback_content)(query_text)

def post_process_results_enhanced(results, limit, query_text, query_intent):
    """Enhanced post-processing leveraging rich metadata"""
    # Filter by distance threshold
    filtered_results = [r for r in results if r.embedding_distance <= SIMILARITY_THRESHOLD]
    
    if not filtered_results:
        logger.warning(f"No results passed similarity threshold for: {query_text}")
        return results[:limit]  # Fallback to original results
    
    # Enhanced chunk type weighting with metadata consideration
    for result in filtered_results:
        chunk_type = result.metadata.get("type", "unknown")
        base_weight = CHUNK_TYPE_WEIGHTS.get(chunk_type, 1.0)
        
        # Additional boosting based on metadata richness
        metadata_boost = 1.0
        
        # Connectivity-based boosting
        connectivity_score = result.metadata.get("connectivity_score", 0)
        if connectivity_score > 3:
            metadata_boost += CONNECTIVITY_BOOST["high_connectivity"]
        
        if result.metadata.get("has_career_progression"):
            metadata_boost += CONNECTIVITY_BOOST["has_career_progression"]
        
        if result.metadata.get("has_role_connections"):
            metadata_boost += CONNECTIVITY_BOOST["has_role_connections"]
        
        if result.metadata.get("role_level_requirements"):
            metadata_boost += CONNECTIVITY_BOOST["skill_mappings"]
        
        # Intent-specific boosting
        if query_intent == "career_progression" and result.metadata.get("has_career_progression"):
            metadata_boost += 0.1
        elif query_intent == "skill_requirements" and result.metadata.get("has_role_connections"):
            metadata_boost += 0.1
        
        adjusted_weight = base_weight * metadata_boost
        result.adjusted_distance = result.embedding_distance / adjusted_weight
    
    # Sort by adjusted distance
    filtered_results.sort(key=lambda x: x.adjusted_distance)
    
    # Enhanced consolidation with connectivity awareness
    consolidated = consolidate_related_chunks_enhanced(filtered_results, limit, query_text, query_intent)
    
    return consolidated[:limit]

def consolidate_related_chunks_enhanced(chunks, limit, query_text, query_intent):
    """Enhanced consolidation that preserves connectivity information"""
    # Check if query suggests looking for connections
    connection_keywords = ["career path", "progression", "next role", "advancement", "skills for", "roles that use"]
    is_connection_query = any(keyword in query_text.lower() for keyword in connection_keywords)
    
    if is_connection_query or query_intent in ["career_progression", "skill_requirements", "role_connections"]:
        # For connection queries, prefer chunks with rich relational metadata
        chunks.sort(key=lambda x: (
            x.adjusted_distance,
            -x.metadata.get("connectivity_score", 0),
            -len(x.metadata.get("used_in_roles", [])),
            -len(x.metadata.get("next_roles_from_career_map", []))
        ))
        return chunks[:limit]
    else:
        # Use enhanced consolidation for regular queries
        return consolidate_related_chunks(chunks, limit)

def consolidate_related_chunks(chunks, limit):
    """Group chunks by skill/role and keep the best representative for each"""
    grouped = defaultdict(list)
    
    for chunk in chunks:
        metadata = chunk.metadata if hasattr(chunk, 'metadata') else {}
        
        # Enhanced grouping logic leveraging rich metadata
        if metadata.get("type", "").startswith("role_"):
            # Group by role title, considering contextual titles
            key = metadata.get("title", "unknown_role")
            if metadata.get("contextual_title"):
                key = f"role_{metadata.get('title')}"
        elif metadata.get("skill_category") in ["functional", "enabling"]:
            # Group by skill name
            key = f"skill_{metadata.get('skill', metadata.get('title', 'unknown_skill'))}"
        elif metadata.get("type", "").startswith("career_"):
            # Group career-related chunks by domain or grade
            if "domain" in metadata.get("type", ""):
                key = f"domain_{metadata.get('domain_name', 'unknown')}"
            elif "grade" in metadata.get("type", ""):
                key = f"grade_{metadata.get('grade_name', 'unknown')}"
            elif "progression" in metadata.get("type", ""):
                key = f"progression_{metadata.get('source_role', 'unknown')}"
            else:
                key = f"career_{metadata.get('title', 'unknown')}"
        else:
            key = f"general_{metadata.get('title', 'unknown')}"
        
        grouped[key].append(chunk)
    
    # For each group, select the best representative
    consolidated = []
    for entity, entity_chunks in grouped.items():
        # Sort by type preference and adjusted distance
        entity_chunks.sort(key=lambda x: (
            -CHUNK_TYPE_WEIGHTS.get(x.metadata.get("type", ""), 0.9),
            x.adjusted_distance
        ))
        
        # Take the best chunk from each group
        best_chunk = entity_chunks[0]
        
        # Enhance metadata with group information
        if hasattr(best_chunk, 'metadata') and best_chunk.metadata:
            best_chunk.metadata['related_chunks_count'] = len(entity_chunks)
            best_chunk.metadata['group_key'] = entity
        
        consolidated.append(best_chunk)
    
    # Sort again by adjusted distance
    consolidated.sort(key=lambda x: x.adjusted_distance)
    return consolidated

def format_results_enhanced(results, query_text, query_intent):
    """Enhanced result formatting with connectivity information"""
    formatted_items = []
    
    for item in results:
        metadata = item.metadata if hasattr(item, 'metadata') else {}
        
        # Calculate enhanced relevance
        base_relevance = max(0, min(100, 100 - (item.adjusted_distance * 100)))
        connectivity_bonus = min(5, metadata.get("connectivity_score", 0))
        relevance = min(100, base_relevance + connectivity_bonus)
        
        # Enhanced result item with connectivity info
        result_item = {
            'title': metadata.get('title', 'Unnamed Content'),
            'type': metadata.get('type', 'unknown'),
            'text': item.text,
            'content': item.text,
            'relevance': f"{relevance:.1f}%",
            'metadata': metadata,
            'skill_category': metadata.get('skill_category', 'unknown'),
            'distance': item.embedding_distance,
            'connectivity_score': metadata.get('connectivity_score', 0)
        }
        
        # Add connectivity-specific information
        if metadata.get('used_in_roles'):
            result_item['connected_roles'] = metadata['used_in_roles']
        
        if metadata.get('next_roles_from_career_map'):
            result_item['career_progression'] = metadata['next_roles_from_career_map']
        
        if metadata.get('role_level_requirements'):
            result_item['skill_requirements'] = metadata['role_level_requirements']
        
        formatted_items.append(result_item)
    
    # Enhanced metadata
    result_metadata = {
        'query': query_text,
        'query_intent': query_intent,
        'result_count': len(formatted_items),
        'result_types': list(set(item['type'] for item in formatted_items)),
        'connectivity_features': {
            'items_with_role_connections': sum(1 for item in formatted_items if item.get('connected_roles')),
            'items_with_career_progression': sum(1 for item in formatted_items if item.get('career_progression')),
            'avg_connectivity_score': sum(item['connectivity_score'] for item in formatted_items) / len(formatted_items) if formatted_items else 0
        }
    }
    
    return {
        'found': len(formatted_items) > 0,
        'items': formatted_items,
        'metadata': result_metadata,
        'count': len(formatted_items)
    }

async def try_query_expansion(query_text, limit, section):
    """Enhanced query expansion with connectivity awareness"""
    # Intent-based expansions
    intent = detect_query_intent(query_text)
    
    expansions = []
    if intent == "career_progression":
        expansions = [
            f"{query_text} career path progression",
            f"{query_text} next role advancement",
            f"career progression from {query_text}"
        ]
    elif intent == "skill_requirements":
        expansions = [
            f"skills required for {query_text}",
            f"{query_text} competencies requirements",
            f"functional enabling skills {query_text}"
        ]
    else:
        # General expansions
        expansions = [
            f"{query_text} description definition",
            f"what is {query_text}",
            f"{query_text} in psf-aai framework",
        ]
    
    for expansion in expansions:
        results = await search_similar_content_async(expansion, limit, section, "")
        if results.get('found', False) and results.get('items', []):
            # Add note that query was expanded
            results['metadata'] = results.get('metadata', {})
            results['metadata']['query_expanded'] = True
            results['metadata']['original_query'] = query_text
            return results
    
    # No results found even with expansion
    return await sync_to_async(create_fallback_content)(query_text)

def create_fallback_content(query_text):
    """Enhanced PSF-AAI specific fallback content with connectivity information"""
    logger.warning(f"Providing enhanced fallback content for query: {query_text}")
    query_lower = query_text.lower()
    
    # Enhanced fallback content with connectivity context
    if any(term in query_lower for term in ["career", "progression", "path", "advancement"]):
        return {
            'found': True,
            'items': [
                {
                    "text": "The PSF-AAI framework provides clear career progression paths across multiple domains. For example, Data Analysts can progress to Senior Data Analysts, then to Data Science roles or Business Intelligence positions, depending on their chosen specialization.",
                    "metadata": {
                        "type": "fallback_career",
                        "title": "Career Progression in PSF-AAI",
                        "psf_section": "career_map",
                        "connectivity_score": 5,
                        "has_career_progression": True
                    },
                    "relevance": "85.0%",
                    "connectivity_score": 5
                }
            ],
            'metadata': {
                'query': query_text,
                'query_intent': 'career_progression',
                'is_fallback': True
            },
            'count': 1
        }
    elif any(term in query_lower for term in ["skills", "competencies", "requirements"]):
        return {
            'found': True,
            'items': [
                {
                    "text": "PSF-AAI defines comprehensive skill requirements for each role, including both Functional Skills (technical competencies) and Enabling Skills (soft skills). Each skill has specific proficiency levels with detailed knowledge and application requirements.",
                    "metadata": {
                        "type": "fallback_skills",
                        "title": "Skill Requirements in PSF-AAI",
                        "psf_section": "functional_skills",
                        "connectivity_score": 4,
                        "has_role_connections": True
                    },
                    "relevance": "80.0%",
                    "connectivity_score": 4
                }
            ],
            'metadata': {
                'query': query_text,
                'query_intent': 'skill_requirements',
                'is_fallback': True
            },
            'count': 1
        }
    else:
        return {
            'found': True,
            'items': [
                {
                    "text": "The Philippine Skills Framework for Analytics and AI (PSF-AAI) provides comprehensive guidance on skills, career paths, and competency development for data and AI professionals, with detailed role mappings and progression pathways.",
                    "metadata": {
                        "type": "fallback_general",
                        "title": "PSF-AAI Framework Overview",
                        "psf_section": "general",
                        "connectivity_score": 3
                    },
                    "relevance": "75.0%",
                    "connectivity_score": 3
                }
            ],
            'metadata': {
                'query': query_text,
                'query_intent': 'general_search',
                'is_fallback': True
            },
            'count': 1
        }

# Legacy search function for backward compatibility
def search_similar_content(query_text, limit=5, section=None):
    """Legacy search function - redirects to async version"""
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, we can't use loop.run_until_complete
            logger.warning("Legacy search called from async context - returning limited results")
            return {"error": "Use async version in async context"}
        else:
            return loop.run_until_complete(search_similar_content_async(query_text, limit, section))
    except RuntimeError:
        # No event loop
        return asyncio.run(search_similar_content_async(query_text, limit, section))

if __name__ == "__main__":
    # Setup console logging for direct script execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Example usage for testing the enhanced search function
    test_queries = [
        "data science career path",
        "skills for machine learning engineer",
        "progression from data analyst"
    ]
    
    for test_query in test_queries:
        print(f"\n" + "="*50)
        print(f"Testing enhanced search for: '{test_query}'")
        print("="*50)
        
        search_results = search_similar_content(test_query, limit=3)
        
        if isinstance(search_results, dict) and search_results.get('found'):
            print(f"Found {search_results['count']} results")
            print(f"Query intent: {search_results['metadata'].get('query_intent', 'unknown')}")
            
            for i, result in enumerate(search_results['items']):
                print(f"\n{i+1}. {result['title']} (Relevance: {result['relevance']})")
                print(f"   Type: {result['type']}")
                print(f"   Connectivity Score: {result.get('connectivity_score', 0)}")
                if result.get('connected_roles'):
                    print(f"   Connected Roles: {', '.join(result['connected_roles'][:3])}")
                if result.get('career_progression'):
                    print(f"   Career Progression: {', '.join(result['career_progression'][:3])}")
                print(f"   Content: {result['content'][:100]}...")
        else:
            print(f"No results found or error occurred")