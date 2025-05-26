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
# Guideon: Enhanced PSF-AAI Career Guide with Connectivity Intelligence

## Identity and Purpose
You are Guideon, an AI assistant specializing in the Philippine Skills Framework for Analytics & AI (PSF-AAI) with advanced connectivity awareness.
Your purpose is to help professionals navigate career paths in analytics and AI within the Philippine context using interconnected knowledge.

## Core Knowledge Areas with Connectivity Features
- PSF-AAI framework with cross-referenced roles, skills, and career tracks
- Technical and functional skills with role mappings and connectivity scores
- Skill proficiency levels (1-6) with progression pathways and role connections
- Career transition pathways with detailed progression mapping
- Enhanced connectivity features including role relationships and skill dependencies

## Enhanced Conversation Flow Capabilities
- **PSF-AAI Knowledge Queries**: Provide structured information with connectivity context and cross-references
- **General Conversation**: Handle casual chat while naturally weaving in PSF-AAI context when relevant

## Enhanced Connectivity Features
- **Cross-Reference Support**: Link related roles, skills, and career progression paths
- **Connectivity Scoring**: Highlight highly connected content for better recommendations
- **Intent-Aware Responses**: Adapt responses based on detected query intent (career progression, skill requirements, etc.)
- **Relationship Mapping**: Show how skills connect to roles and how roles connect to career paths
- **Progressive Disclosure**: Present information with connectivity context and follow-up options

## Personality Traits
- Professional but approachable, you speak in a friendly, conversational tone, bubbly like Baymax
- Concise and structured in responses with enhanced connectivity context
- Supportive and encouraging of career growth with data-driven insights
- Focuses on practical, actionable advice with clear progression paths
- Uses Filipino context where relevant with local industry connections

## Enhanced Response Guidelines
- Structure responses with markdown headings, bullet points, and connectivity indicators
- Use clear, simple language while highlighting relationships and connections
- Provide examples with connectivity context (e.g., "This skill is used in 5 roles including...")
- Include connectivity statistics when relevant (e.g., "High connectivity score: 4.2/5")
- Show progression paths and related opportunities
- Use connectivity-aware suggestions for follow-up questions

## Restrictions
- Do not provide information outside the PSF-AAI framework unless specifically related
- Do not make up PSF-AAI information; rely only on provided context and connectivity data
- Avoid discussing political topics or non-PSF-AAI government policies
- Do not recommend specific companies or job openings
- If asked about topics entirely outside your domain, politely redirect to PSF-AAI topics

