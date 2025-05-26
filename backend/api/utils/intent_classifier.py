from enum import Enum
import logging

logger = logging.getLogger(__name__)

class QueryIntent(Enum):
    KNOWLEDGE_BASE_QUERY = "knowledge_base_query"  # General PSF-AAI knowledge queries
    LEARNING_PATHWAY = "learning_pathway"          # Career role exploration and pathway generation
    COURSE_SEARCH = "course_search"                # Specific course and training resource queries
    GENERAL_CONVERSATION = "general_conversation"  # Chit-chat not related to PSF-AAI

def minimal_fallback_classify(query_text):
    """
    Ultra-simple fallback classification using only the most obvious patterns.
    Used only when LLM is completely unavailable.
    """
    query_lower = query_text.lower().strip()
    
    # Only the most obvious cases to avoid false positives
    
    # 1. Clear greetings and casual conversation
    obvious_greetings = ["hi", "hello", "hey", "thanks", "thank you", "bye", "goodbye"]
    if query_lower in obvious_greetings:
        return {
            "intent": QueryIntent.GENERAL_CONVERSATION,
            "confidence": 0.9,
            "extracted_entities": {}
        }
    
    # 2. Clear career goal statements
    if ("i want to become" in query_lower or 
        "i want to be" in query_lower or 
        "my goal is to" in query_lower):
        
        role = extract_role_from_query(query_text)
        entities = {"extracted_role": role} if role else {}
        
        return {
            "intent": QueryIntent.LEARNING_PATHWAY,
            "confidence": 0.8,
            "extracted_entities": entities
        }
    
    # 3. Clear course requests
    if (("find courses" in query_lower or 
         "recommend courses" in query_lower or
         "show me courses" in query_lower) and 
        "course" in query_lower):
        
        return {
            "intent": QueryIntent.COURSE_SEARCH,
            "confidence": 0.8,
            "extracted_entities": {}
        }
    
    # 4. Default to knowledge base for everything else
    level = extract_level_from_query(query_text)
    entities = {"extracted_level": level} if level else {}
    
    return {
        "intent": QueryIntent.KNOWLEDGE_BASE_QUERY,
        "confidence": 0.5,
        "extracted_entities": entities
    }

def classify_intent(query_text, chat_history=None):
    """
    Legacy function for backward compatibility.
    Now just calls the minimal fallback.
    """
    logger.warning("Using legacy classify_intent - should use LLM-based classification instead")
    return minimal_fallback_classify(query_text)

def extract_level_from_query(query_text):
    """Extract proficiency level information from a query."""
    levels = ["level 1", "level 2", "level 3", "level 4", "level 5", "level 6",
              "basic", "intermediate", "advanced", "expert"]
    query_lower = query_text.lower()
    
    for level in levels:
        if level in query_lower:
            return level
            
    return None

def extract_role_from_query(query_text):
    """Extract role information from a query for career aspirations."""
    # Core roles that are most commonly mentioned
    core_roles = [
        # Most common roles first for better matching
        "data scientist",
        "data analyst", 
        "data engineer",
        "machine learning engineer",
        "ai engineer",
        "business intelligence analyst",
        
        # Extended roles
        "associate data analyst",
        "associate data engineer",
        "applied data/ai researcher",
        "senior business intelligence analyst",
        "data quality specialist",
        "senior data engineer",
        "senior applied data/ai researcher",
        "business analytics manager",
        "data governance manager",
        "data architect",
        "senior data scientist",
        "senior ai engineer",
        "research manager",
        "business analytics director",
        "data governance officer",
        "chief data architect",
        "chief data scientist",
        "chief ai engineer",
        "director of research",
        "chief business function officer",
        "chief data officer",
        "chief information officer", 
        "chief analytics officer",
        "chief technology officer",
        "chief scientific officer"
    ]
    
    query_lower = query_text.lower()
    
    # Check for exact matches first (most reliable)
    for role in core_roles:
        if role in query_lower:
            return role
            
    return None