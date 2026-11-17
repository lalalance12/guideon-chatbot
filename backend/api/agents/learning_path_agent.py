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
    Enhanced with flow context awareness and connectivity features.
    """
    
    def __init__(self, llm=None):
        super().__init__(llm=llm)
        self.agent = None
        if self.llm:
            self.agent = Agent(
                name="LearningPathAgentLLM",
                model=self.llm,
                system_message="You are a career pathway assistant for the PSF-AAI framework with enhanced connectivity awareness."
            )

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """**ENHANCED: Process with flow context awareness**"""
        logger.info(f"[LearningPathAgent] Processing with flow enhancement: {query[:60]}")
        
        # **NEW: Extract flow context**
        flow_context, flow_action, response_format, flow_state = self.get_flow_context(context)
        flow_preserved_context = self.get_flow_preserved_context(context)
        connectivity_context = self.get_connectivity_context(context)
        focus_role, focus_topic = self.get_focus_elements(context)
        
        logger.debug(f"[LearningPathAgent] Flow context - Action: {flow_action}, Focus: role={focus_role}")
        
        intent = context.get("intent")
        if intent != QueryIntent.LEARNING_PATHWAY:
            return self._create_invalid_intent_response(context)
        
        try:
            # **ENHANCED: Extract entities with flow context**
            extracted_entities = context.get("extracted_entities", {})
            possible_entities = self._extract_enhanced_entities(extracted_entities, flow_preserved_context, focus_role)
            filtered_entities = self._filter_psf_entities(possible_entities)
            
            logger.debug(f"[LearningPathAgent] Extracted entities: {possible_entities}, Filtered: {filtered_entities}")
            
            # **ENHANCED: Process based on flow action and entities**
            if flow_action == "career_overview_with_connections" and focus_role:
                return self._create_career_overview_response(focus_role, context)
            elif flow_action == "clarify_entity_with_suggestions":
                return self._create_enhanced_clarification_response(context, filtered_entities)
            elif len(filtered_entities) == 0:
                return self._create_enhanced_clarification_response(context, [])
            elif len(filtered_entities) == 1:
                return self._create_career_pathway_response(filtered_entities[0], context)
            else:
                return self._create_multiple_entities_response(filtered_entities, context)
                
        except Exception as e:
            logger.exception(f"Error in enhanced learning path agent: {str(e)}")
            return self._create_error_response(str(e), context)

    def _extract_enhanced_entities(self, extracted_entities: Dict[str, Any], 
                                 flow_preserved_context: Dict[str, Any], 
                                 focus_role: str) -> List[str]:
        """**ENHANCED: Extract entities with flow context**"""
        possible_entities = []
        
        # First check flow context
        if focus_role:
            possible_entities.append(focus_role)
            
        # Check preserved flow context
        if flow_preserved_context.get("current_entity"):
            possible_entities.append(flow_preserved_context["current_entity"])
            
        # Check extracted entities
        if "extracted_role" in extracted_entities:
            role_data = extracted_entities["extracted_role"]
            if isinstance(role_data, list):
                possible_entities.extend([r for r in role_data if r])
            elif role_data:
                possible_entities.append(role_data)
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys([e for e in possible_entities if e]))

    def _create_career_overview_response(self, role: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """**NEW: Create enhanced career overview response**"""
        
        flow_context, flow_action, response_format, flow_state = self.get_flow_context(context)
        
        response_text = f"Here's your enhanced career pathway for the {role} role. This includes detailed skill requirements, progression paths, and connectivity with other PSF-AAI roles."
        
        result = {
            "found": True,
            "entity": role,
            "message": response_text,
            "show_goto_career_button": True,
            "goto_career_role": role,
            "career_overview_mode": True,
            "connectivity_enhanced": True
        }
        
        # Add flow-specific enhancements
        if response_format.get("include_pathways"):
            result["include_progression_paths"] = True
            
        if flow_context.get("include_pathways"):
            result["show_progression_options"] = True
            
        logger.info(f"[LearningPathAgent] Created career overview for {role} with connectivity features")
        return self.add_flow_metadata(result, context)

    def _create_enhanced_clarification_response(self, context: Dict[str, Any], 
                                              filtered_entities: List[str] = None) -> Dict[str, Any]:
        """**ENHANCED: Create clarification response with flow context**"""
        
        flow_context, flow_action, response_format, flow_state = self.get_flow_context(context)
        focus_role, focus_topic = self.get_focus_elements(context)
        
        PSF_AAI_ROLES = [
            "associate data analyst", "data analyst", "associate data engineer",
            "business intelligence analyst", "data engineer", "machine learning engineer",
            "applied data/ai researcher", "senior business intelligence analyst",
            "data quality specialist", "senior data engineer", "data scientist",
            "ai engineer", "senior applied data/ai researcher", "business analytics manager",
            "data governance manager", "data architect", "senior data scientist",
            "senior ai engineer", "research manager", "business analytics director",
            "data governance officer", "chief data architect", "chief data scientist",
            "chief ai engineer", "director of research", "chief business function officer",
            "chief data officer", "chief information officer", "chief analytics officer",
            "chief technology officer", "chief scientific officer"
        ]
        
        # Enhanced clarification based on flow context
        if filtered_entities and len(filtered_entities) > 1:
            clarification_text = "I found multiple career roles that might interest you. Which PSF-AAI role would you like to explore in detail?"
            available_roles = filtered_entities
        elif focus_topic:
            clarification_text = f"I see you're interested in {focus_topic}. Which PSF-AAI career role would you like to explore that uses this skill?"
            available_roles = PSF_AAI_ROLES
        else:
            clarification_text = "Please clarify your career goal. Which PSF-AAI career role interests you? I can show detailed pathways, skill requirements, and progression options."
            available_roles = PSF_AAI_ROLES
        
        result = {
            "found": False,
            "reason": "clarification_needed",
            "message": clarification_text,
            "available_roles": available_roles,
            "show_role_selection_button": True,
            "connectivity_hints": True
        }
        
        # Add flow-specific enhancements
        if flow_action == "clarify_entity_with_suggestions":
            result["enhanced_suggestions"] = True
            result["show_connectivity_preview"] = True
            
        return self.add_flow_metadata(result, context)

    def _create_career_pathway_response(self, entity: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """**ENHANCED: Create career pathway response with connectivity**"""
        
        flow_context, flow_action, response_format, flow_state = self.get_flow_context(context)
        
        response_text = f"Here is the enhanced pathway for the {entity} role. Click below to view detailed information including skill requirements, progression paths, and connections to other roles."
        
        result = {
            "found": True,
            "entity": entity,
            "message": response_text,
            "show_goto_career_button": True,
            "goto_career_role": entity,
            "pathway_enhanced": True
        }
        
        # Add flow-specific features
        if response_format.get("connectivity_features"):
            result["include_role_connections"] = True
            result["include_skill_mappings"] = True
            
        logger.info(f"[LearningPathAgent] Created enhanced pathway for {entity}")
        return self.add_flow_metadata(result, context)

    def _create_multiple_entities_response(self, filtered_entities: List[str], context: Dict[str, Any]) -> Dict[str, Any]:
        """**ENHANCED: Handle multiple entities with connectivity context**"""
        
        clarification_text = "I found several career roles that match your query. Which one would you like to explore in detail? I can show detailed pathways and connections for each."
        
        result = {
            "found": False,
            "reason": "multiple_entities_found",
            "message": clarification_text,
            "available_roles": filtered_entities,
            "show_role_selection_button": True,
            "multiple_options_mode": True,
            "connectivity_preview": True
        }
        
        return self.add_flow_metadata(result, context)

    def _filter_psf_entities(self, entities: List[str]) -> List[str]:
        """Filter entities to only include PSF-AAI recognized roles"""
        PSF_AAI_ROLES = [
            "associate data analyst", "data analyst", "associate data engineer",
            "business intelligence analyst", "data engineer", "machine learning engineer",
            "applied data/ai researcher", "senior business intelligence analyst",
            "data quality specialist", "senior data engineer", "data scientist",
            "ai engineer", "senior applied data/ai researcher", "business analytics manager",
            "data governance manager", "data architect", "senior data scientist",
            "senior ai engineer", "research manager", "business analytics director",
            "data governance officer", "chief data architect", "chief data scientist",
            "chief ai engineer", "director of research", "chief business function officer",
            "chief data officer", "chief information officer", "chief analytics officer",
            "chief technology officer", "chief scientific officer"
        ]
        
        return [e for e in entities if e and e.lower() in PSF_AAI_ROLES]

    def _create_invalid_intent_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle non-learning pathway intents"""
        result = {
            "found": False,
            "reason": "not_learning_pathway_intent",
            "message": "This doesn't appear to be a career pathway question. How can I help you with PSF-AAI career guidance?"
        }
        return self.add_flow_metadata(result, context)

    def _create_error_response(self, error_message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Create error response with flow context"""
        result = {
            "found": False,
            "reason": "processing_error",
            "message": f"I encountered an issue processing your career pathway request: {error_message}",
            "error": error_message
        }
        return self.add_flow_metadata(result, context)