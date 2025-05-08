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
            context: Contains chat_history and memory_context if available
            
        Returns:
            Dict with classified intent and confidence score
        """
        chat_history = context.get('chat_history', None)
        memory_context = context.get('memory_context', {})
        
        # Use memory_context to enhance confidence in intent classification
        if memory_context:
            # If we have recent context for short queries (follow-up questions)
            recent_context = memory_context.get('recent_context', [])
            user_preferences = memory_context.get('user_preferences', [])
            
            # Combine chat history with memory insights for richer context
            if not chat_history:
                chat_history = []
                
            # Create synthetic history from memory contexts if needed
            if recent_context and len(query.split()) <= 5:
                for content in recent_context:
                    chat_history.append(type('MemoryMessage', (), {
                        'content': content,
                        'role': 'user' 
                    }))
        
        # Use existing intent classifier with enhanced chat history
        intent, confidence = classify_intent(query, chat_history)
        
        # Improve intent detection with follow-up patterns
        if confidence < 0.7 and chat_history and len(chat_history) > 1:
            # Check if current query seems like a follow-up
            follow_up_patterns = [
                r"^(and|also|what about|how about|tell me more|elaborate|explain)",
                r"^(yes|yeah|sure|ok|okay|go on)",
                r"^(no|nope)"
            ]
            
            is_follow_up = any(re.match(pattern, query.lower()) for pattern in follow_up_patterns)
            
            if is_follow_up:
                # If it's a follow-up and we have low confidence, try to maintain previous context
                conversation_topics = memory_context.get('conversation_topics', [])
                if conversation_topics:
                    # Use conversation topics to boost confidence for relevant intents
                    for topic in conversation_topics:
                        topic_lower = topic.lower()
                        # Check if any of these key patterns exist in the conversation topics
                        if 'career' in topic_lower or 'path' in topic_lower:
                            intent = QueryIntent.CAREER_PATH
                            confidence += 0.2
                            break
                        elif 'role' in topic_lower or 'job' in topic_lower or 'position' in topic_lower:
                            intent = QueryIntent.ROLE_INFO
                            confidence += 0.2
                            break
                        elif 'skill' in topic_lower and ('level' in topic_lower or 'progress' in topic_lower):
                            intent = QueryIntent.SKILL_PROGRESSION
                            confidence += 0.2
                            break
                        elif 'skill' in topic_lower:
                            intent = QueryIntent.SKILL_INFO
                            confidence += 0.2
                            break
                        elif 'learn' in topic_lower or 'course' in topic_lower or 'education' in topic_lower:
                            intent = QueryIntent.EDUCATION_ADVICE
                            confidence += 0.2
                            break
        
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
            "confidence": min(confidence, 1.0),  # Cap confidence at 1.0
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