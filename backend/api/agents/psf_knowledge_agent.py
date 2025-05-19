from __future__ import annotations
import logging
from typing import Dict, Any, Set, List

from .base_agent import BaseAgent
from ..utils.query_vectors import (
    search_similar_content_async, 
    get_related_content_by_id,
    get_skill_levels,
    get_career_progression,
    comprehensive_search,
    create_fallback_content
)
from ..utils.intent_classifier import QueryIntent

logger = logging.getLogger(__name__)

class PSFKnowledgeAgent(BaseAgent):
    """Retrieves PSF-AAI knowledge-base information."""

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        intent = context.get("intent")
        extracted_entities = context.get("extracted_entities", {})
        extracted_level = extracted_entities.get("extracted_level") or context.get("extracted_level")
        extracted_role = extracted_entities.get("extracted_role")
        extracted_skill = extracted_entities.get("extracted_skill") or extracted_entities.get("skill")
        limit = 5

        # Handle flow-specific context if available
        flow_context = context.get("flow", {})
        flow_action = flow_context.get("flow_action")
        
        logger.debug("KB search: %s | intent=%s level=%s role=%s skill=%s flow_action=%s",
                     query, getattr(intent, "value", intent), extracted_level, 
                     extracted_role, extracted_skill, flow_action)

        # Determine search strategy based on flow action
        if flow_action == "retrieve_career_map":
            logger.info("Using career map search strategy")
            search_query = "career map domains job grades vertical tracks horizontal levels psf-aai"
            results = await search_similar_content_async(search_query, entity_type="career_map", limit=limit)
        
        elif flow_action == "role_skills" and "role" in flow_context:
            logger.info(f"Looking up skills for role: {flow_context['role']}")
            # First find the role
            role_results = await search_similar_content_async(
                flow_context["role"], 
                entity_type="job_role", 
                limit=1
            )
            
            if role_results and len(role_results) > 0:
                role_id = role_results[0].get("metadata", {}).get("id")
                if role_id:
                    # Get skills required for this role
                    skill_results = await get_related_content_by_id(role_id, relation_type="skills")
                    # Combine role info with skills
                    results = role_results + skill_results
                else:
                    results = role_results
            else:
                # If role not found by exact match, try broader search
                results = await comprehensive_search(
                    f"{flow_context['role']} skills requirements", 
                    limit=limit
                )
        
        elif flow_action == "list_available_roles":
            logger.info("Listing available roles")
            results = await search_similar_content_async(
                "all roles job positions psf-aai", 
                entity_type="job_role",
                limit=10
            )
            
        elif flow_action == "generate_pathway" and "role" in flow_context:
            logger.info(f"Generating learning pathway for role: {flow_context['role']}")
            # First find the role
            role_results = await search_similar_content_async(
                flow_context["role"], 
                entity_type="job_role", 
                limit=1
            )
            
            if role_results and len(role_results) > 0:
                role_id = role_results[0].get("metadata", {}).get("id")
                if role_id:
                    # Get skills required for this role
                    skill_results = await get_related_content_by_id(role_id, relation_type="skills")
                    # Get career progression information
                    career_results = await get_career_progression(role_id)
                    # Combine all information
                    results = role_results + skill_results + career_results
                else:
                    results = role_results
            else:
                # If role not found by exact match, try broader search
                results = await comprehensive_search(
                    f"{flow_context['role']} career pathway progression", 
                    limit=limit
                )
                
        elif flow_action == "course_search" and "topic" in flow_context:
            logger.info(f"Searching for courses related to: {flow_context['topic']}")
            # For course search, we primarily want skill information
            skill_query = flow_context["topic"]
            
            # First try to find as a skill
            skill_results = await search_similar_content_async(
                skill_query, 
                section="functional_skills",
                limit=3
            )
            
            # If no functional skills, try enabling skills
            if not skill_results:
                skill_results = await search_similar_content_async(
                    skill_query, 
                    section="enabling_skills",
                    limit=3
                )
                
            # If no specific skills found, do a general search
            if not skill_results:
                results = await comprehensive_search(
                    f"{skill_query} skill learning resources courses", 
                    limit=limit
                )
            else:
                results = skill_results
                
        # Default flow or intent-based search
        elif intent == QueryIntent.KNOWLEDGE_BASE_QUERY:
            # Check if we have specific entities to search for
            if extracted_role:
                logger.info(f"Knowledge query about role: {extracted_role}")
                results = await self._build_role_response(
                    extracted_role, 
                    extracted_level, 
                    limit
                )
            elif extracted_skill:
                logger.info(f"Knowledge query about skill: {extracted_skill}")
                results = await self._build_skill_response(
                    extracted_skill, 
                    extracted_level, 
                    limit
                )
            else:
                # General knowledge query
                logger.info(f"General knowledge query: {query}")
                results = await comprehensive_search(query, limit=limit)
                
        elif intent == QueryIntent.LEARNING_PATHWAY:
            if extracted_role:
                logger.info(f"Learning pathway for role: {extracted_role}")
                results = await self._build_learning_pathway_response(
                    extracted_role, 
                    limit
                )
            else:
                logger.info(f"General learning pathway query: {query}")
                results = await comprehensive_search(
                    f"{query} career path progression learning pathway", 
                    limit=limit
                )
                
        elif intent == QueryIntent.COURSE_SEARCH:
            logger.info(f"Course search query: {query}")
            # For course search, focus on skills
            if extracted_skill:
                results = await search_similar_content_async(
                    f"{extracted_skill} skill competency learning", 
                    limit=limit
                )
            else:
                results = await comprehensive_search(
                    f"{query} skill learning resources courses", 
                    limit=limit
                )
        
        else:
            # Fallback to general search
            logger.info(f"Fallback to general search: {query}")
            results = await comprehensive_search(query, limit=limit)

        if isinstance(results, dict) and "error" in results:
            return self._fail("search_error", f"Error searching knowledge base: {results['error']}")
            
        if not results:
            # Try fallback content
            fallback_results = create_fallback_content(query)
            if fallback_results:
                logger.info("Using fallback content for query")
                return {
                    "found": True,
                    "items": fallback_results,
                    "metadata": {
                        "query_intent": getattr(intent, "value", intent),
                        "result_count": len(fallback_results),
                        "result_types": ["fallback"],
                        "fallback": True,
                        "search_query": query
                    },
                    "count": len(fallback_results),
                }
            return self._fail("no_results", "No information found for this query.")

        filtered, types = self._filter_results(intent, extracted_level, results)
        if not filtered:
            return self._fail("low_relevance", "Information found but not relevant enough.")

        # Add flow-specific metadata to the response
        return {
            "found": True,
            "items": filtered[:limit],
            "metadata": {
                "query_intent": getattr(intent, "value", intent),
                "extracted_level": extracted_level,
                "extracted_role": extracted_role, 
                "extracted_skill": extracted_skill,
                "result_count": len(filtered),
                "result_types": list(types),
                "flow_action": flow_action
            },
            "count": len(filtered[:limit]),
        }

    async def _build_role_response(self, role_name: str, level: str, limit: int) -> List[Dict]:
        """Build a comprehensive response about a specific role."""
        # First search for the role
        role_results = await search_similar_content_async(
            role_name, 
            entity_type="job_role",
            limit=1
        )
        
        if not role_results:
            return await comprehensive_search(f"{role_name} role job position", limit=limit)
            
        role_id = role_results[0].get("metadata", {}).get("id")
        if not role_id:
            return role_results
            
        # Get skills required for this role
        skill_results = await get_related_content_by_id(
            role_id, 
            relation_type="skills",
            limit=limit
        )
        
        # Get career progression information
        career_results = await get_career_progression(role_id)
        
        # Combine all results with separators
        combined_results = role_results.copy()
        
        if skill_results:
            # Add a separator
            combined_results.append({
                "text": "--- Skills Required ---",
                "metadata": {"type": "separator"},
                "is_separator": True
            })
            combined_results.extend(skill_results)
        
        if career_results:
            # Add a separator
            combined_results.append({
                "text": "--- Career Path ---",
                "metadata": {"type": "separator"},
                "is_separator": True
            })
            combined_results.extend(career_results)
            
        return combined_results

    async def _build_skill_response(self, skill_name: str, level: str, limit: int) -> List[Dict]:
        """Build a comprehensive response about a specific skill."""
        # First try functional skills
        skill_results = await search_similar_content_async(
            skill_name,
            section="functional_skills",
            limit=1
        )
        
        # If not found, try enabling skills
        if not skill_results:
            skill_results = await search_similar_content_async(
                skill_name,
                section="enabling_skills",
                limit=1
            )
            
        # If still not found, do a general search
        if not skill_results:
            return await comprehensive_search(f"{skill_name} skill competency", limit=limit)
            
        skill_id = skill_results[0].get("metadata", {}).get("id")
        if not skill_id:
            return skill_results
            
        # If a level was specified, get that specific level
        if level:
            parent_id = skill_results[0].get("metadata", {}).get("parent_skill_id", skill_id)
            level_results = await get_skill_levels(parent_id)
            
            # Filter for the specific level
            matching_levels = [l for l in level_results if 
                              str(l.get("metadata", {}).get("level")) == str(level)]
                            
            if matching_levels:
                combined_results = skill_results + matching_levels
            else:
                combined_results = skill_results + level_results
        else:
            # Get all levels
            parent_id = skill_results[0].get("metadata", {}).get("parent_skill_id", skill_id)
            level_results = await get_skill_levels(parent_id)
            
            # Get roles that require this skill
            role_results = await get_related_content_by_id(
                skill_id, 
                relation_type="roles",
                limit=3
            )
            
            # Combine all results with separators
            combined_results = skill_results.copy()
            
            if level_results:
                # Add a separator
                combined_results.append({
                    "text": "--- Proficiency Levels ---",
                    "metadata": {"type": "separator"},
                    "is_separator": True
                })
                combined_results.extend(level_results)
            
            if role_results:
                # Add a separator
                combined_results.append({
                    "text": "--- Roles Requiring This Skill ---",
                    "metadata": {"type": "separator"},
                    "is_separator": True
                })
                combined_results.extend(role_results)
                
        return combined_results

    async def _build_learning_pathway_response(self, role_name: str, limit: int) -> List[Dict]:
        """Build a comprehensive learning pathway response for a role."""
        # Similar to _build_role_response but with an emphasis on learning pathway
        role_results = await search_similar_content_async(
            role_name, 
            entity_type="job_role",
            limit=1
        )
        
        if not role_results:
            return await comprehensive_search(f"{role_name} career path learning progression", limit=limit)
            
        # Get the role ID
        role_id = role_results[0].get("metadata", {}).get("id")
        if not role_id:
            return role_results
            
        # Get skills required for this role (with more emphasis on details)
        skill_results = await get_related_content_by_id(
            role_id, 
            relation_type="skills",
            limit=limit
        )
        
        # For each skill, get its levels too
        enhanced_skill_results = []
        if skill_results:
            for skill_result in skill_results[:3]:  # Limit to top 3 skills to avoid too much info
                skill_id = skill_result.get("metadata", {}).get("id")
                if skill_id:
                    # Get levels for this skill
                    level_results = await get_skill_levels(skill_id, limit=3)
                    if level_results:
                        enhanced_skill_results.append(skill_result)
                        enhanced_skill_results.append({
                            "text": f"--- {skill_result.get('metadata', {}).get('title', 'Skill')} Levels ---",
                            "metadata": {"type": "separator"},
                            "is_separator": True
                        })
                        enhanced_skill_results.extend(level_results)
        
        # Get career progression information
        career_results = await get_career_progression(role_id)
        
        # Combine all results with separators
        combined_results = role_results.copy()
        
        if enhanced_skill_results:
            # Add a separator
            combined_results.append({
                "text": "--- Skills Required (with Proficiency Levels) ---",
                "metadata": {"type": "separator"},
                "is_separator": True
            })
            combined_results.extend(enhanced_skill_results)
        elif skill_results:
            # Fallback if enhanced skill results couldn't be generated
            combined_results.append({
                "text": "--- Skills Required ---",
                "metadata": {"type": "separator"},
                "is_separator": True
            })
            combined_results.extend(skill_results)
        
        if career_results:
            # Add a separator
            combined_results.append({
                "text": "--- Career Progression Path ---",
                "metadata": {"type": "separator"},
                "is_separator": True
            })
            combined_results.extend(career_results)
            
        return combined_results
    
    def _filter_results(self, intent, lvl, raw):
        filtered = []
        types = set()

        # Check if results contain separator markers
        has_separators = any(item.get("is_separator", False) for item in raw)

        for item in raw:
            # If this is a separator marker, keep it as is
            if item.get("is_separator", False):
                filtered.append(item)
                continue
                
            meta = item.get("metadata", {})
            item_type = meta.get("type", "")
            entity_type = meta.get("entity_type", "")
            relation_type = item.get("relation_type", "")
            distance = item.get("distance", 1.0)
            lvl_match = meta.get("level")

            if item_type:
                types.add(item_type)
            if entity_type:
                types.add(entity_type)
            if relation_type:
                types.add(relation_type)
                
            # If the item came from relationship traversal, include it without distance filtering
            if relation_type or has_separators:
                result = {
                    "title": meta.get("title", "Related Information"),
                    "type": item_type or entity_type or relation_type,
                    "text": item.get("text", ""),
                    "content": item.get("text", ""),
                    "metadata": meta,
                }
                filtered.append(result)
                continue
                
            # Filter based on similarity threshold
            if distance >= 0.78:  # Higher threshold = more relevant
                continue
                
            result = {
                "title": meta.get("title", "Information"),
                "type": item_type or entity_type,
                "text": item.get("text", ""),
                "content": item.get("text", ""),
                "relevance": f"{(1 - distance) * 100:.1f}%",
                "metadata": meta,
            }
            
            # Prioritize level matches if level was specified
            if lvl is not None and str(lvl_match) == str(lvl):
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