from __future__ import annotations
from typing import Dict, Any, Tuple, Optional
import time
import logging
import re, asyncio

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
            logger.warning("Using rule-based intent classification (LLM unavailable)")
            classification = self._rule_based_classification(query, context)
            classification["processing_time"] = time.time() - start
            return classification
        
        # Prepare conversation history if available
        chat_history = self._format_chat_history(context.get("chat_history", []))
        print(f"{chat_history}, this is chat history" )
        # Construct the classification prompt
        prompt = self._construct_prompt(query, chat_history)
            
        try:
                # Generate classification with LLM using robust method calling
                if hasattr(self.agent, "arun"):
                    run_response = await self.agent.arun(prompt)
                else:
                    # Fall back to threaded run() if arun() isn't available
                    run_response = await asyncio.to_thread(self.agent.run, prompt)
                    
                # Extract content safely using getattr for robustness
                response = getattr(run_response, "content", str(run_response))
                logger.debug(f"LLM classification response: {response[:200]}...")

                # Parse the LLM's response
                intent, confidence, extracted_entities = self._parse_llm_response(response, query)

                # If parsing failed, fall back to rule-based
                if not intent:
                    logger.warning("Failed to parse LLM response, using rule-based classification")
                    classification = self._rule_based_classification(query, context)
                else:
                    classification = {
                        "intent": intent,
                        "confidence": confidence,
                        "extracted_entities": extracted_entities,
                        "llm_response": response[:500]  # Store truncated response for debugging
                    }

                classification["processing_time"] = time.time() - start
                classification["method"] = "llm" if intent else "rule_based_fallback"
                return classification

        except Exception as e:
            logger.exception(f"Error during intent classification: {e}")
            # Fall back to rule-based on error
            classification = self._rule_based_classification(query, context)
            classification["processing_time"] = time.time() - start
            classification["method"] = "rule_based_fallback"
            classification["error"] = str(e)
            return classification

    def _construct_prompt(self, query: str, chat_history: str = "") -> str:
        """Build a prompt for the LLM to classify the intent."""
        intent_descriptions = {
            QueryIntent.KNOWLEDGE_BASE_QUERY: "Questions about PSF-AAI framework, including roles, skills, career paths, proficiency levels, or any information contained in the PSF-AAI knowledge base. Questions about career roles, progression paths, or how to develop skills for specific roles within the PSF-AAI framework" ,
            # QueryIntent.LEARNING_PATHWAY: "Questions about career roles, progression paths, or how to develop skills for specific roles within the PSF-AAI framework",
            QueryIntent.COURSE_SEARCH: "Questions about asking for specific courses even if they have levels (eg. Applications Development(Level 3)), training, or education resources to learn particular skills",
            QueryIntent.GENERAL_CONVERSATION: "General conversation or topics unrelated to PSF-AAI or professional development",
        }
        
        # Build the intent descriptions section
        descriptions = "\n".join([f"- {intent.value}: {desc}" for intent, desc in intent_descriptions.items()])
        
        # Build the prompt
        prompt = f"""# Intent Classification Task

You are an AI assistant specializing in the Philippine Skills Framework for Analytics & AI (PSF-AAI).

## Available Intents:
{descriptions}

## User Query:
"{query}"

{f'## Recent Conversation History:\n{chat_history}\n' if chat_history else ''}

## Instructions:
1. Analyze the query and determine the SINGLE most appropriate intent
2. Extract any relevant entities (skills, roles mentioned)
3. Provide your classification in the following format:

INTENT: [intent name]
CONFIDENCE: [0.0-1.0]
ENTITIES: [comma-separated list of extracted entities]
REASONING: [brief explanation of why you chose this intent]

Only respond with this exact format!
"""
        return prompt

    def _parse_llm_response(self, response: str, query: str) -> Tuple[Optional[QueryIntent], float, Dict[str, Any]]:
        """Parse the LLM's intent classification response."""
        try:
            # Extract intent
            intent_match = re.search(r"INTENT:\s*(\w+)", response)
            intent_name = intent_match.group(1).lower() if intent_match else ""
            
            # Try to map the intent name to an enum
            intent = None
            for enum_intent in QueryIntent:
                if enum_intent.value == intent_name:
                    intent = enum_intent
                    break
            
            # If no match, try to find the most similar intent
            if not intent:
                for enum_intent in QueryIntent:
                    if enum_intent.value in intent_name or intent_name in enum_intent.value:
                        intent = enum_intent
                        break
            
            # Extract confidence
            confidence_match = re.search(r"CONFIDENCE:\s*(0\.\d+|1\.0|1)", response)
            confidence = float(confidence_match.group(1)) if confidence_match else 0.5
            
            # Extract entities
            entities_match = re.search(r"ENTITIES:\s*(.+?)(?=\n|$)", response)
            entities_text = entities_match.group(1) if entities_match else ""
            
            # Process entities
            extracted_entities = {}
            if entities_text and entities_text.lower() != "none":
                entity_items = [item.strip() for item in entities_text.split(",")]
                
                for entity in entity_items:
                    if "role:" in entity.lower():
                        extracted_entities["extracted_role"] = entity.split(":", 1)[1].strip()
                    elif "level:" in entity.lower():
                        extracted_entities["extracted_level"] = entity.split(":", 1)[1].strip()
                    elif "skill:" in entity.lower():
                        extracted_entities["skill"] = entity.split(":", 1)[1].strip()
                    else:
                        # Just add as generic entity
                        extracted_entities[f"entity_{len(extracted_entities)}"] = entity
            
            # Fall back to rule-based role extraction if LLM didn't find a role
            if intent == QueryIntent.LEARNING_PATHWAY and "extracted_role" not in extracted_entities:
                from ..utils.intent_classifier import extract_role_from_query
                role = extract_role_from_query(query)
                if role:
                    extracted_entities["extracted_role"] = role
            
            # Return parsed information
            if intent:
                return intent, confidence, extracted_entities
            else:
                logger.warning(f"Failed to parse intent from: {response[:100]}")
                return None, 0.0, {}
                
        except Exception as e:
            logger.exception(f"Error parsing LLM response: {e}")
            return None, 0.0, {}

    def _format_chat_history(self, history: list) -> str:
        """Format chat history for context in the prompt."""
        if not history or len(history) == 0:
            return ""
            
        formatted = []
        for item in history[-5:]:  # Only use the 5 most recent messages
            role = "User" if item.get("is_user", False) else "Assistant"
            text = item.get("text", "").replace("\n", " ")
            formatted.append(f"{role}: {text}")
            
        return "\n".join(formatted)

    def _rule_based_classification(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Fall back to rule-based classification when LLM is unavailable."""
        result = classify_intent(query, context.get("chat_history"))
        logger.info(f"Rule-based classification: {result.get('intent').value} ({result.get('confidence'):.2f})")
        return result