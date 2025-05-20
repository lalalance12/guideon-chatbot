from __future__ import annotations
from typing import Dict, Any, Tuple, Optional
import json
import time
import logging

from .base_agent import BaseAgent
from ..utils.intent_classifier import QueryIntent, classify_intent
from agno.agent import Agent
from agno.models.ollama import Ollama

logger = logging.getLogger(__name__)

class IntentClassifierAgent(BaseAgent):
    """
    Uses an LLM to classify the user's intent from their raw query.
    Provides more sophisticated intent classification than keyword matching.
    """

    def __init__(self) -> None:
        try:
            llama_model = Ollama(id="llama3.1:8b-instruct-q4_1", provider="Ollama", host="http://localhost:11434")
            self.agent = Agent(
                name="IntentClassifier",
                model=llama_model,
            )
            logger.info("Intent classifier agent initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize intent classifier agent: {e}")
            self.agent = None

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the user query to determine the primary intent.
        Uses LLM to naturally detect intent transitions without keyword lists.
        """
        start = time.time()
        logger.info(f"Classifying intent for query: {query[:60]}...")
        
        # Fall back to rule-based if LLM not available
        if not self.agent:
            return self._rule_based_classification(query, context)
        
        # Prepare conversation history and get previous intent
        chat_history = self._format_chat_history(context.get("chat_history", []))
        previous_intent = context.get("previous_intent")
        
        # Build context-aware prompt that asks LLM to assess transition directly
        prompt = self._construct_context_aware_prompt(query, chat_history, previous_intent)
        
        try:
            # Generate intent classification with LLM
            response = await self.agent.arun(prompt)
            intent, confidence, extracted_entities, is_transition = self._parse_transition_aware_response(
                response.content, query, previous_intent
            )
            
            return {
                "intent": intent,
                "confidence": confidence,
                "extracted_entities": extracted_entities,
                "is_transition": is_transition,
                "previous_intent": previous_intent if is_transition else None,
                "processing_time": time.time() - start
            }
        except Exception as e:
            logger.error(f"Error in LLM intent classification: {e}")
            # Fall back to rule-based classification
            return self._rule_based_classification(query, context)

    def _construct_context_aware_prompt(self, query: str, chat_history: str, previous_intent: str = None) -> str:
        """Build a prompt that asks the LLM to consider both intent and potential topic transitions."""
        
        # Add transition analysis to the prompt
        transition_context = ""
        if previous_intent:
            transition_context = f"""
The user's previous conversation was about: {previous_intent}

IMPORTANT: Determine if the user is intentionally changing topics or continuing the previous conversation.
"""

        return f"""Analyze the following user query in the context of their conversation: "{query}"

Previous conversation context:
{chat_history}
{transition_context}

1. Determine the user's primary intent from these categories:
   - knowledge_base_query: Questions about PSF-AAI framework, roles, skills
   - learning_pathway: Questions about career paths, progression, how to become certain roles
   - course_search: Requests for courses, training, learning materials
   - general_conversation: Greetings, thanks, chit-chat, unrelated to PSF-AAI

2. If the previous conversation topic was known, determine if this query represents an intentional topic change.

Return a JSON object with:
- "intent": the most likely intent category
- "confidence": confidence score from 0.0 to 1.0
- "extracted_entities": any relevant entities (roles, skills, etc.)
- "is_topic_change": true/false indicating if user is intentionally changing topics from their previous conversation

Example: {{"intent": "knowledge_base_query", "confidence": 0.85, "extracted_entities": {{"role": "Data Scientist"}}, "is_topic_change": true}}
"""

    def _parse_transition_aware_response(self, response: str, query: str, previous_intent: str = None) -> Tuple[Optional[QueryIntent], float, Dict[str, Any], bool]:
        """Parse the LLM response, including transition detection."""
        try:
            # Clean the response to extract just the JSON
            response_text = response.strip()
            if "```json" in response_text:
                # Extract JSON from code block
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                # Extract from generic code block
                response_text = response_text.split("```")[1].strip()
            
            # Parse the JSON
            intent_data = json.loads(response_text)
            
            # Extract intent 
            intent_str = intent_data.get("intent", "").lower()
            try:
                # Map to QueryIntent enum
                intent = QueryIntent(intent_str)
            except (ValueError, KeyError):
                logger.warning(f"Unknown intent '{intent_str}', defaulting to GENERAL_CONVERSATION")
                intent = QueryIntent.GENERAL_CONVERSATION
                
            # Extract confidence
            confidence = float(intent_data.get("confidence", 0.5))
            
            # Extract entities
            entities = intent_data.get("extracted_entities", {})
            
            # Determine if this is a topic change
            is_transition = intent_data.get("is_topic_change", False)
            
            # If previous intent exists and changed, that's also a sign of transition
            if previous_intent and previous_intent != str(intent) and confidence > 0.4:
                # Intent changed with reasonable confidence
                logger.info(f"Detected intent change from {previous_intent} to {intent}")
                is_transition = True
            
            return intent, confidence, entities, is_transition
            
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            logger.error(f"Error parsing LLM response: {e}")
            logger.debug(f"Raw response: {response}")
            
            # Fallback to basic intent detection
            query_lower = query.lower()
            if any(word in query_lower for word in ["course", "class", "training", "learn", "study"]):
                return QueryIntent.COURSE_SEARCH, 0.6, {}, False
            elif any(word in query_lower for word in ["career", "path", "become", "role", "job"]):
                return QueryIntent.LEARNING_PATHWAY, 0.6, {}, False
            elif any(word in query_lower for word in ["what is", "tell me about", "explain", "framework"]):
                return QueryIntent.KNOWLEDGE_BASE_QUERY, 0.6, {}, False
            else:
                return QueryIntent.GENERAL_CONVERSATION, 0.5, {}, False

    def _format_chat_history(self, history: list) -> str:
        """Format the chat history for inclusion in the prompt."""
        if not history:
            return "No previous conversation."
            
        formatted = []
        for msg in history:
            prefix = "User:" if msg.get("is_user", False) else "Assistant:"
            text = msg.get("text", "").replace("\n", " ")
            if len(text) > 100:
                text = text[:97] + "..."
            formatted.append(f"{prefix} {text}")
        
        # Only keep last few turns to avoid prompt getting too long
        if len(formatted) > 6:
            formatted = formatted[-6:]
        
        return "\n".join(formatted)
        
    def _rule_based_classification(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback to rule-based classification when LLM is unavailable."""
        logger.info("Using rule-based intent classification")
        
        try:
            # Use the simple classifier
            result = classify_intent(query)
            intent = result.get("intent", QueryIntent.GENERAL_CONVERSATION)
            confidence = result.get("confidence", 0.5)
            extracted_entities = result.get("extracted_entities", {})
            
            # Simple transition detection
            previous_intent = context.get("previous_intent")
            is_transition = False
            if previous_intent and previous_intent != str(intent):
                is_transition = True
                
            return {
                "intent": intent,
                "confidence": confidence,
                "extracted_entities": extracted_entities,
                "is_transition": is_transition
            }
        except Exception as e:
            logger.error(f"Error in rule-based classification: {e}")
            return {
                "intent": QueryIntent.GENERAL_CONVERSATION,
                "confidence": 0.3,
                "extracted_entities": {},
                "is_transition": False
            }