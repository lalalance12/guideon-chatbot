from .base_agent import BaseAgent
from .psf_knowledge_agent import PSFKnowledgeAgent
from .course_search_agent import CourseSearchAgent
from .learning_path_agent import LearningPathAgent
from ..utils.intent_classifier import QueryIntent
import asyncio
import logging
import time
from typing import Dict, Any

logger = logging.getLogger(__name__)

class OrchestratorAgent(BaseAgent):
    """Coordinates the execution of specialized agents based on intent"""
    
    def __init__(self):
        self.knowledge_agent = PSFKnowledgeAgent()
        self.course_agent = CourseSearchAgent()
        self.learning_path_agent = LearningPathAgent()
    
    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orchestrates the execution of specialized agents
        
        Args:
            query: The user's query
            context: Contains intent, chat_history, etc.
            
        Returns:
            Dict with combined results from all agents
        """
        start_time = time.time()
        logger.info(f"Orchestrating response for query: {query[:50]}..." if len(query) > 50 else query)
        
        intent = context.get('intent')
        
        # Prepare tasks for parallel execution
        tasks = []
        agent_results = {}
        
        # Always query PSF knowledge base
        tasks.append(self._execute_agent(self.knowledge_agent, query, context, "knowledge_base"))
        
        # Add specialized agents based on intent
        if intent in [QueryIntent.EDUCATION_ADVICE, QueryIntent.SKILL_PROGRESSION]:
            tasks.append(self._execute_agent(self.course_agent, query, context, "course_search"))
        
        if intent == QueryIntent.CAREER_PATH:
            tasks.append(self._execute_agent(self.learning_path_agent, query, context, "learning_path"))
        
        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Agent execution failed: {str(result)}")
            elif isinstance(result, dict) and len(result) == 2:
                key, value = next(iter(result.items()))
                agent_results[key] = value
        
        processing_time = time.time() - start_time
        logger.info(f"Orchestration completed in {processing_time:.2f}s")
        
        return agent_results
    
    async def _execute_agent(self, agent, query, context, key):
        """Helper method to execute an agent and wrap its result with a key"""
        try:
            result = await agent.process(query, context)
            return {key: result}
        except Exception as e:
            logger.error(f"Error executing {agent.__class__.__name__}: {str(e)}")
            raise e