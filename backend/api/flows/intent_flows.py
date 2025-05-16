from enum import Enum
from typing import Dict, Any, List, Optional
import logging
from abc import ABC, abstractmethod
from ..utils.intent_classifier import QueryIntent, extract_role_from_query

logger = logging.getLogger(__name__)

class FlowStage(Enum):
    INITIAL = "initial"
    CLARIFICATION = "clarification"
    INFORMATION = "information"
    RECOMMENDATION = "recommendation"
    FOLLOW_UP = "follow_up"

class IntentFlow(ABC):
    """Base class for intent-specific conversation flows"""
    
    def __init__(self):
        self.current_stage = FlowStage.INITIAL
        self.context = {}
    
    @abstractmethod
    def process(self, query: str, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        """Process the current query within this flow and update state"""
        return {"flow_action": "general_response"}
    
    @abstractmethod
    def get_next_response_format(self) -> Dict[str, Any]:
        """Return formatting instructions for the next response"""
        return {"format": "conversational"}
    
    @abstractmethod
    def should_activate_agents(self) -> List[str]:
        """Return list of agent names that should be activated for current stage"""
        return ["knowledge_agent"]

class KnowledgeBaseFlow(IntentFlow):
    """Flow for PSF-AAI knowledge base queries"""
    
    def process(self, query: str, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        # Initial query - information stage
        if self.current_stage == FlowStage.INITIAL:
            self.current_stage = FlowStage.INFORMATION
            
            # Check for career map specific query
            query_lower = query.lower()
            if any(term in query_lower for term in ["career map", "career path", "job progression", "domains", "career tracks"]):
                self.context["knowledge_sections"] = ["career_map"]
                return {"flow_action": "retrieve_career_map"}
            else:
                self.context["knowledge_sections"] = ["functional_skills", "enabling_skills", "roles", "career_map"]
                return {"flow_action": "retrieve_knowledge", "sections": self.context["knowledge_sections"]}
            
        # After providing information, go to follow-up
        elif self.current_stage == FlowStage.INFORMATION:
            self.current_stage = FlowStage.FOLLOW_UP
            return {"flow_action": "suggest_related", "current_topic": self.context.get("last_topic")}
        
        return {"flow_action": "general_response"}
    
    def get_next_response_format(self) -> Dict[str, Any]:
        if self.current_stage == FlowStage.INFORMATION:
            # Check for career map specific query
            if self.context.get("knowledge_sections") == ["career_map"]:
                return {
                    "format": "career_map",
                    "sections": ["Overview", "Domains", "Progression Paths"],
                    "style": "structured"
                }
            else:
                return {
                    "format": "structured",
                    "sections": ["Definition", "Description", "Examples"],
                    "style": "educational"
                }
        return {"format": "conversational"}
    
    def should_activate_agents(self) -> List[str]:
        return ["knowledge_agent"]

class LearningPathwayFlow(IntentFlow):
    """Flow for career role exploration and pathway generation"""
    
    def process(self, query: str, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        extracted_entities = conversation_context.get("extracted_entities", {})
        extracted_role = extracted_entities.get("extracted_role")
        
        # Initial query - if role identified, go to information
        if self.current_stage == FlowStage.INITIAL:
            if extracted_role:
                self.current_stage = FlowStage.INFORMATION
                self.context["current_role"] = extracted_role
                return {"flow_action": "role_skills", "role": extracted_role}
            else:
                # No role specified, show available roles
                self.current_stage = FlowStage.CLARIFICATION
                return {"flow_action": "list_available_roles"}
        
        # Clarification stage - extract role from response
        elif self.current_stage == FlowStage.CLARIFICATION:
            # Try to extract role from the new query
            role = extract_role_from_query(query)
            
            if role:
                self.current_stage = FlowStage.INFORMATION
                self.context["current_role"] = role
                return {"flow_action": "role_skills", "role": role}
            else:
                # Still no role, suggest some options but stay in CLARIFICATION stage
                return {"flow_action": "suggest_common_roles"}
        
        # If a role is mentioned at any point, go to information stage
        role_mentioned = extract_role_from_query(query)
        if role_mentioned:
            self.current_stage = FlowStage.INFORMATION
            self.context["current_role"] = role_mentioned
            return {"flow_action": "role_skills", "role": role_mentioned}
        
        # Default response for unhandled states
        return {"flow_action": "general_response"}
    
    def get_next_response_format(self) -> Dict[str, Any]:
        if self.current_stage == FlowStage.CLARIFICATION:
            return {
                "format": "role_listing",
                "sections": ["Available Roles", "Instructions"]
            }
        elif self.current_stage == FlowStage.INFORMATION:
            return {
                "format": "role_skills",
                "sections": ["Role Overview", "Functional Skills", "Enabling Skills"]
            }
        return {"format": "conversational"}
    
    def should_activate_agents(self) -> List[str]:
        if self.current_stage == FlowStage.CLARIFICATION:
            return ["knowledge_agent", "learning_path_agent"]  # Need both for listing roles
        elif self.current_stage == FlowStage.INFORMATION:
            return ["knowledge_agent", "learning_path_agent"]  # Need both for role skills
        return ["knowledge_agent"]

class CourseSearchFlow(IntentFlow):
    """Flow for course and learning resource searches"""
    
    def process(self, query: str, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        # Initial query - go to recommendation
        if self.current_stage == FlowStage.INITIAL:
            self.current_stage = FlowStage.RECOMMENDATION
            # Extract skills or topics from the query
            # This is a simplified example - would need more logic in real implementation
            extracted_skill = conversation_context.get("extracted_entities", {}).get("skill")
            self.context["search_topic"] = extracted_skill or query
            return {"flow_action": "course_search", "topic": self.context["search_topic"]}
        
        # After recommendation, go to follow-up
        elif self.current_stage == FlowStage.RECOMMENDATION:
            self.current_stage = FlowStage.FOLLOW_UP
            return {"flow_action": "suggest_related_courses", "current_topic": self.context.get("search_topic")}
        
        return {"flow_action": "general_response"}
    
    def get_next_response_format(self) -> Dict[str, Any]:
        if self.current_stage == FlowStage.RECOMMENDATION:
            return {
                "format": "course_list",
                "sections": ["Course Name", "Provider", "Description", "Difficulty", "Link"]
            }
        return {"format": "conversational"}
    
    def should_activate_agents(self) -> List[str]:
        return ["knowledge_agent", "course_agent"]

class GeneralConversationFlow(IntentFlow):
    """Flow for general chit-chat not related to PSF-AAI"""
    
    def process(self, query: str, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        self.current_stage = FlowStage.INFORMATION
        return {"flow_action": "general_chat_response"}
    
    def get_next_response_format(self) -> Dict[str, Any]:
        return {"format": "conversational"}
    
    def should_activate_agents(self) -> List[str]:
        # No need for specialized agents for general conversation
        return ["knowledge_agent"]  # Default to knowledge agent for basic responses

class FlowController:
    """Controls and manages intent-specific conversation flows"""
    
    def __init__(self):
        self.flows = {
            QueryIntent.KNOWLEDGE_BASE_QUERY: KnowledgeBaseFlow,
            QueryIntent.LEARNING_PATHWAY: LearningPathwayFlow,
            QueryIntent.COURSE_SEARCH: CourseSearchFlow,
            QueryIntent.GENERAL_CONVERSATION: GeneralConversationFlow
        }
        self.active_flow = None
        self.active_intent = None
    
    def process_query(self, query: str, intent: QueryIntent, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process a query with the appropriate flow based on intent"""
        
        try:
            # Check if the intent is valid
            if intent not in self.flows:
                logger.warning(f"Unknown intent: {intent}, defaulting to general conversation")
                intent = QueryIntent.GENERAL_CONVERSATION
            
            # Check if we need to initialize a new flow
            if not self.active_flow or intent != self.active_intent:
                logger.info(f"Starting new flow for intent: {intent}")
                self.active_intent = intent
                self.active_flow = self.flows[intent]()
            
            # Process with the active flow
            flow_instructions = self.active_flow.process(query, context)
            
            # Validate flow instructions
            if not isinstance(flow_instructions, dict):
                logger.warning(f"Flow returned non-dict result: {flow_instructions}")
                flow_instructions = {"flow_action": "general_response"}
            
            # Add flow-specific response formatting
            flow_instructions["response_format"] = self.active_flow.get_next_response_format()
            
            # Add which agents should be activated
            agents = self.active_flow.should_activate_agents()
            flow_instructions["activate_agents"] = agents if isinstance(agents, list) else ["knowledge_agent"]
            
            logger.debug(f"Flow instructions: {flow_instructions}")
            return flow_instructions
            
        except Exception as e:
            logger.error(f"Error in flow processing: {e}", exc_info=True)
            # Fallback to basic response in case of errors
            return {
                "flow_action": "error_response",
                "response_format": {"format": "conversational"},
                "activate_agents": ["knowledge_agent"],
                "error": str(e)
            }