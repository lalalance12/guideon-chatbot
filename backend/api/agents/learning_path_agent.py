from __future__ import annotations
from typing import Dict, Any, List, Optional
import logging
import asyncio

from .base_agent import BaseAgent
from ..utils.intent_classifier import QueryIntent
from agno.agent import Agent

logger = logging.getLogger(__name__)

class LearningPathAgent(BaseAgent):
    """
    Generates personalized learning pathways based on career aspirations.
    Provides information about roles, required skills, and progression paths.
    """
    
    def __init__(self, llm=None):
        """Initialize the learning path agent with an optional LLM."""
        super().__init__(llm=llm)
        self.agent = None
        if self.llm:
            self.agent = Agent(
                name="LearningPathAgentLLM",
                model=self.llm,
                system_message="You are a career pathway assistant for the PSF-AAI framework."
            )

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process queries related to learning pathways and career progression"""
        flow_context, flow_action, _ = self.get_flow_context(context)
        intent = context.get("intent")
        PSF_AAI_ROLES = [
            "associate data analyst",
            "data analyst",
            "associate data engineer",
            "business intelligence analyst",
            "data engineer",
            "machine learning engineer",
            "applied data/ai researcher",
            "senior business intelligence analyst",
            "data quality specialist",
            "senior data engineer",
            "data scientist",
            "ai engineer",
            "senior applied data/ai researcher",
            "business analytics manager",
            "data governance manager",
            "data architect",
            "senior data scientist",
            "senior ai engineer",
            "research manager",
            "business analytics director",
            "data governance officer",
            "chief data architect",
            "chief data scientist",
            "chief ai engineer",
            "director of research",
            "chief business function officer",
            "chief data officer",
            "chief information officer",
            "chief analytics officer",
            "chief technology officer",
            "chief scientific officer"
        ]
        if intent != QueryIntent.LEARNING_PATHWAY:
            return {
                "found": False,
                "reason": "not_learning_pathway_intent",
                "message": "No learning path information for this query type."
            }
        try:
            extracted_entities = context.get("extracted_entities", {})
            possible_entities = []
            if "extracted_role" in extracted_entities:
                if isinstance(extracted_entities["extracted_role"], list):
                    possible_entities.extend([r for r in extracted_entities["extracted_role"] if r])
                elif extracted_entities["extracted_role"]:
                    possible_entities.append(extracted_entities["extracted_role"])
            filtered_entities = [e for e in possible_entities if e and e.lower() in PSF_AAI_ROLES]
            if len(filtered_entities) == 0:
                # Vague or no valid entity: ask for clarification
                clarification_text = "Please clarify your career goal. Which of these PSF-AAI career roles are you interested in?"
                return {
                    "found": False,
                    "reason": "no_valid_entity_specified",
                    "message": clarification_text,
                    "available_roles": PSF_AAI_ROLES,
                    "show_role_selection_button": True
                }
            elif len(filtered_entities) == 1:
                entity = filtered_entities[0]
                response_text = f"Here is the pathway for the {entity} role you requested. You can click the button below to view detailed information about this career path."
                # Add a log statement to confirm this is being reached
                logger.info(f"[LearningPathAgent] Found valid entity: {entity}, returning with show_goto_career_button=True")
                return {
                    "found": True,
                    "entity": entity,
                    "message": response_text,
                    "show_goto_career_button": True,
                    "goto_career_role": entity
                }
            else:
                # Multiple possible roles/entities found
                clarification_text = "I found a few possible matches for your query. Which of these PSF-AAI career roles are you interested in?"
                return {
                    "found": False,
                    "reason": "multiple_entities_found",
                    "message": clarification_text,
                    "available_roles": filtered_entities, # Show only the filtered matches
                    "show_role_selection_button": True
                }
        except Exception as e:
            logger.exception(f"Error in learning path agent: {str(e)}")
            return {
                "found": False,
                "reason": "exception",
                "message": f"Error retrieving learning path information: {str(e)}"
            }