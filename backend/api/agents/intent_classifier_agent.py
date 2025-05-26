from __future__ import annotations
from typing import Dict, Any, Tuple, Optional
import time
import logging
import re, asyncio

from .base_agent import BaseAgent
from ..utils.intent_classifier import QueryIntent, classify_intent
from agno.agent import Agent
from agno.models.ollama import Ollama
from .flow_manager_agent import FlowManagerAgent

logger = logging.getLogger(__name__)

class IntentClassifierAgent(BaseAgent):
    """
    Uses an LLM to classify the user's intent from their raw query.
    Provides more sophisticated intent classification than keyword matching.
    """

    def __init__(self, llm=None) -> None:
        """Initialize the intent classifier with an LLM."""
        super().__init__(llm=llm)
        
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
                system_message="You are an intent classification assistant that analyzes user queries."
            )
        except Exception as e:
            logger.error(f"Failed to initialize intent classifier LLM: {e}")
            self.agent = None
            logger.warning("Will fall back to rule-based classification")

    def _get_last_assistant_message(self, chat_history: list) -> str:
        # Find the most recent assistant message in the chat history
        for item in reversed(chat_history):
            if not item.get("is_user", False):
                return item.get("text", "")
        return ""

    def _is_general_conversation(self, query: str, chat_history: list) -> bool:
        # Simple greeting/banter detection
        q = query.lower().strip()
        greetings = [
            "hi", "hello", "hey", "what's up", "how are you", "good morning", "good afternoon", "good evening",
            "how's it going", "how are you doing", "what's new", "what's up guideon", "who are you", "tell me a joke", "what is your name"
        ]
        for g in greetings:
            if g in q:
                return True
        # If the query is short and not semantically related to the last assistant message, treat as general conversation
        if len(q.split()) <= 6:
            last_assistant = self._get_last_assistant_message(chat_history)
            if last_assistant:
                # Use a simple similarity check (can be improved with embeddings)
                if not any(word in last_assistant.lower() for word in q.split() if len(word) > 2):
                    return True
        return False

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        logger.info(f"Classifying intent for query: {query[:60]}...")
        chat_history = context.get("chat_history", [])
        use_history = not self._is_general_conversation(query, chat_history)
        chat_history_for_llm = chat_history if use_history else []
        context_for_llm = dict(context)
        context_for_llm["chat_history"] = chat_history_for_llm

        if not self.agent:
            logger.warning("Using rule-based intent classification (LLM unavailable)")
            classification = self._rule_based_classification(query, context_for_llm)
        else:
            classification = await self._llm_classification(query, context_for_llm)
        
        # Check with flow manager for flow continuity
        chat_id = context.get('chat_id')
        if chat_id:
            # Create flow manager instance 
            flow_manager = FlowManagerAgent()
            
            # Check if we should continue an existing flow
            flow_check = await flow_manager.check_flow_transition(
                query, classification.get("intent"), context
            )
            
            # If flow manager recommends continuing the flow, update the intent
            if flow_check.get("should_continue_flow", False):
                classification["intent"] = flow_check.get("continue_with_intent", classification.get("intent"))
                classification["flow_continued"] = True
        
        # Only add previous_intent for explicit follow-up/clarification queries
        if self._is_vague_followup(query, chat_history):
            previous_intent = context.get("intent")
            classification["previous_intent"] = previous_intent
        # Otherwise, do not add previous_intent to avoid sticky context
        classification["processing_time"] = time.time() - start
        return classification

    async def _llm_classification(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Classify intent using the LLM."""
        start = time.time()
        
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
            QueryIntent.KNOWLEDGE_BASE_QUERY: (
                "Questions seeking factual information, definitions, descriptions, or overviews directly from the PSF-AAI knowledge base. "
                "Includes queries about what a skill or role is, details about proficiency levels, or the structure of the PSF-AAI framework. "
                "Example: 'What is the PSF-AAI?', 'Describe the Data Engineer role', 'What are enabling skills?'"
            ),
            QueryIntent.LEARNING_PATHWAY: (
                "Questions about career progression, upskilling, or learning paths within the PSF-AAI framework. "
                "Includes queries about how to move from one role to another, what skills or courses are needed for advancement, "
                "and steps to achieve a specific job title. Example: 'How do I become a Data Scientist?', "
                "How to be <role>? "
                "'What is the learning path for Machine Learning?', 'What skills do I need to move to Senior AI Engineer?'"
            ),
            QueryIntent.COURSE_SEARCH: (
                "Questions requesting specific courses, training, or educational resources to learn a skill or prepare for a role. "
                "Includes queries mentioning course names, levels, or asking where to study a particular topic. "
                "Example: 'Find courses for Data Visualization', 'Are there Level 3 courses for Applications Development?', 'Recommend training for AI Engineering'"
            ),
            QueryIntent.GENERAL_CONVERSATION: (
                "General conversation, short or topics unrelated to PSF-AAI or professional/career development. "
                "Example: 'How's the weather?', 'Tell me a joke', 'What is your name?'"
            ),
        }
        
        # Build the intent descriptions section
        descriptions = "\n".join([f"- {intent.value}: {desc}" for intent, desc in intent_descriptions.items()])
        
        # Build the prompt
        prompt = f"""# Intent Classification Task

You are an AI assistant specializing in the Philippine Skills Framework for Analytics & AI (PSF-AAI).

## Available Intents:
{descriptions}

{f'## Recent Conversation History:\n{chat_history}\n' if chat_history else ''}

## User Query:
"{query}"

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

    def _is_vague_followup(self, query: str, chat_history: list) -> bool:
        # Detect vague follow-up queries (e.g., 'what about that?', 'tell me more', etc.)
        vague_phrases = [
            "what about that", "what about it", "tell me more", "more info", "can you explain more", "what else", "and that", "what about the last one", "the previous one", "the last course", "the second course", "the first course"
        ]
        q = query.lower().strip()
        for phrase in vague_phrases:
            if phrase in q:
                return True
        # If the query is very short and refers to 'that', 'it', etc.
        if len(q.split()) <= 5 and any(word in q for word in ["that", "it", "one", "this"]):
            return True
        return False