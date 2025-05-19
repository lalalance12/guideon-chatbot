from __future__ import annotations
from typing import Dict, Any, List
import logging
import time

from .base_agent import BaseAgent
from ..utils.intent_classifier import QueryIntent
from agno.agent import Agent
from agno.models.ollama import Ollama

logger = logging.getLogger(__name__)

class ResponseSynthesizerAgent(BaseAgent):
    """Synthesizes a coherent response from multiple agent outputs."""

    def __init__(self) -> None:
        """Initialize the response synthesizer with an LLM."""

        self.system_prompt = """
# Guideon: PSF-AAI Career Guide

## Identity and Purpose
You are Guideon, an AI assistant specializing in the Philippine Skills Framework for Analytics & AI (PSF-AAI).
Your purpose is to help professionals navigate career paths in analytics and AI within the Philippine context.

## Core Knowledge Areas
- PSF-AAI framework, roles, and career tracks
- Technical and functional skills in analytics and AI
- Skill proficiency levels (1-6) and progression
- Educational resources and course recommendations
- Career transition pathways between roles

## Conversation Flow Capabilities
- **PSF-AAI Knowledge Queries**: When asked about the framework, roles, or skills, provide structured information from the knowledge base
- **Career Role Exploration**: When no specific role is mentioned in career queries, present available roles with descriptions
- **Role-Specific Skills**: When a specific role is mentioned, display its functional and enabling skills requirements
- **Learning Pathway Generation**: Help users understand how to progress toward their target career role
- **Course Recommendations**: Suggest relevant learning resources based on skills gaps

## Personality Traits
- Professional but approachable, you speak in a friendly, conversational tone, bubbly like Baymax.
- Concise and structured in responses
- Supportive and encouraging of career growth
- Focuses on practical, actionable advice
- Uses Filipino context where relevant

## Response Guidelines
- Structure responses with markdown headings and bullet points; use compact, readable formatting
- Use clear, simple language; avoid jargon unless necessary
- Provide examples or analogies to clarify complex concepts

## Restrictions
- Do not provide information outside the PSF-AAI framework unless specifically related
- Do not make up PSF-AAI information; rely only on provided context
- Avoid discussing political topics or non-PSF-AAI government policies
- Do not recommend specific companies or job openings
- If asked about topics entirely outside your domain, politely redirect to PSF-AAI topics

## Response Format
- Start with a direct answer to the query
- Include relevant PSF-AAI context and details
- Note: Give what the user wants to put extra stuff in the response
"""
        try:
            # Initialize the LLM agent
            self.llm = Ollama(id="llama3.1:8b-instruct-q8_0", # type: ignore
                              provider="Ollama",
                              host="http://localhost:11434")
            self.agent = Agent(
                name="Synthesizer",
                model=self.llm, # type: ignore
                system_message=self.system_prompt,
            )
        except Exception as e:
            logger.error(f"Error initializing Response Synthesizer: {e}")
            self.agent = None

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synthesize a response based on multiple agent outputs and the flow context.
        """
        start = time.time()
        logger.info(f"Synthesizing response for query: {query[:60]}...")

        # Check if we have a valid LLM
        if not self.agent:
            logger.warning("No LLM available for response synthesis, using fallback")
            return self._fallback_response(query, context)

        # Get flow-specific response format if available
        flow_context = context.get("flow", {})
        response_format = flow_context.get("response_format", {"format": "conversational"})
        flow_action = flow_context.get("flow_action", "general_response")

        # Build prompt based on format and flow action
        if response_format.get("format") == "structured":
            prompt = self._build_structured_prompt(query, context, response_format)
        elif response_format.get("format") == "role_profile":
            prompt = self._build_role_profile_prompt(query, context, response_format)
        elif response_format.get("format") == "career_map":
            prompt = self._build_career_map_prompt(query, context, response_format)
        elif response_format.get("format") == "role_skills":
            prompt = self._build_role_skills_prompt(query, context, response_format)
        elif response_format.get("format") == "role_listing":
            prompt = self._build_role_listing_prompt(query, context, response_format)
        elif response_format.get("format") == "learning_pathway":
            prompt = self._build_learning_pathway_prompt(query, context, response_format)
        elif response_format.get("format") == "course_list":
            prompt = self._build_course_list_prompt(query, context, response_format)
        else:
            prompt = self._build_standard_prompt(query, context)

        try:
            # Directly use arun since it's now a stable part of the API
            run_response = await self.agent.arun(prompt)
            text = getattr(run_response, "content", str(run_response))  # Safely get content

            return {
                "response_text": text,
                "processing_time": time.time() - start,
                "format_used": response_format.get("format"),
                "flow_action": flow_action
            }
        except Exception as e:
            logger.error(f"Error in response synthesis: {e}")
            return self._fallback_response(query, context)

    def _build_standard_prompt(self, query: str, context: Dict[str, Any]) -> str:
        """Build a standard prompt for general conversational responses."""
        chat_history = context.get("chat_history", [])
        history_text = ""
        # Log the chat history for debugging
        logger.debug(f"Chat history: {chat_history}")
        if chat_history:
            history_text = "\n## Conversation History:\n"
            for msg in chat_history[-3:]:
                # This is the key line - convert boolean to capitalized role name
                role = "User" if msg.get("is_user") else "Assistant"
                text = msg.get("text", "").replace("\n", " ")
                if msg.get("summarized"):
                    history_text += f"{role} (summarized): {text}\n"
                else:
                    history_text += f"{role}: {text}\n"
                
        agent_responses = context.get("agent_responses", {})
        knowledge_parts = []
        for agent_name, response in agent_responses.items():
            if agent_name == "knowledge_base" and response.get("found", False):
                items = response.get("items", [])
                for item in items:
                    knowledge_parts.append(f"- {item.get('title', 'Information')}: {item.get('text', '')}")
        knowledge_text = "\n".join(knowledge_parts) if knowledge_parts else "No specific information found."

        prompt = f"""# Response Generation Task

