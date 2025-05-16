from __future__ import annotations
import logging
import asyncio
import time
from typing import Dict, Any, Tuple, Optional

from .base_agent import BaseAgent
from ..utils.intent_classifier import QueryIntent
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
            # Initialize with the same pattern used in response_synthesizer_agent.py
            self.llm = Ollama(id="llama3.1:8b-instruct-q4_1",
                              provider="Ollama", 
                              host="http://localhost:11434")
            
            # Create an agent wrapper for the model
            self.agent = Agent(
                name="IntentClassifier",
                model=self.llm,
                system_message="You are an intent classification assistant that analyzes user queries."
            )
            logger.info("IntentClassifierAgent initialized with Ollama LLM")
        except Exception as e:
            logger.error(f"Failed to initialize Ollama LLM: {e}")
            self.llm = None
            self.agent = None

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the user query to determine the primary intent.
        """
        start = time.time()
        logger.info(f"Classifying intent for query: {query[:60]}...")
        
        # Fall back to rule-based if LLM not available
        if not self.agent:
            logger.warning("LLM not available, falling back to rule-based classification")
            return self._rule_based_classification(query, context)
        
        # Prepare conversation history if available
        chat_history = self._format_chat_history(context.get("chat_history", []))
        
        # Construct the classification prompt
        prompt = self._construct_prompt(query, chat_history)
        
        try:
            # Use the agent to generate a response (matching the pattern in synthesizer)
            if hasattr(self.agent, "arun"):
                run_resp = await self.agent.arun(prompt)
            else:
                run_resp = await asyncio.to_thread(self.agent.run, prompt)
                
            # Extract text content from response
            response = getattr(run_resp, "content", str(run_resp))
            
            # Parse the response
            intent, confidence, entities = self._parse_llm_response(response, query)
            
            result = {
                "intent": intent,
                "confidence": confidence,
                "extracted_entities": entities
            }
            
            logger.info(f"Classified intent as {intent.value} with confidence {confidence:.2f} in {time.time() - start:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"LLM classification failed: {e}. Falling back to rule-based.")
            return self._rule_based_classification(query, context)

    def _construct_prompt(self, query: str, chat_history: str = "") -> str:
        """Build a prompt for the LLM to classify the intent."""
        intent_descriptions = {
            QueryIntent.CAREER_PATH: "Questions about career progression, paths from one role to another",
            QueryIntent.ROLE_INFO: "Questions about specific roles or positions",
            QueryIntent.SKILL_INFO: "Questions about specific skills or competencies",
            QueryIntent.SKILL_LEVEL_INFO: "Questions about specific proficiency levels for skills",
            QueryIntent.SKILL_PROGRESSION: "Questions about how to advance skills between levels",
            QueryIntent.SKILL_COMPARISON: "Comparing different skills",
            QueryIntent.EDUCATION_ADVICE: "Questions about training, courses, or learning paths",
            QueryIntent.FUNCTIONAL_SKILLS: "Questions about technical/functional skills",
            QueryIntent.ENABLING_SKILLS: "Questions about soft skills/enabling skills",
            QueryIntent.JOB_ROLES: "Questions about specific job roles",
            QueryIntent.CAREER_MAP: "Questions about overall career mapping",
            QueryIntent.GENERAL_QUERY: "General questions or chitchat"
        }
        
        # Build the intent descriptions section
        descriptions = "\n".join([f"- {intent.value}: {desc}" for intent, desc in intent_descriptions.items()])
        
        # Build the history section if present
        history_section = ""
        if chat_history:
            history_section = "## Recent Conversation History:\n{}\n".format(chat_history)
        
        # Build the prompt
        prompt = """# Intent Classification Task

You are an AI assistant specializing in classifying user queries about data science, AI, and career development.

## Available Intents:
{}

## User Query:
"{}"

{}
## Instructions:
1. Analyze the query and determine the SINGLE most appropriate intent
2. Extract any relevant entities (skills, roles, levels mentioned)
3. Provide your classification in the following format:

INTENT: [intent name]
CONFIDENCE: [0.0-1.0]
ENTITIES: [comma-separated list of extracted entities]
REASONING: [brief explanation of why you chose this intent]

Only respond with this exact format!
""".format(descriptions, query, history_section)
        
        return prompt

    def _parse_llm_response(self, response: str, query: str) -> Tuple[QueryIntent, float, Dict[str, Any]]:
        """Parse the LLM's response to extract intent, confidence and entities."""
        try:
            # Default values
            intent = QueryIntent.GENERAL_QUERY
            confidence = 0.5
            entities = {}
            
            # Parse lines
            lines = response.strip().split('\n')
            for line in lines:
                line = line.strip()
                
                if line.startswith("INTENT:"):
                    intent_str = line[7:].strip().lower()
                    # Try to match to enum
                    for intent_enum in QueryIntent:
                        if intent_enum.value.lower() == intent_str:
                            intent = intent_enum
                            break
                
                elif line.startswith("CONFIDENCE:"):
                    try:
                        conf_str = line[11:].strip()
                        confidence = float(conf_str)
                        # Ensure valid range
                        confidence = max(0.0, min(1.0, confidence))
                    except:
                        pass
                
                elif line.startswith("ENTITIES:"):
                    entities_str = line[9:].strip()
                    if entities_str and entities_str.lower() != "none":
                        entity_list = [e.strip() for e in entities_str.split(',')]
                        entities = {"detected": entity_list}
            
            return intent, confidence, entities
            
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            # Fall back to a reasonable default
            return QueryIntent.GENERAL_QUERY, 0.5, {}

    def _format_chat_history(self, history: list) -> str:
        """Format chat history for inclusion in the prompt."""
        if not history:
            return ""
            
        formatted = []
        for msg in history[-3:]:  # Only use last 3 messages for context
            if 'role' in msg and 'content' in msg:
                role = "User" if msg['role'].lower() == 'user' else "Assistant"
                content = msg['content']
                formatted.append(f"{role}: {content}")
                
        return "\n".join(formatted)

    def _rule_based_classification(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Fall back to rule-based classification when LLM is unavailable."""
        # Import the original classifier function
        from ..utils.intent_classifier import classify_intent, extract_level_from_query
        
        # Use the existing rule-based classifier
        intent, confidence = classify_intent(query, context.get('chat_history'))
        
        # Extract any entities using existing methods
        level = extract_level_from_query(query) if extract_level_from_query else None
        entities = {"level": level} if level else {}
        
        return {
            "intent": intent,
            "confidence": confidence,
            "extracted_entities": entities
        }