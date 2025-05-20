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
        logger.info(f"[Flow:KnowledgeBaseFlow] Stage: {self.current_stage} | Query: {query}")
        # Initial query - information stage
        if self.current_stage == FlowStage.INITIAL:
            self.current_stage = FlowStage.INFORMATION
            logger.info(f"[Flow:KnowledgeBaseFlow] Transition to INFORMATION stage")
            # Check for career map specific query
            query_lower = query.lower()
            if any(term in query_lower for term in ["career map", "career path", "job progression", "domains", "career tracks"]):
                self.context["knowledge_sections"] = ["career_map"]
                logger.info(f"[Flow:KnowledgeBaseFlow] Action: retrieve_career_map")
                return {"flow_action": "retrieve_career_map"}
            else:
                self.context["knowledge_sections"] = ["functional_skills", "enabling_skills", "roles", "career_map"]
                logger.info(f"[Flow:KnowledgeBaseFlow] Action: retrieve_knowledge, sections: {self.context['knowledge_sections']}")
                return {"flow_action": "retrieve_knowledge", "sections": self.context["knowledge_sections"]}
        elif self.current_stage == FlowStage.INFORMATION:
            self.current_stage = FlowStage.FOLLOW_UP
            logger.info(f"[Flow:KnowledgeBaseFlow] Transition to FOLLOW_UP stage")
            return {"flow_action": "suggest_related", "current_topic": self.context.get("last_topic")}
        logger.info(f"[Flow:KnowledgeBaseFlow] Action: general_response")
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
        logger.info(f"[Flow:LearningPathwayFlow] Stage: {self.current_stage} | Query: {query}")
        extracted_entities = conversation_context.get("extracted_entities", {})
        extracted_role = extracted_entities.get("extracted_role")
        if self.current_stage == FlowStage.INITIAL:
            if extracted_role:
                self.current_stage = FlowStage.INFORMATION
                self.context["current_role"] = extracted_role
                logger.info(f"[Flow:LearningPathwayFlow] Transition to INFORMATION stage, role: {extracted_role}")
                return {"flow_action": "role_skills", "role": extracted_role}
            else:
                self.current_stage = FlowStage.CLARIFICATION
                logger.info(f"[Flow:LearningPathwayFlow] Transition to CLARIFICATION stage")
                return {"flow_action": "list_available_roles"}
        elif self.current_stage == FlowStage.CLARIFICATION:
            role = extract_role_from_query(query)
            if role:
                self.current_stage = FlowStage.INFORMATION
                self.context["current_role"] = role
                logger.info(f"[Flow:LearningPathwayFlow] Transition to INFORMATION stage, role: {role}")
                return {"flow_action": "role_skills", "role": role}
            else:
                logger.info(f"[Flow:LearningPathwayFlow] Action: suggest_common_roles")
                return {"flow_action": "suggest_common_roles"}
        role_mentioned = extract_role_from_query(query)
        if role_mentioned:
            self.current_stage = FlowStage.INFORMATION
            self.context["current_role"] = role_mentioned
            logger.info(f"[Flow:LearningPathwayFlow] Transition to INFORMATION stage, role: {role_mentioned}")
            return {"flow_action": "role_skills", "role": role_mentioned}
        logger.info(f"[Flow:LearningPathwayFlow] Action: general_response")
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
        logger.info(f"[Flow:CourseSearchFlow] Stage: {self.current_stage} | Query: {query}")
        extracted_entities = conversation_context.get("extracted_entities", {})
        extracted_skill = extracted_entities.get("skill") or extracted_entities.get("topic") # Also check for 'topic'

        if self.current_stage == FlowStage.INITIAL:
            # Try to get skill from current query if not in extracted_entities
            if not extracted_skill:
                 # A simple heuristic: if query is short and possibly a skill.
                 # More sophisticated extraction might be needed in IntentClassifierAgent or here.
                if len(query.split()) <= 3: # Example: "Python programming"
                    extracted_skill = query 

            if extracted_skill:
                self.current_stage = FlowStage.RECOMMENDATION
                self.context["search_topic"] = extracted_skill
                logger.info(f"[Flow:CourseSearchFlow] Transition to RECOMMENDATION stage, topic: {extracted_skill}")
                return {"flow_action": "course_search", "topic": extracted_skill}
            else:
                self.current_stage = FlowStage.CLARIFICATION
                logger.info(f"[Flow:CourseSearchFlow] Transition to CLARIFICATION stage, topic unclear.")
                return {"flow_action": "clarify_course_topic"}

        elif self.current_stage == FlowStage.CLARIFICATION:
            # Assume the user's entire query is the topic they want to clarify with.
            # More sophisticated extraction could be added here.
            clarified_topic = query
            if clarified_topic:
                self.current_stage = FlowStage.RECOMMENDATION
                self.context["search_topic"] = clarified_topic
                logger.info(f"[Flow:CourseSearchFlow] Transition to RECOMMENDATION stage from CLARIFICATION, topic: {clarified_topic}")
                return {"flow_action": "course_search", "topic": clarified_topic}
            else:
                # If query is empty or still unclear, ask again.
                logger.info(f"[Flow:CourseSearchFlow] Remaining in CLARIFICATION stage, topic still unclear.")
                return {"flow_action": "request_course_topic_details"} # Or re-use clarify_course_topic

        elif self.current_stage == FlowStage.RECOMMENDATION:
            self.current_stage = FlowStage.FOLLOW_UP
            logger.info(f"[Flow:CourseSearchFlow] Transition to FOLLOW_UP stage")
            return {"flow_action": "suggest_related_courses", "current_topic": self.context.get("search_topic")}
        logger.info(f"[Flow:CourseSearchFlow] Action: general_response")
        return {"flow_action": "general_response"}
    
    def get_next_response_format(self) -> Dict[str, Any]:
        if self.current_stage == FlowStage.CLARIFICATION:
            return {
                "format": "clarification_prompt",
                "prompt_message": "What specific skill or topic are you looking for courses on? For example, 'Python programming' or 'data analysis'."
            }
        elif self.current_stage == FlowStage.RECOMMENDATION:
            return {
                "format": "course_list",
                "sections": ["Course Name", "Provider", "Description", "Difficulty", "Link"]
            }
        return {"format": "conversational"}
    
    def should_activate_agents(self) -> List[str]:
        if self.current_stage == FlowStage.CLARIFICATION:
            # Knowledge agent might help suggest topics if the user is very vague,
            # but for direct clarification, specific course agent might not be needed yet.
            # Let's assume the user will provide the topic.
            return ["knowledge_agent"] 
        return ["knowledge_agent", "course_agent"]