## User Query:
"{query}"

{history_text}

## Available Knowledge:
{knowledge_text}

## Instructions:
Note: Try to use all the data you got from the Knowledge Base, do not truncate or lose data.
If the user is very vague and not specific like using words like "it", "this", "that", "there", etc., ask them to clarify their question and be more specific.
Create a helpful, conversational response that addresses the user's query using the available knowledge.
If it isn't related to the PSF-AAI and there isn't enough information to fully answer the query based on the knowledge base, acknowledge this and tell them that this is not your scope.
Keep your response friendly, straightforward, CONCISE, and conversational because you are conversing with a real person.

End your response with a simple encouragement like: "Feel free to ask more questions about PSF-AAI roles, skills, or career pathways. You can also ask me to search for courses to help you learn!"

## Response:
"""
        return prompt

    def _build_structured_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any]) -> str:
        """Build a prompt for structured educational responses."""
        chat_history = context.get("chat_history", [])
        history_text = ""
            # Log the chat history for debugging
        logger.debug(f"Chat history: {chat_history}")
        if chat_history:
            history_text = "\n## Conversation History:\n"
            for msg in chat_history[-3:]:
                # This is the key line - convert boolean to capitalized role name
                role = "User" if msg.get("is_user") else "Assistant"
                text = msg.get("text", "").replace("\n", " ")
                if msg.get("summarized"):
                    history_text += f"{role} (summarized): {text}\n"
                else:
                    history_text += f"{role}: {text}\n"

        agent_responses = context.get("agent_responses", {})
        kb_response = agent_responses.get("knowledge_base", {})
        sections = format_info.get("sections", ["Definition", "Description", "Examples"])
        sections_text = ", ".join(sections)
        knowledge_parts = []
        if kb_response.get("found", False):
            items = kb_response.get("items", [])
            for item in items:
                knowledge_parts.append(f"- {item.get('title', 'Information')}: {item.get('text', '')}")
        knowledge_text = "\n".join(knowledge_parts) if knowledge_parts else "No specific information found."

        prompt = f"""# Structured Educational Response Task

## User Query:
"{query}"

{history_text}

## Available Knowledge:
{knowledge_text}