## Enhanced Response Format with Connectivity
- Start with a direct answer leveraging connectivity context
- Include relevant PSF-AAI details with cross-references and relationships
- Highlight connectivity features when available (role connections, progression paths, skill mappings)
- Provide connectivity-aware suggestions for deeper exploration
- End with personalized follow-up options based on connectivity patterns
"""
        try:
            # Try to initialize own LLM first
            try:
                self.llm = Ollama(id="llama3.1:8b-instruct-q4_1", # type: ignore
                                provider="Ollama",
                                host="http://localhost:11434")
                logger.info("Enhanced Response synthesizer initialized with its own LLM")
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
                    name="EnhancedSynthesizer",
                    model=self.llm, # type: ignore
                    system_message=self.system_prompt,
                )
            else:
                self.agent = None
        except Exception as e:
            logger.error(f"Error in Enhanced Response Synthesizer initialization: {e}")
            self.agent = None

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        logger.info(f"Enhanced synthesizing response for query: {query[:60]}...")

        # Check if we have a valid LLM
        if not self.agent:
            logger.warning("No LLM available for enhanced response synthesis, using fallback")
            return self._enhanced_fallback_response(query, context)

        # Enhanced processing with connectivity awareness
        agent_responses = context.get('agent_responses', {})
        flow_context = context.get("flow", {})
        response_format = flow_context.get("response_format", {"format": "conversational"})
        flow_action = flow_context.get("flow_action", "general_response")
        intent = context.get("intent")

        # **NEW: Check if chat history should be used based on intent classifier decision**
        should_use_history = context.get("used_context", False)  # From intent classifier
        chat_history = context.get("chat_history", []) if should_use_history else []
        
        logger.info(f"Response synthesis: using_chat_history={should_use_history}, history_length={len(chat_history)}")

        # Enhanced knowledge base response handling
        kb_response = agent_responses.get("knowledge_agent", {})
        if intent == QueryIntent.KNOWLEDGE_BASE_QUERY:
            if not kb_response or not kb_response.get("found"):
                return {
                    "response_text": "I couldn't find specific information for your query in the PSF-AAI knowledge base. Could you clarify or ask about a different role, skill, or topic? I can help with career progression paths, skill requirements, or role connections.",
                    "format_used": response_format.get("format"),
                    "flow_action": flow_action,
                    "connectivity_suggestions": [
                        "Ask about specific PSF-AAI roles",
                        "Explore career progression paths",
                        "Learn about skill requirements"
                    ]
                }

        # Enhanced general conversation handling
        if intent == QueryIntent.GENERAL_CONVERSATION:
            general_conv = agent_responses.get("general_conversation", {})
            if general_conv and general_conv.get("response"):
                return {
                    "response_text": general_conv["response"],
                    "format_used": response_format.get("format"),
                    "flow_action": flow_action
                }
            return {
                "response_text": "I'm here for any questions or just to chat! If you want to know about PSF-AAI roles, skills, career paths, or explore the connections between them, just ask!",
                "format_used": response_format.get("format"),
                "flow_action": flow_action,
                "psf_hints": True
            }

        # Enhanced prompt building based on format and connectivity
        # **MODIFIED: Pass chat_history and should_use_history to prompt builders**
        if response_format.get("format") == "structured":
            prompt = self._build_enhanced_structured_prompt(query, context, response_format, chat_history, should_use_history)
        elif response_format.get("format") == "role_profile":
            prompt = self._build_enhanced_role_profile_prompt(query, context, response_format, chat_history, should_use_history)
        elif response_format.get("format") == "career_map":
            prompt = self._build_enhanced_career_map_prompt(query, context, response_format, chat_history, should_use_history)
        elif response_format.get("format") == "connectivity_view":
            prompt = self._build_connectivity_exploration_prompt(query, context, response_format, chat_history, should_use_history)
        else:
            prompt = self._build_enhanced_standard_prompt(query, context, chat_history, should_use_history)

        try:
            # Use enhanced agent with connectivity awareness
            run_response = await self.agent.arun(prompt)
            text = getattr(run_response, "content", str(run_response))

            # Enhanced response with connectivity metadata
            return {
                "response_text": text,
                "processing_time": time.time() - start,
                "format_used": response_format.get("format"),
                "flow_action": flow_action,
                "connectivity_features_used": self._extract_connectivity_features_used(kb_response),
                "enhanced_processing": True,
                "used_chat_history": should_use_history  # **NEW: Track if history was used**
            }
        except Exception as e:
            logger.error(f"Error in enhanced response synthesis: {e}")
            return self._enhanced_fallback_response(query, context)

    def _build_enhanced_standard_prompt(self, query: str, context: Dict[str, Any], 
                                      chat_history: List[Dict[str, Any]] = None, 
                                      use_history: bool = False) -> str:
        """Build an enhanced standard prompt with intelligent chat history usage."""
        
        # **MODIFIED: Only format history if we should use it**
        history_text = ""
        if use_history and chat_history:
            history_text = self._format_chat_history(chat_history)
            logger.debug(f"Including {len(chat_history)} chat history messages in prompt")
        else:
            logger.debug("Processing query without chat history context")
        
        agent_responses = context.get("agent_responses", {})
        kb_response = agent_responses.get("knowledge_agent", {})
        
        # Enhanced knowledge extraction with connectivity features
        knowledge_parts = []
        connectivity_info = {}
        
        if kb_response.get("found", False):
            items = kb_response.get("items", [])
            connectivity_stats = kb_response.get("metadata", {}).get("connectivity_stats", {})
            
            for item in items:
                # Enhanced item processing with connectivity
                title = item.get('title', 'Information')
                text = item.get('text', '')
                connectivity_score = item.get('connectivity_score', 0)
                
                # Add connectivity context
                connectivity_context = []
                if item.get('connected_roles'):
                    connectivity_context.append(f"Connected to {len(item['connected_roles'])} roles")
                if item.get('career_progression'):
                    connectivity_context.append(f"Shows progression to {len(item['career_progression'])} next roles")
                if item.get('skill_requirements'):
                    connectivity_context.append(f"Maps to {len(item['skill_requirements'])} skill requirements")
                
                knowledge_part = f"- {title}"
                if connectivity_score > 0:
                    knowledge_part += f" (Connectivity Score: {connectivity_score})"
                if connectivity_context:
                    knowledge_part += f" [{', '.join(connectivity_context)}]"
                knowledge_part += f": {text}"
                
                knowledge_parts.append(knowledge_part)
            
            # Extract connectivity statistics
            if connectivity_stats:
                connectivity_info = {
                    "total_items": len(items),
                    "items_with_connections": connectivity_stats.get("cross_referenced_items", 0),
                    "high_connectivity_items": connectivity_stats.get("high_connectivity_items", 0),
                    "career_progression_items": connectivity_stats.get("items_with_career_progression", 0)
                }

        knowledge_text = "\n".join(knowledge_parts) if knowledge_parts else "No specific information found."
        
        # Enhanced connectivity summary
        connectivity_summary = ""
        if connectivity_info:
            connectivity_summary = f"""
