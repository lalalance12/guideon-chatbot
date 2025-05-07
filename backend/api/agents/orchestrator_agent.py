from __future__ import annotations
import asyncio, logging, time
from typing import Dict, Any

from .base_agent import BaseAgent
from .psf_knowledge_agent import PSFKnowledgeAgent
from .course_search_agent import CourseSearchAgent
from .learning_path_agent import LearningPathAgent
from ..utils.intent_classifier import QueryIntent

logger = logging.getLogger(__name__)

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
                aggregated.update(res)          # <- accept {key: value} dicts of any length

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
