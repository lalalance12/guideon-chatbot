from __future__ import annotations
from typing import Dict, Any, Tuple, Optional
import time
import logging
import re, asyncio
import json

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
        """Initialize the intent classifier with an LLM."""
        try:
            self.llm = Ollama(id="llama3.1:8b-instruct-q4_1",
                              provider="Ollama", 
                              host="http://localhost:11434")
            self.agent = Agent(
                name="IntentClassifier", 
                model=self.llm,
                system_message="You are an intent classification assistant that analyzes user queries."
            )
            logger.info("Intent classifier initialized with LLM")
        except Exception as e:
            logger.error(f"Failed to initialize intent classifier LLM: {e}")
            self.agent = None
            logger.warning("Will fall back to rule-based classification")

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the user query to determine the primary intent.
        """
        start = time.time()
        logger.info(f"Classifying intent for query: {query[:60]}...")
        
        # Fall back to rule-based if LLM not available
        if not self.agent:
            return self._rule_based_classification(query, context)
        
        # Prepare conversation history if available
        chat_history = self._format_chat_history(context.get("chat_history", []))
        
        # Check for transitions - look for explicit indicators that user wants to change topics
        transition_indicators = [
            "instead", "rather", "actually", "actually i want", "let's change topics", 
            "i want to ask about", "let me ask", "different question", 
            "another question", "new topic", "change subject", "forget about",
            "don't want", "not interested", "something else"
        ]
        
        # Check if user is explicitly trying to change topics
        is_transition = any(indicator in query.lower() for indicator in transition_indicators)
        
        # Give stronger weight to new intent if transitioning
        if is_transition:
            logger.info("Detected intent transition indicators in query")
            prompt = self._construct_transition_prompt(query, chat_history)
        else:
            # Construct the regular classification prompt
            prompt = self._construct_prompt(query, chat_history)
            
        try:
            # Generate intent classification with LLM
            response = await self.agent.arun(prompt)
            intent, confidence, extracted_entities = self._parse_llm_response(response.content, query)
            
            # Weigh transition more heavily
            if is_transition and confidence > 0.3:  # Lower threshold for transitions
                logger.info(f"Accepting transition to new intent: {intent}")
                # Return with high confidence to encourage transition
                return {
                    "intent": intent,
                    "confidence": max(confidence, 0.75),  # Boost confidence for transitions
                    "extracted_entities": extracted_entities,
                    "is_transition": True,
                    "processing_time": time.time() - start
                }
            
            return {
                "intent": intent,
                "confidence": confidence,
                "extracted_entities": extracted_entities,
                "processing_time": time.time() - start
            }
        except Exception as e:
            logger.error(f"Error in LLM intent classification: {e}")
            # Fall back to rule-based classification
            return self._rule_based_classification(query, context)

    def _construct_transition_prompt(self, query: str, chat_history: str = "") -> str:
        """Build a prompt for the LLM to recognize intent transitions."""
        return f"""The user appears to be changing the topic with this new query: "{query}"

Previous conversation context:
{chat_history}

Based on this new query, determine the user's NEW intent. Ignore previous context when deciding intent.
Choose from these intents:
- knowledge_base_query: Questions about PSF-AAI framework, roles, skills
- learning_pathway: Questions about career paths, progression, how to become certain roles
- course_search: Requests for courses, training, learning materials
- general_conversation: Greetings, thanks, chit-chat, unrelated to PSF-AAI

Return a JSON object with:
1. "intent": the most likely intent category
2. "confidence": confidence score from 0.0 to 1.0
3. "extracted_entities": any relevant entities (roles, skills, etc.)

Example: {{"intent": "knowledge_base_query", "confidence": 0.85, "extracted_entities": {{"role": "Data Scientist"}}}}
"""

    def _construct_prompt(self, query: str, chat_history: str = "") -> str:
        """Build a prompt for the LLM to classify the intent."""
        return f"""Determine the intent of the user's query: "{query}"

Previous conversation context:
{chat_history}

Choose from these intents:
- knowledge_base_query: Questions about PSF-AAI framework, roles, skills
- learning_pathway: Questions about career paths, progression, how to become certain roles
- course_search: Requests for courses, training, learning materials
- general_conversation: Greetings, thanks, chit-chat, unrelated to PSF-AAI

Return a JSON object with:
1. "intent": the most likely intent category
2. "confidence": confidence score from 0.0 to 1.0
3. "extracted_entities": any relevant entities (roles, skills, etc.)

Example: {{"intent": "knowledge_base_query", "confidence": 0.85, "extracted_entities": {{"role": "Data Scientist"}}}}
"""

    def _parse_llm_response(self, response: str, query: str) -> Tuple[Optional[QueryIntent], float, Dict[str, Any]]:
        """Parse the LLM response to extract intent, confidence and entities."""
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
            
            return intent, confidence, entities
            
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            logger.error(f"Error parsing LLM response: {e}")
            logger.debug(f"Raw response: {response}")
            
            # Fallback to basic intent detection
            query_lower = query.lower()
            if any(word in query_lower for word in ["course", "class", "training", "learn", "study"]):
                return QueryIntent.COURSE_SEARCH, 0.6, {}
            elif any(word in query_lower for word in ["career", "path", "become", "role", "job"]):
                return QueryIntent.LEARNING_PATHWAY, 0.6, {}
            elif any(word in query_lower for word in ["what is", "tell me about", "explain", "framework"]):
                return QueryIntent.KNOWLEDGE_BASE_QUERY, 0.6, {}
            else:
                return QueryIntent.GENERAL_CONVERSATION, 0.5, {}

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
        """Fall back to rule-based classification when LLM is unavailable."""
        result = classify_intent(query, context.get("chat_history"))
        logger.info(f"Rule-based classification: {result.get('intent').value} ({result.get('confidence'):.2f})")
        return result