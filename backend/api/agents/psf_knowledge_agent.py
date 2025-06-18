from __future__ import annotations
import asyncio, logging
from typing import Dict, Any, Set, List

from .base_agent import BaseAgent
from ..utils.query_vectors import search_similar_content, search_similar_content_async, create_fallback_content
from ..utils.intent_classifier import QueryIntent

logger = logging.getLogger(__name__)

class PSFKnowledgeAgent(BaseAgent):
    """Retrieves PSF-AAI knowledge-base information with enhanced connectivity features."""
    
    def __init__(self, llm=None):
        """Initialize the PSF knowledge agent with an optional LLM."""
        super().__init__(llm=llm)
        self.name = "knowledge_agent"  # Consistent naming for correct result mapping

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process a knowledge base query and return relevant information with enhanced connectivity."""
        intent = context.get("intent")
        extracted_entities = context.get("extracted_entities", {})
        extracted_level = extracted_entities.get("extracted_level") or context.get("extracted_level")
        extracted_role = extracted_entities.get("extracted_role") or context.get("extracted_role")
        flow_context = context.get("flow", {})
        flow_action = flow_context.get("flow_action")
        
        logger.debug("Enhanced KB search: %s | intent=%s level=%s role=%s flow_action=%s",
                     query, getattr(intent, "value", intent), extracted_level, 
                     extracted_role, flow_action)

        # Determine section filter and build enhanced search query
        section_filter = self._determine_section_filter(intent, flow_action, flow_context)
        search_query, limit = self._build_enhanced_search_query(
            intent, query, extracted_level, extracted_role, 5, flow_action, flow_context
        )

        try:
            # Perform enhanced vector search with connectivity awareness
            results = await search_similar_content_async(
                search_query, limit=limit, section=section_filter
            )
            
            if isinstance(results, dict) and results.get("error"):
                logger.error(f"Vector search error: {results['error']}")
                return self._fail("search_error", f"Error searching knowledge base: {results['error']}")
                
            # Enhanced results processing with connectivity information
            items = results.get("items", [])
            result_metadata = results.get("metadata", {})
            
            if not items:
                logger.warning("No results found for query: %s", query)
                return self._fail("no_results", "No information found for this query.")
                
            # Enhanced filtering and prioritization with connectivity awareness
            filtered_items, result_types, connectivity_stats = self._filter_results_enhanced(
                intent, extracted_level, extracted_role, items, result_metadata
            )
            
            if not filtered_items:
                logger.warning("No relevant results after filtering for query: %s", query)
                return self._fail("low_relevance", "Information found but not relevant enough.")
                
            # Return enhanced results with connectivity information
            return {
                "found": True,
                "items": filtered_items[:limit],
                "metadata": {
                    "query_intent": getattr(intent, "value", intent),
                    "extracted_level": extracted_level,
                    "extracted_role": extracted_role,
                    "result_count": len(filtered_items),
                    "result_types": list(result_types),
                    "flow_action": flow_action,
                    "search_query": search_query,
                    "section_filter": section_filter,
                    "connectivity_stats": connectivity_stats,
                    "query_intent_detected": result_metadata.get("query_intent"),
                    "connectivity_features": result_metadata.get("connectivity_features", {})
                },
                "count": len(filtered_items[:limit]),
                "agent_name": self.name,
                "agent_class": self.__class__.__name__,
                "processing_time": results.get("processing_time", 0),
                "enhanced_features": {
                    "connectivity_aware": True,
                    "intent_detection": True,
                    "cross_reference_support": True
                }
            }
            
        except Exception as exc:
            logger.error(f"Error during enhanced vector search: {exc}")
            return self._fail("exception", f"Error accessing knowledge base: {exc}")

    def _determine_section_filter(self, intent, flow_action, flow_context):
        """Enhanced section filtering with connectivity awareness"""
        
        # Flow action based filtering with enhanced connectivity
        if flow_action == "retrieve_career_map":
            return "career_map"
        elif flow_action == "role_information":
            return "job_roles"
        elif flow_action == "retrieve_knowledge" and flow_context.get("sections"):
            sections = flow_context.get("sections", [])
            if len(sections) == 1:
                section_map = {
                    "functional_skills": "functional_skills",
                    "enabling_skills": "enabling_skills",
                    "job_roles": "job_roles",
                    "career_map": "career_map"
                }
                return section_map.get(sections[0])
            
        # Intent-based filtering with enhanced logic
        if isinstance(intent, str):
            intent_str = intent
        else:
            intent_str = getattr(intent, "value", "")
            
        # Enhanced intent mapping
        intent_section_map = {
            "learning_pathway": None,  # Need cross-section search for pathways
            "course_search": None,     # Course search needs all sections
            "career_progression": "career_map",  # Focus on career progression
            "skill_requirements": None,  # Need both skill types
            "role_connections": "job_roles"  # Focus on roles
        }
        
        if intent_str in intent_section_map:
            return intent_section_map[intent_str]
        
        # Enhanced skill type detection
        if isinstance(intent, str):
            intent_str = intent.lower()
        else:
            intent_str = getattr(intent, "value", "").lower()
    
        skill_indicators = {
            "enabling_skills": ["enabling skill", "soft skill", "behavioral", "interpersonal"],
            "functional_skills": ["functional skill", "technical skill", "hard skill", "programming"]
        }
        
        for section, indicators in skill_indicators.items():
            if any(indicator in intent_str for indicator in indicators):
                return section
    
        # Default: no section filter for comprehensive search
        return None

    def _build_enhanced_search_query(self, intent, query, level, role, limit, flow_action=None, flow_context=None):
        """Build enhanced search query leveraging connectivity features"""
        search_query = query
        query_lower = query.lower()
        
        # Enhanced flow-specific queries with connectivity context
        if flow_action == "retrieve_career_map":
            search_query = "career progression domains job grades vertical specialization horizontal advancement analytics AI framework"
            limit = 8
        elif flow_action == "role_information" and role:
            search_query = f"{role} responsibilities tasks skills requirements career progression next roles"
            limit = 8
        elif flow_action == "generate_pathway" and role:
            search_query = f"{role} career progression pathway skills development advancement next roles"
            limit = 8
        elif flow_action == "retrieve_knowledge" and flow_context and flow_context.get("sections"):
            sections = flow_context.get("sections", [])
            
            # Enhanced section-specific queries with connectivity
            section_queries = {
                "functional_skills": "functional skills technical competencies proficiency levels role requirements",
                "enabling_skills": "enabling skills soft skills behavioral competencies role applications",
                "job_roles": "job roles positions responsibilities career progression skills requirements",
                "career_map": "career map progression domains grades advancement pathways"
            }
            
            section_terms = [section_queries.get(section, section) for section in sections]
            if section_terms:
                search_query = f"{query} {' '.join(section_terms)}"
                limit = 6
            
        # Enhanced skill-specific queries with role connectivity
        elif any(skill_type in query_lower for skill_type in ["enabling skill", "soft skill"]):
            if role:
                search_query = f"{role} enabling skills soft skills behavioral competencies required"
            else:
                search_query = f"{query} enabling skills behavioral competencies role applications"
            limit = 6
        
        elif any(skill_type in query_lower for skill_type in ["functional skill", "technical skill"]):
            if role:
                search_query = f"{role} functional skills technical competencies required"
            else:
                search_query = f"{query} functional skills technical competencies role requirements"
            limit = 6
    
        # Enhanced intent-based query building with connectivity
        elif intent == QueryIntent.KNOWLEDGE_BASE_QUERY:
            query_enhancements = {
                "career": ["career map", "progression", "advancement", "domains", "grades"],
                "role": ["responsibilities", "tasks", "skills", "requirements", "progression"],
                "skill": ["competencies", "proficiency", "levels", "applications"],
                "progression": ["advancement", "pathway", "development", "next roles"],
                "level": ["proficiency", "competency", "requirements", "applications"]
            }
            
            # Detect query type and enhance accordingly
            for category, keywords in query_enhancements.items():
                if any(keyword in query_lower for keyword in keywords):
                    enhancement = " ".join(keywords)
                    search_query = f"{query} {enhancement}"
                    if role:
                        search_query += f" {role}"
                    if level:
                        search_query += f" level {level}"
                    break
                    
        elif intent == QueryIntent.LEARNING_PATHWAY:
            # Enhanced pathway queries with comprehensive connectivity
            if role:
                search_query = f"{role} career progression pathway skills development requirements next roles advancement"
                limit = 8
            else:
                search_query = f"{query} career pathway progression skills development role advancement"
                limit = 6
                    
        elif intent == QueryIntent.COURSE_SEARCH:
            # Enhanced course search with skill-role connectivity
            search_query = f"{query} skills development learning training education competencies"
            limit = 6
        
        # Default enhancement with PSF-AAI context
        else:
            search_query = f"{query} PSF-AAI analytics AI framework"
            
        return search_query, limit
    
    def _filter_results_enhanced(self, intent, level, role, raw_results, result_metadata):
        """Enhanced filtering with connectivity awareness and cross-reference support"""
        filtered = []
        types = set()
        
        # Enhanced connectivity statistics
        connectivity_stats = {
            "items_with_role_connections": 0,
            "items_with_career_progression": 0,
            "items_with_skill_mappings": 0,
            "high_connectivity_items": 0,
            "cross_referenced_items": 0
        }

        # Detect sub-intent for enhanced prioritization
        sub_intent = self._detect_sub_intent(intent, raw_results)
        
        # Enhanced relevance threshold based on connectivity
        base_threshold = 0.75
        if result_metadata.get("connectivity_features", {}).get("avg_connectivity_score", 0) > 2:
            base_threshold = 0.78  # More lenient for highly connected content

        for item in raw_results:
            meta = item.get("metadata", {})
            item_type = meta.get("type", "")
            distance = item.get("distance", 1.0)
            lvl_match = meta.get("level")
            skill_category = meta.get("skill_category", "")
            connectivity_score = meta.get("connectivity_score", 0)
            
            # Enhanced connectivity features
            used_in_roles = meta.get("used_in_roles", [])
            connected_roles = item.get("connected_roles", [])
            career_progression = item.get("career_progression", [])
            skill_requirements = item.get("skill_requirements", [])
            
            if item_type:
                types.add(item_type)
                
            # Enhanced threshold adjustment based on intent and connectivity
            threshold = base_threshold
            if intent == QueryIntent.LEARNING_PATHWAY:
                threshold = 0.8  # More lenient for pathways
            elif connectivity_score > 3:
                threshold = 0.8  # More lenient for highly connected content
            elif sub_intent and item_type == sub_intent:
                threshold = 0.78  # More lenient for matching sub-intent
            
            if distance >= threshold:
                continue
                
            # Enhanced result object with connectivity information
            result = {
                "title": meta.get("title", "Information"),
                "type": item_type,
                "text": item.get("text", ""),
                "content": item.get("content", item.get("text", "")),
                "relevance": f"{(1 - distance) * 100:.1f}%",
                "metadata": meta,
                "skill_category": skill_category,
                "distance": distance,
                "connectivity_score": connectivity_score
            }
            
            # Add enhanced connectivity information
            if connected_roles:
                result["connected_roles"] = connected_roles
                connectivity_stats["items_with_role_connections"] += 1
                
            if career_progression:
                result["career_progression"] = career_progression
                connectivity_stats["items_with_career_progression"] += 1
                
            if skill_requirements:
                result["skill_requirements"] = skill_requirements
                connectivity_stats["items_with_skill_mappings"] += 1
                
            if connectivity_score > 3:
                connectivity_stats["high_connectivity_items"] += 1
                
            # Enhanced prioritization with connectivity awareness
            priority_score = self._calculate_priority_score(
                result, intent, role, level, sub_intent, used_in_roles
            )
            result["priority_score"] = priority_score
            
            # Insert based on priority score
            insert_index = 0
            for i, existing in enumerate(filtered):
                if existing.get("priority_score", 0) > priority_score:
                    insert_index = i + 1
                else:
                    break
            filtered.insert(insert_index, result)

        # Update cross-reference statistics
        connectivity_stats["cross_referenced_items"] = sum(
            1 for item in filtered 
            if (item.get("connected_roles") or item.get("career_progression") or 
                item.get("skill_requirements"))
        )

        return filtered, types, connectivity_stats

    def _detect_sub_intent(self, intent, raw_results):
        """Enhanced sub-intent detection for better result prioritization"""
        if intent != QueryIntent.KNOWLEDGE_BASE_QUERY or not raw_results:
            return None
            
        # Analyze top results to detect sub-intent patterns
        type_frequency = {}
        connectivity_patterns = {}
        
        for item in raw_results[:5]:  # Analyze top 5 results
            item_type = item.get("metadata", {}).get("type", "")
            if item_type:
                type_frequency[item_type] = type_frequency.get(item_type, 0) + 1
                
            # Analyze connectivity patterns
            meta = item.get("metadata", {})
            if meta.get("has_career_progression"):
                connectivity_patterns["career_focus"] = connectivity_patterns.get("career_focus", 0) + 1
            if meta.get("has_role_connections"):
                connectivity_patterns["role_focus"] = connectivity_patterns.get("role_focus", 0) + 1
        
        # Determine sub-intent based on patterns
        if connectivity_patterns.get("career_focus", 0) >= 2:
            return "career_progression_path"
        elif connectivity_patterns.get("role_focus", 0) >= 2:
            return "whole_role"
        elif type_frequency:
            return max(type_frequency, key=type_frequency.get)
            
        return None

    def _calculate_priority_score(self, result, intent, role, level, sub_intent, used_in_roles):
        """Calculate enhanced priority score based on connectivity and relevance"""
        score = 0
        meta = result.get("metadata", {})
        
        # Base relevance score
        distance = result.get("distance", 1.0)
        score += (1 - distance) * 100
        
        # Enhanced connectivity bonuses
        connectivity_score = result.get("connectivity_score", 0)
        score += min(10, connectivity_score * 2)  # Up to 10 bonus points
        
        # Role-specific bonuses
        if role and isinstance(role, str) and role.strip():
            if role.lower() in meta.get("title", "").lower():
                score += 15  # Exact role match
            elif used_in_roles and role in used_in_roles:
                score += 10  # Role uses this skill
            elif result.get("connected_roles") and role in result.get("connected_roles", []):
                score += 8   # Role connection
        
        # Level-specific bonuses
        if level is not None and str(meta.get("level")) == str(level):
            score += 12
        
        # Intent and sub-intent bonuses
        if sub_intent and result.get("type") == sub_intent:
            score += 8
        
        # Enhanced connectivity feature bonuses
        if result.get("career_progression"):
            score += 5
        if result.get("skill_requirements"):
            score += 4
        if meta.get("has_career_progression") and intent == QueryIntent.LEARNING_PATHWAY:
            score += 10
            
        return score

    def _fail(self, reason: str, message: str) -> Dict[str, Any]:
        """Return enhanced failure response with connectivity-aware PSF-AAI information."""
        return {
            "found": False,
            "reason": reason,
            "message": message,
            "psf_aai_info": self._get_enhanced_psf_aai_info(),
            "agent_name": self.name,
            "agent_class": self.__class__.__name__,
            "enhanced_features": {
                "connectivity_aware": True,
                "intent_detection": True,
                "cross_reference_support": True
            }
        }
    
    def _get_enhanced_psf_aai_info(self):
        """Returns enhanced PSF-AAI information with connectivity features"""
        return {
            "name": "Philippine Skills Framework for Analytics & Artificial Intelligence (PSF-AAI)",
            "description": "A comprehensive, interconnected competency framework with enhanced career progression pathways and skill connectivity mapping.",
            "purpose": "Provides structured guidance for education, training, and career development in data analytics and AI with detailed role relationships and skill mappings.",
            "enhanced_features": [
                "Interconnected career progression pathways",
                "Cross-referenced skill-role mappings",
                "Multi-domain career tracks",
                "Competency level progressions with role connections",
                "Intent-aware knowledge retrieval",
                "Connectivity-based recommendations"
            ],
            "components": [
                "Career roles with detailed progression paths",
                "Functional skills (Levels 1-6) with role mappings",
                "Enabling skills with behavioral competencies",
                "Domain-specific career tracks",
                "Grade-level advancement pathways",
                "Cross-referenced skill requirements"
            ],
            "applications": [
                "Personalized career pathway planning",
                "Skills gap analysis and development",
                "Curriculum design with role alignment",
                "Workforce planning and competency mapping",
                "Industry-led training and microcredentialing",
                "AI-powered career guidance and recommendations"
            ],
            "connectivity_features": [
                "Role-to-skill relationship mapping",
                "Career progression pathway tracking",
                "Cross-domain skill transferability",
                "Competency-based role recommendations",
                "Skills-to-career pathway alignment"
            ],
            "more_info": "Visit psf-aai.vercel.app or contact the Analytics & AI Association of the Philippines (AAP) for comprehensive career guidance"
        }

    def _apply_flow_enhancements(self, search_params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """**NEW: Apply flow-specific enhancements to search parameters**"""
    
        flow_context, flow_action, response_format, flow_state = self.get_flow_context(context)
        focus_role, focus_topic = self.get_focus_elements(context)
    
        # Apply flow-specific search enhancements
        if flow_action == "career_overview_with_connections" and focus_role:
            search_params["role_focus"] = focus_role
            search_params["include_progression_paths"] = True
            search_params["sections"] = ["job_roles", "career_map", "functional_skills"]
        
        elif flow_action == "explore_skill_connections" and focus_topic:
            search_params["skill_focus"] = focus_topic
            search_params["emphasize_connectivity"] = True
            search_params["sections"] = ["functional_skills", "enabling_skills", "job_roles"]
        
        elif flow_action == "comprehensive_connectivity_view":
            search_params["connectivity_mode"] = True
            search_params["include_all_relationships"] = True
        
        # Enhance search based on response format
        format_type = response_format.get("format", "conversational")
        if format_type == "role_profile":
            search_params["prioritize_role_info"] = True
        elif format_type == "career_map":
            search_params["prioritize_career_progression"] = True
        elif format_type == "connectivity_view":
            search_params["prioritize_connections"] = True
    
        return search_params