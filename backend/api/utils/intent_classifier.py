import logging
import re
from enum import Enum

logger = logging.getLogger(__name__)

class QueryIntent(Enum):
    CAREER_PATH = "career_path"         # Questions about progression from one role to another
    ROLE_INFO = "role_info"             # Questions about specific roles
    SKILL_INFO = "skill_info"           # Questions about specific skills
    SKILL_LEVEL_INFO = "skill_level_info" # Questions about specific proficiency levels
    SKILL_PROGRESSION = "skill_progression" # Questions about advancing between levels
    SKILL_COMPARISON = "skill_comparison" # Comparing different skills
    EDUCATION_ADVICE = "education_advice" # Questions about learning paths/education
    FUNCTIONAL_SKILLS = "functional_skills" # Questions about functional skills
    ENABLING_SKILLS = "enabling_skills" # Questions about enabling skills
    JOB_ROLES = "job_roles"             # Questions about job roles
    CAREER_MAP = "career_map"           # Questions about career maps
    GENERAL_QUERY = "general_query"     # General questions not related to the knowledge base

def classify_intent(query_text, chat_history=None):
    """
    Analyzes the query and chat history to determine the user's intent.
    Returns a QueryIntent enum and confidence score.
    """
    query_lower = query_text.lower()
    
    # Dictionary of intents and their associated keywords
    intent_keywords = {
        QueryIntent.CAREER_PATH: [
            "career map", "progression path", "career domain", "job grades",
            "vertical tracks", "horizontal levels", "job level", "career advancement",
            "psf-aai framework", "analytics career", "ai career path", "how to become", "steps to"
        ],
        QueryIntent.ROLE_INFO: [
            "role", "job", "position", "career", "responsibilities", "duties",
            "job title", "key tasks", "performance expectations"
        ],
        QueryIntent.SKILL_INFO: [
            "functional skill", "enabling skill", "competency", "ability",
            "skills application", "range of application", "skill requirements",
            "technical skill", "soft skill"
        ],
        QueryIntent.FUNCTIONAL_SKILLS: [
            "functional skills", "technical skills", "fs_", "analytics skills"
        ],
        QueryIntent.ENABLING_SKILLS: [
            "enabling skills", "soft skills", "esc_", "communication skills"
        ],
        QueryIntent.JOB_ROLES: [
            "job roles", "role description", "role responsibilities", "role tasks"
        ],
        QueryIntent.CAREER_MAP: [
            "career map", "career progression", "career path", "job levels"
        ],
        QueryIntent.SKILL_LEVEL_INFO: [
            "level 1", "level 2", "level 3", "level 4", "level 5", "level 6",
            "proficiency level", "beginner level", "advanced level", "expert level"
        ],
        QueryIntent.SKILL_PROGRESSION: [
            "skill progression", "advance from level", "move up levels", "improve proficiency"
        ],
        QueryIntent.EDUCATION_ADVICE: [
            "learn", "study", "course", "training", "education", "certification",
            "degree", "bootcamp", "tutorial", "resources", "books"
        ],
        QueryIntent.GENERAL_QUERY: [
            "hello", "hi", "thanks", "thank you", "goodbye", "help"
        ]
    }
    
    # Score each intent based on keyword matches
    intent_scores = {intent: 0.0 for intent in QueryIntent}
    
    # Check current query
    for intent, keywords in intent_keywords.items():
        for keyword in keywords:
            if keyword in query_lower:
                intent_scores[intent] += len(keyword.split())  # Weight multi-word keywords higher
    
    # Get the highest scoring intent
    max_score = max(intent_scores.values())
    selected_intent = max(intent_scores, key=intent_scores.get)
    
    # Confidence calculation
    confidence = min(max_score / 5.0, 1.0) if max_score > 0 else 0.0
    
    # Default to GENERAL_QUERY if confidence is too low
    if confidence < 0.4:
        selected_intent = QueryIntent.GENERAL_QUERY
    
    logger.info(f"Intent: {selected_intent.value}, Score: {max_score:.2f}, Confidence: {confidence:.2f}")
    return selected_intent, confidence

def extract_level_from_query(query_text):
    """Extract level information from a query if present."""
    level_pattern = r'level\s*(\d+)'
    level_matches = re.findall(level_pattern, query_text.lower())
    return int(level_matches[0]) if level_matches else None