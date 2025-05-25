from __future__ import annotations
from typing import Dict, Any, List, Optional
import logging
import asyncio

from .base_agent import BaseAgent
from ..utils.query_vectors import search_similar_content_async
from ..utils.intent_classifier import QueryIntent

logger = logging.getLogger(__name__)

class LearningPathAgent(BaseAgent):
    """
    Generates personalized learning pathways based on career aspirations.
    Provides information about roles, required skills, and progression paths.
    """
    
    def __init__(self, llm=None):
        """Initialize the learning path agent with an optional LLM."""
        super().__init__(llm=llm)

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process queries related to learning pathways and career progression"""
        flow_context, flow_action, _ = self.get_flow_context(context)
        intent = context.get("intent")
        PSF_AAI_ROLES = [
            "associate data analyst",
            "data analyst",
            "associate data engineer",
            "business intelligence analyst",
            "data engineer",
            "machine learning engineer",
            "applied data/ai researcher",
            "senior business intelligence analyst",
            "data quality specialist",
            "senior data engineer",
            "data scientist",
            "ai engineer",
            "senior applied data/ai researcher",
            "business analytics manager",
            "data governance manager",
            "data architect",
            "senior data scientist",
            "senior ai engineer",
            "research manager",
            "business analytics director",
            "data governance officer",
            "chief data architect",
            "chief data scientist",
            "chief ai engineer",
            "director of research",
            "chief business function officer",
            "chief data officer",
            "chief information officer",
            "chief analytics officer",
            "chief technology officer",
            "chief scientific officer"
        ]
        if intent != QueryIntent.LEARNING_PATHWAY:
            return {
                "found": False,
                "reason": "not_learning_pathway_intent",
                "message": "No learning path information for this query type."
            }
        try:
            extracted_entities = context.get("extracted_entities", {})
            possible_entities = []
            if "extracted_role" in extracted_entities:
                if isinstance(extracted_entities["extracted_role"], list):
                    possible_entities.extend([r for r in extracted_entities["extracted_role"] if r])
                elif extracted_entities["extracted_role"]:
                    possible_entities.append(extracted_entities["extracted_role"])
            # Only consider roles in PSF_AAI_ROLES
            filtered_entities = [e for e in possible_entities if e and e.lower() in PSF_AAI_ROLES]
            if len(filtered_entities) == 0:
                return {
                    "found": False,
                    "reason": "no_valid_entity_specified",
                    "message": "Please select one of the available PSF-AAI career roles for learning pathways.",
                    "available_roles": PSF_AAI_ROLES
                }
            elif len(filtered_entities) == 1:
                entity = filtered_entities[0]
                # Fetch both the career map (overview) and the skills for the role
                career_map = await self._get_career_map(entity)
                skills = await self._get_role_skills(entity)
                return {
                    "found": True,
                    "entity": entity,
                    "career_map": career_map,
                    "skills": skills,
                    "action": "career_map_and_skills"
                }
            else:
                return {
                    "found": False,
                    "reason": "multiple_entities_found",
                    "entities": filtered_entities,
                    "message": f"Multiple possible roles/entities found: {', '.join(filtered_entities)}. Which one would you like a career overview for?"
                }
        except Exception as e:
            logger.exception(f"Error in learning path agent: {str(e)}")
            return {
                "found": False,
                "reason": "exception",
                "message": f"Error retrieving learning path information: {str(e)}"
            }

    async def _get_career_map(self, entity: str) -> str:
        """Fetch the career map/overview for a given role/entity from the knowledge base, using only relevant chunk types."""
        try:
            # Only consider relevant chunk types for career map
            results = await search_similar_content_async(
                f"{entity} career map overview PSF-AAI progression path",
                limit=3
            )
            # Filter for relevant chunk types
            for item in results:
                meta = item.get("metadata", {})
                chunk_type = meta.get("type", "")
                if chunk_type in ["career_map_overview", "career_map_domain", "career_map_grade", "whole_role"]:
                    return item.get("text", "No career map found for this role.")
            return f"No career map found for {entity}."
        except Exception as e:
            logger.error(f"Error retrieving career map for {entity}: {e}")
            return f"Error retrieving career map for {entity}."

    async def _get_career_overview(self, entity: str) -> str:
        """Fetch the career overview for a given role/entity from the knowledge base."""
        try:
            # Search for the role/entity overview in the vector database
            results = await search_similar_content_async(
                f"{entity} role overview career description responsibilities PSF-AAI", 
                limit=1
            )
            if results and isinstance(results, list) and results[0].get("text"):
                return results[0]["text"]
            return f"No career overview found for {entity}."
        except Exception as e:
            logger.error(f"Error retrieving career overview for {entity}: {e}")
            return f"Error retrieving career overview for {entity}."

    async def _get_available_roles(self) -> List[Dict[str, str]]:
        """Return available roles with descriptions from PSF-AAI framework"""
        try:
            # Search for role information in the vector database
            results = await search_similar_content_async(
                "PSF-AAI career roles job titles descriptions responsibilities", 
                limit=15
            )
            
            # Process results to extract unique roles
            roles = []
            seen_titles = set()
            
            for item in results:
                # Extract metadata
                metadata = item.get("metadata", {})
                item_type = metadata.get("type", "")
                
                # Only process role-type entries
                if item_type == "role":
                    title = metadata.get("title", "").strip()
                    
                    # Skip if no title or we've already seen this role
                    if not title or title.lower() in seen_titles:
                        continue
                        
                    # Add to our results
                    seen_titles.add(title.lower())
                    roles.append({
                        "title": title,
                        "description": item.get("text", "")[:200] + "..." if len(item.get("text", "")) > 200 else item.get("text", "No description available")
                    })
            
            return roles
            
        except Exception as e:
            logger.error(f"Error retrieving available roles: {e}")
            # Return fallback roles if we encounter an error
            return [
                {"title": "Data Analyst", "description": "Analyzes and interprets data to inform decision-making"},
                {"title": "Data Engineer", "description": "Builds and maintains data pipelines and infrastructure"},
                {"title": "Data Scientist", "description": "Applies statistical analysis and machine learning to extract insights"},
                {"title": "AI Engineer", "description": "Develops and implements artificial intelligence systems"},
                {"title": "Business Intelligence Analyst", "description": "Creates dashboards and reports for business insights"}
            ]

    async def _get_role_skills(self, role: str) -> Dict[str, List[str]]:
        """Get functional and enabling skills for a specific role using only relevant chunk types."""
        try:
            # Search for role skills using only relevant chunk types
            results = await search_similar_content_async(
                f"{role} functional skills enabling skills requirements",
                limit=5
            )
            functional_skills = []
            enabling_skills = []
            for item in results:
                meta = item.get("metadata", {})
                chunk_type = meta.get("type", "")
                # Only use relevant chunk types
                if chunk_type in ["whole_role", "role_skills", "fs_complete_overview", "esc_complete_overview"]:
                    # Extract functional skills
                    if "required_functional_skills" in meta:
                        for fs in meta["required_functional_skills"]:
                            skill = fs.get("skill")
                            if skill and skill not in functional_skills:
                                functional_skills.append(skill)
                    # Extract enabling skills
                    if "required_enabling_skills" in meta:
                        for es in meta["required_enabling_skills"]:
                            skill = es.get("skill")
                            if skill and skill not in enabling_skills:
                                enabling_skills.append(skill)
            # Fallback if not enough found
            if len(functional_skills) < 3:
                functional_skills = self._get_fallback_functional_skills(role)
            if len(enabling_skills) < 3:
                enabling_skills = self._get_fallback_enabling_skills(role)
            return {
                "functional_skills": functional_skills[:7],
                "enabling_skills": enabling_skills[:7]
            }
        except Exception as e:
            logger.error(f"Error retrieving skills for {role}: {e}")
            return {
                "functional_skills": self._get_fallback_functional_skills(role),
                "enabling_skills": self._get_fallback_enabling_skills(role)
            }
    
    def _get_fallback_functional_skills(self, role: str) -> List[str]:
        """Provide fallback functional skills for common roles"""
        role_lower = role.lower()
        
        if "data analyst" in role_lower:
            return ["Data Analytics", "Data Visualization", "SQL", "Data Engineering", "Business Needs Analysis"]
        elif "data scientist" in role_lower:
            return ["Machine Learning", "Statistical Analysis", "Data Analytics", "Data Engineering", "Data Visualization"]
        elif "engineer" in role_lower:
            return ["Data Engineering", "Software Development", "ML Operations", "Cloud Technologies", "Database Management"]
        elif "intelligence" in role_lower or "bi" in role_lower:
            return ["Business Intelligence", "Data Visualization", "SQL", "Data Modeling", "Reporting"]
        else:
            return ["Data Analytics", "Data Management", "Technical Skills", "Programming", "Statistics"]
    
    def _get_fallback_enabling_skills(self, role: str) -> List[str]:
        """Provide fallback enabling skills for common roles"""
        return ["Communication", "Critical Thinking", "Problem Solving", "Teamwork", "Learning Agility", "Digital Fluency"]