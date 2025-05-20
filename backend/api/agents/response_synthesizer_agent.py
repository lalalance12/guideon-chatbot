from __future__ import annotations
from typing import Dict, Any, List
import time
import logging
import json

from .base_agent import BaseAgent
from ..utils.intent_classifier import QueryIntent
from agno.agent import Agent
from agno.models.ollama import Ollama

logger = logging.getLogger(__name__)

class ResponseSynthesizerAgent(BaseAgent):
    """Synthesizes a coherent response from multiple agent outputs."""

    def __init__(self) -> None:
        try:
            llama_model = Ollama(id="llama3.1:8b-instruct-q4_1", provider="Ollama", host="http://localhost:11434")
            self.agent = Agent(
                name="ResponseSynthesizer",
                model=llama_model,
            )
            logger.info("Response synthesizer agent initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize response synthesizer agent: {e}")
            self.agent = None

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Synthesize a final response from multiple agent outputs."""
        start_time = time.time()
        logger.info(f"Synthesizing response for: {query[:60]}...")
        
        # Initialize LLM if not already initialized
        if not self.agent:
            try:
                llama_model = Ollama(id="llama3.1:8b-instruct-q4_1", provider="Ollama", host="http://localhost:11434")
                self.agent = Agent(
                    name="ResponseSynthesizer",
                    model=llama_model,
                )
                logger.info("Response synthesizer agent initialized")
            except Exception as e:
                logger.error(f"Failed to initialize response synthesizer agent: {e}")
                return {"response": "I'm having trouble forming a response right now. Please try again later."}
        
        # Check for LLM-detected transitions
        is_transition = context.get("is_transition", False) or context.get("flow", {}).get("is_transition", False)
        previous_intent = context.get("previous_intent") or context.get("flow", {}).get("previous_intent")
        current_intent = context.get("intent")
        
        # Get response format information if available
        format_info = context.get("response_format", {"format": "conversational"})
        format_type = format_info.get("format", "conversational")
        
        # Determine the appropriate prompt based on context
        if is_transition and previous_intent and current_intent:
            # Build a transition-aware prompt
            prompt = self._build_transition_prompt(query, context, previous_intent, current_intent)
        elif format_type == "topic_selection":
            prompt = self._build_topic_selection_prompt(query, context, format_info)
        elif format_type == "course_list":
            prompt = self._build_course_list_prompt(query, context, format_info)
        elif format_type == "role_profile":
            prompt = self._build_role_profile_prompt(query, context, format_info)
        elif format_type == "learning_pathway":
            prompt = self._build_learning_pathway_prompt(query, context, format_info)
        elif format_type == "clarification_request":
            prompt = self._build_clarification_prompt(query, context, format_info)
        else:
            # Default to standard response format
            prompt = self._build_standard_prompt(query, context)
        
        try:
            # Generate the response with LLM
            response = await self.agent.arun(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            processing_time = time.time() - start_time
            return {
                "response": response_text,
                "processing_time": processing_time,
                "format": format_type
            }
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return {
                "response": "I apologize, but I'm having trouble generating a response right now. Please try again.",
                "error": str(e)
            }

    def _build_transition_prompt(self, query: str, context: Dict[str, Any], previous_intent: str, current_intent: str) -> str:
        """Build a prompt that handles topic transitions detected by the LLM."""
        
        # Extract relevant information from context for each intent type
        knowledge_info = ""
        if "knowledge_base" in context:
            kb_result = context["knowledge_base"]
            knowledge_info = kb_result.get("relevant_info", kb_result.get("response", ""))
            
        course_info = ""
        if "course_search" in context:
            course_result = context["course_search"]
            if course_result.get("found", False) and course_result.get("courses"):
                courses = course_result["courses"]
                course_info = f"Found {len(courses)} courses related to {course_result.get('topic', 'the topic')}"
                
                # Add course names for context
                if len(courses) > 0:
                    course_names = [c.get("title", "Untitled Course") for c in courses[:3]]
                    course_info += f". Top courses: {', '.join(course_names)}"
        
        path_info = ""
        if "learning_path" in context:
            path_result = context["learning_path"]
            path_info = path_result.get("summary", "")
        
        # Format user-friendly intent names
        intent_names = {
            "knowledge_base_query": "information about the PSF-AAI framework",
            "course_search": "course recommendations",
            "learning_pathway": "career path information",
            "general_conversation": "our general conversation"
        }
        
        from_intent_name = intent_names.get(previous_intent, "our previous topic")
        to_intent_name = intent_names.get(current_intent, "your new question")
        
        return f"""The user has naturally shifted from {from_intent_name} to {to_intent_name} with this query:
"{query}"

Relevant information for the new topic:
- Knowledge information: {knowledge_info}
- Course information: {course_info}
- Learning path information: {path_info}

