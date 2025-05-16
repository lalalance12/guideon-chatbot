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

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process queries related to learning pathways and career progression"""
        
        # Extract flow context and action
        flow_context, flow_action, _ = self.get_flow_context(context)
        intent = context.get("intent")
        
        # Only process learning pathway intents
        if intent != QueryIntent.LEARNING_PATHWAY:
            return {
                "found": False,
                "reason": "not_learning_pathway_intent",
                "message": "No learning path information for this query type."
            }
        
        try:
            # Check if a specific role was mentioned
            extracted_entities = context.get("extracted_entities", {})
            role = extracted_entities.get("extracted_role")
            
            # Case 1: No specific role mentioned - show available roles
            if not role and flow_action in ["list_available_roles", "suggest_common_roles"]:
                # Get all available roles from the knowledge base
                roles = await self._get_available_roles()
                return {
                    "found": True,
                    "roles": roles,
                    "action": "list_available_roles"
                }
            
            # Case 2: Specific role mentioned - show skills for that role
            elif role or flow_action == "role_skills":
                # If role came from flow context, use that
                specified_role = role or flow_context.get("role")
                if not specified_role:
                    return {
                        "found": False,
                        "reason": "no_role_specified",
                        "message": "No specific role was mentioned."
                    }
                
                # Get skills for the specified role
                skills = await self._get_role_skills(specified_role)
                return {
                    "found": True,
                    "role": specified_role,
                    "skills": skills,
                    "action": "role_skills"
                }
            
            # Default action
            return {
                "found": False,
                "reason": "unknown_action",
                "message": "Not sure what information to provide about learning pathways."
            }
            
        except Exception as e:
            logger.exception(f"Error in learning path agent: {str(e)}")
            return {
                "found": False,
                "reason": "exception",
                "message": f"Error retrieving learning path information: {str(e)}"
            }

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
        """Get functional and enabling skills for a specific role"""
        try:
            # Search for functional skills
            functional_results = await search_similar_content_async(
                f"{role} functional skills technical competencies requirements", 
                limit=10
            )
            
            # Search for enabling skills
            enabling_results = await search_similar_content_async(
                f"{role} enabling skills soft skills competencies", 
                limit=10
            )
            
            # Process the results to extract skills
            functional_skills = []
            enabling_skills = []
            
            # Extract skills from functional results
            for item in functional_results:
                metadata = item.get("metadata", {})
                item_type = metadata.get("type", "")
                
                # If it's explicitly a functional skill, add it
                if item_type == "functional_skill":
                    skill = metadata.get("title", "").strip()
                    if skill and skill not in functional_skills:
                        functional_skills.append(skill)
                
                # Try to extract skills from the text using simple patterns
                text = item.get("text", "").lower()
                if "functional skill" in text or "technical skill" in text:
                    lines = text.split('\n')
                    for line in lines:
                        if line.strip() and ":" not in line and len(line) > 5 and not line.startswith("("):
                            skill = line.strip().capitalize()
                            if skill and skill not in functional_skills:
                                functional_skills.append(skill)
            
            # Extract skills from enabling results
            for item in enabling_results:
                metadata = item.get("metadata", {})
                item_type = metadata.get("type", "")
                
                # If it's explicitly an enabling skill, add it
                if item_type == "enabling_skill":
                    skill = metadata.get("title", "").strip()
                    if skill and skill not in enabling_skills:
                        enabling_skills.append(skill)
                
                # Try to extract skills from the text using simple patterns
                text = item.get("text", "").lower()
                if "enabling skill" in text or "soft skill" in text:
                    lines = text.split('\n')
                    for line in lines:
                        if line.strip() and ":" not in line and len(line) > 5 and not line.startswith("("):
                            skill = line.strip().capitalize()
                            if skill and skill not in enabling_skills:
                                enabling_skills.append(skill)
            
            # If we still didn't find enough skills, use fallbacks
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