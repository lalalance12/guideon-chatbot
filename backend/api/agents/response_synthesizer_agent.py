from .base_agent import BaseAgent
from ..utils.intent_classifier import QueryIntent
from agno.agent import Agent
from agno.models.ollama import Ollama
import logging
import json
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class ResponseSynthesizerAgent(BaseAgent):
    """Synthesizes responses from multiple information sources"""
    
    def __init__(self):
        # Initialize LLM for response generation
        try:
            self.llm = Ollama(
                id="llama3.1:8b-instruct-q4_1",
                provider="Ollama",
                host="http://localhost:11434"
            )
        except Exception as e:
            logger.error(f"Error initializing Ollama LLM: {e}")
            self.llm = None
    
    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synthesizes a coherent response from the outputs of other agents
        
        Args:
            query: The user's query text
            context: Contains results from knowledge agent, course agent, etc.
            
        Returns:
            Dict with synthesized response
        """
        intent = context.get('intent')
        confidence = context.get('confidence', 0.0)
        
        # Get results from the knowledge base
        kb_results = context.get('knowledge_base', {})
        kb_found = kb_results.get('found', False)
        
        # Optional components based on intent
        course_results = context.get('course_search', {})
        path_results = context.get('learning_path', {})
        
        # Determine if we have a valid response
        if not kb_found and confidence < 0.6:
            # Low confidence and no knowledge base results
            return {
                "response": self._create_general_response(query),
                "source": "fallback"
            }
        
        # For LLM-based response generation
        if self.llm:
            return await self._generate_llm_response(query, intent, kb_results, course_results, path_results)
        
        # Fallback to template-based response if LLM not available
        return {
            "response": self._create_template_response(query, intent, kb_results, course_results, path_results),
            "source": "template"
        }
    
    async def _generate_llm_response(self, query, intent, kb_results, course_results, path_results):
        """Use the LLM to generate a coherent response from all components"""
        try:
            # Prepare the context for the LLM
            llm_context = {
                "query": query,
                "intent": intent.value if hasattr(intent, 'value') else str(intent),
                "psf_knowledge": self._format_kb_results(kb_results),
                "courses": self._format_course_results(course_results),
                "learning_path": self._format_path_results(path_results)
            }
            
            # Convert to JSON string for the prompt
            context_json = json.dumps(llm_context, indent=2)
            
            # Create the prompt
            prompt = {
                "content": f"""You are Guideon, an AI assistant specializing in the Philippine Skills Framework for Analytics & AI (PSF-AAI).
                
                Generate a helpful response to the user query based on these information sources. Focus on being clear, accurate, and helpful.
                
                USER QUERY: {query}
                
                INFORMATION SOURCES:
                {context_json}
                
                Guidelines for your response:
                1. Address the user's question directly and concisely
                2. If PSF knowledge was found, this should be your primary source
                3. For education intents, include course recommendations if available
                4. For career path intents, include learning path information if available
                5. Use a conversational, helpful tone
                6. Format your response with appropriate headings and structure
                7. Only include relevant information; don't mention sources that don't apply
                
                Your response:"""
            }
            
            # Generate the response
            response = await self.llm.invoke([prompt])
            
            return {
                "response": response.content,
                "source": "llm"
            }
            
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            return {
                "response": self._create_template_response(query, intent, kb_results, course_results, path_results),
                "source": "template_fallback"
            }
    
    def _format_kb_results(self, kb_results):
        """Format knowledge base results for the LLM"""
        if not kb_results or not kb_results.get('found', False):
            return {"found": False}
        
        items = kb_results.get('items', [])
        formatted_items = []
        
        for item in items:
            formatted_items.append({
                "title": item.get('title', ''),
                "type": item.get('type', ''),
                "content": item.get('content', '')
            })
        
        return {
            "found": True,
            "items": formatted_items,
            "count": len(formatted_items)
        }
    
    def _format_course_results(self, course_results):
        """Format course results for the LLM"""
        if not course_results or not course_results.get('found', False):
            return {"found": False}
        
        return {
            "found": True,
            "courses": course_results.get('courses', []),
            "count": course_results.get('count', 0)
        }
    
    def _format_path_results(self, path_results):
        """Format learning path results for the LLM"""
        if not path_results or not path_results.get('found', False):
            return {"found": False}
        
        return {
            "found": True,
            "source_role": path_results.get('source_role', ''),
            "target_role": path_results.get('target_role', ''),
            "path": path_results.get('path', [])
        }
    
    def _create_template_response(self, query, intent, kb_results, course_results, path_results):
        """Create a template-based response when LLM is not available"""
        response_parts = []
        
        # Add greeting
        response_parts.append("Hello! I'm Guideon, your PSF-AAI career guide.")
        
        # Add knowledge base information if available
        if kb_results and kb_results.get('found', False):
            items = kb_results.get('items', [])
            if items:
                response_parts.append("\n## PSF-AAI Information")
                for item in items[:2]:  # Limit to first 2 items
                    title = item.get('title', '')
                    content = item.get('content', '')
                    if title and content:
                        response_parts.append(f"\n### {title}")
                        response_parts.append(content[:300] + "..." if len(content) > 300 else content)
        elif kb_results and not kb_results.get('found', False):
            response_parts.append("\nI don't have specific information about that in the PSF-AAI framework.")
            if kb_results.get('psf_aai_info'):
                info = kb_results.get('psf_aai_info')
                response_parts.append(f"\nThe PSF-AAI is {info.get('description')} It {info.get('purpose')}")
        
        # Add course recommendations if available
        if course_results and course_results.get('found', False):
            courses = course_results.get('courses', [])
            if courses:
                response_parts.append("\n## Recommended Courses")
                for course in courses:
                    response_parts.append(f"\n- **{course.get('title')}** by {course.get('provider')} (Rating: {course.get('rating', 'N/A')})")
        
        # Add learning path if available
        if path_results and path_results.get('found', False):
            source = path_results.get('source_role', '')
            target = path_results.get('target_role', '')
            path = path_results.get('path', [])
            
            if source and target and path:
                response_parts.append(f"\n## Career Path: {source.title()} → {target.title()}")
                for step in path:
                    response_parts.append(f"\n### {step.get('name')}")
                    response_parts.append(f"\n{step.get('description')}")
                    skills = step.get('skills', [])
                    if skills:
                        response_parts.append("\nKey skills: " + ", ".join(skills))
                    if step.get('estimated_time'):
                        response_parts.append(f"\nEstimated time: {step.get('estimated_time')}")
        
        # Add closing
        response_parts.append("\nIs there anything specific you'd like to know more about?")
        
        return "\n".join(response_parts)
    
    def _create_general_response(self, query):
        """Create a general response when we don't have specific information"""
        return f"""Hello! I'm Guideon, your guide to the Philippine Skills Framework for Analytics & AI (PSF-AAI).

I specialize in providing information about:
- Analytics and AI career roles and pathways
- Functional skills and their proficiency levels (1-6)
- Learning resources and progression paths

Your query about "{query}" doesn't seem to be specifically about the PSF-AAI framework. Could you please ask something related to analytics or AI careers in the Philippines? I'd be happy to help with information about specific roles, skills, or career progression paths."""