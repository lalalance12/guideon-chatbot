from .base_agent import BaseAgent
from ..utils.intent_classifier import QueryIntent
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import time
import random
from typing import List, Dict, Optional, Any
import asyncio

logger = logging.getLogger(__name__)

class CourseSearchAgent(BaseAgent):
    """Agent responsible for finding relevant courses based on user query"""
    
    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        intent = context.get("intent")
        if intent not in {QueryIntent.EDUCATION_ADVICE, QueryIntent.SKILL_PROGRESSION}:
            return {"found": False, "reason": "not_education_intent",
                    "message": "No course search performed for this query type."}

        try:
            params  = self._parse_query(query)
            # run the (blocking) search in a worker thread
            courses: List[Dict[str, str]] = await asyncio.to_thread(self._search_courses, params)
        except Exception as exc:
            logger.error("Course search error: %s", exc)
            return {"found": False, "reason": "exception",
                    "message": f"Error finding courses: {exc}"}

        if not courses:
            return {"found": False, "reason": "no_courses",
                    "message": "No relevant courses found for this query."}

        return {"found": True, "courses": courses, "count": len(courses)}
    
    def _parse_query(self, query: str) -> Dict[str, str]:
        """Extract searchable terms from the user query"""
        # Simple implementation - would be better with LLM parsing
        keywords = ["python", "data science", "machine learning", "ai", "analytics", 
                   "statistics", "sql", "database", "visualization", "beginner", 
                   "intermediate", "advanced"]
        
        query_lower = query.lower()
        
        # Extract recognized keywords
        found_keywords = [kw for kw in keywords if kw in query_lower]
        
        # If no keywords found, use whole query
        if not found_keywords:
            return {"query": query, "filters": None}
        
        # Use the first keyword as main query
        main_query = found_keywords[0]
        
        # Use rest as filters
        filters = {}
        for kw in found_keywords[1:]:
            if kw in ["beginner", "intermediate", "advanced"]:
                filters["level"] = kw
            else:
                if "topic" not in filters:
                    filters["topic"] = []
                filters["topic"].append(kw)
        
        return {"query": main_query, "filters": filters}
    
    def _search_courses(self, search_params: Dict[str, str]) -> List[Dict[str, str]]:
        """Mock implementation of course search - would connect to course_search.py in production"""
        # In a real implementation, this would call the CourseSearchAPI
        # For now, returning mock data based on the search parameters
        
        query = search_params.get("query", "").lower()
        
        # Simple mock course database
        mock_courses = [
            {
                "title": "Introduction to Python Programming",
                "provider": "Coursera",
                "rating": "4.8",
                "url": "https://www.coursera.org/learn/python-programming",
                "tags": ["python", "programming", "beginner"]
            },
            {
                "title": "Data Science and Machine Learning with Python",
                "provider": "edX",
                "rating": "4.7",
                "url": "https://www.edx.org/learn/data-science-python",
                "tags": ["python", "data science", "machine learning", "intermediate"]
            },
            {
                "title": "Advanced Analytics and AI Applications",
                "provider": "Udemy",
                "rating": "4.5",
                "url": "https://www.udemy.com/course/advanced-analytics-ai",
                "tags": ["analytics", "ai", "advanced"]
            },
            {
                "title": "SQL Database Management",
                "provider": "Pluralsight",
                "rating": "4.6",
                "url": "https://www.pluralsight.com/courses/sql-database",
                "tags": ["sql", "database", "beginner"]
            },
            {
                "title": "Data Visualization with Tableau",
                "provider": "LinkedIn Learning",
                "rating": "4.4",
                "url": "https://www.linkedin.com/learning/data-visualization-tableau",
                "tags": ["visualization", "analytics", "intermediate"]
            }
        ]
        
        # Filter courses based on query
        if query:
            filtered_courses = [
                course for course in mock_courses 
                if query in course["title"].lower() or 
                   any(query in tag for tag in course["tags"])
            ]
        else:
            filtered_courses = mock_courses
        
        # Apply additional filters if any
        filters = search_params.get("filters")
        if filters:
            if "level" in filters:
                level = filters["level"]
                filtered_courses = [
                    course for course in filtered_courses
                    if level in course["tags"]
                ]
            
            if "topic" in filters and filters["topic"]:
                topics = filters["topic"]
                filtered_courses = [
                    course for course in filtered_courses
                    if any(topic in course["tags"] for topic in topics)
                ]
        
        # Return results (limited to 3 for brevity)
        return filtered_courses[:3]