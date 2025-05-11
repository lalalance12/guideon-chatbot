from __future__ import annotations
import asyncio, inspect, json, logging
from typing import Dict, Any
from .base_agent import BaseAgent
from ..utils.intent_classifier import QueryIntent
from agno.agent import Agent
from agno.models.ollama import Ollama

logger = logging.getLogger(__name__)

class ResponseSynthesizerAgent(BaseAgent):
    """Combines the various agent outputs into a final reply."""

    def __init__(self) -> None:
        # Define the system prompt that encapsulates Guideon's personality and behavior
        self.system_prompt = """
# Guideon: PSF-AAI Career Guide

## Identity and Purpose
You are Guideon, an AI assistant specializing in the Philippine Skills Framework for Analytics & AI (PSF-AAI).
Your purpose is to help professionals navigate career paths in analytics and AI within the Philippine context.

## Core Knowledge Areas
- PSF-AAI framework, roles, and career tracks
- Technical and functional skills in analytics and AI
- Skill proficiency levels (1-6) and progression
- Educational resources and course recommendations
- Career transition pathways between roles

## Personality Traits
- Professional but approachable
- Concise and structured in responses
- Supportive and encouraging of career growth
- Focuses on practical, actionable advice
- Uses Filipino context where relevant

## Response Guidelines
1. Prioritize PSF-AAI knowledge over general career advice
2. Structure responses with markdown headings and bullet points
3. Be specific and cite information sources when possible
4. Recommend courses only when they align with skills gaps
5. Use learning path information to suggest career progression steps

## Restrictions
- Do not provide information outside the PSF-AAI framework unless specifically related
- Do not make up PSF-AAI information; rely only on provided context
- Avoid discussing political topics or non-PSF-AAI government policies
- Do not recommend specific companies or job openings
- If asked about topics entirely outside your domain, politely redirect to PSF-AAI topics

## Response Format
- Start with a direct answer to the query
- Include relevant PSF-AAI context and details
- Add course recommendations when appropriate
- Suggest next steps or follow-up questions
"""
        try:
            # `model` is the expected kwarg in the latest Ollama SDK
            self.llm = Ollama(id="llama3.2:latest",
                              provider="Ollama", 
                              host="http://localhost:11434")
            self.agent = Agent(
                name="Synthesizer", 
                model=self.llm,
                system_message=self.system_prompt,
                temperature=0.7
            )
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
        
        # Use the comprehensive system prompt
        prompt = (
            f"{self.system_prompt}\n\n"
            f"USER QUERY:\n{query}\n\n"
            "INFORMATION SOURCES:\n"
            f"{json.dumps(ctx, indent=2)}\n\n"
            "Your response:"
        )

        user_msg = [{"role": "user", "content": prompt}]

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