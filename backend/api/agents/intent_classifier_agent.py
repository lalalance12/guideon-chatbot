import re
import logging
from typing import Dict, Any
from .base_agent import BaseAgent
from ..utils.intent_classifier import classify_intent, extract_level_from_query, QueryIntent

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
        
        # Extract level or section information from the query
        extracted_level = extract_level_from_query(query)
        psf_section = None
        
        # Map intent to corresponding PSF section if applicable
        if intent == QueryIntent.FUNCTIONAL_SKILLS:
            psf_section = "functional_skills"
        elif intent == QueryIntent.ENABLING_SKILLS:
            psf_section = "enabling_skills"
        elif intent in [QueryIntent.ROLE_INFO, QueryIntent.JOB_ROLES]:
            psf_section = "job_roles"
        elif intent == QueryIntent.CAREER_PATH:
            psf_section = "career_map"
        
        # Get human-readable description of the intent
        description = self._get_intent_description(intent)
        
        # Prepare response with extracted level or section
        result = {
            "intent": intent,
            "confidence": confidence,
            "description": description
        }
        
        if extracted_level is not None:
            result["extracted_level"] = extracted_level
        
        if psf_section is not None:
            result["psf_section"] = psf_section
        
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
            QueryIntent.FUNCTIONAL_SKILLS: "Questions about functional skills in the PSF-AAI framework",
            QueryIntent.ENABLING_SKILLS: "Questions about enabling skills in the PSF-AAI framework",
            QueryIntent.JOB_ROLES: "Questions about job roles in the PSF-AAI framework",
            QueryIntent.CAREER_MAP: "Questions about career maps in the PSF-AAI framework",
            QueryIntent.GENERAL_QUERY: "General questions not related to specific career topics"
        }
        return descriptions.get(intent, "General query")
    
    def handle_error(self, err):
        """Handle errors during intent classification"""
        logger.error(f"Error in intent classification: {err}")
        return {
            "intent": QueryIntent.GENERAL_QUERY,
            "confidence": 0.0,
            "description": "Could not determine intent due to an error",
            "error": str(err)
        }