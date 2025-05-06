import logging, re
from agno.agent import Agent
from agno.models.ollama import Ollama

from ..utils.query_vectors import search_similar_content
from ..utils.intent_classifier import classify_intent, QueryIntent
from ..models import Chat, Message

logger = logging.getLogger(__name__)

def knowledge_base_tool(query: str, intent=None, extracted_level=None, limit=8, **kwargs):
    """
    Searches the career knowledge base based on query and intent
    
    Args:
        query: The search query
        intent: Classified QueryIntent to optimize search
        extracted_level: Specific skill level the user is asking about (if detected)
        limit: Maximum number of results to return
    """
    try:
        logger.debug(f"Searching knowledge base for: {query} with intent: {intent}, level: {extracted_level}")
        
        # Adjust search based on intent
        search_query = query
        search_limit = limit
        
        # Intent-specific search adjustments
        if intent == "skill_level_info" and extracted_level is not None:
            search_query = f"{query} level {extracted_level}"
            search_limit = limit * 1.5
            
        elif intent == "skill_progression":
            search_query = f"{query} progression levels path"
            search_limit = limit * 1.5
            
        elif intent == "skill_info":
            search_query = f"{query} functional skill description overview"
            
        elif intent == "role_info":
            search_query = f"{query} role description responsibilities tasks"
            
        elif intent == "career_path":
            search_query = f"{query} career map domain job grades progression"
        
        # Perform the search with adjusted parameters
        results = search_similar_content(search_query, limit=int(search_limit))
        
        # Handle errors and empty results
        if isinstance(results, dict) and "error" in results:
            logger.warning(f"Search error: {results['error']}")
            return {
                "found": False,
                "reason": "search_error",
                "message": f"Error searching knowledge base: {results['error']}",
                "psf_aai_info": get_psf_aai_info()
            }
            
        if not results:
            logger.info("No results found in knowledge base")
            return {
                "found": False,
                "reason": "no_results",
                "message": "No specific information found in our knowledge base for this query.",
                "psf_aai_info": get_psf_aai_info()
            }
        
        # Filter and structure results based on intent
        formatted_results = []
        result_types = set()
        
        # Intent-specific prioritization
        if intent == "skill_level_info" and extracted_level is not None:
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
                "psf_aai_info": get_psf_aai_info()
            }
        
        # Result metadata to help agent interpret results
        result_metadata = {
            "query_intent": intent,
            "extracted_level": extracted_level,
            "result_count": len(formatted_results),
            "result_types": list(result_types)
        }
        
        # Return successful results
        return {
            "found": True,
            "items": formatted_results[:int(limit)],  # Add int() conversion here
            "metadata": result_metadata,
            "count": len(formatted_results[:int(limit)])  # And here
        }
            
    except Exception as e:
        logger.error(f"Error searching knowledge base: {e}")
        return {
            "found": False,
            "reason": "exception",
            "message": f"Error accessing knowledge base: {str(e)}",
            "psf_aai_info": get_psf_aai_info()
        }

def get_psf_aai_info():
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
    
def classify_intent_tool(user_input: str, conversation_history=None, **kwargs):
    """
    Analyzes the query to determine what the user is asking about
    
    Args:
        user_input: The user's query
        conversation_history: Previous messages for context
        
    Returns:
        The classified intent and confidence
    """
    try:
        # Convert conversation history format if needed
        chat_history = []
        if conversation_history and isinstance(conversation_history, list):
            for msg in conversation_history:
                role = msg.get('role', '')
                content = msg.get('content', '')
                if role and content:
                    temp_msg = type('Message', (), {'role': role, 'content': content})
                    chat_history.append(temp_msg)
        
        # Extract level information from the query using regex
        level_pattern = r'level\s*(\d+)'
        level_matches = re.findall(level_pattern, user_input.lower())
        extracted_level = int(level_matches[0]) if level_matches else None
        
        # Basic intent classification keywords
        query_lower = user_input.lower()
        
        # Default to general query
        intent = "general_query"
        confidence = 0.5
        
        # Simple keyword-based classification
        if any(kw in query_lower for kw in ["level", "proficiency", "entry level", "senior level", "junior level"]):
            intent = "skill_level_info"
            confidence = 0.8
        elif any(kw in query_lower for kw in ["skill", "ability", "competency"]):
            if any(kw in query_lower for kw in ["progress", "advance", "improve", "grow", "develop"]):
                intent = "skill_progression"
                confidence = 0.8
            else:
                intent = "skill_info"
                confidence = 0.7
        elif any(kw in query_lower for kw in ["role", "job", "position", "career"]):
            intent = "role_info"
            confidence = 0.7
        elif any(kw in query_lower for kw in ["path", "progression", "advance", "next step", "move up"]):
            intent = "career_path"
            confidence = 0.7
        
        # Prepare response with extracted level if available
        result = {
            "intent": intent,
            "confidence": confidence,
            "description": f"Query about {intent.replace('_', ' ')}"
        }
        
        if extracted_level is not None:
            result["extracted_level"] = extracted_level
        
        return result
    except Exception as e:
        logger.error(f"Intent classification error: {e}")
        return {
            "intent": "general_query",
            "confidence": 0.5,
            "error": str(e)
        }

