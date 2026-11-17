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
    """Synthesizes responses from PSF Knowledge Agent and General Conversation Agent with enhanced connectivity awareness."""

    def __init__(self, llm=None) -> None:
        """Initialize the response synthesizer with an LLM."""
        super().__init__(llm=llm)
        
        self.system_prompt = """
# Guideon: PSF-AAI Career Guide

## Identity and Purpose
You are Guideon, an AI assistant specializing in the Philippine Skills Framework for Analytics & AI (PSF-AAI).
Your purpose is to help professionals navigate career paths in analytics and AI within the Philippine context.

## Core Knowledge Areas
- PSF-AAI framework with roles, skills, and career tracks
- Technical and functional skills with role mappings
- Skill proficiency levels (1-6) with progression pathways
- Career transition pathways with progression mapping
- Role relationships and skill dependencies

## Conversation Capabilities
- **PSF-AAI Knowledge Queries**: Provide structured information with helpful connections and cross-references
- **General Conversation**: Handle casual chat while naturally mentioning PSF-AAI context when relevant

## User-Friendly Features
- **Connected Information**: Show how roles, skills, and career paths relate to each other
- **Progressive Learning**: Present information with clear next steps and follow-up options
- **Practical Guidance**: Focus on actionable advice for career development
- **Local Context**: Use Filipino industry context where relevant

## Personality Traits
- Professional but approachable, friendly and conversational like Baymax
- Concise and structured in responses
- Supportive and encouraging of career growth
- Focuses on practical, actionable advice
- Helpful without being overwhelming

## Response Guidelines
- Structure responses with markdown headings and bullet points
- Use clear, simple language
- Provide practical examples and connections
- Show relationships between roles, skills, and career paths naturally
- Include helpful suggestions for follow-up questions
- NEVER mention technical terms like "connectivity scores", "metadata", or internal system details

## Restrictions
- Do not provide information outside the PSF-AAI framework unless specifically related
- Do not make up PSF-AAI information; rely only on provided context
- Avoid discussing political topics or non-PSF-AAI government policies
- Do not recommend specific companies or job openings
- NEVER expose internal system details, scores, or technical metadata to users
- If asked about topics entirely outside your domain, politely redirect to PSF-AAI topics

## Response Format
- Start with a direct answer
- Include relevant PSF-AAI details with helpful connections
- Show how information relates to career development
- Provide practical next steps
- End with personalized follow-up suggestions
"""
        try:
            # Try to initialize own LLM first
            try:
                self.llm = Ollama(id="llama3.1:8b-instruct-q4_1", # type: ignore
                                provider="Ollama",
                                host="http://localhost:11434")
                logger.info("Response synthesizer initialized with its own LLM")
            except Exception as llm_error:
                # If own LLM fails, fall back to provided LLM
                if llm:
                    self.llm = llm
                    logger.info("Failed to initialize own LLM, using shared LLM instance")
                else:
                    # No LLM available at all
                    logger.error(f"Failed to initialize own LLM and no shared LLM provided: {llm_error}")
                    self.llm = None
            
            # Only create agent if we have an LLM
            if self.llm:
                self.agent = Agent(
                    name="Synthesizer",
                    model=self.llm, # type: ignore
                    system_message=self.system_prompt,
                )
            else:
                self.agent = None
        except Exception as e:
            logger.error(f"Error in Response Synthesizer initialization: {e}")
            self.agent = None

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        logger.info(f"Synthesizing response for query: {query[:60]}...")

        # Check if we have a valid LLM
        if not self.agent:
            logger.warning("No LLM available for response synthesis, using fallback")
            return self._create_fallback_response(query, context)

        # Get processing context
        agent_responses = context.get('agent_responses', {})
        flow_context = context.get("flow", {})
        response_format = flow_context.get("response_format", {"format": "conversational"})
        flow_action = flow_context.get("flow_action", "general_response")
        intent = context.get("intent")

        # Check if chat history should be used based on intent classifier decision
        should_use_history = context.get("used_context", False)  # From intent classifier
        chat_history = context.get("chat_history", []) if should_use_history else []
        
        logger.info(f"Response synthesis: using_chat_history={should_use_history}, history_length={len(chat_history)}")

        # Handle knowledge base response
        kb_response = agent_responses.get("knowledge_agent", {})
        if intent == QueryIntent.KNOWLEDGE_BASE_QUERY:
            if not kb_response or not kb_response.get("found"):
                return {
                    "response_text": "I couldn't find specific information for your query in the PSF-AAI knowledge base. Could you clarify or ask about a different role, skill, or topic? I can help with career progression paths, skill requirements, or role connections.",
                    "format_used": response_format.get("format"),
                    "flow_action": flow_action
                }

        # Handle general conversation
        if intent == QueryIntent.GENERAL_CONVERSATION:
            general_conv = agent_responses.get("general_conversation", {})
            if general_conv and general_conv.get("response"):
                return {
                    "response_text": general_conv["response"],
                    "format_used": response_format.get("format"),
                    "flow_action": flow_action
                }
            return {
                "response_text": "I'm here for any questions or just to chat! If you want to know about PSF-AAI roles, skills, career paths, or explore how they connect, just ask!",
                "format_used": response_format.get("format"),
                "flow_action": flow_action
            }

        # Build prompts based on format
        if response_format.get("format") == "structured":
            prompt = self._build_structured_prompt(query, context, response_format, chat_history, should_use_history)
        elif response_format.get("format") == "role_profile":
            prompt = self._build_role_profile_prompt(query, context, response_format, chat_history, should_use_history)
        elif response_format.get("format") == "career_map":
            prompt = self._build_career_map_prompt(query, context, response_format, chat_history, should_use_history)
        elif response_format.get("format") == "connectivity_view":
            prompt = self._build_connectivity_exploration_prompt(query, context, response_format, chat_history, should_use_history)
        else:
            prompt = self._build_standard_prompt(query, context, chat_history, should_use_history)

        try:
            # Generate response
            run_response = await self.agent.arun(prompt)
            text = getattr(run_response, "content", str(run_response))

            # Return clean response without exposing internal details
            return {
                "response_text": text,
                "processing_time": time.time() - start,
                "format_used": response_format.get("format"),
                "flow_action": flow_action,
                "used_chat_history": should_use_history
            }
        except Exception as e:
            logger.error(f"Error in response synthesis: {e}")
            return self._create_fallback_response(query, context)

    def _build_standard_prompt(self, query: str, context: Dict[str, Any], 
                              chat_history: List[Dict[str, Any]] = None, 
                              use_history: bool = False) -> str:
        """Build a standard prompt with intelligent chat history usage."""
        
        # Only format history if we should use it
        history_text = ""
        if use_history and chat_history:
            history_text = self._format_chat_history(chat_history)
            logger.debug(f"Including {len(chat_history)} chat history messages in prompt")
        else:
            logger.debug("Processing query without chat history context")
        
        agent_responses = context.get("agent_responses", {})
        kb_response = agent_responses.get("knowledge_agent", {})
        
        # **CLEANED: Extract knowledge without exposing technical details**
        knowledge_parts = []
        user_friendly_connections = []
        
        if kb_response.get("found", False):
            items = kb_response.get("items", [])
            
            for item in items:
                title = item.get('title', 'Information')
                text = item.get('text', '')
                
                # **HIDDEN: Don't show connectivity scores to users**
                knowledge_parts.append(f"- **{title}**: {text}")
                
                # **USER-FRIENDLY: Present connections naturally**
                if item.get('connected_roles'):
                    roles = item['connected_roles'][:3]  # Show top 3 to avoid overwhelm
                    if len(roles) > 0:
                        user_friendly_connections.append(f"This relates to roles like: {', '.join(roles)}")
                
                if item.get('career_progression'):
                    next_roles = item['career_progression'][:2]  # Show top 2
                    if len(next_roles) > 0:
                        user_friendly_connections.append(f"Career progression opportunities: {', '.join(next_roles)}")
                
                if item.get('skill_requirements'):
                    skill_count = len(item['skill_requirements'])
                    if skill_count > 0:
                        user_friendly_connections.append(f"Connected to {skill_count} key skills")

        knowledge_text = "\n".join(knowledge_parts) if knowledge_parts else "No specific information found."
        connections_text = "\n- ".join(user_friendly_connections) if user_friendly_connections else ""

        # Context instructions based on whether history is being used
        context_instructions = ""
        if use_history and history_text:
            context_instructions = """
## Context Awareness:
This query appears to reference previous conversation. Use the conversation history to understand contextual references like "that", "it", "this", etc.
"""
        else:
            context_instructions = """
## Context Awareness:
This query appears to be standalone and self-contained. Process it independently without needing additional context.
"""

        prompt = f"""# Response Generation Task

## User Query:
"{query}"

{history_text}

{context_instructions}

## Knowledge Base Results:
{knowledge_text}

## Helpful Connections Found:
{connections_text}

## Instructions:
You have access to PSF-AAI knowledge. Use this information to:

1. **Provide comprehensive answers** using all available knowledge base data
2. **Show helpful connections** naturally (how roles relate to each other, career paths, skill relationships)
3. **Focus on practical guidance** for career development
4. **Handle vague queries** by asking for clarification while suggesting specific PSF-AAI topics
5. **Present information clearly** without overwhelming the user

**Response Style:**
- Keep responses friendly, conversational, and CONCISE while being comprehensive
- Use connection information to provide more valuable insights
- Structure information clearly with markdown formatting when helpful
- Focus on actionable, practical guidance for career development
- NEVER mention technical details like "connectivity scores" or "metadata"

**Connection Enhancement:**
- When discussing roles, mention related positions and progression paths naturally
- When explaining skills, reference which roles use them
- When showing career paths, include skill development suggestions
- Present connections as helpful relationships, not technical data

**IMPORTANT: Keep all technical details internal. Users should only see:**
- Role names and descriptions
- Natural career connections
- Practical skill relationships
- Helpful progression suggestions

End your response with encouraging follow-up suggestions:
"Feel free to explore more PSF-AAI connections! Ask about career progression paths, skill requirements for roles, or how different competencies work together!"

## Response:
"""
        return prompt

    def _build_structured_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any],
                                chat_history: List[Dict[str, Any]] = None, 
                                use_history: bool = False) -> str:
        """Build a structured prompt with intelligent chat history usage."""
        
        # Only include history if needed
        history_text = ""
        if use_history and chat_history:
            history_text = self._format_chat_history(chat_history)

        agent_responses = context.get("agent_responses", {})
        kb_response = agent_responses.get("knowledge_agent", {})
        sections = format_info.get("sections", ["Definition", "Description", "Applications", "Connections"])
        
        # **CLEANED: Process knowledge without exposing technical details**
        knowledge_parts = []
        helpful_connections = []
        
        if kb_response.get("found", False):
            items = kb_response.get("items", [])
            
            for item in items:
                title = item.get('title', 'Information')
                text = item.get('text', '')
                item_type = item.get('metadata', {}).get('type', '')
                
                # **HIDDEN: Don't show connectivity scores**
                knowledge_parts.append(f"- **{title}** ({item_type}): {text}")
                
                # **USER-FRIENDLY: Present connections naturally**
                if item.get('connected_roles'):
                    helpful_connections.append(f"Related roles: {', '.join(item['connected_roles'][:3])}")
                if item.get('career_progression'):
                    helpful_connections.append(f"Career paths: {', '.join(item['career_progression'][:2])}")
                if item.get('skill_requirements'):
                    helpful_connections.append(f"Key skills involved: {len(item['skill_requirements'])} competencies")

        knowledge_text = "\n".join(knowledge_parts) if knowledge_parts else "No specific information found."
        connections_text = "\n- ".join(helpful_connections) if helpful_connections else "No specific connections identified."
        sections_text = ", ".join(sections)

        # Context instructions based on history usage
        context_instructions = ""
        if use_history and history_text:
            context_instructions = """
## Context Awareness:
This query may reference previous conversation. Use the conversation history to understand what the user is referring to.
"""
        else:
            context_instructions = """
## Context Awareness:
This query appears to be standalone. Process it as a self-contained request.
"""

        prompt = f"""# Structured Educational Response

## User Query:
"{query}"

{history_text}

{context_instructions}

## Knowledge Base Results:
{knowledge_text}

## Helpful Connections:
- {connections_text}

## Instructions:
Create a structured educational response that uses helpful connections. Use these sections if applicable: {sections_text}

**Structure Requirements:**
1. **Comprehensive Coverage**: Use all available knowledge base data without truncation
2. **Natural Connections**: Weave relationship information naturally into each section
3. **Practical Focus**: Show how connections provide actionable career guidance
4. **Clear Organization**: Use markdown headers and bullet points

**Vague Query Handling**: If the user is vague (using "it", "this", "that"), ask for clarification while suggesting specific PSF-AAI exploration areas.

**IMPORTANT**: Present information clearly without technical jargon. Focus on practical career guidance.

**Conclusion**: Include helpful follow-up suggestions like:
"Want to explore the career connections further? Ask about progression paths from specific roles, or discover which skills work well together in the PSF-AAI framework!"

## Structured Response:
"""
        return prompt

    def _build_role_profile_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any],
                                  chat_history: List[Dict[str, Any]] = None, 
                                  use_history: bool = False) -> str:
        """Build a role profile prompt with intelligent chat history usage."""
        
        # Only include history if needed
        history_text = ""
        if use_history and chat_history:
            history_text = self._format_chat_history(chat_history)

        agent_responses = context.get("agent_responses", {})
        kb_response = agent_responses.get("knowledge_agent", {})
        flow_context = context.get("flow", {})
        role = flow_context.get("role", "the role")
        
        # **CLEANED: Process role analysis without technical details**
        role_info = {}
        career_connections = {}
        
        if kb_response.get("found", False):
            items = kb_response.get("items", [])
            
            for item in items:
                item_type = item.get('metadata', {}).get('type', '')
                
                if 'role' in item_type:
                    role_info = {
                        'title': item.get('title', role),
                        'description': item.get('text', ''),
                        'grade': item.get('metadata', {}).get('role_grade', 'N/A'),
                        'domain': item.get('metadata', {}).get('role_domain', 'N/A')
                    }
                    
                    # **USER-FRIENDLY: Present career connections naturally**
                    if item.get('career_progression'):
                        career_connections['next_roles'] = item['career_progression'][:3]
                    if item.get('connected_roles'):
                        career_connections['related_roles'] = item['connected_roles'][:3]
                    if item.get('skill_requirements'):
                        career_connections['key_skills'] = len(item['skill_requirements'])

        knowledge_parts = []
        if kb_response.get("found", False):
            for item in kb_response.get("items", []):
                knowledge_parts.append(f"- {item.get('title', 'Information')}: {item.get('text', '')}")
        knowledge_text = "\n".join(knowledge_parts) if knowledge_parts else f"No specific information found about {role}."

        # **USER-FRIENDLY: Present career connections naturally**
        connections_summary = ""
        if career_connections:
            connections_summary = "## Career Connections:\n"
            if career_connections.get('next_roles'):
                connections_summary += f"- **Career Growth**: {', '.join(career_connections['next_roles'])}\n"
            if career_connections.get('related_roles'):
                connections_summary += f"- **Related Positions**: {', '.join(career_connections['related_roles'])}\n"
            if career_connections.get('key_skills'):
                connections_summary += f"- **Key Skills**: {career_connections['key_skills']} important competencies\n"

        # Context instructions based on history usage
        context_instructions = ""
        if use_history and history_text:
            context_instructions = """
## Context Awareness:
This query may reference previous conversation about roles or career paths.
"""
        else:
            context_instructions = """
## Context Awareness:
This query appears to be about a specific role. Process it as a standalone role inquiry.
"""

        prompt = f"""# Role Profile Generation

## User Query:
"{query}"

{history_text}

{context_instructions}

## Role Being Analyzed:
{role_info.get('title', role)} (Grade: {role_info.get('grade', 'N/A')}, Domain: {role_info.get('domain', 'N/A')})

## Knowledge Base Results:
{knowledge_text}

{connections_summary}

## Instructions:
Create a comprehensive role profile with these sections:

1. **Role Overview** - Description with grade and domain context
2. **Key Responsibilities** - Tasks and duties with connections to other roles
3. **Required Competencies** - Skills with practical applications
4. **Career Connections** - Progression paths, related roles, and advancement options
5. **Skill Development Path** - Learning progression with role alignment

**Requirements:**
- Highlight career progression opportunities with specific next roles
- Show relationships to other positions in the framework naturally
- Provide actionable career development guidance
- Focus on practical, helpful information

**Vague Query Handling**: If user is vague, ask for clarification while suggesting specific role exploration options.

**IMPORTANT**: Present all information in user-friendly terms without technical jargon.

**Conclusion**: Include helpful encouragement like:
"Interested in the career connections for this role? Ask about specific skill requirements, progression pathways, or explore related positions in the PSF-AAI framework!"

## Role Profile:
"""
        return prompt

    def _build_career_map_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any],
                                chat_history: List[Dict[str, Any]] = None, 
                                use_history: bool = False) -> str:
        """Build a career map prompt with intelligent chat history usage."""
        
        # Only include history if needed
        history_text = ""
        if use_history and chat_history:
            history_text = self._format_chat_history(chat_history)

        agent_responses = context.get("agent_responses", {})
        kb_response = agent_responses.get("knowledge_agent", {})
        
        # **CLEANED: Process career map without technical details**
        career_map_items = []
        framework_info = {}
        progression_paths = []
        
        if kb_response.get("found", False):
            items = kb_response.get("items", [])
            
            for item in items:
                item_type = item.get("metadata", {}).get("type", "")
                title = item.get('title', '')
                text = item.get('text', '')
                
                if "career_map" in item_type:
                    career_map_items.append(f"- **{title}**: {text}")
                    
                    # **USER-FRIENDLY: Extract framework information**
                    if "domain" in item_type:
                        domain_name = item.get('metadata', {}).get('domain_name', '')
                        if domain_name:
                            framework_info[f"Domain: {domain_name}"] = {
                                'roles_count': item.get('metadata', {}).get('roles_count', 0),
                                'description': text[:200] + "..." if len(text) > 200 else text
                            }
                    
                    elif "grade" in item_type:
                        grade_name = item.get('metadata', {}).get('grade_name', '')
                        if grade_name:
                            framework_info[f"Level: {grade_name}"] = {
                                'positions_count': item.get('metadata', {}).get('positions_count', 0),
                                'description': text[:200] + "..." if len(text) > 200 else text
                            }
                
                elif "progression" in item_type:
                    progression_paths.append({
                        'from_role': item.get('metadata', {}).get('source_role', ''),
                        'to_roles': item.get('metadata', {}).get('target_next_roles', []),
                        'description': text[:150] + "..." if len(text) > 150 else text
                    })

        career_map_text = "\n".join(career_map_items) if career_map_items else "No specific career map information found."
        
        # **USER-FRIENDLY: Present framework summary**
        framework_summary = ""
        if framework_info or progression_paths:
            framework_summary = "## Framework Overview:\n"
            if framework_info:
                framework_summary += f"- **Specializations**: {len([k for k in framework_info.keys() if 'Domain:' in k])} career tracks\n"
                framework_summary += f"- **Career Levels**: {len([k for k in framework_info.keys() if 'Level:' in k])} progression stages\n"
            if progression_paths:
                framework_summary += f"- **Career Paths**: {len(progression_paths)} specific advancement routes\n"

        # Context instructions based on history usage
        context_instructions = ""
        if use_history and history_text:
            context_instructions = """
## Context Awareness:
This query may reference previous conversation about career paths or framework navigation.
"""
        else:
            context_instructions = """
## Context Awareness:
This query appears to be about career mapping. Process it as a standalone career exploration request.
"""

        prompt = f"""# Career Map Visualization

## User Query:
"{query}"

{history_text}

{context_instructions}

## Career Map Information:
{career_map_text}

{framework_summary}

## Instructions:
Create a comprehensive career map visualization with these sections:

1. **Framework Overview** - Explain the PSF-AAI career structure
2. **Domain Specializations** - Different career tracks and their focuses
3. **Career Level Progressions** - How to advance through different stages
4. **Progression Pathways** - Specific routes for career advancement
5. **Navigation Guide** - How to use the framework for career planning

**Requirements:**
- Use domain and grade information to show framework structure clearly
- Highlight specific progression pathways with practical guidance
- Provide actionable navigation guidance for career planning
- Focus on helping users understand their career options

**Visual Structure**: Use markdown formatting, bullet points, and clear hierarchies to show:
- Career Tracks → Roles → Advancement Levels
- Cross-track transition opportunities
- Clear career progression paths

**Vague Query Handling**: If user is vague, ask for clarification while suggesting specific career exploration areas.

**IMPORTANT**: Present all information in clear, practical terms without technical details.

**Conclusion**: Include helpful encouragement like:
"Ready to explore specific career paths on this map? Ask about progression from particular roles, skill requirements for advancement, or opportunities to transition between different tracks!"

## Career Map Response:
"""
        return prompt

    def _build_connectivity_exploration_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any],
                                             chat_history: List[Dict[str, Any]] = None, 
                                             use_history: bool = False) -> str:
        """Build a prompt specifically for connectivity exploration responses."""
        
        # Only include history if needed
        history_text = ""
        if use_history and chat_history:
            history_text = self._format_chat_history(chat_history)

        agent_responses = context.get("agent_responses", {})
        kb_response = agent_responses.get("knowledge_agent", {})
        
        # **CLEANED: Process connections without technical details**
        connection_insights = {
            'role_connections': [],
            'skill_mappings': [],
            'career_progressions': [],
            'practical_connections': []
        }
        
        if kb_response.get("found", False):
            items = kb_response.get("items", [])
            
            for item in items:
                title = item.get('title', '')
                
                # **USER-FRIENDLY: Extract practical connections**
                if item.get('connected_roles'):
                    unique_roles = list(set(item['connected_roles'][:5]))  # Top 5
                    connection_insights['role_connections'].extend(unique_roles)
                    connection_insights['practical_connections'].append(f"{title} connects to roles like: {', '.join(unique_roles[:3])}")
                
                if item.get('skill_requirements'):
                    skill_count = len(item['skill_requirements'])
                    connection_insights['practical_connections'].append(f"{title} involves {skill_count} key skills")
                
                if item.get('career_progression'):
                    next_roles = item['career_progression'][:3]
                    connection_insights['practical_connections'].append(f"From {title}, you can advance to: {', '.join(next_roles)}")

        # Build user-friendly insights
        helpful_insights = []
        if connection_insights['role_connections']:
            unique_roles = list(set(connection_insights['role_connections']))
            helpful_insights.append(f"**Connected Roles**: Found connections to {len(unique_roles)} different positions")
        
        if connection_insights['practical_connections']:
            helpful_insights.extend(connection_insights['practical_connections'][:5])  # Top 5 to avoid overwhelm

        knowledge_parts = []
        if kb_response.get("found", False):
            for item in kb_response.get("items", []):
                knowledge_parts.append(f"- {item.get('title', 'Information')}: {item.get('text', '')}")
        knowledge_text = "\n".join(knowledge_parts) if knowledge_parts else "No specific connectivity information found."

        insights_summary = "\n- ".join(helpful_insights) if helpful_insights else "No connection patterns identified."

        # Context instructions based on history usage
        context_instructions = ""
        if use_history and history_text:
            context_instructions = """
## Context Awareness:
This query may reference previous conversation about connections or relationships within the PSF-AAI framework.
"""
        else:
            context_instructions = """
## Context Awareness:
This query appears to be about exploring connections. Process it as a standalone connectivity exploration request.
"""

        prompt = f"""# Connection Exploration Response

## User Query:
"{query}"

{history_text}

{context_instructions}

## Knowledge Base Results:
{knowledge_text}

## Helpful Connections Found:
- {insights_summary}

## Instructions:
Create an interactive connection exploration response with these sections:

1. **Connection Overview** - What connections were discovered
2. **Relationship Mapping** - How different elements connect (roles ↔ skills ↔ careers)
3. **Pathway Discovery** - Specific progression and development routes
4. **Practical Insights** - Valuable connections for career planning
5. **Exploration Opportunities** - What the user can discover next

**Features to Highlight:**
- Show practical relationships between roles, skills, and career paths
- Map clear progression routes
- Identify valuable connection points for career planning
- Suggest exploration paths based on discovered connections

**Interactive Elements**:
- Provide specific follow-up questions the user can ask
- Suggest practical scenarios for career exploration
- Offer deep-dive options for interesting connections

**IMPORTANT**: Present all connection information in user-friendly, practical terms. Focus on how connections help with career planning.

**Conclusion**: End with helpful encouragement like:
"The PSF-AAI framework is rich with helpful connections! Want to dive deeper? Ask about specific role transitions, explore skill development paths, or discover career opportunities through these professional networks!"

## Connection Response:
"""
        return prompt

    def _format_chat_history(self, chat_history: List[Dict[str, Any]]) -> str:
        """Format chat history for prompt inclusion."""
        if not chat_history:
            return ""
            
        history_text = "\n## Conversation History:\n"
        for msg in chat_history[-3:]:  # Last 3 messages
            role = "User" if msg.get("is_user") else "Assistant"
            text = msg.get("text", "").replace("\n", " ")
            if msg.get("summarized"):
                history_text += f"{role} (summarized): {text}\n"
            else:
                history_text += f"{role}: {text}\n"
        
        return history_text

    def _create_fallback_response(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a fallback response."""
        intent = context.get("intent")
        response_text = "I'm having a little trouble connecting right now, but I'm still here to help with PSF-AAI!"

        if intent == QueryIntent.KNOWLEDGE_BASE_QUERY:
            response_text = "I can usually provide comprehensive information about the PSF-AAI framework with career connections and skill mappings. What specific role, skill, or career path interests you?"
        elif intent == QueryIntent.GENERAL_CONVERSATION:
            response_text = "I'm here to help explore the PSF-AAI framework and its career connections, but I'm also happy to chat! How can I assist you today?"
        else:
            response_text = "I'm here to help explore the PSF-AAI framework and its career connections. How can I assist your professional development journey today?"

        return {
            "response_text": response_text + " Please try asking again in a moment.",
            "format_used": "fallback",
            "flow_action": "fallback_response"
        }