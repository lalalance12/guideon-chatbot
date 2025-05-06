from .base_agent import BaseAgent
from ..utils.intent_classifier import classify_intent, QueryIntent
import logging
import re
from typing import Dict, Any

logger = logging.getLogger(__name__)

class IntentClassifierAgent(BaseAgent):
    """Agent responsible for classifying user query intents"""
    
    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify the intent of the user query
        
        Args:
            query: The user's query text
            context: Contains chat_history if available
            
        Returns:
            Dict with classified intent and confidence score
        """
        chat_history = context.get('chat_history', None)
        
        # Use existing intent classifier
        intent, confidence = classify_intent(query, chat_history)
        
        # Extract level information from the query using regex if relevant
        extracted_level = None
        if intent in [QueryIntent.SKILL_LEVEL_INFO, QueryIntent.SKILL_PROGRESSION]:
            level_pattern = r'level\s*(\d+)'
            level_matches = re.findall(level_pattern, query.lower())
            extracted_level = int(level_matches[0]) if level_matches else None
        
        # Get human-readable description of the intent
        description = self._get_intent_description(intent)
        
        # Prepare response with extracted level if available
        result = {
            "intent": intent,
            "confidence": confidence,
            "description": description
        }
        
        if extracted_level is not None:
            result["extracted_level"] = extracted_level
        
        logger.info(f"Intent classified as: {intent.value} (confidence: {confidence:.2f})")
        return result
    
    def _get_intent_description(self, intent):
        """Returns a human-readable description of the intent"""
        descriptions = {
            QueryIntent.CAREER_PATH: "Questions about career progression and advancement paths",
            QueryIntent.ROLE_INFO: "Questions about specific job roles and responsibilities",
            QueryIntent.SKILL_INFO: "Questions about specific skills and competencies",
            QueryIntent.SKILL_LEVEL_INFO: "Questions about specific skill proficiency levels",
            QueryIntent.SKILL_PROGRESSION: "Questions about advancing through skill levels",
            QueryIntent.SKILL_COMPARISON: "Comparing different skills or competencies",
            QueryIntent.EDUCATION_ADVICE: "Questions about learning resources and education",
            QueryIntent.GENERAL_QUERY: "General questions not related to specific career topics"
        }
        return descriptions.get(intent, "General query")