def get_intent_description(intent):
    """Returns a human-readable description of the intent"""
    descriptions = {
        QueryIntent.CAREER_PATH: "Questions about career progression and advancement paths",
        QueryIntent.ROLE_INFO: "Questions about specific job roles and responsibilities",
        QueryIntent.SKILL_INFO: "Questions about specific skills and competencies",
        QueryIntent.SKILL_LEVEL_INFO: "Questions about specific skill proficiency levels",
        QueryIntent.SKILL_PROGRESSION: "Questions about advancing through skill levels",
        QueryIntent.SKILL_COMPARISON: "Comparing different skills or competencies",
        QueryIntent.EDUCATION_ADVICE: "Questions about learning resources and education",
        QueryIntent.GENERAL_QUERY: "General questions not related to specific career topics"
    }
    return descriptions.get(intent, "General query")

# Career guidance agent definition
career_agent = Agent(
    name="GuideonCareerAgent",
    model=Ollama(
        id="llama3.1:8b-instruct-q4_1",
        provider="Ollama",
        host="http://localhost:11434"
    ),
    tools=[classify_intent_tool, knowledge_base_tool],
    instructions=[
        "You are Guideon, an AI assistant specializing in the Philippine Skills Framework for Analytics & AI (PSF-AAI).",
        
        "About PSF-AAI:",
        "- PSF-AAI is a structured competency map for analytics and AI careers in the Philippines",
        "- Developed by the Analytics & AI Association of the Philippines (AAP) and DICT",
        "- Defines functional skills, enabling skills, career roles, and proficiency levels (1-6)",
        "- Serves as a reference for education, workforce planning, and career development",
        
        "For each user query:",
        "1. First run classify_intent_tool to identify what the user wants to know and any specific level mentioned.",
        "2. Then run knowledge_base_tool to search our PSF-AAI database, which contains:",
        "   - Functional skills with descriptions, knowledge requirements, and practical applications",
        "   - Different proficiency levels (1-6) with specific expectations at each level",
        "   - Job roles and career progression paths",
        
        "When answering skill level questions:",
        "- If a specific level is asked about (like 'Level 3'): Focus on that level's requirements and applications",
        "- If asking about progression: Explain how to advance through the levels",
        "- If asking about a skill generally: Provide an overview and mention the different levels available",
        
        "When knowledge_base_tool returns different result types:",
        "- fs_overview: Use this for general information about the skill",
        "- fs_level: Use this for level-specific information",
        "- fs_skill_bullet: Use these for specific abilities required at a level",
        "- fs_knowledge: Use these for knowledge requirements at a level",
        "- fs_progression: Use this to explain advancement through levels",
        "- fs_range: Use this to explain where/how the skill is applied",
        "- role_description: Use this for role overview information",
        "- role_tasks: Use this for specific responsibilities of a role",
        "- career_map_domain: Use this for information about career tracks",
        "- career_map_overview: Use this for the general career framework",
        
        "When knowledge_base_tool finds nothing (found=False):",
        "- Always emphasize that you specialize in the PSF-AAI framework",
        "- Explain that the Philippine Skills Framework for Analytics & Artificial Intelligence (PSF-AAI) is a structured competency map developed by the AAP and DICT",
        "- Mention that PSF-AAI defines career roles, functional skills with proficiency levels 1-6, and enabling skills for the analytics and AI sector in the Philippines",
        "- Suggest they ask about specific skills, roles, or levels from the PSF-AAI",
        "- Use the psf_aai_info provided in the tool response to provide accurate framework details",
        
        "Always be helpful, conversational, and focus on actionable guidance.",
        "Organize your responses with clear sections when providing detailed information.",
        "Cite specific data from the PSF-AAI knowledge base when available."
    ],
    markdown=True,
    show_tool_calls=True,
    debug_mode=True,
)