from __future__ import annotations
from typing import Dict, Any, Optional
import time
import logging
import json
import re
import asyncio

from .base_agent import BaseAgent
from ..utils.intent_classifier import QueryIntent, minimal_fallback_classify
from agno.agent import Agent
from agno.models.ollama import Ollama
from .flow_manager_agent import FlowManagerAgent

logger = logging.getLogger(__name__)

class IntentClassifierAgent(BaseAgent):
    """
    LLM-first intent classifier with minimal heuristic fallback.
    Uses sophisticated prompt engineering instead of keyword matching.
    """

    def __init__(self, llm=None) -> None:
        """Initialize the intent classifier with an LLM."""
        super().__init__(llm=llm)
        
        self.system_prompt = """You are an expert intent classifier for the Philippine Skills Framework for Analytics & AI (PSF-AAI).

Your job is to classify user queries into exactly ONE intent and determine if conversation context is needed.

INTENTS:
1. knowledge_base_query - Questions about PSF-AAI facts, roles, skills, definitions, framework structure
2. learning_pathway - Career goal statements ("I want to become...", "My goal is to be...")  
3. course_search - Requests for courses, training, educational resources
4. general_conversation - Greetings, casual chat, jokes, non-PSF topics

CONTEXT ANALYSIS:
Determine if the query needs previous conversation context:
- needs_context: true if query uses pronouns (it, that, this) or has incomplete references
- needs_context: false if query is complete and self-contained

Always respond in this exact JSON format:
{
  "intent": "intent_name",
  "confidence": 0.95,
  "needs_context": true,
  "entities": {
    "role": "extracted role if any",
    "skill": "extracted skill if any", 
    "level": "extracted level if any"
  },
  "reasoning": "brief explanation"
}"""
        
        try:
            # Use provided LLM if available, otherwise initialize own
            if not self.llm:
                self.llm = Ollama(id="llama3.1:8b-instruct-q4_1",
                                provider="Ollama", 
                                host="http://localhost:11434")
                logger.info("Intent classifier initialized with its own LLM")
            else:
                logger.info("Intent classifier using shared LLM instance")
                
            self.agent = Agent(
                name="IntentClassifier", 
                model=self.llm,
                system_message=self.system_prompt
            )
        except Exception as e:
            logger.error(f"Failed to initialize intent classifier LLM: {e}")
            self.agent = None
            logger.warning("Will fall back to minimal rule-based classification")

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        logger.info(f"LLM-first intent classification for: {query[:60]}...")
        
        if not self.agent:
            logger.warning("LLM unavailable, using minimal fallback")
            return self._emergency_fallback(query, context)
        
        try:
            # Step 1: Initial classification to determine context needs
            initial_result = await self._classify_with_llm(query, context, use_history=False)
            
            # Step 2: If LLM says it needs context, re-classify with chat history
            if initial_result.get("needs_context") and context.get("chat_history"):
                logger.info("LLM determined context is needed - re-classifying with chat history")
                final_result = await self._classify_with_llm(query, context, use_history=True)
                final_result["used_context"] = True
            else:
                final_result = initial_result
                final_result["used_context"] = False
            
            # Check with flow manager for flow continuity
            await self._check_flow_continuity(query, final_result, context)
            
            final_result["processing_time"] = time.time() - start
            final_result["method"] = "llm_classification"
            
            return final_result
            
        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return self._emergency_fallback(query, context)

    async def _classify_with_llm(self, query: str, context: Dict[str, Any], use_history: bool = False) -> Dict[str, Any]:
        """Perform LLM-based classification with optional chat history."""
        
        # Build prompt
        if use_history and context.get("chat_history"):
            chat_history = self._format_chat_history(context["chat_history"][-3:])
            prompt = f"""Previous conversation:
{chat_history}

Current query: "{query}"

Classify this query with full conversation context."""
        else:
            prompt = f"""Query: "{query}"

Classify this standalone query."""
        
        # Get LLM response
        if hasattr(self.agent, "arun"):
            response = await self.agent.arun(prompt)
        else:
            response = await asyncio.to_thread(self.agent.run, prompt)
            
        response_text = getattr(response, "content", str(response))
        logger.debug(f"LLM response: {response_text[:200]}...")
        
        # Parse JSON response
        return self._parse_llm_response(response_text, query)

    def _parse_llm_response(self, response_text: str, query: str) -> Dict[str, Any]:
        """Parse JSON response from LLM with robust error handling."""
        try:
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in LLM response")
                
            parsed_json = json.loads(json_match.group())
            
            # Validate and convert intent
            intent_name = parsed_json.get("intent", "").lower()
            intent_map = {
                "knowledge_base_query": QueryIntent.KNOWLEDGE_BASE_QUERY,
                "learning_pathway": QueryIntent.LEARNING_PATHWAY,
                "course_search": QueryIntent.COURSE_SEARCH,
                "general_conversation": QueryIntent.GENERAL_CONVERSATION
            }
            
            intent = intent_map.get(intent_name)
            if not intent:
                # Try partial matching
                for key, value in intent_map.items():
                    if key in intent_name or intent_name in key:
                        intent = value
                        break
                
                if not intent:
                    raise ValueError(f"Unknown intent: {intent_name}")
            
            # Extract entities and clean them up
            entities = parsed_json.get("entities", {})
            extracted_entities = {}
            
            # Clean up entity extraction
            if isinstance(entities, dict):
                for key, value in entities.items():
                    if value and value.lower() not in ["none", "null", "", "n/a"]:
                        if key == "role":
                            extracted_entities["extracted_role"] = value
                        elif key == "level":
                            extracted_entities["extracted_level"] = value
                        elif key == "skill":
                            extracted_entities["skill"] = value
                        else:
                            extracted_entities[key] = value
            
            # Fallback role extraction for learning pathway
            if intent == QueryIntent.LEARNING_PATHWAY and "extracted_role" not in extracted_entities:
                from ..utils.intent_classifier import extract_role_from_query
                role = extract_role_from_query(query)
                if role:
                    extracted_entities["extracted_role"] = role
            
            return {
                "intent": intent,
                "confidence": min(max(parsed_json.get("confidence", 0.8), 0.0), 1.0),
                "needs_context": parsed_json.get("needs_context", False),
                "extracted_entities": extracted_entities,
                "reasoning": parsed_json.get("reasoning", "")
            }
            
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.debug(f"Response was: {response_text}")
            raise

    def _format_chat_history(self, history: list) -> str:
        """Format chat history for LLM context."""
        if not history:
            return ""
            
        formatted = []
        for item in history:
            role = "User" if item.get("is_user", False) else "Assistant"
            text = item.get("text", "").replace("\n", " ")[:200]  # Truncate long messages
            formatted.append(f"{role}: {text}")
            
        return "\n".join(formatted)

    async def _check_flow_continuity(self, query: str, classification: Dict[str, Any], context: Dict[str, Any]):
        """Check with flow manager for flow continuity."""
        chat_id = context.get('chat_id')
        if not chat_id:
            return
            
        try:
            flow_manager = FlowManagerAgent()
            flow_check = await flow_manager.check_flow_transition(
                query, classification.get("intent"), context
            )
            
            if flow_check.get("should_continue_flow", False):
                classification["intent"] = flow_check.get("continue_with_intent", classification["intent"])
                classification["flow_continued"] = True
                logger.info("Flow manager updated intent for flow continuity")
                
        except Exception as e:
            logger.error(f"Flow continuity check failed: {e}")
            # Don't fail the entire classification for this

    def _emergency_fallback(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Ultra-minimal fallback when LLM is completely unavailable."""
        try:
            # Use the simplified fallback from utils
            result = minimal_fallback_classify(query)
            result["method"] = "emergency_fallback"
            result["processing_time"] = 0.1
            result["used_context"] = False
            
            logger.warning(f"Emergency fallback classification: {result['intent'].value}")
            return result
            
        except Exception as e:
            logger.error(f"Even emergency fallback failed: {e}")
            # Absolute last resort
            return {
                "intent": QueryIntent.KNOWLEDGE_BASE_QUERY,
                "confidence": 0.3,
                "extracted_entities": {},
                "method": "absolute_fallback",
                "processing_time": 0.1,
                "used_context": False,
                "error": str(e)
            }