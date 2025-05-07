import logging
from enum import Enum
import re

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
            "psf-aai framework", "analytics career", "ai career path", "how to become", "steps to"
        ],
        QueryIntent.ROLE_INFO: [
            # General role terms
            "role", "job", "position", "career", 
            # Common role keywords (often part of titles)
            "analyst", "scientist", "engineer", "developer", "manager", "consultant", 
            "specialist", "architect", "lead", "officer", "administrator", "associate", "senior", "principal", "director", "head", "chief",
            # Phrases indicating request for role information
            "job title", "responsibilities", "key tasks", "duties", "what does a", "tell me about the role", "describe the job",
            "performance expectations" # Specific to your data structure for roles
        ],
        QueryIntent.SKILL_INFO: [
            "functional skill", "enabling skill", "competency", "ability",
            "underpinning knowledge", "skills application", "range of application",
            "skill requirements", "what skills", "psf-aai skills", "technical skill", "soft skill"
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
    intent_scores = {intent: 0.0 for intent in QueryIntent} # Use float for scores
    
    # Check current query
    for intent, keywords in intent_keywords.items():
        for keyword in keywords:
            if keyword in query_lower:
                # Give more weight to multi-word keywords as they are more specific
                intent_scores[intent] += len(keyword.split()) 
    
    # Specific pattern check for "what is/are/about [potential role name]"
    # This gives a bonus to ROLE_INFO if the structure matches and the subject sounds like a role.
    role_query_pattern = r"^(what is|what's|what are|tell me about|describe) (an?|the)?\s*([\w\s]+?)(?:\?|$)"
    match = re.search(role_query_pattern, query_lower)
    if match:
        potential_role_name = match.group(3).strip()
        # Check if potential_role_name contains any of the specific role keywords
        # These are common terms found in job titles
        role_title_keywords = ["analyst", "scientist", "engineer", "developer", "manager", "consultant", "specialist", "architect", "lead", "officer", "administrator", "associate", "coordinator", "executive"]
        if any(rk_word in potential_role_name for rk_word in role_title_keywords):
            # If not primarily asking about skills for that role
            if not any(skill_kw in query_lower for skill_kw in ["skill", "skills", "competency", "competencies"]):
                intent_scores[QueryIntent.ROLE_INFO] += 3.0 # Add a significant bonus for definitional role queries

    # Check chat history for context if available
    if chat_history:
        user_messages = [msg.content.lower() for msg in chat_history if msg.role == 'user'][-3:]
        for message in user_messages:
            for intent, keywords in intent_keywords.items():
                for keyword in keywords:
                    if keyword in message:
                        intent_scores[intent] += 0.5 * len(keyword.split()) # Weighted less
    
    # Get the highest scoring intent
    max_score = 0
    selected_intent = QueryIntent.GENERAL_QUERY  # Default
    
    if any(intent_scores.values()): # Check if any scores were made
        # Sort by score to handle ties (though less likely with weighted scores)
        sorted_intents = sorted(intent_scores.items(), key=lambda item: item[1], reverse=True)
        if sorted_intents[0][1] > 0: # Ensure max_score is positive
            selected_intent = sorted_intents[0][0]
            max_score = sorted_intents[0][1]

    # Refined confidence calculation (heuristic)
    # Consider the number of unique keywords matched for the selected intent vs. total keywords for that intent
    # This is a placeholder for a more robust confidence metric.
    # For now, base it on the score relative to a hypothetical max possible score for a short query.
    if max_score > 0:
        # Simple confidence: if score is high, confidence is high.
        # Max possible score for a short query with a few strong keywords could be ~5-10.
        confidence = min(max_score / 5.0, 1.0) 
    else:
        confidence = 0.0

    # If confidence is too low, or no keywords matched, default to general.
    # Increased threshold slightly as scores are higher now.
    if confidence < 0.6 and selected_intent != QueryIntent.GENERAL_QUERY: 
        # Check if it's a very short query that might be general
        if len(query_lower.split()) < 4 and max_score < 2.0:
             selected_intent = QueryIntent.GENERAL_QUERY
             logger.debug(f"Low score for short query, defaulting to GENERAL_QUERY. Original intent: {selected_intent.value}, score: {max_score}")
        else:
            logger.debug(f"Confidence {confidence:.2f} is below threshold (0.6) but keeping intent {selected_intent.value} due to score {max_score} or query length.")
    elif max_score == 0:
        selected_intent = QueryIntent.GENERAL_QUERY
        confidence = 0.0 # No keywords matched at all
    
    logger.info(f"Intent: {selected_intent.value}, Score: {max_score:.2f}, Confidence: {confidence:.2f}")
    
    return selected_intent, confidence