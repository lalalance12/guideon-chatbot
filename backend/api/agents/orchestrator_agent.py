from __future__ import annotations
from typing import Dict, Any, List
import asyncio
import logging
import time

from .base_agent import BaseAgent
from .psf_knowledge_agent import PSFKnowledgeAgent
from .course_search_agent import CourseSearchAgent
from .learning_path_agent import LearningPathAgent
from ..utils.intent_classifier import QueryIntent
from ..flows.intent_flows import FlowController
from agno.agent import Agent
from .flow_manager_agent import FlowManagerAgent
from .general_conversation_agent import GeneralConversationAgent

logger = logging.getLogger(__name__)

class OrchestratorAgent(BaseAgent):
    """Coordinates the execution of specialised agents based on intent."""

    SYSTEM_PROMPT = (
        "You are an AI orchestrator for the Guideon Chatbot. "
        "Your primary role is to understand the user's intent and the ongoing conversation flow. "
        "Based on this, you will intelligently route the user's query to the most appropriate specialized agent "
        "(e.g., PSFKnowledgeAgent, CourseSearchAgent, LearningPathAgent, GeneralConversationAgent) "
        "or manage the conversational flow transitions. Ensure seamless and contextually relevant interactions."
    )

    def __init__(self, llm=None) -> None:
        super().__init__(llm=llm)
        self.knowledge_agent = PSFKnowledgeAgent(llm=llm)
        self.course_agent = CourseSearchAgent(llm=llm)
        self.learning_path_agent = LearningPathAgent(llm=llm)
        self.flow_manager = FlowManagerAgent(llm=llm)
        self.general_conversation_agent = GeneralConversationAgent(llm=llm)

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        logger.info("Orchestrating query: %s", query[:60])

        intent = context.get("intent")
        previous_intent = context.get("previous_intent")
        logger.info(f"[Orchestrator] Received intent: {getattr(intent, 'value', intent)}")
        
        # First, consult the flow manager agent
        flow_result = await self.flow_manager.process(query, context)
        flow_instructions = flow_result.get("flow_instructions", {})
        logger.info(f"[Orchestrator] Flow instructions: {flow_instructions}")
        
        # **NEW: Create enhanced context for agents with flow information**
        enhanced_context = self._create_enhanced_context(context, flow_result, flow_instructions)
        
        # Update context with flow information
        context.update({
            "flow": flow_instructions,
            "current_flow_state": flow_result.get("current_flow", {}),
            "previous_intent": previous_intent
        })
        
        # Determine which agents to activate based on flow
        tasks = []
        agents_to_activate = flow_instructions.get("activate_agents", [])
        
        # Ensure we only activate one agent
        if len(agents_to_activate) > 1:
            logger.warning(f"[Orchestrator] Multiple agents specified: {agents_to_activate}. Using only the first one.")
            agents_to_activate = [agents_to_activate[0]]
            
        logger.info(f"[Orchestrator] Agent to activate: {agents_to_activate}")

        # If course_search and clarification is needed, skip agent execution
        if getattr(intent, 'value', intent) == "course_search" and flow_instructions.get('flow_action') in ("clarify_course_topic", "request_course_topic_details"):
            # No agent execution needed, just return flow info
            return {
                "agents_processed": 0,
                "processing_time": time.time() - start,
                "context": context
            }
        
        # If switching between general conversation and knowledge base, acknowledge and skip agent execution
        if flow_instructions.get("flow_action") == "intent_switch_acknowledge":
            logger.info(f"[Orchestrator] Intent switch acknowledged: {flow_instructions.get('message')}")
            context["agent_responses"] = {"intent_switch": flow_instructions.get("message")}
            return {
                "agents_processed": 0,
                "processing_time": time.time() - start,
                "context": context
            }
        
        # Map agent names to actual agent instances
        agent_map = {
            "knowledge_agent": self.knowledge_agent,
            "knowledge_base": self.knowledge_agent,
            "learning_path_agent": self.learning_path_agent,
            "course_agent": self.course_agent,
            "general_conversation_agent": self.general_conversation_agent
        }
          # Activate only the specified agent (should be only one now)
        for agent_name in agents_to_activate:
            if agent_name in agent_map:
                logger.info(f"[Orchestrator] Activating agent: {agent_name}")
                # Log if user_id is present in context
                if 'user_id' in context:
                    logger.info(f"[Orchestrator] Passing user_id: {context.get('user_id')} to {agent_name}")
                else:
                    logger.warning(f"[Orchestrator] No user_id found in context to pass to {agent_name}")
                agent = agent_map[agent_name]
                # **PASS ENHANCED CONTEXT TO AGENTS**
                tasks.append(self._execute_agent(agent, query, enhanced_context, agent_name))
                logger.info(f"[Orchestrator] Scheduled {agent_name} with enhanced flow context")

        # Execute the selected agent
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        agent_responses = {}
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Agent error: {result}")
                continue
                
            if not result:
                continue
                
            # Add each agent's response to the collection
            agent_name = result.get("agent_name", f"agent_{i}")
            logger.info(f"[Orchestrator] Result from {agent_name}: {result}")
            agent_responses[agent_name] = result
        
        # Update context with agent responses
        context["agent_responses"] = agent_responses

        current_intent_value = getattr(context.get("intent"), 'value', None)

        # If learning_pathway intent and learning_path_agent has a direct action response
        if current_intent_value == QueryIntent.LEARNING_PATHWAY.value:
            # Log the agent responses to check what's available
            logger.info(f"[Orchestrator] Agent responses for learning pathway: {agent_responses}")
            
            # Look for the response using both possible keys
            learning_path_response = agent_responses.get("learning_path", {})
            if not learning_path_response:
                learning_path_response = agent_responses.get("learning_path_agent", {})
                
            # Log the found response
            logger.info(f"[Orchestrator] Learning path response: {learning_path_response}")
                
            if learning_path_response and (learning_path_response.get("show_goto_career_button") or learning_path_response.get("show_role_selection_button")):
                return {
                    "response": learning_path_response.get("response"),
                    "goto_career_role": learning_path_response.get("goto_career_role"),
                    "show_goto_career_button": learning_path_response.get("show_goto_career_button", False),
                    "available_roles": learning_path_response.get("available_roles"),
                    "show_role_selection_button": learning_path_response.get("show_role_selection_button", False),
                    "context": context,
                    "agents_processed": len(agent_responses),
                    "processing_time": time.time() - start
                }

        # If course_search intent and course_agent has courses or clarification
        if current_intent_value == QueryIntent.COURSE_SEARCH.value:
            course_agent_response = agent_responses.get("course_agent", {})
            logger.info(f"[Orchestrator] Course agent response: {course_agent_response}")
            if course_agent_response and (course_agent_response.get("courses") or course_agent_response.get("needs_clarification")):
                    return {
                        "response": course_agent_response.get("response", "Based on your query, here are some recommended courses:"),
                        "needs_clarification": course_agent_response.get("needs_clarification", False),
                        "clarification_options": course_agent_response.get("clarification_options", []),
                        "courses": course_agent_response.get("courses", []),                    
                        "show_course_suggestions": course_agent_response.get("show_course_suggestions", True) 
                                                  if course_agent_response.get("courses", []) else False,
                        "intent": context.get("intent"),
                        "context": context
                    }
          # Return orchestrated results if no direct action was taken
        logger.info("[Orchestrator] No direct action response from specialized agents, proceeding to general processing for synthesizer.")
        return {
            "agents_processed": len(agent_responses),
            "processing_time": time.time() - start,
            "context": context
        }

    def _create_enhanced_context(self, original_context: Dict[str, Any], 
                               flow_result: Dict[str, Any], 
                               flow_instructions: Dict[str, Any]) -> Dict[str, Any]:
        """
        **NEW METHOD: Create enhanced context with flow information for agents**
        This preserves all original context while adding flow-specific data
        """
        enhanced_context = original_context.copy()  # Start with original context
        
        # Add flow-specific information
        enhanced_context.update({
            # Flow state information
            "flow_context": flow_instructions,
            "current_flow_state": flow_result.get("current_flow", {}),
            "flow_stage": flow_instructions.get("flow_stage"),
            "flow_type": flow_instructions.get("flow_type"),
            
            # Response formatting hints
            "response_format": flow_instructions.get("response_format", {"format": "conversational"}),
            "flow_action": flow_instructions.get("flow_action", "general_response"),
            
            # Connectivity context (if available)
            "connectivity_context": flow_result.get("current_flow", {}).get("connectivity_context", {}),
            
            # Flow metadata
            "flow_enhanced": True,
            "new_flow": flow_instructions.get("new_flow", False),
            "continued_flow": flow_instructions.get("continued_flow", False)
        })
        
        # Preserve specific flow context (role, topic, etc.)
        flow_context = flow_result.get("current_flow", {}).get("context", {})
        if flow_context:
            enhanced_context["flow_preserved_context"] = flow_context
            
            # Extract commonly used context items to top level for easy access
            if "current_entity" in flow_context:
                enhanced_context["focus_role"] = flow_context["current_entity"]
            if "search_topic" in flow_context:
                enhanced_context["focus_topic"] = flow_context["search_topic"]
            if "detected_role" in flow_context:
                enhanced_context["detected_role"] = flow_context["detected_role"]
        
        logger.debug(f"[Orchestrator] Enhanced context created with flow data: {list(enhanced_context.keys())}")
        return enhanced_context

    async def _execute_agent(self, agent: BaseAgent, query: str, 
                            context: Dict[str, Any], key: str) -> Dict[str, Any]:
        """
        **MODIFIED: Execute agent with enhanced context and flow metadata**
        """
        try:
            logger.info(f"[Orchestrator] Executing {key} with enhanced flow context")
            
            # Let the agent process with full enhanced context
            # Log the context keys being passed to the agent
            logger.info(f"[Orchestrator] Executing {agent.__class__.__name__} with context keys: {list(context.keys())}")
            if 'user_id' in context:
                logger.info(f"[Orchestrator] Context contains user_id: {context['user_id']}")
            
            result = await agent.process(query, context)
            
            if result is None:
                logger.warning(f"Agent {key} returned None")
                return {"agent_name": key, "error": "No result returned"}
            
            # Ensure agent_name is set for identification
            if not result.get("agent_name"):
                result["agent_name"] = key
                
            # **NEW: Add flow metadata to agent results**
            result = self._add_flow_metadata_to_result(result, context)
                
            logger.info(f"[Orchestrator] Agent {key} completed successfully with flow enhancement")
            return result
            
        except Exception as e:
            logger.error(f"Error executing agent {key}: {e}", exc_info=True)
            return {
                "agent_name": key,
                "error": str(e),
                "flow_enhanced": True
            }

    def _add_flow_metadata_to_result(self, result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        **NEW METHOD: Add flow metadata to agent results for better tracking**
        """
        if "metadata" not in result:
            result["metadata"] = {}
            
        # Add flow information to metadata
        result["metadata"].update({
            "flow_stage": context.get("flow_stage"),
            "flow_action": context.get("flow_action"),
            "flow_type": context.get("flow_type"),
            "response_format": context.get("response_format", {}).get("format"),
            "flow_enhanced": True
        })
        
        # Add focus context if available
        if context.get("focus_role"):
            result["metadata"]["focus_role"] = context["focus_role"]
        if context.get("focus_topic"):
            result["metadata"]["focus_topic"] = context["focus_topic"]
            
        return result