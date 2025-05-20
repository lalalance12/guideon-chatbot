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

## Personality Traits
- Professional but approachable, with a friendly, conversational tone like a helpful mentor
- Concise and structured in responses, with a focus on clarity
- Supportive of career growth with practical encouragement
- Focuses on actionable advice tailored to the user's situation
- Uses Filipino context where relevant to make examples more relatable
- Patient and understanding when users are unclear about career paths
- Shows active listening by referencing previous questions when appropriate
- Balances honesty about skill requirements with encouragement

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

## Response Guidelines
- Structure responses with markdown headings and bullet points for easy reading
- Use clear, simple language; avoid jargon unless necessary
- Provide relevant examples or analogies to clarify complex concepts
- Acknowledge the user's questions directly before answering
- When discussing challenges, pair them with practical next steps
- End responses with a simple invitation to ask follow-up questions
- For learning pathways, emphasize progress rather than gaps
- Include brief transitional phrases between sections to improve flow

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
            self.llm = Ollama(id="llama3.1:8b-instruct-q4_1", # type: ignore
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

        # Check for clarification needs first
        agent_results = context.get("agent_responses", {})
        
        # Check each agent result for clarification needs
        for agent_name, result in agent_results.items():
            if result.get("needs_clarification") or (not result.get("found", True) and result.get("reason") == "clarification_needed"):
                logger.info(f"Need for clarification detected from {agent_name}")
                clarification_message = result.get("message", "I need more information to help you. Could you please clarify?")
                
                return {
                    "response_text": clarification_message,
                    "processing_time": time.time() - start,
                    "format_used": "clarification_request",
                    "flow_action": "request_clarification"
                }

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
        
        # Extract knowledge base results with improved handling for structured data
        if "knowledge_base" in agent_responses and agent_responses["knowledge_base"].get("found", False):
            items = agent_responses["knowledge_base"].get("items", [])
            
            # Check for section separators
            current_section = None
            for item in items:
                # Handle separator items
                if item.get("is_separator", False):
                    current_section = item.get("text", "").replace("-", "").strip()
                    knowledge_parts.append(f"\n**{current_section}:**")
                    continue
                
                # Handle regular content items
                title = item.get('title', 'Information')
                content = item.get('text', '')
                item_type = item.get('type', '')
                relation_type = item.get('relation_type', '')
                
                # Format based on item type and relation
                if relation_type == "related_by_explicit_reference":
                    knowledge_parts.append(f"- Related {title}: {content}")
                elif relation_type == "skill_level":
                    knowledge_parts.append(f"- Skill Level Detail ({title}): {content}")
                elif relation_type == "career_path":
                    knowledge_parts.append(f"- Career Path Information ({title}): {content}")
                elif item_type == "whole_role" or item_type == "fs_complete_overview" or item_type == "esc_complete_overview":
                    # For complete entity overviews, use the full text
                    knowledge_parts.append(f"- {title}: {content}")
                else:
                    # Standard format for other items
                    knowledge_parts.append(f"- {title}: {content}")
                    
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

If the knowledge includes related items or connections between skills and roles, be sure to mention these relationships.

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
        kb_items = kb_response.get("items", [])
        sections = format_info.get("sections", ["Definition", "Description", "Examples"])
        sections_text = ", ".join(sections)
        
        # Check if there are section separators in the KB results
        has_separators = any(item.get("is_separator", False) for item in kb_items)
        
        prompt = f"""# Structured Educational Response Task

## User Query:
"{query}"

{history_text}

## Available Knowledge:
"""
        # If we have section separators, organize context by sections
        if has_separators:
            current_section = "General Information"
            for item in kb_items:
                if item.get("is_separator", False):
                    # Update current section based on separator text
                    current_section = item.get("text", "").replace("-", "").strip()
                    prompt += f"\n### {current_section}:\n"
                else:
                    title = item.get('title', 'Information')
                    content = item.get('text', '')
                    if content:
                        prompt += f"- {title}: {content}\n"
        else:
            # Standard approach for non-sectioned content
            for item in kb_items:
                if kb_response.get("found", False):
                    title = item.get('title', 'Information')
                    content = item.get('text', '')
                    if content:
                        prompt += f"- {title}: {content}\n"

        # Instructions for output structure
        prompt += f"""

## Instructions:
Note: Try to use all the data you got from the Knowledge Base, do not truncate or lose data.
IF the user is very vague and not specific like using words like "it", "this", "that", "there", etc., Do not generate sections, just directly ask them to clarify their question and be more specific.
Create a structured educational response with these sections: {sections_text} if available, else try and answer in your own structured education response.
Present the information in a clear, organized manner that helps the user understand the topic thoroughly.
Include specific details from the knowledge base when available.
Dont give educational resources
Use markdown formatting for headers and bullet points.

If the knowledge includes relationships between items (like skills required for roles or roles requiring certain skills), be sure to emphasize these connections in your response.

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
        
        # Extract knowledge items with improved handling for role information
        kb_response = agent_responses.get("knowledge_base", {})
        kb_items = kb_response.get("items", [])
        
        # Prepare sections for different information types
        role_info = []
        skill_info = []
        career_info = []
        
        # Extract KB data organized by section
        has_separators = any(item.get("is_separator", False) for item in kb_items)
        
        if has_separators:
            current_section = "General Information"
            for item in kb_items:
                if item.get("is_separator", False):
                    # Update section
                    current_section = item.get("text", "").replace("-", "").strip()
                else:
                    title = item.get('title', 'Information')
                    content = item.get('text', '')
                    metadata = item.get('metadata', {})
                    entity_type = metadata.get('entity_type', '')
                    
                    # Sort information into appropriate sections
                    if "Skills" in current_section:
                        skill_info.append(f"- {title}: {content}")
                    elif "Career Path" in current_section:
                        career_info.append(f"- {title}: {content}")
                    elif entity_type == 'job_role' or "whole_role" in metadata.get('type', ''):
                        role_info.append(f"- {title}: {content}")
                    else:
                        role_info.append(f"- {title}: {content}")
        else:
            # Standard approach for non-sectioned content
            for item in kb_items:
                if kb_response.get("found", False):
                    title = item.get('title', 'Information')
                    content = item.get('text', '')
                    metadata = item.get('metadata', {})
                    entity_type = metadata.get('entity_type', '')
                    
                    # Categorize based on entity type
                    if entity_type == 'functional_skill' or entity_type == 'enabling_skill':
                        skill_info.append(f"- {title}: {content}")
                    elif "career" in entity_type.lower() or "domain" in entity_type.lower():
                        career_info.append(f"- {title}: {content}")
                    else:
                        role_info.append(f"- {title}: {content}")
        
        # Format the collected information
        role_info_text = "\n".join(role_info) if role_info else f"No specific information found about {role}."
        skill_info_text = "\n".join(skill_info) if skill_info else "No specific skill requirements found."
        career_info_text = "\n".join(career_info) if career_info else "No specific career progression information found."

        prompt = f"""# Role Profile Generation Task

## User Query:
"{query}"

{history_text}

## Role Being Discussed:
{role}

## Role Information:
{role_info_text}

## Skill Requirements:
{skill_info_text}

## Career Progression:
{career_info_text}

## Instructions:
Note: Try to use all the data you got from the Knowledge Base, do not truncate or lose data.
If the user is very vague and not specific like using words like "it", "this", "that", "there", etc., ask them to clarify their question and be more specific.
Create a comprehensive profile for the role of {role} with the following sections:
1. Role Description - Brief overview of what the role entails
2. Responsibilities - Key tasks and responsibilities
3. Required Skills - Technical and soft skills needed, organized by functional and enabling skills
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
        
        # Extract knowledge items with improved handling for pathway information
        kb_response = agent_responses.get("knowledge_base", {})
        kb_items = kb_response.get("items", []) if kb_response.get("found", False) else []
        
        # Prepare information categories
        role_info = []
        skill_info = []
        learning_resources = []
        career_progression = []
        
        # Extract KB data organized by section
        has_separators = any(item.get("is_separator", False) for item in kb_items)
        
        if has_separators:
            current_section = "General Information"
            for item in kb_items:
                if item.get("is_separator", False):
                    # Update section
                    current_section = item.get("text", "").replace("-", "").strip()
                else:
                    title = item.get('title', 'Information')
                    content = item.get('text', '')
                    
                    # Categorize based on section
                    if "Skills" in current_section:
                        skill_info.append(f"- {title}: {content}")
                    elif "Career Path" in current_section:
                        career_progression.append(f"- {title}: {content}")
                    elif "Role" in current_section:
                        role_info.append(f"- {title}: {content}")
                    else:
                        # Default to role info for uncategorized items
                        role_info.append(f"- {title}: {content}")
        else:
            # Standard approach for non-sectioned content
            for item in kb_items:
                title = item.get('title', 'Information')
                content = item.get('text', '')
                metadata = item.get('metadata', {})
                entity_type = metadata.get('entity_type', '')
                
                # Categorize based on entity type
                if entity_type == 'functional_skill' or entity_type == 'enabling_skill':
                    skill_info.append(f"- {title}: {content}")
                elif "career" in entity_type.lower() or "domain" in entity_type.lower():
                    career_progression.append(f"- {title}: {content}")
                elif entity_type == 'job_role' or "role" in entity_type.lower():
                    role_info.append(f"- {title}: {content}")
                else:
                    # Default to role info for uncategorized items
                    role_info.append(f"- {title}: {content}")
        
        # Add course information if available
        if "course_search" in agent_responses:
            courses = agent_responses["course_search"].get("courses", [])
            if courses:
                for i, course in enumerate(courses): # type: ignore
                    learning_resources.append(f"- Course {i+1}: {course.get('title', 'Untitled')}")
                    learning_resources.append(f"  Provider: {course.get('provider', 'Unknown')}")
                    learning_resources.append(f"  Level: {course.get('level', 'Not specified')}")
        
        # Include learning pathway information if available
        if "learning_path" in agent_responses:
            pathway = agent_responses["learning_path"].get("pathway", {})
            if pathway:
                steps = pathway.get("steps", [])
                for step in steps:
                    learning_resources.append(f"- Pathway Step: {step}")
        
        # Format the collected information
        role_info_text = "\n".join(role_info) if role_info else f"No specific information found about {role}."
        skill_info_text = "\n".join(skill_info) if skill_info else "No specific skill requirements found."
        learning_resources_text = "\n".join(learning_resources) if learning_resources else "No specific learning resources found."
        career_progression_text = "\n".join(career_progression) if career_progression else "No specific career progression information found."

        prompt = f"""# Learning Pathway Generation Task

## User Query:
"{query}"

## Target Role:
{role}

## Role Information:
{role_info_text}

## Required Skills:
{skill_info_text}

## Learning Resources:
{learning_resources_text}

## Career Progression:
{career_progression_text}

## Instructions:
Note: Try to use all the data you got from the Knowledge Base, do not truncate or lose data.
If the user is very vague and not specific like using words like "it", "this", "that", "there", etc., ask them to clarify their question and be more specific.
Create a personalized learning pathway for someone aspiring to become a {role}.
Structure your response with these sections:
1. Current Level - Assumed starting point based on the query
2. Target Level - Description of the {role} position
3. Recommended Skills - Key skills to develop with proficiency targets
4. Learning Resources - Suggested courses, books, or practice projects
5. Next Steps - Clear actions the user can take to progress toward the role

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
        
        # Also include related skill information from knowledge base
        kb_response = agent_responses.get("knowledge_base", {})
        kb_items = kb_response.get("items", []) if kb_response.get("found", False) else []
        skill_info = []
        
        for item in kb_items:
            metadata = item.get('metadata', {})
            entity_type = metadata.get('entity_type', '')
            if entity_type == 'functional_skill' or entity_type == 'enabling_skill':
                title = item.get('title', 'Skill')
                content = item.get('text', '')
                skill_info.append(f"- {title}: {content}")
        
        related_skills_text = "\n".join(skill_info) if skill_info else "No specific skill information found."

        prompt = f"""# Course Recommendation Task

## User Query:
"{query}"

## Topic:
{topic}

## Related Skills Information:
{related_skills_text}

## Available Courses:
{course_info}

## Instructions:
Note: Try to use all the data you got from the Knowledge Base, do not truncate or lose data.
If the user is very vague and not specific like using words like "it", "this", "that", "there", etc., ask them to clarify their question and be more specific.
Create a helpful response recommending courses related to {topic}.
Structure your response with:
1. Brief introduction explaining the importance of {topic} and related skills
2. List of recommended courses with name, provider, and brief description
3. Suggested learning path (beginner to advanced)
4. Additional tips for learning this topic effectively

Use markdown formatting for the course list. If no specific courses are available,
provide general advice on how to find good courses on this topic based on the skill information.

Conclude with a simple encouragement like: "Need more course options or want to explore PSF-AAI roles that use these skills? Just ask!"

## Response:
"""
        return prompt

    def _build_role_skills_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any]) -> str:
        """Build a prompt for displaying role skills."""
        agent_responses = context.get("agent_responses", {})
        flow_context = context.get("flow", {})
        role = flow_context.get("role", "the role")
        
        # Extract knowledge items with improved handling for skill information
        kb_response = agent_responses.get("knowledge_base", {})
        kb_items = kb_response.get("items", []) if kb_response.get("found", False) else []
        
        # Prepare information categories
        role_description = []
        functional_skills = []
        enabling_skills = []
        
        # Extract KB data organized by section
        has_separators = any(item.get("is_separator", False) for item in kb_items)
        
        if has_separators:
            current_section = "General Information"
            for item in kb_items:
                if item.get("is_separator", False):
                    # Update section
                    current_section = item.get("text", "").replace("-", "").strip()
                else:
                    title = item.get('title', 'Information')
                    content = item.get('text', '')
                    metadata = item.get('metadata', {})
                    entity_type = metadata.get('entity_type', '')
                    
                    # Categorize based on section and entity type
                    if "Skills Required" in current_section or "Skills" in current_section:
                        if "functional" in title.lower() or "functional" in metadata.get('skill_category', '').lower():
                            functional_skills.append(f"- {title}: {content}")
                        elif "enabling" in title.lower() or "enabling" in metadata.get('skill_category', '').lower():
                            enabling_skills.append(f"- {title}: {content}")
                        else:
                            # Default to functional if unclear
                            functional_skills.append(f"- {title}: {content}")
                    elif entity_type == 'job_role' or "whole_role" in metadata.get('type', ''):
                        role_description.append(f"- {title}: {content}")
                    else:
                        role_description.append(f"- {title}: {content}")
        else:
            # Standard approach for non-sectioned content
            for item in kb_items:
                title = item.get('title', 'Information')
                content = item.get('text', '')
                metadata = item.get('metadata', {})
                entity_type = metadata.get('entity_type', '')
                skill_category = metadata.get('skill_category', '')
                
                if entity_type == 'functional_skill' or "functional" in skill_category.lower():
                    functional_skills.append(f"- {title}: {content}")
                elif entity_type == 'enabling_skill' or "enabling" in skill_category.lower():
                    enabling_skills.append(f"- {title}: {content}")
                elif entity_type == 'job_role' or "whole_role" in metadata.get('type', ''):
                    role_description.append(f"- {title}: {content}")
                else:
                    role_description.append(f"- {title}: {content}")
        
        # Also include learning path data if available
        skills_info = {}
        if "learning_path" in agent_responses:
            skills_info = agent_responses["learning_path"].get("skills", {})
            fs_from_path = skills_info.get("functional_skills", [])
            es_from_path = skills_info.get("enabling_skills", [])
            
            # Add any skills from learning path not already included
            for skill in fs_from_path:
                functional_skills.append(f"- {skill}")
            for skill in es_from_path:
                enabling_skills.append(f"- {skill}")
        
        # Format the collected information
        role_description_text = "\n".join(role_description) if role_description else f"No specific information found about {role}."
        functional_skills_text = "\n".join(functional_skills) if functional_skills else "No specific functional skills found."
        enabling_skills_text = "\n".join(enabling_skills) if enabling_skills else "No specific enabling skills found."

        prompt = f"""# Role Skills Profile

## User Query:
"{query}"

## Role:
{role}

## Role Description:
{role_description_text}

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
2. Functional Skills - Technical skills required with brief explanations of why they're important
3. Enabling Skills - Soft skills and competencies needed with context on their application
4. Skill Development - Brief advice on how to develop these skills

Use markdown formatting with headers and bullet points. If information is limited, provide industry-standard expectations for this role.

End with a simple encouragement like: "Want to find courses for these skills or learn about career progression from this PSF-AAI role? Let me know!"

## Response:
"""
        return prompt

    def _build_role_listing_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any]) -> str:
        """Build a prompt for displaying available roles."""
        agent_responses = context.get("agent_responses", {})
        
        # Extract roles from both knowledge base and learning path results
        roles = []
        if "learning_path" in agent_responses:
            roles = agent_responses["learning_path"].get("roles", [])
        
        # Also check knowledge base for role information
        kb_response = agent_responses.get("knowledge_base", {})
        kb_items = kb_response.get("items", []) if kb_response.get("found", False) else []
        
        # Extract career domain information for organizing roles
        career_domains = []
        domain_roles = {}
        
        for item in kb_items:
            metadata = item.get('metadata', {})
            entity_type = metadata.get('entity_type', '')
            item_type = metadata.get('type', '')
            
            if entity_type == 'career_domain' or item_type == 'career_map_domain':
                domain_name = metadata.get('domain', '') or metadata.get('title', '').replace('Domain: ', '')
                if domain_name:
                    career_domains.append(domain_name)
                    domain_roles[domain_name] = metadata.get('roles', [])
            elif entity_type == 'job_role' or item_type == 'whole_role':
                # Add to roles list if not already included
                role_title = metadata.get('title', '')
                if role_title and not any(r.get('title') == role_title for r in roles): # type: ignore
                    roles.append({
                        'title': role_title,
                        'description': item.get('text', 'No description available')
                    })
        
        # Format role information
        roles_text = ""
        if career_domains and domain_roles:
            # If we have domain information, organize roles by domain
            roles_text += "Roles organized by career domains:\n\n"
            for domain in career_domains:
                roles_text += f"Domain: {domain}\n"
                domain_role_list = domain_roles.get(domain, [])
                if domain_role_list:
                    for role_info in domain_role_list:
                        role_name = role_info.get('name', '')
                        role_grade = role_info.get('grade', '')
                        if role_name:
                            # Find corresponding role in roles list
                            role_desc = next((r.get('description', 'No description available') 
                                            for r in roles if r.get('title') == role_name), # type: ignore
                                            'No description available')
                            roles_text += f"- {role_name} (Grade: {role_grade}): {role_desc[:200]}...\n"
                else:
                    roles_text += "- No specific roles listed for this domain\n"
        elif roles:
            # If we only have a flat list of roles
            for i, role in enumerate(roles, 1): # type: ignore
                roles_text += f"\nRole {i}: {role.get('title', 'Unknown Role')}\n"
                roles_text += f"Description: {role.get('description', 'No description available')}\n"
        else:
            roles_text = "No specific roles found in the knowledge base."

        prompt = f"""# PSF-AAI Career Roles

## User Query:
"{query}"

## Available Roles and Career Paths:
{roles_text}

## Instructions:
Note: Try to use all the data you got from the Knowledge Base, do not truncate or lose data.
If the user is very vague and not specific like using words like "it", "this", "that", "there", etc., ask them to clarify their question and be more specific.
Create a response that presents the available career roles in the PSF-AAI framework.
Format your response as follows:
1. Introduction - Brief explanation of PSF-AAI career framework
2. Available Roles - List the roles with brief descriptions, organized by domain if that information is available
3. Career Progression - Explain how these roles relate to each other in terms of career advancement
4. Instructions - Guide the user to choose a role they're interested in learning more about

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
        kb_items = kb_response.get("items", []) if kb_response.get("found", False) else []
        
        # Organize career map information by type
        overview_info = []
        domain_info = []
        grade_info = []
        
        for item in kb_items:
            metadata = item.get('metadata', {})
            entity_type = metadata.get('entity_type', '')
            item_type = metadata.get('type', '')
            title = item.get('title', 'Career Map Information')
            content = item.get('text', '')
            
            if entity_type == 'career_map' or item_type == 'career_map_overview':
                overview_info.append(f"- {title}: {content}")
                # Extract domains and grades from metadata if available
                domains = metadata.get('domains', [])
                grades = metadata.get('grades', [])
                if domains:
                    overview_info.append(f"- Domains: {', '.join(domains)}")
                if grades:
                    overview_info.append(f"- Job Grades: {', '.join(grades)}")
            elif entity_type == 'career_domain' or item_type == 'career_map_domain':
                domain_info.append(f"- {title}: {content}")
                # Extract roles in this domain from metadata if available
                roles = metadata.get('roles', [])
                if roles:
                    role_list = []
                    for role_info in roles:
                        role_name = role_info.get('name', '')
                        role_grade = role_info.get('grade', '')
                        if role_name:
                            role_list.append(f"{role_name} (Grade: {role_grade})")
                    if role_list:
                        domain_info.append(f"  Roles: {', '.join(role_list)}")
            elif "grade" in title.lower():
                grade_info.append(f"- {title}: {content}")
        
        # Format the collected information
        overview_text = "\n".join(overview_info) if overview_info else "No specific career map overview found."
        domain_text = "\n".join(domain_info) if domain_info else "No specific domain information found."
        grade_text = "\n".join(grade_info) if grade_info else "No specific grade level information found."

        prompt = f"""# Career Map Visualization Task

## User Query:
"{query}"

{history_text}

## Career Map Overview:
{overview_text}

## Career Domains:
{domain_text}

## Job Grades/Levels:
{grade_text}

## Instructions:
Note: Try to use all the data you got from the Knowledge Base, do not truncate or lose data.
If the user is very vague and not specific like using words like "it", "this", "that", "there", etc., ask them to clarify their question and be more specific.
Create a structured response that visualizes the PSF-AAI career map framework with these sections:
1. Overview - Explain what the career map is and how it's organized
2. Domains/Vertical Tracks - Describe the different domains or vertical specialization areas
3. Job Grades/Horizontal Levels - Explain the progression levels across the framework
4. Example Paths - Show a few example progression paths within or across domains

Use markdown formatting to create a clear visual structure. If possible, use bullet points or other formatting to show hierarchical relationships between roles.

If the knowledge includes specific connections between roles and domains, emphasize these relationships in your explanation.

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