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
    CONNECTIVITY_EXPLORATION = "connectivity_exploration"  # New stage for exploring connections

class IntentFlow(ABC):
    """Enhanced base class for intent-specific conversation flows with connectivity awareness"""
    
    def __init__(self):
        self.current_stage = FlowStage.INITIAL
        self.context = {}
        self.connectivity_context = {}  # Track connectivity-related context
    
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
    """Enhanced flow for PSF-AAI knowledge base queries with connectivity awareness"""
    
    def process(self, query: str, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[Flow:KnowledgeBaseFlow] Stage: {self.current_stage} | Query: {query}")
        prev_intent = conversation_context.get("previous_intent")
        
        # Handle transition from general conversation
        if prev_intent == QueryIntent.GENERAL_CONVERSATION:
            logger.info("[Flow:KnowledgeBaseFlow] Transitioned from General Conversation to KnowledgeBaseFlow")
            self.current_stage = FlowStage.INFORMATION
            return {
                "flow_action": "intent_switch_acknowledge", 
                "message": "Switching to PSF-AAI knowledge mode with enhanced connectivity features.", 
                "current_topic": None
            }
        
        query_lower = query.lower()
        extracted_entities = conversation_context.get("extracted_entities", {})
        extracted_role = extracted_entities.get("extracted_role")
        extracted_level = extracted_entities.get("extracted_level")
        
        # Enhanced connectivity-aware query processing
        if self.current_stage == FlowStage.INITIAL:
            return self._process_initial_stage(query_lower, extracted_entities)
            
        elif self.current_stage == FlowStage.INFORMATION:
            return self._process_information_stage(query_lower, conversation_context)
            
        elif self.current_stage == FlowStage.FOLLOW_UP:
            return self._process_follow_up_stage(query, conversation_context)
            
        elif self.current_stage == FlowStage.CONNECTIVITY_EXPLORATION:
            return self._process_connectivity_stage(query, conversation_context)
                
        # Default action
        logger.info(f"[Flow:KnowledgeBaseFlow] Action: general_response")
        return {"flow_action": "general_response"}
    
    def _process_initial_stage(self, query_lower: str, extracted_entities: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced initial stage processing with connectivity detection"""
        extracted_role = extracted_entities.get("extracted_role")
        extracted_level = extracted_entities.get("extracted_level")
        
        # Enhanced connectivity-aware query categorization
        query_categories = {
            "career_progression": [
                "career map", "career path", "job progression", "domains", 
                "vertical tracks", "horizontal levels", "job grades", 
                "career domains", "track progression", "advancement path",
                "next role", "career advancement", "progression pathway"
            ],
            "role_information": [
                "role responsibilities", "job duties", "position requirements", 
                "role tasks", "what does a", "role description", "job profile",
                "role skills", "position skills", "career path from"
            ],
            "functional_skills": [
                "functional skill", "technical skill", "technical competency", 
                "technical requirement", "hard skill", "programming skill",
                "coding skill", "data skill", "ai skill", "analytics skill",
                "technical proficiency", "competency level"
            ],
            "enabling_skills": [
                "enabling skill", "soft skill", "transversal skill", 
                "interpersonal skill", "non-technical skill", "behavioral competency",
                "leadership skill", "communication skill", "teamwork", "collaboration"
            ],
            "skill_connections": [
                "skills for", "skills needed for", "skills required by",
                "roles that use", "jobs requiring", "positions with",
                "skill requirements", "competency mapping"
            ],
            "connectivity_exploration": [
                "how are", "connection between", "relationship between",
                "linked to", "related to", "connects to", "leads to"
            ]
        }
        
        # Detect query category
        detected_category = None
        for category, keywords in query_categories.items():
            if any(keyword in query_lower for keyword in keywords):
                detected_category = category
                break
        
        # Process based on detected category
        if detected_category == "career_progression":
            self.current_stage = FlowStage.INFORMATION
            self.context["knowledge_sections"] = ["career_map"]
            self.context["query_type"] = "career_progression"
            return {"flow_action": "retrieve_career_map"}
            
        elif detected_category == "role_information":
            self.current_stage = FlowStage.INFORMATION
            self.context["knowledge_sections"] = ["job_roles"]
            self.context["query_type"] = "role_information"
            if extracted_role:
                self.context["detected_role"] = extracted_role
            return {"flow_action": "role_information"}
            
        elif detected_category == "functional_skills":
            self.current_stage = FlowStage.INFORMATION
            self.context["knowledge_sections"] = ["functional_skills"]
            self.context["query_type"] = "functional_skills"
            if extracted_level:
                self.context["detected_level"] = extracted_level
            return {"flow_action": "retrieve_knowledge", "sections": ["functional_skills"]}
            
        elif detected_category == "enabling_skills":
            self.current_stage = FlowStage.INFORMATION
            self.context["knowledge_sections"] = ["enabling_skills"]
            self.context["query_type"] = "enabling_skills"
            if extracted_level:
                self.context["detected_level"] = extracted_level
            return {"flow_action": "retrieve_knowledge", "sections": ["enabling_skills"]}
            
        elif detected_category == "skill_connections":
            self.current_stage = FlowStage.CONNECTIVITY_EXPLORATION
            self.context["knowledge_sections"] = ["functional_skills", "enabling_skills", "job_roles"]
            self.context["query_type"] = "skill_connections"
            return {"flow_action": "explore_skill_connections"}
            
        elif detected_category == "connectivity_exploration":
            self.current_stage = FlowStage.CONNECTIVITY_EXPLORATION
            self.context["knowledge_sections"] = ["career_map", "job_roles", "functional_skills"]
            self.context["query_type"] = "connectivity_exploration"
            return {"flow_action": "explore_connections"}
            
        # Enhanced general processing
        elif any(term in query_lower for term in [
            "psf", "framework", "analytics", "ai", "artificial intelligence", 
            "skills framework", "psf-aai", "about the framework", 
            "what is psf", "overview", "introduction"
        ]):
            self.current_stage = FlowStage.INFORMATION
            self.context["knowledge_sections"] = ["general"]
            self.context["query_type"] = "framework_overview"
            return {"flow_action": "retrieve_knowledge", "sections": ["general"]}
            
        # Default: comprehensive search with connectivity
        else:
            self.current_stage = FlowStage.INFORMATION
            self.context["knowledge_sections"] = ["functional_skills", "enabling_skills", "job_roles", "career_map"]
            self.context["query_type"] = "comprehensive_search"
            return {"flow_action": "retrieve_knowledge", "sections": self.context["knowledge_sections"]}
    
    def _process_information_stage(self, query_lower: str, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced information stage with connectivity follow-up"""
        # Check if user wants to explore connections
        connection_indicators = [
            "what roles use", "career path from", "progression from", 
            "next steps", "how to advance", "related roles", "similar skills"
        ]
        
        if any(indicator in query_lower for indicator in connection_indicators):
            self.current_stage = FlowStage.CONNECTIVITY_EXPLORATION
            return {"flow_action": "explore_connections"}
        
        # Transition to follow-up with enhanced connectivity suggestions
        self.current_stage = FlowStage.FOLLOW_UP
        current_topic = self._determine_current_topic()
        return {
            "flow_action": "suggest_related_with_connections", 
            "current_topic": current_topic,
            "connectivity_options": self._get_connectivity_options()
        }
    
    def _process_follow_up_stage(self, query: str, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced follow-up processing with connectivity awareness"""
        if self._is_clarification_question(query):
            return {
                "flow_action": "provide_clarification", 
                "sections": self.context.get("knowledge_sections", ["functional_skills", "enabling_skills", "job_roles"])
            }
        elif self._is_connectivity_question(query):
            self.current_stage = FlowStage.CONNECTIVITY_EXPLORATION
            return {"flow_action": "explore_connections"}
        else:
            # New question - reset and reprocess
            self.current_stage = FlowStage.INITIAL
            return self.process(query, conversation_context)
    
    def _process_connectivity_stage(self, query: str, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        """Process connectivity exploration queries"""
        query_lower = query.lower()
        
        # Enhanced connectivity actions
        if any(term in query_lower for term in ["career path", "progression", "advance"]):
            return {"flow_action": "show_career_progressions"}
        elif any(term in query_lower for term in ["skills for", "requirements", "needed"]):
            return {"flow_action": "show_skill_requirements"}
        elif any(term in query_lower for term in ["roles that use", "jobs with", "positions"]):
            return {"flow_action": "show_role_connections"}
        else:
            return {"flow_action": "comprehensive_connectivity_view"}
    
    def _determine_current_topic(self) -> str:
        """Determine current topic from context for enhanced suggestions"""
        if "detected_role" in self.context:
            return self.context["detected_role"]
        elif "detected_level" in self.context:
            return f"Level {self.context['detected_level']}"
        elif "query_type" in self.context:
            return self.context["query_type"].replace("_", " ").title()
        else:
            return "PSF-AAI Framework"
    
    def _get_connectivity_options(self) -> List[str]:
        """Get relevant connectivity exploration options"""
        query_type = self.context.get("query_type", "")
        
        base_options = [
            "Career progression paths",
            "Related roles and positions",
            "Skill requirements and mappings"
        ]
        
        if query_type == "role_information":
            return base_options + [
                "Skills needed for this role",
                "Career advancement options",
                "Related positions in other domains"
            ]
        elif query_type in ["functional_skills", "enabling_skills"]:
            return base_options + [
                "Roles requiring this skill",
                "Skill level progressions",
                "Complementary skills"
            ]
        elif query_type == "career_progression":
            return base_options + [
                "Domain transition options",
                "Grade advancement requirements",
                "Cross-functional pathways"
            ]
        
        return base_options
    
    def _is_clarification_question(self, query: str) -> bool:
        """Enhanced clarification detection"""
        q = query.lower()
        clarification_patterns = [
            "what do you mean", "can you explain", "tell me more", "elaborate",
            "what is that", "how does that", "why is that", "give example", 
            "show example", "what does that mean", "i don't understand",
            "what's the difference", "how is it different", "clarify", "details"
        ]
        return any(pattern in q for pattern in clarification_patterns)
    
    def _is_connectivity_question(self, query: str) -> bool:
        """Detect connectivity exploration questions"""
        q = query.lower()
        connectivity_patterns = [
            "how are they connected", "what's the relationship", "how do they relate",
            "progression from", "career path", "next role", "advancement",
            "roles that use", "skills for", "requirements", "connected to",
            "leads to", "pathways", "connections"
        ]
        return any(pattern in q for pattern in connectivity_patterns)
    
    def get_next_response_format(self) -> Dict[str, Any]:
        """Enhanced response formatting with connectivity awareness"""
        sections = self.context.get("knowledge_sections", [])
        query_type = self.context.get("query_type", "")
        
        if self.current_stage == FlowStage.CONNECTIVITY_EXPLORATION:
            return {
                "format": "connectivity_view",
                "sections": ["Connections", "Pathways", "Requirements", "Recommendations"],
                "style": "interactive",
                "connectivity_features": True
            }
        elif query_type == "career_progression" or sections == ["career_map"]:
            return {
                "format": "career_map",
                "sections": ["Overview", "Domains", "Progression Paths", "Connectivity"],
                "style": "structured",
                "connectivity_features": True
            }
        elif query_type == "role_information" or sections == ["job_roles"]:
            return {
                "format": "role_profile",
                "sections": ["Role Description", "Responsibilities", "Required Skills", "Career Path", "Connections"],
                "style": "profile",
                "connectivity_features": True
            }
        elif sections == ["functional_skills"] or sections == ["enabling_skills"]:
            return {
                "format": "structured",
                "sections": ["Definition", "Description", "Levels", "Role Applications", "Connections"],
                "style": "educational",
                "connectivity_features": True
            }
        else:
            return {
                "format": "conversational",
                "connectivity_features": True
            }
    
    def should_activate_agents(self) -> List[str]:
        return ["knowledge_agent"]

class LearningPathwayFlow(IntentFlow):
    """Enhanced flow for career role exploration and pathway generation with connectivity"""
    
    def process(self, query: str, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[Flow:LearningPathwayFlow] Stage: {self.current_stage} | Query: {query}")
        extracted_entities = conversation_context.get("extracted_entities", {})
        
        # Enhanced entity extraction with connectivity context
        possible_entities = self._extract_enhanced_entities(extracted_entities)
        filtered_entities = self._filter_psf_entities(possible_entities)
        
        if self.current_stage == FlowStage.INITIAL:
            return self._process_initial_pathway_stage(filtered_entities)
        elif self.current_stage == FlowStage.CLARIFICATION:
            return self._process_clarification_stage(query, filtered_entities)
        elif self.current_stage == FlowStage.INFORMATION:
            return self._process_pathway_information_stage()
        
        return {"flow_action": "general_response"}
    
    def _extract_enhanced_entities(self, extracted_entities: Dict[str, Any]) -> List[str]:
        """Enhanced entity extraction with better handling"""
        possible_entities = []
        
        if "extracted_role" in extracted_entities:
            role_data = extracted_entities["extracted_role"]
            if isinstance(role_data, list):
                possible_entities.extend([r for r in role_data if r])
            elif role_data:
                possible_entities.append(role_data)
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys([e for e in possible_entities if e]))
    
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
    
    def _process_initial_pathway_stage(self, filtered_entities: List[str]) -> Dict[str, Any]:
        """Process initial stage with enhanced connectivity awareness"""
        if len(filtered_entities) == 0:
            self.current_stage = FlowStage.CLARIFICATION
            return {
                "flow_action": "clarify_entity_with_suggestions",
                "clarification_needed": True,
                "connectivity_hints": True
            }
        elif len(filtered_entities) == 1:
            self.current_stage = FlowStage.INFORMATION
            self.context["current_entity"] = filtered_entities[0]
            self.connectivity_context["focus_role"] = filtered_entities[0]
            return {
                "flow_action": "career_overview_with_connections",
                "entity": filtered_entities[0],
                "include_pathways": True
            }
        else:
            self.current_stage = FlowStage.CLARIFICATION
            return {
                "flow_action": "choose_entity_with_context",
                "entities": filtered_entities,
                "clarification_needed": True,
                "show_connections": True
            }
    
    def _process_clarification_stage(self, query: str, filtered_entities: List[str]) -> Dict[str, Any]:
        """Enhanced clarification processing"""
        role = extract_role_from_query(query)
        if role and self._is_valid_psf_role(role):
            self.current_stage = FlowStage.INFORMATION
            self.context["current_entity"] = role
            self.connectivity_context["focus_role"] = role
            return {
                "flow_action": "career_overview_with_connections", 
                "entity": role,
                "include_pathways": True
            }
        else:
            return {
                "flow_action": "clarify_entity_with_examples",
                "clarification_needed": True,
                "provide_examples": True
            }
    
    def _process_pathway_information_stage(self) -> Dict[str, Any]:
        """Enhanced information stage with connectivity exploration"""
        self.current_stage = FlowStage.CONNECTIVITY_EXPLORATION
        return {
            "flow_action": "suggest_pathway_connections", 
            "current_entity": self.context.get("current_entity"),
            "explore_connections": True
        }
    
    def _is_valid_psf_role(self, role: str) -> bool:
        """Check if role is valid in PSF-AAI"""
        PSF_AAI_ROLES = [
            "associate data analyst", "data analyst", "associate data engineer",
            "business intelligence analyst", "data engineer", "machine learning engineer",
            # ... (complete list as above)
        ]
        return role.lower() in PSF_AAI_ROLES
    
    def get_next_response_format(self) -> Dict[str, Any]:
        """Enhanced formatting with connectivity features"""
        if self.current_stage == FlowStage.CLARIFICATION:
            return {
                "format": "entity_clarification",
                "prompt_message": "Which career role interests you? I can show career paths, skill requirements, and progression options.",
                "connectivity_features": True
            }
        elif self.current_stage == FlowStage.INFORMATION:
            return {
                "format": "career_overview",
                "sections": ["Role Overview", "Career Path", "Required Skills", "Progression Options"],
                "connectivity_features": True
            }
        elif self.current_stage == FlowStage.CONNECTIVITY_EXPLORATION:
            return {
                "format": "pathway_connections",
                "sections": ["Current Role", "Advancement Paths", "Skill Development", "Related Opportunities"],
                "connectivity_features": True
            }
        return {"format": "conversational", "connectivity_features": True}

    def should_activate_agents(self) -> List[str]:
        return ["learning_path_agent"]

class CourseSearchFlow(IntentFlow):
    """Enhanced flow for course and learning resource searches with skill connectivity"""
    
    def process(self, query: str, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[Flow:CourseSearchFlow] Stage: {self.current_stage} | Query: {query}")
        extracted_entities = conversation_context.get("extracted_entities", {})
        extracted_skill = extracted_entities.get("skill") or extracted_entities.get("topic")

        if self.current_stage == FlowStage.INITIAL:
            return self._process_initial_course_stage(query, extracted_skill)
        elif self.current_stage == FlowStage.CLARIFICATION:
            return self._process_course_clarification_stage(query)
        elif self.current_stage == FlowStage.RECOMMENDATION:
            return self._process_course_recommendation_stage()
        
        return {"flow_action": "general_response"}
    
    def _process_initial_course_stage(self, query: str, extracted_skill: str) -> Dict[str, Any]:
        """Enhanced initial processing with skill connectivity"""
        if not extracted_skill and len(query.split()) <= 3:
            extracted_skill = query

        if extracted_skill:
            self.current_stage = FlowStage.RECOMMENDATION
            self.context["search_topic"] = extracted_skill
            self.connectivity_context["skill_focus"] = extracted_skill
            return {
                "flow_action": "course_search_with_context",
                "topic": extracted_skill,
                "include_skill_connections": True
            }
        else:
            self.current_stage = FlowStage.CLARIFICATION
            return {"flow_action": "clarify_course_topic_with_suggestions"}
    
    def _process_course_clarification_stage(self, query: str) -> Dict[str, Any]:
        """Enhanced clarification with skill connectivity hints"""
        clarified_topic = query.strip()
        if clarified_topic:
            self.current_stage = FlowStage.RECOMMENDATION
            self.context["search_topic"] = clarified_topic
            self.connectivity_context["skill_focus"] = clarified_topic
            return {
                "flow_action": "course_search_with_context",
                "topic": clarified_topic,
                "include_skill_connections": True
            }
        else:
            return {"flow_action": "request_specific_course_topic"}
    
    def _process_course_recommendation_stage(self) -> Dict[str, Any]:
        """Enhanced recommendation with related courses"""
        self.current_stage = FlowStage.FOLLOW_UP
        return {
            "flow_action": "suggest_related_courses_with_pathways",
            "current_topic": self.context.get("search_topic"),
            "show_learning_paths": True
        }
    
    def get_next_response_format(self) -> Dict[str, Any]:
        """Enhanced formatting with connectivity awareness"""
        if self.current_stage == FlowStage.CLARIFICATION:
            return {
                "format": "clarification_prompt",
                "prompt_message": "What skill or topic would you like to learn? I can suggest courses and show how they connect to career roles.",
                "connectivity_features": True
            }
        elif self.current_stage == FlowStage.RECOMMENDATION:
            return {
                "format": "course_list",
                "sections": ["Course Name", "Provider", "Description", "Difficulty", "Career Relevance", "Link"],
                "connectivity_features": True
            }
        return {"format": "conversational", "connectivity_features": True}
    
    def should_activate_agents(self) -> List[str]:
        return ["course_agent"]

class GeneralConversationFlow(IntentFlow):
    """Enhanced flow for general conversation with PSF-AAI awareness"""
    
    def process(self, query: str, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[Flow:GeneralConversationFlow] Stage: {self.current_stage} | Query: {query}")
        
        prev_intent = conversation_context.get("previous_intent")
        if prev_intent == QueryIntent.KNOWLEDGE_BASE_QUERY:
            logger.info("[Flow:GeneralConversationFlow] Transitioned from KnowledgeBaseFlow to General Conversation")
            self.current_stage = FlowStage.INFORMATION
            return {
                "flow_action": "intent_switch_acknowledge", 
                "message": "Switching to general conversation mode. Feel free to ask about anything!",
                "current_topic": None
            }
        
        self.current_stage = FlowStage.INFORMATION
        return {"flow_action": "general_chat_response_with_hints"}
    
    def get_next_response_format(self) -> Dict[str, Any]:
        return {
            "format": "conversational",
            "include_psf_hints": True  # Hint about PSF-AAI capabilities
        }
    
    def should_activate_agents(self) -> List[str]:
        return ["general_conversation_agent"]

class FlowController:
    """Enhanced flow controller with connectivity awareness"""
    
    def __init__(self):
        self.flows = {
            QueryIntent.KNOWLEDGE_BASE_QUERY: KnowledgeBaseFlow,
            QueryIntent.LEARNING_PATHWAY: LearningPathwayFlow,
            QueryIntent.COURSE_SEARCH: CourseSearchFlow,
            QueryIntent.GENERAL_CONVERSATION: GeneralConversationFlow
        }
        self.active_flow = None
        self.active_intent = None
        self.connectivity_context = {}  # Track cross-flow connectivity
    
    def process_query(self, query: str, intent: QueryIntent, context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            logger.info(f"[FlowController] Enhanced processing - Intent: {getattr(intent, 'value', intent)} | Query: {query}")
            
            if intent not in self.flows:
                logger.warning(f"Unknown intent: {intent}, defaulting to general conversation")
                intent = QueryIntent.GENERAL_CONVERSATION
            
            # Enhanced flow management with connectivity preservation
            if not self.active_flow or intent != self.active_intent:
                logger.info(f"[FlowController] Starting new enhanced flow for intent: {intent}")
                
                # Preserve connectivity context across flow transitions
                if self.active_flow and hasattr(self.active_flow, 'connectivity_context'):
                    self.connectivity_context.update(self.active_flow.connectivity_context)
                
                self.active_intent = intent
                self.active_flow = self.flows[intent]()
                
                # Transfer connectivity context to new flow
                if hasattr(self.active_flow, 'connectivity_context'):
                    self.active_flow.connectivity_context.update(self.connectivity_context)
            
            # Enhanced context with connectivity information
            enhanced_context = {
                **context,
                "connectivity_context": self.connectivity_context,
                "flow_history": getattr(self, 'flow_history', [])
            }
            
            flow_instructions = self.active_flow.process(query, enhanced_context)
            logger.info(f"[FlowController] Enhanced flow instructions: {flow_instructions}")
            
            if not isinstance(flow_instructions, dict):
                logger.warning(f"Flow returned non-dict result: {flow_instructions}")
                flow_instructions = {"flow_action": "general_response"}
            
            # Enhanced response formatting with connectivity features
            response_format = self.active_flow.get_next_response_format()
            flow_instructions["response_format"] = response_format
            
            # Enhanced agent activation
            agents = self.active_flow.should_activate_agents()
            if agents and len(agents) > 0:
                primary_agent = agents[0]
                logger.info(f"[FlowController] Using enhanced primary agent: {primary_agent}")
                flow_instructions["activate_agents"] = [primary_agent]
            else:
                flow_instructions["activate_agents"] = ["knowledge_agent"]
            
            # Add connectivity features flag
            flow_instructions["connectivity_features_enabled"] = True
            
            logger.debug(f"[FlowController] Final enhanced flow instructions: {flow_instructions}")
            return flow_instructions
            
        except Exception as e:
            logger.error(f"Error in enhanced flow processing: {e}", exc_info=True)
            return {
                "flow_action": "error_response",
                "response_format": {"format": "conversational"},
                "activate_agents": ["knowledge_agent"],
                "connectivity_features_enabled": True,
                "error": str(e)
            }