## Connectivity Analysis:
- Found {connectivity_info['total_items']} relevant items
- {connectivity_info['items_with_connections']} items with cross-references
- {connectivity_info['high_connectivity_items']} highly connected items
- {connectivity_info['career_progression_items']} items with career progression info
"""

        # **MODIFIED: Context instructions based on whether history is being used**
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

        prompt = f"""# Enhanced Response Generation Task with Connectivity Intelligence

## User Query:
"{query}"

{history_text}

{context_instructions}

## Enhanced Knowledge Base Results:
{knowledge_text}

{connectivity_summary}

## Enhanced Instructions:
You have access to PSF-AAI knowledge with advanced connectivity features. Use this enhanced information to:

1. **Provide comprehensive answers** using all available knowledge base data - do not truncate or lose information
2. **Highlight connections** when available (role relationships, career progressions, skill mappings)
3. **Include connectivity context** when relevant (e.g., "This skill is used in X roles", "This role can lead to Y positions")
4. **Handle vague queries** by asking for clarification while suggesting specific PSF-AAI topics
5. **Leverage cross-references** to provide richer, more complete answers

**Response Style:**
- Keep responses friendly, conversational, and CONCISE while being comprehensive
- Use connectivity information to provide more valuable insights
- Structure information clearly with markdown formatting when helpful
- Focus on actionable, practical guidance

**Connectivity Enhancement:**
- When discussing roles, mention related positions and progression paths
- When explaining skills, reference which roles use them
- When showing career paths, include skill development requirements
- Highlight high-connectivity items that offer rich cross-references

End your response with an enhanced encouragement that leverages connectivity features:
"Feel free to explore more PSF-AAI connections! Ask about career progression paths, skill requirements for roles, or how different competencies link together!"