## Instructions:
Note: Try to use all the data you got from the Knowledge Base, do not truncate or lose data.
IF the user is very vague and not specific like using words like "it", "this", "that", "there", etc., Do not generate sections, just directly ask them to clarify their question and be more specific.
Create a structured educational response with these sections: {sections_text} if available, else try and answer in your own structured education response.
Present the information in a clear, organized manner that helps the user understand the topic thoroughly.
Include specific details from the knowledge base when available.
Use markdown formatting for headers and bullet points.

End with a simple encouragement like: "Want to dive deeper into other PSF-AAI topics or find courses for these skills? Just let me know!"

## Response:
"""
        return prompt

    def _build_role_profile_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any]) -> str:
        """Build a prompt for role profile responses."""


        chat_history = context.get("chat_history", [])
        history_text = ""
            # Log the chat history for debugging
        logger.debug(f"Chat history: {chat_history}")
        if chat_history:
            history_text = "\n## Conversation History:\n"
            for msg in chat_history[-3:]:
                # This is the key line - convert boolean to capitalized role name
                role = "User" if msg.get("is_user") else "Assistant"
                text = msg.get("text", "").replace("\n", " ")
                if msg.get("summarized"):
                    history_text += f"{role} (summarized): {text}\n"
                else:
                    history_text += f"{role}: {text}\n"

        agent_responses = context.get("agent_responses", {})
        flow_context = context.get("flow", {})
        role = flow_context.get("role", "the role")
        knowledge_parts = []
        if "knowledge_base" in agent_responses and agent_responses["knowledge_base"].get("found", False):
            items = agent_responses["knowledge_base"].get("items", [])
            for item in items:
                knowledge_parts.append(f"- {item.get('title', 'Information')}: {item.get('text', '')}")
        knowledge_text = "\n".join(knowledge_parts) if knowledge_parts else f"No specific information found about {role}."

        prompt = f"""# Role Profile Generation Task

## User Query:
"{query}"

{history_text}

## Role Being Discussed:
{role}

## Available Knowledge:
{knowledge_text}

## Instructions:
Note: Try to use all the data you got from the Knowledge Base, do not truncate or lose data.
If the user is very vague and not specific like using words like "it", "this", "that", "there", etc., ask them to clarify their question and be more specific.
Create a comprehensive profile for the role of {role} with the following sections:
1. Role Description - Brief overview of what the role entails
2. Responsibilities - Key tasks and responsibilities
3. Required Skills - Technical and soft skills needed
4. Career Path - Potential progression from and to this role

Use markdown formatting for headers. If information is missing for any section, acknowledge this but provide general industry insights about that aspect of the role.

Conclude with a simple encouragement like: "Interested in courses for these skills or want to explore other PSF-AAI roles? Feel free to ask!"

## Response:
"""
        return prompt

    def _build_learning_pathway_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any]) -> str:
        """Build a prompt for learning pathway responses."""
        agent_responses = context.get("agent_responses", {})
        flow_context = context.get("flow", {})
        role = flow_context.get("role", "the targeted role")
        pathway_info = "No learning pathway information available."
        if "learning_path" in agent_responses:
            pathway = agent_responses["learning_path"].get("pathway", {})
            if pathway:
                steps = pathway.get("steps", [])
                pathway_info = "\n".join([f"- {step}" for step in steps]) if steps else "No specific steps defined."

        prompt = f"""# Learning Pathway Generation Task

## User Query:
"{query}"

## Target Role:
{role}

## Available Pathway Information:
{pathway_info}

## Instructions:
Note: Try to use all the data you got from the Knowledge Base, do not truncate or lose data.
If the user is very vague and not specific like using words like "it", "this", "that", "there", etc., ask them to clarify their question and be more specific.
Create a personalized learning pathway for someone aspiring to become a {role}.
Structure your response with these sections:
1. Current Level - Assumed starting point based on the query
2. Target Level - Description of the {role} position
3. Recommended Skills - Key skills to develop with proficiency targets
4. Learning Resources - Suggested courses, books, or practice projects

Use markdown formatting and make the pathway practical and actionable.
If specific information is missing, provide general industry best practices.

End with a simple encouragement like: "Ready to find courses for these skills or explore other PSF-AAI career pathways? I'm here to help!"

