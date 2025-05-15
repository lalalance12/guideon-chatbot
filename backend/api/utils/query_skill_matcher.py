import logging
from .skill_course_matcher import (
    get_embedding_for_text,
    cosine_similarity,
    SKILL_EMBEDDINGS
)

logger = logging.getLogger(__name__)

def find_skill_and_knowledge_for_query(query_text, similarity_threshold=0.6, top_n=1):
    """
    For a given query, find the most semantically similar skill title and 
    return its underpinning knowledge text.
    
    Args:
        query_text (str): The query text to match against skills
        similarity_threshold (float): Minimum similarity score to consider a match
        top_n (int): Number of top matches to return
        
    Returns:
        list: List of dicts with keys: skill_title, similarity, underpinning_knowledge
    """
    # Get embedding for the query
    query_emb = get_embedding_for_text(query_text)
    if not query_emb:
        logger.warning("No embedding generated for query text.")
        return []
    
    # Group the embeddings by skill_title
    skill_groups = {}
    for item in SKILL_EMBEDDINGS:
        skill_title = item["metadata"].get("title", "")
        if not skill_title:
            continue
            
        if "underpinning_knowledge" not in item["metadata"].get("type", "") and "knowledge" not in item["metadata"]:
            continue
            
        if skill_title not in skill_groups:
            skill_groups[skill_title] = []
            
        skill_groups[skill_title].append(item)
    
    # Calculate similarity for each skill title
    skill_similarities = []
    for skill_title, items in skill_groups.items():
        best_sim = 0
        best_knowledge = ""
        
        for item in items:
            sim = cosine_similarity(query_emb, item["embedding"])
            if sim > best_sim:
                best_sim = sim
                # Get the underpinning knowledge text
                best_knowledge = item.get("text", "")
        
        if best_sim >= similarity_threshold:
            skill_similarities.append({
                "skill_title": skill_title,
                "similarity": best_sim,
                "underpinning_knowledge": best_knowledge
            })
    
    # Sort by similarity
    skill_similarities.sort(key=lambda x: x["similarity"], reverse=True)
    
    return skill_similarities[:top_n]

def get_knowledge_for_query(query_text, similarity_threshold=0.6):
    """
    Convenience function to directly get the best matching underpinning knowledge
    for a query.
    
    Args:
        query_text (str): The query text to match against skills
        similarity_threshold (float): Minimum similarity score to consider a match
        
    Returns:
        dict: Contains best_skill_title, similarity_score, and knowledge_text
              Returns None if no match found
    """
    matches = find_skill_and_knowledge_for_query(
        query_text=query_text,
        similarity_threshold=similarity_threshold,
        top_n=1
    )
    
    if not matches:
        return None
        
    match = matches[0]
    return {
        "best_skill_title": match["skill_title"],
        "similarity_score": match["similarity"],
        "knowledge_text": match["underpinning_knowledge"]
    } 