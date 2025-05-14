import logging
from .skill_course_matcher import (
    match_course_to_skills,
    get_embedding_for_text,
    cosine_similarity,
    SKILL_EMBEDDINGS
)

logger = logging.getLogger(__name__)

# Helper: get all underpinning knowledge for a given skill title

def get_underpinning_knowledge_for_skill(skill_title):
    return [item for item in SKILL_EMBEDDINGS if item["metadata"].get("title", "") == skill_title or item["metadata"].get("knowledge", "")]


def match_course_title_and_description_to_skills(course_title, course_description, title_threshold=0.5, knowledge_threshold=0.4, top_n=3):
    """
    For a given course (title, description), find skills where:
    - The course title is semantically close to the skill title (above title_threshold)
    - The course description is semantically close to at least one underpinning knowledge item under that skill (above knowledge_threshold)
    Returns a list of dicts: [{skill_title, title_similarity, best_knowledge, knowledge_similarity}]
    """
    # 1. Match course title to skills
    skill_matches = match_course_to_skills(course_title, top_n=top_n)
    results = []
    for skill in skill_matches:
        skill_title = skill["skill"]
        title_similarity = skill["similarity"]
        if title_similarity < title_threshold:
            continue
        # 2. Get underpinning knowledge for this skill
        knowledge_items = [item for item in SKILL_EMBEDDINGS if item["metadata"].get("title", "") == skill_title and "knowledge" in item["metadata"]]
        if not knowledge_items:
            continue
        # 3. Embed course description
        desc_emb = get_embedding_for_text(course_description)
        if not desc_emb:
            continue
        # 4. Find best matching underpinning knowledge
        best_knowledge = None
        best_sim = 0.0
        for item in knowledge_items:
            sim = cosine_similarity(desc_emb, item["embedding"])
            if sim > best_sim:
                best_sim = sim
                best_knowledge = item["metadata"]["knowledge"]
        if best_sim >= knowledge_threshold:
            results.append({
                "skill_title": skill_title,
                "title_similarity": title_similarity,
                "best_knowledge": best_knowledge,
                "knowledge_similarity": best_sim
            })
    return results
