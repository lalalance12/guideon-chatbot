from __future__ import annotations
import asyncio, logging
from typing import Dict, Any, Set, List

from .base_agent import BaseAgent
from ..utils.query_vectors import search_similar_content
from ..utils.intent_classifier import QueryIntent

logger = logging.getLogger(__name__)

class PSFKnowledgeAgent(BaseAgent):
    """Retrieves PSF-AAI knowledge-base information."""

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        intent = context.get("intent")
        extracted_level = context.get("extracted_level")
        limit = 5

        logger.debug("KB search: %s | intent=%s level=%s",
                     query, getattr(intent, "value", intent), extracted_level)

        # Build intent-specific search string
        search_query, search_limit = self._build_search_query(intent, query, extracted_level, limit)

        try:
            # Run blocking vector search in a worker thread
            results = await asyncio.to_thread(search_similar_content, search_query, int(search_limit))
            
            # If we don't get any results, try using the async version which might handle Django ORM better
            if not results or (isinstance(results, dict) and "error" in results):
                logger.info("Trying async search method as fallback")
                from ..utils.query_vectors import search_similar_content_async
                results = await search_similar_content_async(search_query, int(search_limit))
        except Exception as exc:
            logger.error("Search error: %s", exc)
            return self._fail("exception", f"Error accessing knowledge base: {exc}")

        if isinstance(results, dict) and "error" in results:
            return self._fail("search_error", f"Error searching knowledge base: {results['error']}")
        if not results:
            return self._fail("no_results", "No information found for this query.")

        formatted, types = self._filter_results(intent, extracted_level, results)
        if not formatted:
            return self._fail("low_relevance", "Information found but not relevant enough.")

        return {
            "found": True,
            "items": formatted[:limit],
            "metadata": {
                "query_intent": getattr(intent, "value", intent),
                "extracted_level": extracted_level,
                "result_count": len(formatted),
                "result_types": list(types),
            },
            "count": len(formatted[:limit]),
        }

    def _build_search_query(self, intent, query, lvl, limit):
        search_query = query
        if intent == QueryIntent.SKILL_LEVEL_INFO and lvl is not None:
            search_query = f"{query} level {lvl}"
            limit *= 1.5
        elif intent == QueryIntent.SKILL_PROGRESSION:
            search_query = f"{query} progression levels path"
            limit *= 1.5
        elif intent == QueryIntent.SKILL_INFO:
            search_query = f"{query} functional skill description overview"
        elif intent == QueryIntent.ROLE_INFO:
            search_query = f"{query} role description responsibilities tasks"
        elif intent == QueryIntent.CAREER_PATH:
            search_query = f"{query} career map domain job grades progression"
        return search_query, limit

    def _filter_results(self, intent, lvl, raw):
        filtered: List[Dict[str, str]] = []
        types: Set[str] = set()

        for item in raw:
            meta = item.get("metadata", {})
            item_type = meta.get("type", "")
            distance = item.get("distance", 1.0)
            lvl_match = meta.get("level")

            if item_type:
                types.add(item_type)
                
            if distance >= 0.75:
                continue
                
            result = {
                "title": meta.get("title", "Information"),
                "type": item_type,
                "content": item.get("text", ""),
                "relevance": f"{(1 - distance) * 100:.1f}%",
            }
            
            # Prioritize exact level hits first
            if intent == QueryIntent.SKILL_LEVEL_INFO and lvl is not None and str(lvl_match) == str(lvl):
                filtered.insert(0, result)
            else:
                filtered.append(result)

        return filtered, types

    def _fail(self, reason: str, message: str) -> Dict[str, Any]:
        return {
            "found": False,
            "reason": reason,
            "message": message,
            "psf_aai_info": self._get_psf_aai_info(),
        }
    
    def _get_psf_aai_info(self):
        """Returns standard information about PSF-AAI to use when KB doesn't have specific answers"""
        return {
            "name": "Philippine Skills Framework for Analytics & Artificial Intelligence (PSF-AAI)",
            "description": "A structured competency map developed collaboratively by the Analytics & Artificial Intelligence Association of the Philippines (AAP) and the Department of Information and Communications Technology (DICT).",
            "purpose": "Guides education, training, and career development in data analytics and AI across the Philippines.",
            "components": [
                "Career roles and job profiles",
                "Functional skills with proficiency levels 1-6",
                "Enabling skills and competencies",
                "Career progression pathways"
            ],
            "applications": [
                "Curriculum design and education planning",
                "Credentialing and skills assessment",
                "Workforce development and planning",
                "Industry-led upskilling and microcredentialing"
            ],
            "more_info": "Visit psf-aai.vercel.app or contact the Analytics & AI Association of the Philippines (AAP)"
        }