## Response:
"""
        return prompt

    def _build_course_list_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any]) -> str:
        """Build a prompt for course list responses."""
        agent_responses = context.get("agent_responses", {})
        flow_context = context.get("flow", {})
        topic = flow_context.get("topic", "the requested topic")
        course_info = "No course information available."
        if "course_search" in agent_responses:
            courses = agent_responses["course_search"].get("courses", [])
            if courses:
                course_info = ""
                for i, course in enumerate(courses): # type: ignore
                    course_info += f"\nCourse {i+1}:\n"
                    course_info += f"- Title: {course.get('title', 'Untitled')}\n"
                    course_info += f"- Provider: {course.get('provider', 'Unknown')}\n"
                    course_info += f"- Description: {course.get('description', 'No description')}\n"
                    course_info += f"- Level: {course.get('level', 'Not specified')}\n"
                    course_info += f"- URL: {course.get('url', 'No link provided')}\n"

        prompt = f"""# Course Recommendation Task

## User Query:
"{query}"

## Topic:
{topic}

## Available Courses:
{course_info}

## Instructions:
Note: Try to use all the data you got from the Knowledge Base, do not truncate or lose data.
If the user is very vague and not specific like using words like "it", "this", "that", "there", etc., ask them to clarify their question and be more specific.
Create a helpful response recommending courses related to {topic}.
Structure your response with:
1. Brief introduction explaining the importance of {topic}
2. List of recommended courses with name, provider, and brief description
3. Suggested learning path (beginner to advanced)
4. Additional tips for learning this topic

Use markdown formatting for the course list. If no specific courses are available,
provide general advice on how to find good courses on this topic.

Conclude with a simple encouragement like: "Need more course options or want to explore PSF-AAI roles that use these skills? Just ask!"

## Response:
"""
        return prompt

    def _build_role_skills_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any]) -> str:
        """Build a prompt for displaying role skills."""
        agent_responses = context.get("agent_responses", {})
        flow_context = context.get("flow", {})
        role = flow_context.get("role", "the role")
        skills_info = {}
        if "learning_path" in agent_responses:
            skills_info = agent_responses["learning_path"].get("skills", {})
        functional_skills = skills_info.get("functional_skills", [])
        functional_skills_text = "\n".join([f"- {skill}" for skill in functional_skills]) if functional_skills else "No specific functional skills found."
        enabling_skills = skills_info.get("enabling_skills", [])
        enabling_skills_text = "\n".join([f"- {skill}" for skill in enabling_skills]) if enabling_skills else "No specific enabling skills found."
        role_description = "No detailed role description available."
        if "knowledge_base" in agent_responses and agent_responses["knowledge_base"].get("found", False):
            items = agent_responses["knowledge_base"].get("items", [])
            for item in items:
                if item.get("type") == "role" and role.lower() in item.get("title", "").lower(): # type: ignore
                    role_description = item.get("text", role_description)
                    break

        prompt = f"""# Role Skills Profile

## User Query:
"{query}"

## Role:
{role}

## Role Description:
{role_description}

## Functional Skills:
{functional_skills_text}

## Enabling Skills:
{enabling_skills_text}

## Instructions:
Note: Try to use all the data you got from the Knowledge Base, do not truncate or lose data.
If the user is very vague and not specific like using words like "it", "this", "that", "there", etc., ask them to clarify their question and be more specific.
Create a comprehensive profile of the skills needed for the {role} position.
Format your response with these sections:
1. Role Overview - Brief description of the {role} position
2. Functional Skills - Technical skills required with brief explanations
3. Enabling Skills - Soft skills and competencies needed

Use markdown formatting with headers and bullet points. If information is limited, provide industry-standard expectations for this role.

End with a simple encouragement like: "Want to find courses for these skills or learn about career progression from this PSF-AAI role? Let me know!"

## Response:
"""
        return prompt

    def _build_role_listing_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any]) -> str:
        """Build a prompt for displaying available roles."""
        agent_responses = context.get("agent_responses", {})
        roles = []
        if "learning_path" in agent_responses:
            roles = agent_responses["learning_path"].get("roles", [])
        roles_text = ""
        if roles:
            for i, role in enumerate(roles, 1): # type: ignore
                roles_text += f"\nRole {i}: {role.get('title', 'Unknown Role')}\n"
                roles_text += f"Description: {role.get('description', 'No description available')}\n"
        else:
            roles_text = "No specific roles found in the knowledge base."

        prompt = f"""# PSF-AAI Career Roles