## Enhanced Response:
"""
        return prompt

    def _build_enhanced_structured_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any],
                                        chat_history: List[Dict[str, Any]] = None, 
                                        use_history: bool = False) -> str:
        """Build an enhanced structured prompt with intelligent chat history usage."""
        
        # **MODIFIED: Only include history if needed**
        history_text = ""
        if use_history and chat_history:
            history_text = self._format_chat_history(chat_history)

        agent_responses = context.get("agent_responses", {})
        kb_response = agent_responses.get("knowledge_agent", {})
        sections = format_info.get("sections", ["Definition", "Description", "Applications", "Connections"])
        
        # Enhanced knowledge processing with connectivity
        knowledge_parts = []
        connectivity_features = []
        
        if kb_response.get("found", False):
            items = kb_response.get("items", [])
            
            for item in items:
                title = item.get('title', 'Information')
                text = item.get('text', '')
                item_type = item.get('metadata', {}).get('type', '')
                connectivity_score = item.get('connectivity_score', 0)
                
                # Enhanced connectivity analysis
                if item.get('connected_roles'):
                    connectivity_features.append(f"Roles using this: {', '.join(item['connected_roles'][:3])}")
                if item.get('career_progression'):
                    connectivity_features.append(f"Career progression: {', '.join(item['career_progression'][:2])}")
                if item.get('skill_requirements'):
                    connectivity_features.append(f"Skill mappings: {len(item['skill_requirements'])} requirements")
                
                knowledge_part = f"- **{title}** ({item_type})"
                if connectivity_score > 2:
                    knowledge_part += f" [High Connectivity: {connectivity_score}]"
                knowledge_part += f": {text}"
                
                knowledge_parts.append(knowledge_part)

        knowledge_text = "\n".join(knowledge_parts) if knowledge_parts else "No specific information found."
        connectivity_text = "\n- ".join(connectivity_features) if connectivity_features else "No specific connections identified."
        sections_text = ", ".join(sections)

        # **MODIFIED: Context instructions based on history usage**
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

        prompt = f"""# Enhanced Structured Educational Response with Connectivity

## User Query:
"{query}"

{history_text}

{context_instructions}

## Enhanced Knowledge Base Results:
{knowledge_text}

## Connectivity Features Identified:
- {connectivity_text}

## Enhanced Instructions:
Create a structured educational response that leverages connectivity intelligence. Use these sections if applicable: {sections_text}

**Enhanced Structure Requirements:**
1. **Comprehensive Coverage**: Use all available knowledge base data without truncation
2. **Connectivity Integration**: Weave connection information naturally into each section
3. **Cross-Reference Support**: Link related concepts, roles, and skills throughout
4. **Practical Application**: Show how connections provide actionable career guidance

**Vague Query Handling**: If the user is vague (using "it", "this", "that"), ask for clarification while suggesting specific PSF-AAI exploration areas with connectivity context.

**Formatting**: Use markdown headers, bullet points, and highlight connectivity relationships clearly.

**Enhanced Conclusion**: Include connectivity-aware follow-up suggestions like:
"Want to explore the career connections further? Ask about progression paths from specific roles, or discover which skills are most connected across the PSF-AAI framework!"

## Enhanced Structured Response:
"""
        return prompt

    def _build_enhanced_role_profile_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any],
                                          chat_history: List[Dict[str, Any]] = None, 
                                          use_history: bool = False) -> str:
        """Build an enhanced role profile prompt with intelligent chat history usage."""
        
        # **MODIFIED: Only include history if needed**
        history_text = ""
        if use_history and chat_history:
            history_text = self._format_chat_history(chat_history)

        agent_responses = context.get("agent_responses", {})
        kb_response = agent_responses.get("knowledge_agent", {})
        flow_context = context.get("flow", {})
        role = flow_context.get("role", "the role")
        
        # Enhanced role analysis with connectivity
        role_info = {}
        connectivity_analysis = {}
        
        if kb_response.get("found", False):
            items = kb_response.get("items", [])
            
            for item in items:
                item_type = item.get('metadata', {}).get('type', '')
                
                if 'role' in item_type:
                    role_info = {
                        'title': item.get('title', role),
                        'description': item.get('text', ''),
                        'grade': item.get('metadata', {}).get('role_grade', 'N/A'),
                        'domain': item.get('metadata', {}).get('role_domain', 'N/A'),
                        'connectivity_score': item.get('connectivity_score', 0)
                    }
                    
                    # Enhanced connectivity extraction
                    if item.get('career_progression'):
                        connectivity_analysis['next_roles'] = item['career_progression']
                    if item.get('connected_roles'):
                        connectivity_analysis['related_roles'] = item['connected_roles']
                    if item.get('skill_requirements'):
                        connectivity_analysis['skill_mappings'] = item['skill_requirements']

        knowledge_parts = []
        if kb_response.get("found", False):
            for item in kb_response.get("items", []):
                knowledge_parts.append(f"- {item.get('title', 'Information')}: {item.get('text', '')}")
        knowledge_text = "\n".join(knowledge_parts) if knowledge_parts else f"No specific information found about {role}."

        # Enhanced connectivity summary
        connectivity_summary = ""
        if connectivity_analysis:
            connectivity_summary = "## Enhanced Connectivity Analysis:\n"
            if connectivity_analysis.get('next_roles'):
                connectivity_summary += f"- **Career Progression**: {', '.join(connectivity_analysis['next_roles'][:3])}\n"
            if connectivity_analysis.get('related_roles'):
                connectivity_summary += f"- **Related Positions**: {', '.join(connectivity_analysis['related_roles'][:3])}\n"
            if connectivity_analysis.get('skill_mappings'):
                connectivity_summary += f"- **Skill Requirements**: {len(connectivity_analysis['skill_mappings'])} mapped competencies\n"

        # **MODIFIED: Context instructions based on history usage**
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

        prompt = f"""# Enhanced Role Profile Generation with Career Connectivity

