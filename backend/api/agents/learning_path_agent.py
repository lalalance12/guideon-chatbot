from .base_agent import BaseAgent
from ..utils.intent_classifier import QueryIntent
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

class LearningPathAgent(BaseAgent):
    """Agent responsible for generating learning path recommendations"""
    
    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates personalized learning path recommendations based on query and intent
        
        Args:
            query: The user's query text
            context: Contains intent, knowledge base results, etc.
            
        Returns:
            Dict with learning path recommendations
        """
        intent = context.get('intent')
        
        # Only process career path related intents
        if intent != QueryIntent.CAREER_PATH:
            return {
                "found": False,
                "reason": "not_career_path_intent",
                "message": "No learning path generated for this query type."
            }
        
        try:
            # Parse key terms from the query
            source_role, target_role = self._extract_career_path_roles(query)
            
            if not source_role or not target_role:
                return {
                    "found": False,
                    "reason": "roles_not_identified",
                    "message": "Could not identify specific roles to create a path between."
                }
            
            # Generate learning path
            learning_path = self._generate_path(source_role, target_role)
            
            return {
                "found": True,
                "source_role": source_role,
                "target_role": target_role,
                "path": learning_path
            }
            
        except Exception as e:
            logger.error(f"Error generating learning path: {str(e)}")
            return {
                "found": False,
                "reason": "exception",
                "message": f"Error generating learning path: {str(e)}"
            }
    
    def _extract_career_path_roles(self, query: str) -> tuple:
        """Extract source and target roles from the query"""
        query_lower = query.lower()
        
        # Common role titles in PSF-AAI
        roles = [
            "data analyst", "data scientist", "ai engineer", "ml engineer",
            "data engineer", "research scientist", "analytics manager",
            "analytics consultant", "data architect", "business intelligence analyst"
        ]
        
        # Transition keywords
        transition_words = ["to", "become", "transition to", "move to", "advance to"]
        
        source_role = None
        target_role = None
        
        # Simple parsing logic - could be enhanced with NLP
        for role in roles:
            if role in query_lower:
                # If we already found one role, this is the second one
                if source_role:
                    target_role = role
                    break
                else:
                    source_role = role
        
        # If only one role found, assume it's the target
        if source_role and not target_role:
            # Check if there are transition words
            for word in transition_words:
                if word in query_lower:
                    # If transition word is present, the found role is likely the target
                    target_role = source_role
                    source_role = "entry level"  # Default starting point
                    break
        
        # Default if nothing specific found
        if not source_role:
            source_role = "entry level"
        if not target_role:
            target_role = "data analyst"  # Most common entry role
            
        return source_role, target_role
    
    def _generate_path(self, source_role: str, target_role: str) -> list:
        """Generate a learning path between source and target roles"""
        # Mock implementation - would be replaced with actual path generation logic
        
        # Define skill progression paths for common role transitions
        paths = {
            ("entry level", "data analyst"): [
                {
                    "name": "Basic Data Skills",
                    "description": "Master fundamental data analysis techniques",
                    "skills": ["SQL", "Excel", "Basic Statistics", "Data Cleaning"],
                    "estimated_time": "2-3 months"
                },
                {
                    "name": "Data Visualization",
                    "description": "Learn to create effective data visualizations",
                    "skills": ["Tableau", "Power BI", "Data Storytelling"],
                    "estimated_time": "1-2 months"
                },
                {
                    "name": "Basic Programming",
                    "description": "Introduction to programming for data analysis",
                    "skills": ["Python Basics", "Pandas", "NumPy"],
                    "estimated_time": "2-3 months"
                }
            ],
            
            ("data analyst", "data scientist"): [
                {
                    "name": "Advanced Statistics",
                    "description": "Develop strong statistical analysis skills",
                    "skills": ["Hypothesis Testing", "Regression Analysis", "Probability"],
                    "estimated_time": "3-4 months"
                },
                {
                    "name": "Machine Learning Foundations",
                    "description": "Learn core machine learning algorithms and concepts",
                    "skills": ["Supervised Learning", "Unsupervised Learning", "Model Evaluation"],
                    "estimated_time": "4-6 months"
                },
                {
                    "name": "Advanced Programming",
                    "description": "Develop advanced programming skills for data science",
                    "skills": ["Python", "Scikit-Learn", "TensorFlow/PyTorch Basics"],
                    "estimated_time": "3-4 months"
                }
            ],
            
            ("data scientist", "ai engineer"): [
                {
                    "name": "Deep Learning",
                    "description": "Master deep learning techniques and frameworks",
                    "skills": ["Neural Networks", "Computer Vision", "NLP", "Advanced PyTorch/TensorFlow"],
                    "estimated_time": "4-6 months"
                },
                {
                    "name": "MLOps",
                    "description": "Learn to deploy and operationalize ML models",
                    "skills": ["Model Deployment", "Monitoring", "CI/CD for ML"],
                    "estimated_time": "2-3 months"
                },
                {
                    "name": "Production Systems",
                    "description": "Build production-ready AI systems",
                    "skills": ["Scalable Architecture", "Performance Optimization", "API Development"],
                    "estimated_time": "3-4 months"
                }
            ]
        }
        
        # Get the path for the requested transition
        key = (source_role, target_role)
        
        # Return specific path if available
        if key in paths:
            return paths[key]
        
        # Otherwise return a generic path
        return [
            {
                "name": f"Transition from {source_role} to {target_role}",
                "description": "Develop the necessary skills for your career transition",
                "skills": ["Domain Knowledge", "Technical Skills", "Soft Skills"],
                "estimated_time": "6-12 months depending on background"
            },
            {
                "name": "Project Portfolio Development",
                "description": "Build projects demonstrating key skills",
                "skills": ["Applied Projects", "Github Portfolio", "Communication"],
                "estimated_time": "3-6 months"
            }
        ]