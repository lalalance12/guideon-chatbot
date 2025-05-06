from .base_agent import BaseAgent
from ..utils.query_vectors import search_similar_content
from ..utils.intent_classifier import QueryIntent
import logging
from typing import Dict, Any, List, Set

logger = logging.getLogger(__name__)

class PSFKnowledgeAgent(BaseAgent):
    """Agent responsible for retrieving PSF-AAI knowledge base information"""
    
    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieves information from the PSF-AAI knowledge base based on query and intent
        
        Args:
            query: The user's query text
            context: Contains intent, extracted_level, etc.
            
        Returns:
            Dict with retrieved knowledge base results
        """
        intent = context.get('intent')
        extracted_level = context.get('extracted_level')
        limit = 8  # Default result limit
        
        logger.debug(f"Searching knowledge base for: {query} with intent: {intent}, level: {extracted_level}")
        
        # Adjust search based on intent
        search_query = query
        search_limit = limit
        
        # Intent-specific search adjustments
        if intent == QueryIntent.SKILL_LEVEL_INFO and extracted_level is not None:
            search_query = f"{query} level {extracted_level}"
            search_limit = limit * 1.5
            
        elif intent == QueryIntent.SKILL_PROGRESSION:
            search_query = f"{query} progression levels path"
            search_limit = limit * 1.5
            
        elif intent == QueryIntent.SKILL_INFO:
            search_query = f"{query} functional skill description overview"
            
        elif intent == QueryIntent.ROLE_INFO:
            search_query = f"{query} role description responsibilities tasks"
            
        elif intent == QueryIntent.CAREER_PATH:
            search_query = f"{query} career map domain job grades progression"
        
        # Perform the search with adjusted parameters
        try:
            results = search_similar_content(search_query, limit=int(search_limit))
            
            # Handle errors and empty results
            if isinstance(results, dict) and "error" in results:
                logger.warning(f"Search error: {results['error']}")
                return {
                    "found": False,
                    "reason": "search_error",
                    "message": f"Error searching knowledge base: {results['error']}",
                    "psf_aai_info": self._get_psf_aai_info()
                }
                
            if not results:
                logger.info("No results found in knowledge base")
                return {
                    "found": False,
                    "reason": "no_results",
                    "message": "No specific information found in our knowledge base for this query.",
                    "psf_aai_info": self._get_psf_aai_info()
                }
            
            # Filter and structure results based on intent
            formatted_results = []
            result_types = set()
            
            # Intent-specific prioritization
            if intent == QueryIntent.SKILL_LEVEL_INFO and extracted_level is not None:
                # For level-specific queries, prioritize exact level matches
                level_matches = []
                other_results = []
                
                for item in results:
                    metadata = item.get('metadata', {})
                    item_type = metadata.get('type', '')
                    item_level = metadata.get('level')
                    distance = item.get('distance', 1.0)
                    
                    # Track result types for metadata
                    if item_type:
                        result_types.add(item_type)
                    
                    # Only include relevant items
                    if distance < 0.75:
                        result = {
                            "title": metadata.get('title', 'Information'),
                            "type": item_type,
                            "content": item.get('text', ''),
                            "relevance": f"{(1-distance)*100:.1f}%"
                        }
                        
                        if item_level and str(item_level) == str(extracted_level):
                            level_matches.append(result)
                        else:
                            other_results.append(result)
                
                # Combine with level-specific results first
                formatted_results = level_matches + other_results
                
            else:
                # Standard processing for other intents
                for item in results:
                    metadata = item.get('metadata', {})
                    item_type = metadata.get('type', '')
                    distance = item.get('distance', 1.0)
                    
                    # Track result types
                    if item_type:
                        result_types.add(item_type)
                    
                    # Add relevant results
                    if distance < 0.75:
                        formatted_results.append({
                            "title": metadata.get('title', 'Information'),
                            "type": item_type,
                            "content": item.get('text', ''),
                            "relevance": f"{(1-distance)*100:.1f}%"
                        })
            
            # If no relevant results after filtering
            if not formatted_results:
                logger.info("Results found but none were relevant enough")
                return {
                    "found": False,
                    "reason": "low_relevance",
                    "message": "Information found but not relevant enough to your question.",
                    "psf_aai_info": self._get_psf_aai_info()
                }
            
            # Result metadata to help agent interpret results
            result_metadata = {
                "query_intent": intent.value if hasattr(intent, 'value') else intent,
                "extracted_level": extracted_level,
                "result_count": len(formatted_results),
                "result_types": list(result_types)
            }
            
            # Return successful results
            return {
                "found": True,
                "items": formatted_results[:int(limit)],
                "metadata": result_metadata,
                "count": len(formatted_results[:int(limit)])
            }
                
        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}")
            return {
                "found": False,
                "reason": "exception",
                "message": f"Error accessing knowledge base: {str(e)}",
                "psf_aai_info": self._get_psf_aai_info()
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