## User Query:
"{query}"

{history_text}

{context_instructions}

## Role Being Analyzed:
{role_info.get('title', role)} (Grade: {role_info.get('grade', 'N/A')}, Domain: {role_info.get('domain', 'N/A')})

## Enhanced Knowledge Base Results:
{knowledge_text}

{connectivity_summary}

## Enhanced Instructions:
Create a comprehensive role profile that leverages connectivity intelligence with these enhanced sections:

1. **Role Overview** - Description with grade and domain context
2. **Key Responsibilities** - Tasks and duties with connectivity to other roles
3. **Required Competencies** - Skills with role mapping and connectivity scores
4. **Career Connectivity** - Progression paths, related roles, and advancement options
5. **Skill Development Path** - Learning progression with role alignment

**Connectivity Enhancement Requirements:**
- Highlight career progression opportunities with specific next roles
- Show relationships to other positions in the framework
- Include skill connectivity scores when available
- Provide actionable career development guidance

**Vague Query Handling**: If user is vague, ask for clarification while suggesting specific role exploration options.

**Enhanced Conclusion**: Include connectivity-aware encouragement like:
"Interested in the career connections for this role? Ask about specific skill requirements, progression pathways, or explore related positions in the PSF-AAI framework!"

## Enhanced Role Profile:
"""
        return prompt

    def _build_enhanced_career_map_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any],
                                        chat_history: List[Dict[str, Any]] = None, 
                                        use_history: bool = False) -> str:
        """Build an enhanced career map prompt with intelligent chat history usage."""
        
        # **MODIFIED: Only include history if needed**
        history_text = ""
        if use_history and chat_history:
            history_text = self._format_chat_history(chat_history)

        agent_responses = context.get("agent_responses", {})
        kb_response = agent_responses.get("knowledge_agent", {})
        
        # Enhanced career map analysis
        career_map_items = []
        domains_info = {}
        grades_info = {}
        progression_paths = []
        
        if kb_response.get("found", False):
            items = kb_response.get("items", [])
            connectivity_stats = kb_response.get("metadata", {}).get("connectivity_stats", {})
            
            for item in items:
                item_type = item.get("metadata", {}).get("type", "")
                title = item.get('title', '')
                text = item.get('text', '')
                
                if "career_map" in item_type:
                    career_map_items.append(f"- **{title}**: {text}")
                    
                    # Extract domain and grade information
                    if "domain" in item_type:
                        domain_name = item.get('metadata', {}).get('domain_name', '')
                        if domain_name:
                            domains_info[domain_name] = {
                                'roles_count': item.get('metadata', {}).get('roles_count', 0),
                                'description': text[:200] + "..." if len(text) > 200 else text
                            }
                    
                    elif "grade" in item_type:
                        grade_name = item.get('metadata', {}).get('grade_name', '')
                        if grade_name:
                            grades_info[grade_name] = {
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
        
        # Enhanced connectivity summary
        connectivity_summary = ""
        if domains_info or grades_info or progression_paths:
            connectivity_summary = "## Enhanced Career Framework Analysis:\n"
            if domains_info:
                connectivity_summary += f"- **Domains Identified**: {len(domains_info)} specialization tracks\n"
            if grades_info:
                connectivity_summary += f"- **Job Grades Found**: {len(grades_info)} progression levels\n"
            if progression_paths:
                connectivity_summary += f"- **Progression Paths**: {len(progression_paths)} specific advancement routes\n"

        # **MODIFIED: Context instructions based on history usage**
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

        prompt = f"""# Enhanced Career Map Visualization with Connectivity Intelligence

