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
        prev_intent = conversation_context.get("previous_intent")
        if prev_intent == QueryIntent.GENERAL_CONVERSATION:
            logger.info("[Flow:KnowledgeBaseFlow] Transitioned from General Conversation to KnowledgeBaseFlow")
            self.current_stage = FlowStage.INFORMATION
            return {"flow_action": "intent_switch_acknowledge", "message": "Switching to PSF-AAI knowledge base mode.", "current_topic": None}
        query_lower = query.lower()
        # --- Distribute info based on query content ---
        if self.current_stage == FlowStage.INITIAL:
            # Career map or progression
            if any(term in query_lower for term in ["career map", "career path", "job progression", "domains", "vertical tracks", "horizontal levels", "job grades", "career domains"]):
                self.current_stage = FlowStage.INFORMATION
                self.context["knowledge_sections"] = ["career_map"]
                logger.info(f"[Flow:KnowledgeBaseFlow] Action: retrieve_career_map")
                return {"flow_action": "retrieve_career_map"}
            # Role-specific
            elif any(term in query_lower for term in ["role", "job", "position", "responsibilities"]):
                self.current_stage = FlowStage.INFORMATION
                self.context["knowledge_sections"] = ["job_roles"]
                logger.info(f"[Flow:KnowledgeBaseFlow] Action: retrieve_role_info")
                return {"flow_action": "role_information"}
            # Functional/enabling skills
            elif any(term in query_lower for term in ["functional skill", "technical skill", "technical competency"]):
                self.current_stage = FlowStage.INFORMATION
                self.context["knowledge_sections"] = ["functional_skills"]
                logger.info(f"[Flow:KnowledgeBaseFlow] Action: retrieve_functional_skills")
                return {"flow_action": "retrieve_knowledge", "sections": ["functional_skills"]}
            elif any(term in query_lower for term in ["enabling skill", "soft skill", "transversal"]):
                self.current_stage = FlowStage.INFORMATION
                self.context["knowledge_sections"] = ["enabling_skills"]
                logger.info(f"[Flow:KnowledgeBaseFlow] Action: retrieve_enabling_skills")
                return {"flow_action": "retrieve_knowledge", "sections": ["enabling_skills"]}
            # General PSF-AAI info
            elif any(term in query_lower for term in ["psf", "framework", "analytics", "ai", "artificial intelligence", "skills framework"]):
                self.current_stage = FlowStage.INFORMATION
                self.context["knowledge_sections"] = ["general"]
                logger.info(f"[Flow:KnowledgeBaseFlow] Action: retrieve_general_info")
                return {"flow_action": "retrieve_knowledge", "sections": ["general"]}
            # Fallback: all sections
            else:
                self.current_stage = FlowStage.INFORMATION
                self.context["knowledge_sections"] = ["functional_skills", "enabling_skills", "job_roles", "career_map"]
                logger.info(f"[Flow:KnowledgeBaseFlow] Action: retrieve_knowledge, sections: {self.context['knowledge_sections']}")
                return {"flow_action": "retrieve_knowledge", "sections": self.context["knowledge_sections"]}
        elif self.current_stage == FlowStage.INFORMATION:
            self.current_stage = FlowStage.FOLLOW_UP
            logger.info(f"[Flow:KnowledgeBaseFlow] Transition to FOLLOW_UP stage")
            return {"flow_action": "suggest_related", "current_topic": self.context.get("last_topic")}
        logger.info(f"[Flow:KnowledgeBaseFlow] Action: general_response")
        return {"flow_action": "general_response"}
    
    def get_next_response_format(self) -> Dict[str, Any]:
        # Pick format based on what section is being retrieved
        sections = self.context.get("knowledge_sections", [])
        if sections == ["career_map"]:
            return {
                "format": "career_map",
                "sections": ["Overview", "Domains", "Progression Paths"],
                "style": "structured"
            }
        elif sections == ["job_roles"]:
            return {
                "format": "role_profile",
                "sections": ["Role Description", "Responsibilities", "Required Skills", "Career Path"],
                "style": "profile"
            }
        elif sections == ["functional_skills"]:
            return {
                "format": "structured",
                "sections": ["Definition", "Description", "Examples"],
                "style": "educational"
            }
        elif sections == ["enabling_skills"]:
            return {
                "format": "structured",
                "sections": ["Definition", "Description", "Examples"],
                "style": "educational"
            }
        elif sections == ["general"]:
            return {
                "format": "structured",
                "sections": ["Overview", "Purpose", "Components", "Applications"],
                "style": "framework"
            }
        else:
            return {"format": "conversational"}
    
    def should_activate_agents(self) -> List[str]:
        # Return only the knowledge agent
        return ["knowledge_agent"]

