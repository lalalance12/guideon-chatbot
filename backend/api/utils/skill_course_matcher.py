import os
import json
import requests
import numpy as np
import logging

OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "bge-m3"

logger = logging.getLogger(__name__)

# Path to your precomputed skill embeddings (update if needed)
SKILL_EMBEDDINGS_PATH = os.path.join(os.path.dirname(__file__), '../data/roles/sample_role_skill_embeddings_bge_m3.json')

# Load skill embeddings once at module load
def load_skill_embeddings():
    logger.info(f"Loading skill embeddings from {SKILL_EMBEDDINGS_PATH}")
    with open(SKILL_EMBEDDINGS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    logger.debug(f"Loaded {len(data)} skill embeddings.")
    return data

SKILL_EMBEDDINGS = load_skill_embeddings()

def get_embedding_for_text(text):
    logger.info(f"Generating embedding for text: {text[:60]}...")
    payload = {"model": EMBEDDING_MODEL, "prompt": text}
    try:
        response = requests.post(OLLAMA_EMBED_URL, json=payload, timeout=60)
        response.raise_for_status()
        embedding_data = response.json()
        embedding = embedding_data.get("embedding", [])
        logger.debug(f"Generated embedding of length {len(embedding)} for text.")
        return embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return []

def cosine_similarity(vec1, vec2):
    logger.debug(f"Calculating cosine similarity.")
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    if v1.shape != v2.shape or v1.size == 0:
        logger.warning("Vectors have mismatched shapes or are empty.")
        return 0.0
    sim = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
    logger.debug(f"Cosine similarity: {sim}")
    return sim

def match_course_to_skills(course_text, top_n=5):
    logger.info(f"Matching course to skills for course text: {course_text[:60]}...")
    course_emb = get_embedding_for_text(course_text)
    if not course_emb:
        logger.warning("No embedding generated for course text.")
        return []
    scored = []
    for skill in SKILL_EMBEDDINGS:
        sim = cosine_similarity(course_emb, skill["embedding"])
        scored.append({
            "skill": skill["metadata"].get("title", ""),
            "similarity": sim,
            "metadata": skill["metadata"]
        })
    scored.sort(key=lambda x: x["similarity"], reverse=True)
    logger.info(f"Top {top_n} skills matched.")
    return scored[:top_n]

def match_courses_batch(course_texts, top_n=5):
    logger.info(f"Matching batch of {len(course_texts)} courses to skills.")
    return [match_course_to_skills(text, top_n=top_n) for text in course_texts]

def match_course_to_underpinning_knowledge(course_text, top_n=5):
    logger.info(f"Matching course to underpinning knowledge for text: {course_text[:60]}...")
    course_emb = get_embedding_for_text(course_text)
    if not course_emb:
        logger.warning("No embedding generated for course text.")
        return []
    scored = []
    for item in SKILL_EMBEDDINGS:
            sim = cosine_similarity(course_emb, item["embedding"])
            scored.append({
                "underpinning_knowledge": item["text"],
                "similarity": sim,
                "metadata": item["metadata"]
            })
    scored.sort(key=lambda x: x["similarity"], reverse=True)
    logger.info(f"Top {top_n} underpinning knowledge items matched.")
    return scored[:top_n]