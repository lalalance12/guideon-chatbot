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

        # Handle flow-specific context if available
        flow_context = context.get("flow", {})
        flow_action = flow_context.get("flow_action")
        
        logger.debug("KB search: %s | intent=%s level=%s flow_action=%s",
                     query, getattr(intent, "value", intent), extracted_level, flow_action)

        # Adjust search based on flow action
        if flow_action == "retrieve_career_map":
            search_query = "career map domains job grades vertical tracks horizontal levels psf-aai"
            search_limit = limit * 2
        elif flow_action == "role_information" and "role" in flow_context:
            role = flow_context.get("role")
            search_query = f"{role} role description responsibilities career path"
            search_limit = limit * 2
        elif flow_action == "generate_pathway" and "role" in flow_context:
            role = flow_context.get("role")
            search_query = f"{role} career progression learning pathway skills development"
            search_limit = limit * 2
        elif flow_action == "retrieve_knowledge" and "sections" in flow_context:
            sections = flow_context.get("sections", [])
            section_str = " ".join(sections)
            search_query = f"{query} {section_str}"
            search_limit = limit
        else:
            # Use the standard intent-based search query builder
            search_query, search_limit = self._build_search_query(intent, query, extracted_level, limit, context)

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

        # Add flow-specific metadata to the response
        return {
            "found": True,
            "items": formatted[:limit],
            "metadata": {
                "query_intent": getattr(intent, "value", intent),
                "extracted_level": extracted_level,
                "result_count": len(formatted),
                "result_types": list(types),
                "flow_action": flow_action,
                "search_query": search_query
            },
            "count": len(formatted[:limit]),
        }

    def _build_search_query(self, intent, query, lvl, limit, context=None):
        search_query = query
        
        # Handle different intent types with specific search optimizations
        if intent == QueryIntent.KNOWLEDGE_BASE_QUERY:
            # Extract entities to help focus the search
            extracted_entities = context.get("extracted_entities", {}) if context else {}
            role = extracted_entities.get("extracted_role")
            level = extracted_entities.get("extracted_level") or lvl
            
            # Detect sub-intent from query keywords
            query_lower = query.lower()
            
            # Check for role-related queries
            if any(term in query_lower for term in ["career map", "career path", "job progression", 
                                            "domains", "vertical tracks", "horizontal levels",
                                            "job grades", "career domains"]):
                search_query = f"{query} career map domain job grades progression psf-aai framework"
                limit *= 2
            
            # Rest of conditions remain the same
            elif role or any(kw in query_lower for kw in ["role", "job", "position", "responsibilities"]):
                if role:
                    search_query = f"{role} role description responsibilities tasks requirements"
                else:
                    search_query = f"{query} role description responsibilities tasks"
                limit *= 1.5
            
            # Check for skill-level specific queries
            elif level and any(kw in query_lower for kw in ["level", "proficiency", "competency"]):
                search_query = f"{query} level {level} proficiency competency"
                limit *= 1.5
            
            # Check for skill progression queries
            elif any(kw in query_lower for kw in ["progression", "advance", "improve", "develop"]):
                search_query = f"{query} progression levels path development improvement"
                limit *= 1.5
            
            # General knowledge queries
            else:
                search_query = f"{query} psf-aai framework knowledge description definition"
                    
        elif intent == QueryIntent.LEARNING_PATHWAY:
            # Extract role if available
            extracted_entities = context.get("extracted_entities", {}) if context else {}
            role = extracted_entities.get("extracted_role")
            
            if role:
                search_query = f"{role} career progression learning pathway skills requirements"
                limit *= 2
            else:
                search_query = f"{query} career pathway progression job roles"
                limit *= 1.5
                    
        elif intent == QueryIntent.COURSE_SEARCH:
            # For course searches, focus on skills and learning
            search_query = f"{query} skill development learning training education"
            limit *= 1.2
            
        # Default case - just use the query as is with a small context hint
        else:
            search_query = f"{query} psf-aai information"
            
        return search_query, limit
    
    def _filter_results(self, intent, lvl, raw):
        filtered: List[Dict[str, str]] = []
        types: Set[str] = set()

        # Determine sub-intent for KNOWLEDGE_BASE_QUERY to prioritize results
        sub_intent = None
        if intent == QueryIntent.KNOWLEDGE_BASE_QUERY:
            # Analyze first few results to guess sub-intent
            top_types = {}
            for item in raw[:3]:
                item_type = item.get("metadata", {}).get("type", "")
                if item_type:
                    top_types[item_type] = top_types.get(item_type, 0) + 1
            
            # Use most common type as sub-intent
            if top_types:
                sub_intent = max(top_types, key=top_types.get)
                logger.debug(f"Detected sub-intent: {sub_intent}")

        for item in raw:
            meta = item.get("metadata", {})
            item_type = meta.get("type", "")
            distance = item.get("distance", 1.0)
            lvl_match = meta.get("level")

            if item_type:
                types.add(item_type)
                
            # Adjust threshold based on intent
            threshold = 0.75
            if intent == QueryIntent.LEARNING_PATHWAY:
                # More lenient for learning pathways as we need broader context
                threshold = 0.8
            elif intent == QueryIntent.KNOWLEDGE_BASE_QUERY and sub_intent:
                # More lenient if we have a specific sub-intent detected
                threshold = 0.78
            
            if distance >= threshold:
                continue
                
            result = {
                "title": meta.get("title", "Information"),
                "type": item_type,
                "text": item.get("text", ""),
                "content": item.get("text", ""),
                "relevance": f"{(1 - distance) * 100:.1f}%",
                "metadata": meta,
            }
            
            # Prioritization logic based on detected intent and sub-intent
            if intent == QueryIntent.KNOWLEDGE_BASE_QUERY:
                if lvl is not None and str(lvl_match) == str(lvl):
                    # Prioritize exact level matches
                    filtered.insert(0, result)
                elif sub_intent and item_type == sub_intent:
                    # Prioritize matches for detected sub-intent
                    filtered.insert(0, result)
                else:
                    filtered.append(result)
            elif intent == QueryIntent.LEARNING_PATHWAY and item_type == "role":
                # Prioritize role information for career queries
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