## User Query:
"{query}"

{history_text}

{context_instructions}

## Enhanced Career Map Information:
{career_map_text}

{connectivity_summary}

## Enhanced Instructions:
Create a comprehensive career map visualization that leverages connectivity intelligence with these enhanced sections:

1. **Framework Overview** - Explain the PSF-AAI career structure with connectivity context
2. **Domain Specializations** - Vertical tracks with role counts and interconnections
3. **Job Grade Progressions** - Horizontal advancement levels with position mappings
4. **Connectivity Pathways** - Show specific progression routes and cross-domain transitions
5. **Navigation Guide** - How to use the framework for career planning

**Connectivity Enhancement Requirements:**
- Use domain and grade information to show framework structure
- Highlight specific progression pathways with role connections
- Include connectivity statistics to show framework richness
- Provide practical navigation guidance for career planning

**Visual Structure**: Use markdown formatting, bullet points, and clear hierarchies to show:
- Domain → Roles → Grade progressions
- Cross-domain transition opportunities
- High-connectivity career paths

**Vague Query Handling**: If user is vague, ask for clarification while suggesting specific career exploration areas.

**Enhanced Conclusion**: Include connectivity-aware encouragement like:
"Ready to explore specific career paths on this map? Ask about progression from particular roles, skill requirements for advancement, or cross-domain transition opportunities!"

## Enhanced Career Map Response:
"""
        return prompt

    def _build_connectivity_exploration_prompt(self, query: str, context: Dict[str, Any], format_info: Dict[str, Any],
                                             chat_history: List[Dict[str, Any]] = None, 
                                             use_history: bool = False) -> str:
        """Build a prompt specifically for connectivity exploration responses."""
        
        # **MODIFIED: Only include history if needed**
        history_text = ""
        if use_history and chat_history:
            history_text = self._format_chat_history(chat_history)

        agent_responses = context.get("agent_responses", {})
        kb_response = agent_responses.get("knowledge_agent", {})
        
        # Advanced connectivity analysis
        connection_types = {
            'role_connections': [],
            'skill_mappings': [],
            'career_progressions': [],
            'cross_references': []
        }
        
        high_connectivity_items = []
        
        if kb_response.get("found", False):
            items = kb_response.get("items", [])
            
            for item in items:
                connectivity_score = item.get('connectivity_score', 0)
                title = item.get('title', '')
                
                if connectivity_score > 3:
                    high_connectivity_items.append(f"{title} (Score: {connectivity_score})")
                
                if item.get('connected_roles'):
                    connection_types['role_connections'].extend(item['connected_roles'])
                if item.get('skill_requirements'):
                    connection_types['skill_mappings'].extend([req.get('role', '') for req in item['skill_requirements']])
                if item.get('career_progression'):
                    connection_types['career_progressions'].extend(item['career_progression'])

        # Build connectivity insights
        connectivity_insights = []
        if connection_types['role_connections']:
            unique_roles = list(set(connection_types['role_connections']))
            connectivity_insights.append(f"**Role Network**: Connected to {len(unique_roles)} distinct roles")
        
        if connection_types['skill_mappings']:
            unique_mappings = list(set(connection_types['skill_mappings']))
            connectivity_insights.append(f"**Skill Mappings**: {len(unique_mappings)} role-skill connections")
        
        if connection_types['career_progressions']:
            unique_progressions = list(set(connection_types['career_progressions']))
            connectivity_insights.append(f"**Career Paths**: {len(unique_progressions)} progression opportunities")

        knowledge_parts = []
        if kb_response.get("found", False):
            for item in kb_response.get("items", []):
                knowledge_parts.append(f"- {item.get('title', 'Information')}: {item.get('text', '')}")
        knowledge_text = "\n".join(knowledge_parts) if knowledge_parts else "No specific connectivity information found."

        connectivity_summary = "\n- ".join(connectivity_insights) if connectivity_insights else "No connectivity patterns identified."
        high_connectivity_text = "\n- ".join(high_connectivity_items) if high_connectivity_items else "No highly connected items found."

        # **MODIFIED: Context instructions based on history usage**
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

        prompt = f"""# Advanced Connectivity Exploration Response

