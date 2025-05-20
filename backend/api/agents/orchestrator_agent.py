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

logger = logging.getLogger(__name__)

# Initialize AGNO agent - keep existing code here

class OrchestratorAgent(BaseAgent):
    """Coordinates the execution of specialised agents based on intent."""

    def __init__(self) -> None:
        self.knowledge_agent = PSFKnowledgeAgent()
        self.course_agent = CourseSearchAgent()
        self.learning_path_agent = LearningPathAgent()
        self.flow_manager = FlowManagerAgent()  # Add the flow manager

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        logger.info("Orchestrating query: %s", query[:60])

        intent = context.get("intent")
        logger.info(f"[Orchestrator] Received intent: {getattr(intent, 'value', intent)}")
        
        # First, consult the flow manager agent
        flow_result = await self.flow_manager.process(query, context)
        flow_instructions = flow_result.get("flow_instructions", {})
        logger.info(f"[Orchestrator] Flow instructions: {flow_instructions}")
        
        # Update context with flow information
        context.update({
            "flow": flow_instructions,
            "current_flow_state": flow_result.get("current_flow", {})
        })
        
        # Determine which agents to activate based on flow
        tasks = []
        agents_to_activate = flow_instructions.get("activate_agents", [])
        logger.info(f"[Orchestrator] Agents to activate: {agents_to_activate}")

        # If course_search and clarification is needed, skip agent execution
        if getattr(intent, 'value', intent) == "course_search" and flow_instructions.get('flow_action') in ("clarify_course_topic", "request_course_topic_details"):
            # No agent execution needed, just return flow info
            return {
                "agents_processed": 0,
                "processing_time": time.time() - start,
                "context": context
            }
        
        if "knowledge_agent" in agents_to_activate:
            logger.info("[Orchestrator] Activating knowledge_agent")
            tasks.append(self._execute_agent(self.knowledge_agent, query, context, "knowledge_base"))
        
        if "learning_path_agent" in agents_to_activate:
            logger.info("[Orchestrator] Activating learning_path_agent")
            tasks.append(self._execute_agent(self.learning_path_agent, query, context, "learning_path"))
        
        if "course_agent" in agents_to_activate:
            logger.info("[Orchestrator] Activating course_agent")
            tasks.append(self._execute_agent(self.course_agent, query, context, "course_search"))

        # If no specialized agents are needed, still collect basic information
        if not tasks:
            logger.info("No specialized agents needed for this query")
            # You might want to add a default agent or placeholder here
            context["agent_responses"] = {}
            return {
                "agents_processed": 0,
                "processing_time": time.time() - start,
                "context": context
            }

        # Execute all selected agents in parallel
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
        
        # Return orchestrated results
        return {
            "agents_processed": len(agent_responses),
            "processing_time": time.time() - start,
            "context": context
        }

    async def _execute_agent(self, agent: BaseAgent, query: str, 
                            context: Dict[str, Any], key: str) -> Dict[str, Any]:
        """Execute a single agent and wrap its response with metadata."""
        start = time.time()
        
        try:
            result = await agent.process(query, context)
            
            # Ensure result is a dictionary
            if not isinstance(result, dict):
                logger.warning(f"Agent {agent.__class__.__name__} returned non-dict: {result}")
                result = {"raw_result": str(result)}
                
            # Add metadata
            result["agent_name"] = key
            result["agent_class"] = agent.__class__.__name__
            result["processing_time"] = time.time() - start
            
            return result
            
        except Exception as e:
            logger.exception(f"Error executing agent {agent.__class__.__name__}: {e}")
            return {
                "agent_name": key,
                "agent_class": agent.__class__.__name__,
                "error": str(e),
                "processing_time": time.time() - start
            }