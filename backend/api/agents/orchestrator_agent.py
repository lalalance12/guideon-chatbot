from __future__ import annotations
from typing import Dict, Any, List
import asyncio
import logging
import time

from ..utils.chat_history_manager import ChatHistoryManager

from .base_agent import BaseAgent
from .psf_knowledge_agent import PSFKnowledgeAgent
from .course_search_agent import CourseSearchAgent
from .learning_path_agent import LearningPathAgent
from ..utils.intent_classifier import QueryIntent
from ..flows.intent_flows import FlowController
from agno.agent import Agent

logger = logging.getLogger(__name__)

# Initialize AGNO agent - keep existing code here

class OrchestratorAgent(BaseAgent):
    """Coordinates the execution of specialised agents based on intent."""

    def __init__(self) -> None:
        self.knowledge_agent = PSFKnowledgeAgent()
        self.course_agent = CourseSearchAgent()
        self.learning_path_agent = LearningPathAgent()
        self.flow_controller = FlowController()

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        logger.info("Orchestrating query: %s", query[:60])

        intent = context.get("intent")
        
        # Get flow-specific instructions
        flow_instructions = self.flow_controller.process_query(
            query, intent, context
        )
        
        # Update context with flow instructions
        if flow_instructions:
            context["flow"] = flow_instructions
        
        # Determine which agents to activate based on flow instructions
        agents_to_activate = flow_instructions.get("activate_agents", ["knowledge_agent"])
        
        results = {}
        
        # Always run the PSF Knowledge Agent for domain knowledge
        if "knowledge_agent" in agents_to_activate:
            kb_result = await self._execute_agent(
                self.knowledge_agent, 
                query, 
                context, 
                "knowledge_base"
            )
            if kb_result:
                results["knowledge_base"] = kb_result
        
        # Run additional agents based on flow and intent
        if "course_agent" in agents_to_activate:
            course_result = await self._execute_agent(
                self.course_agent, 
                query, 
                context, 
                "course_search"
            )
            if course_result:
                results["course_search"] = course_result
        
        if "learning_path_agent" in agents_to_activate:
            path_result = await self._execute_agent(
                self.learning_path_agent, 
                query, 
                context, 
                "learning_path"
            )
            if path_result:
                results["learning_path"] = path_result
        
        # Add runtime metadata
        results["metadata"] = {
            "intent": getattr(intent, "value", str(intent)) if intent else "unknown",
            "processing_time": time.time() - start,
            "flow": flow_instructions.get("flow_action", "general_response")
        }
        
        return results

    async def _execute_agent(self, agent, query, context, key):
        """Execute an agent with the given query and context."""
        try:
            # Make sure chat history and flow information is passed to all agents
            full_context = context.copy()
            
            # This is critical - pass chat history to topic extractor via agents
            if "chat_history" not in full_context and hasattr(self, "chat_id"):
                # Get chat history if not already in context
                chat_history = await ChatHistoryManager.get_simple_history(self.chat_id)
                full_context["chat_history"] = chat_history
            
            result = await agent.process(query, full_context)
            return result
        except Exception as e:
            logger.error(f"Error executing {key} agent: {e}")
            return None