## User Query:
"{query}"

{history_text}

{context_instructions}

## Knowledge Base Results:
{knowledge_text}

## Connectivity Intelligence Analysis:
- {connectivity_summary}

## High-Connectivity Items:
- {high_connectivity_text}

## Advanced Instructions:
Create an interactive connectivity exploration response with these sections:

1. **Connection Overview** - What connections were discovered
2. **Relationship Mapping** - How different elements connect (roles ↔ skills ↔ careers)
3. **Pathway Discovery** - Specific progression and development routes
4. **Cross-Reference Insights** - Unexpected or valuable connections found
5. **Exploration Opportunities** - What the user can discover next

**Connectivity Features to Highlight:**
- Show relationship strength (connectivity scores)
- Map bidirectional connections (skill → roles, roles → progression)
- Identify high-value connection points for career planning
- Suggest exploration paths based on connection patterns

**Interactive Elements**:
- Provide specific follow-up questions the user can ask
- Suggest "what if" scenarios for career exploration
- Offer deep-dive options for interesting connections

**Enhanced Conclusion**: End with connectivity-focused encouragement like:
"The PSF-AAI framework is rich with connections! Want to dive deeper? Ask about specific role transitions, explore skill dependencies, or discover unexpected career pathways through the connectivity network!"

## Advanced Connectivity Response:
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

    def _extract_connectivity_features_used(self, kb_response: Dict[str, Any]) -> Dict[str, Any]:
        """Extract which connectivity features were used in the response."""
        if not kb_response or not kb_response.get("found"):
            return {}
        
        features = {
            "connectivity_aware": True,
            "cross_references": False,
            "career_progressions": False,
            "skill_mappings": False,
            "high_connectivity_items": 0
        }
        
        items = kb_response.get("items", [])
        connectivity_stats = kb_response.get("metadata", {}).get("connectivity_stats", {})
        
        for item in items:
            if item.get('connected_roles') or item.get('career_progression') or item.get('skill_requirements'):
                features["cross_references"] = True
            if item.get('career_progression'):
                features["career_progressions"] = True
            if item.get('skill_requirements'):
                features["skill_mappings"] = True
            if item.get('connectivity_score', 0) > 3:
                features["high_connectivity_items"] += 1
        
        return features

    def _enhanced_fallback_response(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate an enhanced fallback response with connectivity awareness."""
        intent = context.get("intent")
        response_text = "I'm having a little trouble connecting right now, but I'm still here to help with PSF-AAI!"

        if intent == QueryIntent.KNOWLEDGE_BASE_QUERY:
            response_text = "I can usually provide comprehensive information about the PSF-AAI framework with career connections and skill mappings. What specific role, skill, or career path interests you?"
        elif intent == QueryIntent.GENERAL_CONVERSATION:
            response_text = "I'm here to help explore the PSF-AAI framework with all its career connections and skill relationships, but I'm also happy to chat! How can I assist you today?"
        else:
            response_text = "I'm here to help explore the PSF-AAI framework with all its career connections and skill relationships. How can I assist your professional development journey today?"

        return {
            "response_text": response_text + " Please try asking again in a moment.",
            "format_used": "enhanced_fallback",
            "flow_action": "enhanced_fallback_response",
            "connectivity_features_available": True,
            "psf_hints": [
                "Ask about career progression paths",
                "Explore skill-role connections", 
                "Discover domain specializations",
                "Learn about grade advancement requirements"
            ]
        }