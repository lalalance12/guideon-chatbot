from enum import Enum
import logging

logger = logging.getLogger(__name__)

class QueryIntent(Enum):
    KNOWLEDGE_BASE_QUERY = "knowledge_base_query"  # General PSF-AAI knowledge queries
    LEARNING_PATHWAY = "learning_pathway"          # Career role exploration and pathway generation
    COURSE_SEARCH = "course_search"                # Specific course and training resource queries
    GENERAL_CONVERSATION = "general_conversation"  # Chit-chat not related to PSF-AAI

def classify_intent(query_text, chat_history=None):
    """
    Analyzes the query and chat history to determine the user's intent.
    Returns a QueryIntent enum and confidence score.
    """
    query_lower = query_text.lower()
    
    # Dictionary of intents and their associated keywords
    intent_keywords = {
        QueryIntent.KNOWLEDGE_BASE_QUERY: [
            "what is", "tell me about", "explain", "describe", "definition", 
            "psf", "aai", "framework", "role", "functional skill", "enabling skill", 
            "competency", "proficiency", "level", "description",
            "career map", "job grades", "domains", "vertical tracks", "horizontal levels",
            "career progression", "job levels"
        ],
        QueryIntent.LEARNING_PATHWAY: [
            "career path", "learning path", "how to become", "progress to", "want to be",
            "career progression", "skill development", "roadmap", "steps to", "pathway",
            "career transition", "career growth", "advance to", "move up"
        ],
        QueryIntent.COURSE_SEARCH: [
            "course", "training", "learn", "study", "education", "class", "tutorial",
            "certification", "degree", "program", "workshop", "resources", "materials",
            "recommendation", "suggested courses"
        ],
        QueryIntent.GENERAL_CONVERSATION: [
            "hello", "hi", "thanks", "thank you", "how are you", "who are you",
            "your name", "your purpose", "help me", "what can you do"
        ]
    }
    
    # Score each intent based on keyword matches
    intent_scores = {intent: 0 for intent in QueryIntent}
    
    for intent, keywords in intent_keywords.items():
        for keyword in keywords:
            if keyword in query_lower:
                intent_scores[intent] += 1
    
    # Find the highest scoring intent
    max_score = 0
    selected_intent = QueryIntent.GENERAL_CONVERSATION  # Default
    
    for intent, score in intent_scores.items():
        if score > max_score:
            max_score = score
            selected_intent = intent
    
    # Calculate confidence (normalized score)
    confidence = min(max_score / 3, 1.0) if max_score > 0 else 0.5
    
    # Extract additional context
    extracted_entities = {}
    
    # Extract role if this is a learning pathway query
    if selected_intent == QueryIntent.LEARNING_PATHWAY:
        role = extract_role_from_query(query_text)
        if role:
            extracted_entities["extracted_role"] = role
            confidence += 0.1  # Boost confidence if we found a specific role
    
    # Extract level if this is a knowledge base query
    if selected_intent == QueryIntent.KNOWLEDGE_BASE_QUERY:
        level = extract_level_from_query(query_text)
        if level:
            extracted_entities["extracted_level"] = level
            confidence += 0.1  # Boost confidence if we found a specific level
    
    logger.info(f"Classified '{query_text[:30]}...' as {selected_intent.value} with confidence {confidence:.2f}")
    
    return {
        "intent": selected_intent,
        "confidence": confidence,
        "extracted_entities": extracted_entities
    }

def extract_level_from_query(query_text):
    """Extract proficiency level information from a query."""
    levels = ["basic", "intermediate", "advanced", "expert", "level 1", "level 2", "level 3", "level 4"]
    query_lower = query_text.lower()
    
    for level in levels:
        if level in query_lower:
            return level
            
    return None

def extract_role_from_query(query_text):
    """Extract role information from a query for career aspirations."""
    # Updated roles based on career_map.json
    roles = [
        # Associate level
        "associate data analyst",
        
        # Senior Associate level
        "data analyst", 
        "associate data engineer",
        
        # Professional level
        "business intelligence analyst", 
        "data engineer",
        "machine learning engineer", 
        "applied data/ai researcher",
        
        # Senior Professional / Supervisor level
        "senior business intelligence analyst",
        "data quality specialist",
        "senior data engineer",
        "data scientist",
        "ai engineer",
        "senior applied data/ai researcher",
        
        # Manager & Senior Manager level
        "business analytics manager",
        "data governance manager",
        "data architect",
        "senior data scientist",
        "senior ai engineer",
        "research manager",
        
        # Director & Senior Director level
        "business analytics director",
        "data governance officer",
        "chief data architect",
        "chief data scientist",
        "chief ai engineer",
        "director of research",
        
        # C-Level
        "chief business function officer",
        "chief data officer",
        "chief information officer", 
        "chief analytics officer",
        "chief technology officer",
        "chief scientific officer"
    ]
    
    query_lower = query_text.lower()
    
    # Check for exact matches of full role titles
    for role in roles:
        if role in query_lower:
            return role
            
    return None