## User Query:
"{query}"

## Available Roles:
{roles_text}

## Instructions:
Note: Try to use all the data you got from the Knowledge Base, do not truncate or lose data.
If the user is very vague and not specific like using words like "it", "this", "that", "there", etc., ask them to clarify their question and be more specific.
Create a response that presents the available career roles in the PSF-AAI framework.
Format your response as follows:
1. Introduction - Brief explanation of PSF-AAI career framework
2. Available Roles - List the roles with brief descriptions
3. Instructions - Guide the user to choose a role they're interested in

Use markdown formatting with clear headers and numbering. Make the response engaging and helpful.

End with a simple encouragement like: "Curious about a specific PSF-AAI role, the skills needed, or learning pathways? Feel free to ask me more!"

## Response:
"""
        return prompt

    def _build_career_map_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any]) -> str:
        """Build a prompt for career map visualization responses."""

        chat_history = context.get("chat_history", [])
        history_text = ""
            # Log the chat history for debugging
        logger.debug(f"Chat history: {chat_history}")
        if chat_history:
            history_text = "\n## Conversation History:\n"
            for msg in chat_history[-3:]:
                # This is the key line - convert boolean to capitalized role name
                role = "User" if msg.get("is_user") else "Assistant"
                text = msg.get("text", "").replace("\n", " ")
                if msg.get("summarized"):
                    history_text += f"{role} (summarized): {text}\n"
                else:
                    history_text += f"{role}: {text}\n"

        agent_responses = context.get("agent_responses", {})
        kb_response = agent_responses.get("knowledge_base", {})
        career_map_info = []
        if kb_response.get("found", False):
            items = kb_response.get("items", [])
            for item in items:
                item_type = item.get("type", "")
                if "career_map" in item_type:
                    career_map_info.append(f"- {item.get('title', 'Career Map Info')}: {item.get('text', '')}")
        career_map_text = "\n".join(career_map_info) if career_map_info else "No specific career map information found."

        prompt = f"""# Career Map Visualization Task

## User Query:
"{query}"

{history_text}

## Available Career Map Information:
{career_map_text}

## Instructions:
Note: Try to use all the data you got from the Knowledge Base, do not truncate or lose data.
If the user is very vague and not specific like using words like "it", "this", "that", "there", etc., ask them to clarify their question and be more specific.
Create a structured response that visualizes the PSF-AAI career map framework with these sections:
1. Overview - Explain what the career map is and how it's organized
2. Domains/Vertical Tracks - Describe the different domains or vertical specialization areas
3. Job Grades/Horizontal Levels - Explain the progression levels across the framework
4. Example Paths - Show a few example progression paths within or across domains

Use markdown formatting to create a clear visual structure. If possible, use bullet points or other formatting to show hierarchical relationships between roles.

Conclude with a simple encouragement like: "Want to explore specific PSF-AAI roles, skills for progression, or learning pathways on this map? Just ask!"

## Response:
"""
        return prompt

    def _fallback_response(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a fallback response when the LLM is unavailable."""
        intent = context.get("intent")
        response_text = "I'm having a little trouble connecting right now."

        if intent == QueryIntent.KNOWLEDGE_BASE_QUERY:
            response_text = "I can usually provide information about the PSF-AAI framework. What specific role, skill, or career path are you interested in?"
        elif intent == QueryIntent.LEARNING_PATHWAY:
            response_text = "I can help with learning pathways. Which PSF-AAI role are you aiming for?"
        elif intent == QueryIntent.COURSE_SEARCH:
            response_text = "Looking for courses? Tell me what skills or PSF-AAI topics you're interested in."
        else:
            response_text = "I'm here to help with your questions about the PSF-AAI framework. How can I assist you today?"

        return {
            "response_text": response_text + " Please try asking again in a moment.",
            "format_used": "fallback",
            "flow_action": "fallback_response"
        }