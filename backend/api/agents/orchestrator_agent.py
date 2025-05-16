from __future__ import annotations
import asyncio, logging, time
from typing import Dict, Any

from .base_agent import BaseAgent
from .psf_knowledge_agent import PSFKnowledgeAgent
from .course_search_agent import CourseSearchAgent
from .learning_path_agent import LearningPathAgent
from ..utils.intent_classifier import QueryIntent
from agno.agent import Agent
from agno.models.ollama import Ollama

logger = logging.getLogger(__name__)

# Initialize AGNO agent with v1.4.5 API
try:
    # Initialize with Llama model
    llama_model = Ollama(id="llama3.2:latest", provider="Ollama", host="http://localhost:11434")
    
    # Create the agent with the proper configuration for v1.4.5
    agno_agent = Agent(
        name="OrchestratorAGNOAgent",
        model=llama_model,
        add_history_to_messages=True,
        num_history_runs=3,
        enable_session_summaries=True,
        markdown=True
    )
    logger.info("AGNO orchestrator agent initialized successfully with Llama 3.2")
except Exception as e:
    logger.error(f"Failed to initialize full Llama agent: {e}", exc_info=True)
    try:
        # Fallback to simpler initialization
        agno_agent = Agent(
            name="OrchestratorAGNOAgent",
            model=None
        )
        logger.warning("Falling back to simpler Agent initialization")
    except Exception as e2:
        logger.error(f"Failed to initialize any AGNO agent: {e2}", exc_info=True)
        agno_agent = None

class OrchestratorAgent(BaseAgent):
    """Coordinates the execution of specialised agents based on intent."""

    def __init__(self) -> None:
        self.knowledge_agent = PSFKnowledgeAgent()
        self.course_agent     = CourseSearchAgent()
        self.learning_path_agent = LearningPathAgent()

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        logger.info("Orchestrating query: %s", query[:60])

        intent = context.get("intent")
        tasks  = [
            self._execute_agent(self.knowledge_agent,   query, context, "knowledge_base")
        ]

        if intent in {QueryIntent.EDUCATION_ADVICE, QueryIntent.SKILL_PROGRESSION}:
            tasks.append(self._execute_agent(self.course_agent, query, context, "course_search"))
        if intent == QueryIntent.CAREER_PATH:
            tasks.append(self._execute_agent(self.learning_path_agent, query, context, "learning_path"))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        aggregated: Dict[str, Any] = {}
        for res in results:
            if isinstance(res, Exception):
                logger.error("Agent failed: %s", res)
            else:
                aggregated.update(res)

        logger.info("Orchestration finished in %.2fs", time.time() - start)
        return aggregated

    async def _execute_agent(self, agent: BaseAgent, query: str,
                             context: Dict[str, Any], key: str) -> Dict[str, Any]:
        """Run one agent safely and label its output."""
        try:
            result = await agent.process(query, context)
            return {key: result}
        except Exception as exc:
            logger.error("Error in %s: %s", agent.__class__.__name__, exc)
            raise
