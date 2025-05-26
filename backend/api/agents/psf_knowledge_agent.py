from __future__ import annotations
import asyncio, logging
from typing import Dict, Any, Set, List

from .base_agent import BaseAgent
from ..utils.query_vectors import search_similar_content, search_similar_content_async, create_fallback_content
from ..utils.intent_classifier import QueryIntent

logger = logging.getLogger(__name__)

class PSFKnowledgeAgent(BaseAgent):
    """Retrieves PSF-AAI knowledge-base information."""
    
    def __init__(self, llm=None):
        """Initialize the PSF knowledge agent with an optional LLM."""
        super().__init__(llm=llm)

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        intent = context.get("intent")
        extracted_entities = context.get("extracted_entities", {})
        extracted_level = extracted_entities.get("extracted_level") or context.get("extracted_level")
        extracted_role = extracted_entities.get("extracted_role")
        limit = 5

        flow_context = context.get("flow", {})
        flow_action = flow_context.get("flow_action")
        logger.debug("KB search: %s | intent=%s level=%s role=%s flow_action=%s",
                     query, getattr(intent, "value", intent), extracted_level, 
                     extracted_role, flow_action)

        # --- Section filter logic ---
        section_filter = None
        # If the user is asking about a career map or progression
        if flow_action in ("provide_career_map", "retrieve_career_map") or (
            isinstance(query, str) and any(term in query.lower() for term in ["career map", "career path", "job progression", "domains", "vertical tracks", "horizontal levels", "job grades", "career domains"])):
            section_filter = "career_map"
        # If the user is asking about a specific role
        elif (flow_action in ("role_information", "provide_role_info") or extracted_role):
            section_filter = "job_roles"
        # If the user is asking about functional/enabling skills
        elif (flow_action in ("provide_knowledge_info", "retrieve_knowledge") or (isinstance(query, str) and any(term in query.lower() for term in ["functional skill", "technical skill", "enabling skill", "soft skill", "competency", "proficiency"]))):
            # Try to distinguish between functional and enabling
            if any(term in query.lower() for term in ["functional skill", "technical skill", "technical competency"]):
                section_filter = "functional_skills"
            elif any(term in query.lower() for term in ["enabling skill", "soft skill", "transversal"]):
                section_filter = "enabling_skills"
            else:
                section_filter = None
        # If the user is asking for general PSF-AAI info
        elif intent == QueryIntent.KNOWLEDGE_BASE_QUERY:
            section_filter = None  # Search all sections for general info
        # If the user is asking for a learning pathway
        elif intent == QueryIntent.LEARNING_PATHWAY:
            section_filter = None  # Pathways may span multiple sections
        # If the user is searching for courses
        elif intent == QueryIntent.COURSE_SEARCH:
            section_filter = None  # Course search may need all sections

        # --- Build search query ---
        search_query = query
        if section_filter == "career_map":
            search_query = "career map domains job grades vertical tracks horizontal levels psf-aai"
            limit = 8
        elif section_filter == "job_roles" and extracted_role:
            search_query = f"{extracted_role} role description responsibilities skills requirements"
            limit = 8
        elif section_filter == "functional_skills":
            search_query = f"{query} functional skills technical competencies"
            limit = 6
        elif section_filter == "enabling_skills":
            search_query = f"{query} enabling skills soft skills behavioral competencies"
            limit = 6
        elif intent == QueryIntent.LEARNING_PATHWAY and extracted_role:
            search_query = f"{extracted_role} career progression learning pathway skills development"
            limit = 8
        elif intent == QueryIntent.COURSE_SEARCH:
            search_query = f"{query} skill development learning training education"
            limit = 6
        else:
            search_query = f"{query} psf-aai framework knowledge description definition"
            limit = 5

        try:
            results = await search_similar_content_async(
                search_query, limit=limit, section=section_filter
            )
        except Exception as exc:
            logger.error(f"Error during vector search: {exc}")
            return self._fail("exception", f"Error accessing knowledge base: {exc}")

        if isinstance(results, dict) and "error" in results:
            logger.error(f"Vector search error: {results['error']}")
            return self._fail("search_error", f"Error searching knowledge base: {results['error']}")
        if not results:
            logger.warning("No results found for query: %s", query)
            return self._fail("no_results", "No information found for this query.")

        # Filter results: Only include those with high relevance and matching the section if set
        filtered = []
        types = set()
        for item in results:
            meta = item.get("metadata", {})
            item_type = meta.get("type", "")
            distance = item.get("distance", 1.0)
            if section_filter and meta.get("psf_section") != section_filter:
                continue
            if distance >= 0.78:
                continue
            types.add(item_type)
            filtered.append({
                "title": meta.get("title", "Information"),
                "type": item_type,
                "text": item.get("text", ""),
                "content": item.get("text", ""),
                "relevance": f"{(1 - distance) * 100:.1f}%",
                "metadata": meta,
                "skill_category": meta.get("skill_category", ""),
                "distance": distance
            })

        if not filtered:
            logger.warning("No relevant results after filtering for query: %s", query)
            return self._fail("low_relevance", "Information found but not relevant enough.")

        return {
            "found": True,
            "items": filtered[:limit],
            "metadata": {
                "query_intent": getattr(intent, "value", intent),
                "extracted_level": extracted_level,
                "extracted_role": extracted_role,
                "result_count": len(filtered),
                "result_types": list(types),
                "flow_action": flow_action,
                "search_query": search_query,
                "section_filter": section_filter
            },
            "count": len(filtered[:limit]),
        }

    def _determine_section_filter(self, intent, flow_action, flow_context):
        """Determine which PSF-AAI section to filter by based on intent and flow context"""
        
        if flow_action == "retrieve_career_map":
            return "career_map"
        elif flow_action == "role_information":
            return "job_roles"
            
        # Intent-based filtering
        if isinstance(intent, str):
            intent_str = intent
        else:
            intent_str = getattr(intent, "value", "")
            
        if intent_str == "learning_pathway":
            return None  # Need to search across sections for comprehensive pathways
        elif "course_search" in intent_str:
            return None  # Course search needs to pull from all sections
            
        # Check sections specified in flow context
        if flow_context and "sections" in flow_context:
            sections = flow_context.get("sections", [])
            if "functional_skills" in sections:
                return "functional_skills"
            elif "enabling_skills" in sections:
                return "enabling_skills"
            elif "job_roles" in sections:
                return "job_roles"
            
        # Default: no section filter
        return None

    def _build_search_query(self, intent, query, level, role, limit, flow_action=None, flow_context=None):
        """Build an optimized search query based on intent and extracted entities"""
        search_query = query
        
        # Flow-specific queries take precedence
        if flow_action == "retrieve_career_map":
            search_query = "career map domains job grades vertical tracks horizontal levels psf-aai"
            limit *= 2
        elif flow_action == "role_information" and role:
            search_query = f"{role} role description responsibilities skills requirements"
            limit *= 2
        elif flow_action == "generate_pathway" and role:
            search_query = f"{role} career progression learning pathway skills development"
            limit *= 2
        elif flow_action == "retrieve_knowledge" and flow_context.get("sections"):
            sections = flow_context.get("sections", [])
            section_terms = []
            
            if "functional_skills" in sections:
                section_terms.append("functional skills technical competencies")
            if "enabling_skills" in sections:
                section_terms.append("enabling skills soft skills")
            if "job_roles" in sections:
                section_terms.append("job roles positions career")
                
            if section_terms:
                section_str = " ".join(section_terms)
                search_query = f"{query} {section_str}"
            
        # Intent-based query building
        elif intent == QueryIntent.KNOWLEDGE_BASE_QUERY:
            # Extract entities to help focus the search
            query_lower = query.lower()
            
            # Check for role-related queries
            if any(term in query_lower for term in ["career map", "career path", "job progression", 
                                            "domains", "vertical tracks", "horizontal levels",
                                            "job grades", "career domains"]):
                search_query = f"{query} career map domain job grades progression psf-aai framework"
                limit *= 2
            
            # Check for role-specific queries
            elif role or any(kw in query_lower for kw in ["role", "job", "position", "responsibilities"]):
                if role:
                    search_query = f"{role} role description responsibilities tasks requirements skills"
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
            
            # Check for functional skill queries
            elif any(kw in query_lower for kw in ["functional skill", "technical skill", "technical competency"]):
                search_query = f"{query} functional skills technical competencies"
                limit *= 1.5
                
            # Check for enabling skill queries
            elif any(kw in query_lower for kw in ["enabling skill", "soft skill", "transversal"]):
                search_query = f"{query} enabling skills soft skills behavioral competencies"
                limit *= 1.5
                
            # General knowledge queries
            else:
                search_query = f"{query} psf-aai framework knowledge description definition"
                    
        elif intent == QueryIntent.LEARNING_PATHWAY:
            # Optimize for learning pathway queries
            if role:
                search_query = f"{role} career progression learning pathway skills requirements development"
                limit *= 2
            else:
                search_query = f"{query} career pathway progression job roles skills development"
                limit *= 1.5
                    
        elif intent == QueryIntent.COURSE_SEARCH:
            # For course searches, focus on skills and learning
            search_query = f"{query} skill development learning training education"
            limit *= 1.2
            
        # Default case - just use the query as is with a small context hint
        else:
            search_query = f"{query} psf-aai information"
            
        return search_query, limit
    
    def _filter_results(self, intent, level, role, raw):
        """Filter and prioritize search results based on intent and metadata"""
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
            skill_category = meta.get("skill_category", "")
            
            # Extract used_in_roles for comparison
            used_in_roles = meta.get("used_in_roles", [])
            
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
                
            # Build a clean result object
            result = {
                "title": meta.get("title", "Information"),
                "type": item_type,
                "text": item.get("text", ""),
                "content": item.get("text", ""),
                "relevance": f"{(1 - distance) * 100:.1f}%",
                "metadata": meta,
                "skill_category": skill_category,
                "distance": distance
            }
            
            # Prioritization logic - insert high-priority items at the front
            should_prioritize = False
            
            # Role-specific prioritization
            if role and isinstance(role, str) and role.strip():
                # Check if this result mentions the exact role
                if role.lower() in meta.get("title", "").lower():
                    should_prioritize = True
                # Check if this result is for a skill used by the role
                elif role in used_in_roles:
                    should_prioritize = True
            
            # Level-specific prioritization  
            if level is not None and str(lvl_match) == str(level):
                should_prioritize = True
                
            # Intent-based prioritization
            if intent == QueryIntent.KNOWLEDGE_BASE_QUERY and sub_intent and item_type == sub_intent:
                should_prioritize = True
            elif intent == QueryIntent.LEARNING_PATHWAY and ("role" in item_type or "career_map" in item_type):
                should_prioritize = True
                
            # Insert at appropriate position
            if should_prioritize:
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