class LearningPathwayFlow(IntentFlow):
    """Flow for career role exploration and pathway generation"""
    def process(self, query: str, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[Flow:LearningPathwayFlow] Stage: {self.current_stage} | Query: {query}")
        extracted_entities = conversation_context.get("extracted_entities", {})
        # Collect all possible roles/entities
        possible_entities = []
        if "extracted_role" in extracted_entities:
            if isinstance(extracted_entities["extracted_role"], list):
                possible_entities.extend([r for r in extracted_entities["extracted_role"] if r])
            elif extracted_entities["extracted_role"]:
                possible_entities.append(extracted_entities["extracted_role"])
        # Only consider roles in PSF_AAI_ROLES
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
        filtered_entities = [e for e in possible_entities if e and e.lower() in PSF_AAI_ROLES]
        # Remove duplicates
        filtered_entities = list(dict.fromkeys([e for e in filtered_entities if e]))

        if self.current_stage == FlowStage.INITIAL:
            if len(filtered_entities) == 0:
                self.current_stage = FlowStage.CLARIFICATION
                return {
                    "flow_action": "clarify_entity",
                    "available_roles": PSF_AAI_ROLES,
                    "clarification_needed": True
                }
            elif len(filtered_entities) == 1:
                self.current_stage = FlowStage.INFORMATION
                self.context["current_entity"] = filtered_entities[0]
                return {
                    "flow_action": "career_overview",
                    "entity": filtered_entities[0]
                }
            else:
                self.current_stage = FlowStage.CLARIFICATION
                return {
                    "flow_action": "choose_entity",
                    "entities": filtered_entities,
                    "available_roles": PSF_AAI_ROLES,
                    "clarification_needed": True
                }
        elif self.current_stage == FlowStage.CLARIFICATION:
            # Try to extract entity from the new query
            role = extract_role_from_query(query)
            if role and role.lower() in PSF_AAI_ROLES:
                self.current_stage = FlowStage.INFORMATION
                self.context["current_entity"] = role
                return {"flow_action": "career_overview", "entity": role}
            else:
                return {
                    "flow_action": "clarify_entity",
                    "available_roles": PSF_AAI_ROLES,
                    "clarification_needed": True
                }
        elif self.current_stage == FlowStage.INFORMATION:
            logger.info(f"[Flow:LearningPathwayFlow] Action: suggest_related_entities")
            return {"flow_action": "suggest_related_entities", "current_entity": self.context.get("current_entity")}
        logger.info(f"[Flow:LearningPathwayFlow] Action: general_response")
        return {"flow_action": "general_response"}

    def get_next_response_format(self) -> Dict[str, Any]:
        if self.current_stage == FlowStage.CLARIFICATION:
            return {
                "format": "entity_clarification",
                "prompt_message": "Which career role or entity are you interested in? Please specify so I can provide a career overview."
            }
        elif self.current_stage == FlowStage.INFORMATION:
            return {
                "format": "career_overview",
                "sections": ["Role Overview", "Career Path", "Required Skills"]
            }
        return {"format": "conversational"}

    def should_activate_agents(self) -> List[str]:
        # Return only the learning path agent
        return ["learning_path_agent"]

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
        # Return only the course agent
        return ["course_agent"]

class GeneralConversationFlow(IntentFlow):
    """Flow for general chit-chat not related to PSF-AAI"""
    
    def process(self, query: str, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[Flow:GeneralConversationFlow] Stage: {self.current_stage} | Query: {query}")
        # If the previous intent was knowledge base, acknowledge the switch
        prev_intent = conversation_context.get("previous_intent")
        if prev_intent == QueryIntent.KNOWLEDGE_BASE_QUERY:
            logger.info("[Flow:GeneralConversationFlow] Transitioned from KnowledgeBaseFlow to General Conversation")
            self.current_stage = FlowStage.INFORMATION
            return {"flow_action": "intent_switch_acknowledge", "message": "Switching to general conversation mode.", "current_topic": None}
        self.current_stage = FlowStage.INFORMATION
        logger.info(f"[Flow:GeneralConversationFlow] Transition to INFORMATION stage")
        return {"flow_action": "general_chat_response"}
    
    def get_next_response_format(self) -> Dict[str, Any]:
        return {"format": "conversational"}
    
    def should_activate_agents(self) -> List[str]:
        # Return only the general conversation agent
        return ["general_conversation_agent"]

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
            # Ensure we only activate one agent (the first one in the list)
            if agents and len(agents) > 0:
                primary_agent = agents[0]
                logger.info(f"[FlowController] Using primary agent: {primary_agent}")
                flow_instructions["activate_agents"] = [primary_agent]
            else:
                flow_instructions["activate_agents"] = ["knowledge_agent"]  # Default fallback
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