class GeneralConversationFlow(IntentFlow):
    """Flow for general chit-chat not related to PSF-AAI"""
    
    def process(self, query: str, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[Flow:GeneralConversationFlow] Stage: {self.current_stage} | Query: {query}")
        self.current_stage = FlowStage.INFORMATION
        logger.info(f"[Flow:GeneralConversationFlow] Transition to INFORMATION stage")
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
        try:
            logger.info(f"[FlowController] Received intent: {getattr(intent, 'value', intent)} | Query: {query}")
            if intent not in self.flows:
                logger.warning(f"Unknown intent: {intent}, defaulting to general conversation")
                intent = QueryIntent.GENERAL_CONVERSATION
            if not self.active_flow or intent != self.active_intent:
                logger.info(f"[FlowController] Starting new flow for intent: {intent}")
                self.active_intent = intent
                self.active_flow = self.flows[intent]()
            flow_instructions = self.active_flow.process(query, context)
            logger.info(f"[FlowController] Flow instructions: {flow_instructions}")
            if not isinstance(flow_instructions, dict):
                logger.warning(f"Flow returned non-dict result: {flow_instructions}")
                flow_instructions = {"flow_action": "general_response"}
            flow_instructions["response_format"] = self.active_flow.get_next_response_format()
            agents = self.active_flow.should_activate_agents()
            flow_instructions["activate_agents"] = agents if isinstance(agents, list) else ["knowledge_agent"]
            logger.debug(f"[FlowController] Final flow instructions: {flow_instructions}")
            return flow_instructions
        except Exception as e:
            logger.error(f"Error in flow processing: {e}", exc_info=True)
            return {
                "flow_action": "error_response",
                "response_format": {"format": "conversational"},
                "activate_agents": ["knowledge_agent"],
                "error": str(e)
            }