Create a thoughtful response that:
1. Naturally acknowledges the shift in conversation without explicitly mentioning it
   (avoid phrases like "I notice you've changed topics")
2. Flows smoothly to address their new question about {to_intent_name}
3. Provides helpful, accurate information relevant to their query
4. Maintains a conversational, supportive tone throughout

Make the response feel like a natural part of an ongoing conversation while focusing on their current need.
"""

    def _build_standard_prompt(self, query: str, context: Dict[str, Any]) -> str:
        """Build a standard prompt for general responses."""
        # Extract knowledge base information
        knowledge_info = ""
        if "knowledge_base" in context:
            kb_result = context["knowledge_base"]
            knowledge_info = kb_result.get("relevant_info", kb_result.get("response", ""))

        # Get intent information
        intent = context.get("intent", "unknown")
        intent_info = f"User intent: {intent}" if intent else ""

        return f"""The user's query: "{query}"

{intent_info}

Relevant knowledge information:
{knowledge_info}

Create a helpful, conversational response that directly addresses the user's query.
The response should be informative, concise, and maintain a friendly, supportive tone.
"""

    def _build_topic_selection_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any]) -> str:
        """Build a prompt for topic selection responses."""
        topics = format_info.get("topics", [])
        topics_list = ", ".join([f'"{t}"' for t in topics])

        return f"""The user's query: "{query}"

Based on the conversation, multiple topics have been identified: {topics_list}

Create a response that:
1. Acknowledges the multiple potential topics of interest
2. Clearly asks the user which specific topic they'd like to explore
3. Presents the options in a conversational, helpful way
4. Has a friendly tone inviting them to specify their interest

Your response should be concise but warm, making it easy for the user to choose one of the presented topics.
"""

    def _build_course_list_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any]) -> str:
        """Build a prompt for course list responses."""
        # Get course information
        course_info = ""
        topic = ""
        courses = []
        
        if "course_search" in context:
            course_result = context["course_search"]
            if course_result.get("found", False) and course_result.get("courses"):
                courses = course_result["courses"]
                topic = course_result.get("topic", "your topic of interest")
                
                # Format course information
                for idx, course in enumerate(courses[:5], 1):  # Limit to top 5 courses
                    title = course.get("title", "Untitled Course")
                    provider = course.get("provider", "Unknown Provider")
                    description = course.get("description", "No description available.")[:100] + "..."
                    course_info += f"{idx}. {title} by {provider}: {description}\n"
        
        return f"""The user is interested in courses about: "{topic}"

Available courses:
{course_info if course_info else "No specific courses found."}

Create a response that:
1. Acknowledges the user's interest in {topic}
2. Presents the course options in a helpful, organized way
3. Highlights the most relevant aspects of each course
4. Encourages the user to explore these learning opportunities

Your response should be informative yet conversational, focusing on helping the user find the right learning resources.
"""

    def _build_role_profile_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any]) -> str:
        """Build a prompt for role profile responses."""
        role_info = ""
        role_name = ""
        
        if "knowledge_base" in context:
            kb_result = context["knowledge_base"]
            role_info = kb_result.get("role_info", kb_result.get("relevant_info", ""))
            role_name = kb_result.get("role_name", "the requested role")
        
        return f"""The user is asking about the role: "{role_name}"

Role information:
{role_info}

Create a comprehensive profile of this role that:
1. Explains the key responsibilities and functions
2. Outlines the essential skills and qualifications
3. Describes how this role fits within the PSF-AAI framework
4. Provides insight into career progression opportunities

Your response should be structured, informative, and presented in a conversational tone that engages the user.
"""

    def _build_learning_pathway_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any]) -> str:
        """Build a prompt for learning pathway responses."""
        pathway_info = ""
        target_role = ""
        
        if "learning_path" in context:
            path_result = context["learning_path"]
            pathway_info = path_result.get("pathway", path_result.get("summary", ""))
            target_role = path_result.get("role", "the requested role")
        
        return f"""The user is interested in a career pathway to become: "{target_role}"

Pathway information:
{pathway_info}

Create a clear learning pathway that:
1. Outlines the progression steps to become a {target_role}
2. Highlights key skills to develop at each stage
3. Suggests relevant certifications or qualifications
4. Provides practical advice for someone pursuing this career track

Your response should be structured as a roadmap with clear steps, while maintaining a supportive, encouraging tone.
"""

    def _build_clarification_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any]) -> str:
        """Build a prompt for clarification request responses."""
        unclear_topic = format_info.get("topic", "")
        
        return f"""The user's query: "{query}"

The user's request needs clarification regarding: {unclear_topic if unclear_topic else "their learning interests"}

Create a friendly response that:
1. Acknowledges their query in a positive way
2. Politely asks for specific clarification
3. Explains why more information would help provide a better answer
4. Makes it easy for them to respond with the details you need

Your response should be conversational and encouraging, making it comfortable for the user to provide more information.
"""