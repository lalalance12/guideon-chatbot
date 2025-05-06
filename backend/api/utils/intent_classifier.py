import logging
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
            "psf-aai framework", "analytics career", "ai career path"
        ],
        QueryIntent.ROLE_INFO: [
            "job title", "performance expectations", "key tasks", 
            "role description", "what does a", "responsibilities",
            "data scientist", "data analyst", "ai engineer", "analytics role"
        ],
        QueryIntent.SKILL_INFO: [
            "functional skill", "enabling skill", "competency",
            "underpinning knowledge", "skills application", "range of application",
            "skill requirements", "what skills", "psf-aai skills"
        ],
        QueryIntent.SKILL_LEVEL_INFO: [
            "level 1", "level 2", "level 3", "level 4", "level 5", "level 6",
            "proficiency level", "beginner level", "advanced level", "expert level",
            "entry level", "senior level", "skill at level"
        ],
        QueryIntent.SKILL_PROGRESSION: [
            "skill progression", "advance from level", "move up levels", "improve proficiency",
            "grow skills", "develop competency", "progress from beginner", "reach expert"
        ],
        QueryIntent.SKILL_COMPARISON: [
            "compare skills", "difference between", "versus", "vs", 
            "which skill is better", "prioritize skills", "more important skill"
        ],
        QueryIntent.EDUCATION_ADVICE: [
            "learn", "study", "course", "training", "education", "certification",
            "degree", "bootcamp", "self-learn", "tutorial", "resources", "books"
        ],
        QueryIntent.GENERAL_QUERY: [
            "hello", "hi", "thanks", "thank you", "goodbye", "help"
        ]
    }
    
    # Score each intent based on keyword matches
    intent_scores = {intent: 0 for intent in QueryIntent}
    
    # Check current query
    for intent, keywords in intent_keywords.items():
        for keyword in keywords:
            if keyword in query_lower:
                intent_scores[intent] += 1
    
    # Check chat history for context if available
    if chat_history:
        # Get the last 3 user messages for context
        user_messages = [msg.content.lower() for msg in chat_history if msg.role == 'user'][-3:]
        for message in user_messages:
            for intent, keywords in intent_keywords.items():
                for keyword in keywords:
                    if keyword in message:
                        # Past messages affect intent but with lower weight
                        intent_scores[intent] += 0.5
    
    # Get the highest scoring intent
    max_score = 0
    selected_intent = QueryIntent.GENERAL_QUERY  # Default
    
    for intent, score in intent_scores.items():
        if score > max_score:
            max_score = score
            selected_intent = intent
    
    # Set a confidence threshold
    confidence = max_score / (len(query_lower.split()) / 4)  # Normalize by query length
    
    if confidence < 0.5:  # Low confidence threshold
        selected_intent = QueryIntent.GENERAL_QUERY
        logger.debug("Low confidence in intent classification, defaulting to GENERAL_QUERY")
    
    logger.info(f"Intent: {selected_intent.value}, confidence: {confidence:.2f}")
    
    return selected_intent, confidence