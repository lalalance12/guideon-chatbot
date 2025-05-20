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
            
            # Check for role-specific queries
            extracted_role = conversation_context.get("extracted_entities", {}).get("extracted_role")
            if extracted_role:
                self.context["current_role"] = extracted_role
                return {"flow_action": "role_information", "role": extracted_role}
                
            # Check for skill-specific queries
            extracted_skill = conversation_context.get("extracted_entities", {}).get("extracted_skill")
            extracted_level = conversation_context.get("extracted_entities", {}).get("extracted_level")
            if extracted_skill:
                self.context["current_skill"] = extracted_skill
                return {
                    "flow_action": "skill_information", 
                    "skill": extracted_skill,
                    "level": extracted_level
                }
            
            # Default knowledge retrieval
            self.context["knowledge_sections"] = ["functional_skills", "enabling_skills", "roles", "career_map"]
            return {"flow_action": "retrieve_knowledge", "sections": self.context["knowledge_sections"]}
    
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
                # First show skills needed
                return {"flow_action": "role_skills", "role": extracted_role}
            else:
                # No role specified, show available roles
                self.current_stage = FlowStage.CLARIFICATION
                return {"flow_action": "list_available_roles"}
        
        # After showing skills, transition to pathway 
        elif self.current_stage == FlowStage.INFORMATION:
            if "pathway_shown" not in self.context:
                self.context["pathway_shown"] = True
                return {"flow_action": "generate_pathway", "role": self.context.get("current_role")}
            else:
                self.current_stage = FlowStage.FOLLOW_UP
                return {"flow_action": "suggest_next_steps", "role": self.context.get("current_role")}
    
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
    
    def __init__(self):
        super().__init__()
        self.context = {}  # Store flow-specific context
        self.current_stage = FlowStage.INITIAL
    
    def process(self, query: str, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        """Process a query within the course search flow."""
        logger.info(f"Processing course search flow at stage: {self.current_stage}")
        logger.debug(f"Flow context: {self.context}")
        logger.debug(f"Conversation context: {conversation_context}")
        
        # Initial query - determine if clarification needed
        if self.current_stage == FlowStage.INITIAL:
            # Check for ambiguous references
            query_lower = query.lower()
            has_ambiguous_reference = any(word in query_lower for word in ["that", "it", "this", "those", "them"])
            
            # Extract any explicit topics/skills
            extracted_skill = conversation_context.get("extracted_entities", {}).get("extracted_skill")
            
            # Check if we have multiple topics from previous processing
            multiple_topics = conversation_context.get("multiple_topics", [])
            
            # If we have multiple topics from context, ask for clarification
            if multiple_topics and len(multiple_topics) > 1:
                self.current_stage = FlowStage.CLARIFICATION
                self.context["multiple_topics"] = multiple_topics
                return {
                    "flow_action": "request_topic_selection",
                    "needs_clarification": True,
                    "topics": multiple_topics,
                    "response_format": {"format": "topic_selection"}
                }
            
            # If we have a topic from context, use it
            elif multiple_topics and len(multiple_topics) == 1:
                topic = multiple_topics[0]
                self.current_stage = FlowStage.RECOMMENDATION
                self.context["search_topic"] = topic
                return {
                    "flow_action": "course_search",
                    "topic": topic
                }
            
            # If we have a skill, use that
            if extracted_skill:
                topic = extracted_skill
                self.current_stage = FlowStage.RECOMMENDATION
            # If we have an ambiguous reference but no context topic, set flag for clarification
            elif has_ambiguous_reference and not extracted_skill:
                self.current_stage = FlowStage.CLARIFICATION
                return {
                    "flow_action": "request_topic_clarification",
                    "needs_clarification": True,
                    "topic": "",
                    "response_format": {"format": "clarification_request"}
                }
            # Otherwise use the query itself
            else:
                topic = query
                self.current_stage = FlowStage.RECOMMENDATION
                
            self.context["search_topic"] = topic
            return {
                "flow_action": "course_search", 
                "topic": self.context["search_topic"]
            }
        
        # Handle topic selection from multiple options
        elif self.current_stage == FlowStage.CLARIFICATION and "multiple_topics" in self.context:
            logger.info(f"Processing topic selection from: {self.context['multiple_topics']}")
            
            # Try to match user's response to one of the topics
            selected_topic = self._match_topic_selection(query, self.context["multiple_topics"])
            
            if selected_topic:
                logger.info(f"Matched user selection to topic: {selected_topic}")
                self.current_stage = FlowStage.RECOMMENDATION
                self.context["search_topic"] = selected_topic
                return {
                    "flow_action": "course_search",
                    "topic": selected_topic
                }
            else:
                # If no match, use the response as a new topic
                logger.info(f"No topic match found, using query as topic: {query}")
                self.current_stage = FlowStage.RECOMMENDATION
                self.context["search_topic"] = query
                return {
                    "flow_action": "course_search",
                    "topic": query
                }
        
        # Handle regular clarification response
        elif self.current_stage == FlowStage.CLARIFICATION:
            # User has responded to clarification request
            # Their response should contain the topic
            self.current_stage = FlowStage.RECOMMENDATION
            self.context["search_topic"] = query
            return {
                "flow_action": "course_search",
                "topic": self.context["search_topic"]
            }
        
        # After recommendation, go to follow-up
        elif self.current_stage == FlowStage.RECOMMENDATION:
            self.current_stage = FlowStage.FOLLOW_UP
            return {"flow_action": "suggest_related_courses", "topic": self.context["search_topic"]}
        
        # Final state - reset to handle further queries
        elif self.current_stage == FlowStage.FOLLOW_UP:
            self.reset()
            return {"flow_action": "general_response"}
            
        # Default fallback
        return {"flow_action": "general_response"}
    
    def _match_topic_selection(self, user_response: str, topics: List[str]) -> Optional[str]:
        """Match user's selection to one of the multiple topics."""
        user_response = user_response.lower()
        
        # Check for exact matches
        for topic in topics:
            if topic.lower() in user_response:
                return topic
        
        # Check for fuzzy matches (e.g., "python" matches "Data Science with Python")
        for topic in topics:
            words = topic.lower().split()
            for word in words:
                if len(word) > 3 and word in user_response:  # Only match significant words
                    return topic
                
        # No match found
        return None
    
    def get_next_response_format(self) -> Dict[str, Any]:
        if self.current_stage == FlowStage.RECOMMENDATION:
            return {
                "format": "course_list",
                "sections": ["Course Name", "Provider", "Description", "Difficulty", "Link"]
            }
        elif self.current_stage == FlowStage.CLARIFICATION and "multiple_topics" in self.context:
            return {
                "format": "topic_selection",
                "topics": self.context["multiple_topics"]
            }
        return {"format": "conversational"}
    
    def should_activate_agents(self) -> List[str]:
        if self.current_stage == FlowStage.RECOMMENDATION:
            return ["knowledge_agent", "course_agent"]
        elif self.current_stage == FlowStage.FOLLOW_UP:
            return ["knowledge_agent", "course_agent"]
        return []
        
    def reset(self):
        """Reset the flow state."""
        self.current_stage = FlowStage.INITIAL
        self.context = {}

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
            logger.info(f"Processing query with intent: {intent}")
            
            # Check if this is a forced transition (from IntentClassifierAgent)
            is_transition = context.get("is_transition", False)
            
            # If we have an active flow and no forced transition, continue with it
            if self.active_flow and not is_transition:
                # Check if the active flow matches the current intent
                if self.active_intent == intent:
                    # Continue with current flow
                    flow_instructions = self.active_flow.process(query, context)
                    logger.debug(f"Continuing with {self.active_intent} flow, stage: {self.active_flow.current_stage}")
                else:
                    # Intent changed, switch flows
                    logger.info(f"Intent changed from {self.active_intent} to {intent}, switching flows")
                    self._reset_active_flow()
                    self._set_flow_for_intent(intent)
                    flow_instructions = self.active_flow.process(query, context)
            else:
                # No active flow or forced transition, create a new one
                self._reset_active_flow()
                self._set_flow_for_intent(intent)
                flow_instructions = self.active_flow.process(query, context)
                
            # If no flow_action specified, use a default
            if not flow_instructions.get("flow_action"):
                flow_instructions["flow_action"] = "general_response"
                
            # Add response format if available from the flow
            if hasattr(self.active_flow, 'get_next_response_format'):
                response_format = self.active_flow.get_next_response_format()
                if response_format:
                    flow_instructions["response_format"] = response_format
                    
            # Add agent activation information if available
            if hasattr(self.active_flow, 'should_activate_agents'):
                agents_to_activate = self.active_flow.should_activate_agents()
                if agents_to_activate:
                    flow_instructions["activate_agents"] = agents_to_activate
                    
            return flow_instructions
            
        except Exception as e:
            logger.error(f"Error in flow controller: {e}", exc_info=True)
            return {"flow_action": "general_response", "error": str(e)}
        
    def _set_flow_for_intent(self, intent):
        """Set the active flow based on intent"""
        if not intent:
            self.active_flow = None
            self.active_intent = None
            return
            
        try:
            # Handle all possible intents
            if intent == QueryIntent.COURSE_SEARCH:
                self.active_flow = CourseSearchFlow()
                self.active_intent = intent
            elif intent == QueryIntent.LEARNING_PATHWAY:
                self.active_flow = LearningPathwayFlow()
                self.active_intent = intent
            elif intent == QueryIntent.KNOWLEDGE_BASE_QUERY:
                self.active_flow = KnowledgeBaseFlow()
                self.active_intent = intent
            else:
                # Default to general conversation flow
                self.active_flow = GeneralConversationFlow()
                self.active_intent = QueryIntent.GENERAL_CONVERSATION
                
            logger.info(f"Set active flow to {self.active_intent}")
        except Exception as e:
            logger.error(f"Error setting flow for intent {intent}: {e}")
            self.active_flow = None
            self.active_intent = None

    def _reset_active_flow(self):
        """Reset the active flow"""
        if self.active_flow:
            try:
                if hasattr(self.active_flow, 'reset'):
                    self.active_flow.reset()
            except Exception as e:
                logger.error(f"Error resetting flow: {e}")
        
        self.active_flow = None
        self.active_intent = None