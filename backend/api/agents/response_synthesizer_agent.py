from __future__ import annotations
import asyncio, inspect, json, logging
from typing import Dict, Any
from .base_agent import BaseAgent
from ..utils.intent_classifier import QueryIntent
from agno.agent import Agent
from agno.models.ollama import Ollama
from ..utils.context_manager import ContextManager

logger = logging.getLogger(__name__)

class ResponseSynthesizerAgent(BaseAgent):
    """Combines the various agent outputs into a final reply."""

    def __init__(self) -> None:
        try:
            # `model` is the expected kwarg in the latest Ollama SDK
            self.llm = Ollama(id="llama3.1:8b-instruct-q4_1",
                              provider="Ollama", host="http://localhost:11434")
            self.agent = Agent(name="Synthesizer", model=self.llm)
        except Exception as exc:
            logger.error("Could not initialise Ollama: %s", exc)
            self.llm = None  # will fall back to template responses
            self.agent = None

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        intent      = context.get("intent")
        confidence  = context.get("confidence", 0.0)
        kb_results  = context.get("knowledge_base", {})
        course_res  = context.get("course_search", {})
        path_res    = context.get("learning_path", {})

        if not kb_results.get("found") and confidence < 0.6:
            return {"response": self._create_general_response(query), "source": "fallback"}

        if self.llm:
            return await self._generate_llm_response(query, intent, kb_results, course_res, path_res)

        # LLM unavailable
        return {"response": self._create_template_response(query, intent, kb_results,
                                                           course_res, path_res),
                "source": "template"}

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #
    async def _generate_llm_response(self, query, intent, kb, courses, path):
        ctx = {
            "query": query,
            "intent": getattr(intent, "value", str(intent)),
            "psf_knowledge": self._format_kb_results(kb),
            "courses": self._format_course_results(courses),
            "learning_path": self._format_path_results(path),
        }
        
        # Apply context management to ensure we don't exceed token limits
        managed_ctx = ContextManager.truncate_context(ctx)
        
        prompt = (
            "You are Guideon, an AI assistant specialising in the Philippine Skills Framework "
            "for Analytics & AI (PSF-AAI).\n\n"
            f"USER QUERY:\n{query}\n\n"
            "INFORMATION SOURCES:\n"
            f"{json.dumps(managed_ctx, indent=2)}\n\n"
            "Guidelines:\n"
            "1. Answer directly and concisely.\n"
            "2. Use PSF knowledge first if present.\n"
            "3. Include course/path advice when relevant.\n"
            "4. Friendly, structured markdown.\n"
            "5. Omit irrelevant sections.\n\n"
            "Your response:"
        )

        try:
            if self.agent is None:                       # model failed to init
                raise RuntimeError("LLM not available")

            # Agent.run is blocking; Agent.arun is async (Agno ≥ 1.4.0)
            if hasattr(self.agent, "arun"):
                run_resp = await self.agent.arun(prompt)
            else:
                run_resp = await asyncio.to_thread(self.agent.run, prompt)

            text = getattr(run_resp, "content", str(run_resp))
            return {"response": text, "source": "llm"}

        except Exception as exc:
            logger.error("LLM failure: %s", exc)
            return {"response": self._create_template_response(query, intent, kb, courses, path),
                    "source": "template_fallback"}
        
    def _format_kb_results(self, kb_results):
        """Format knowledge base results for the LLM"""
        if not kb_results or not kb_results.get('found', False):
            return {"found": False}

        items = kb_results.get('items', [])
        formatted_items = []

        for item in items:
            formatted_items.append({
                "title": item.get('title', ''),
                "type": item.get('type', ''),
                "content": item.get('content', '')
            })

        return {
            "found": True,
            "items": formatted_items,
            "count": len(formatted_items)
        }
    
    def _format_course_results(self, course_results):
        """Format course results for the LLM"""
        if not course_results or not course_results.get('found', False):
            return {"found": False}
        
        return {
            "found": True,
            "courses": course_results.get('courses', []),
            "count": course_results.get('count', 0)
        }
    
    def _format_path_results(self, path_results):
        """Format learning path results for the LLM"""
        if not path_results or not path_results.get('found', False):
            return {"found": False}
        
        return {
            "found": True,
            "source_role": path_results.get('source_role', ''),
            "target_role": path_results.get('target_role', ''),
            "path": path_results.get('path', [])
        }
    
    def _create_template_response(self, query, intent, kb_results, course_results, path_results):
        """Create a template-based response when LLM is not available"""
        response_parts = []

        # Add greeting
        response_parts.append("Hello! I'm Guideon, your PSF-AAI career guide.")

        # Add knowledge base information if available
        if kb_results and kb_results.get('found', False):
            items = kb_results.get('items', [])
            if items:
                response_parts.append("\n## PSF-AAI Information")
                for item in items[:2]:  # Limit to first 2 items
                    title = item.get('title', '')
                    content = item.get('content', '')
                    if title and content:
                        response_parts.append(f"\n### {title}")
                        response_parts.append(content)
        elif kb_results and not kb_results.get('found', False):
            response_parts.append("\nI don't have specific information about that in the PSF-AAI framework.")

        # Add course recommendations if available
        if course_results and course_results.get('found', False):
            courses = course_results.get('courses', [])
            if courses:
                response_parts.append("\n## Recommended Courses")
                for course in courses:
                    response_parts.append(f"\n- **{course.get('title')}** by {course.get('provider')}")

        # Add learning path if available
        if path_results and path_results.get('found', False):
            source = path_results.get('source_role', '')
            target = path_results.get('target_role', '')
            path = path_results.get('path', [])

            if source and target and path:
                response_parts.append(f"\n## Career Path: {source.title()} → {target.title()}")
                for step in path:
                    response_parts.append(f"\n### {step.get('name')}")
                    response_parts.append(f"\n{step.get('description')}")
                    skills = step.get('skills', [])
                    if skills:
                        response_parts.append("\nKey skills: " + ", ".join(skills))
                    if step.get('estimated_time'):
                        response_parts.append(f"\nEstimated time: {step.get('estimated_time')}")

        # Add closing
        response_parts.append("\nIs there anything specific you'd like to know more about?")

        return "\n".join(response_parts)
    
    def _create_general_response(self, query):
        """Create a general response when we don't have specific information"""
        return f"""Hello! I'm Guideon, your guide to the Philippine Skills Framework for Analytics & AI (PSF-AAI).

I specialize in providing information about:
- Analytics and AI career roles and pathways
- Functional skills and their proficiency levels (1-6)
- Learning resources and progression paths

Your query about "{query}" doesn't seem to be specifically about the PSF-AAI framework. Could you please ask something related to analytics or AI careers in the Philippines? I'd be happy to help with information about specific roles, skills, or career progression paths."""