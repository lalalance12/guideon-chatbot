from .base_agent import BaseAgent
import logging
import asyncio
from agno.agent import Agent
from agno.models.ollama import Ollama

logger = logging.getLogger(__name__)

class GeneralConversationAgent(BaseAgent):
    """
    Handles general conversation, chit-chat, jokes, greetings, and non-PSF-AAI queries.
    Enhanced with flow context awareness and PSF-AAI integration hints.
    """
    def __init__(self, llm=None):
        super().__init__(llm=llm)
        
        # Enhanced system message with clear identity and PSF-AAI connection
        self.system_message = """You are Guideon, an AI chatbot assistant specializing in the Philippine Skills Framework for Analytics & AI (PSF-AAI). You handle both casual conversation and career guidance.

## Your Identity:
- Name: Guideon
- Purpose: PSF-AAI career guidance chatbot for analytics and AI professionals in the Philippines
- Primary Function: Help users navigate career paths, roles, skills, and learning opportunities in the PSF-AAI framework
- Secondary Function: Engage in friendly conversation while always being ready to provide PSF-AAI career guidance

## Your Specialized Knowledge:
- Philippine Skills Framework for Analytics & AI (PSF-AAI)
- Career roles from Associate level to Chief-level positions
- Technical and functional skills mapping
- Career progression pathways in analytics and AI
- Learning recommendations and course suggestions
- Skill requirements for different PSF-AAI roles

## Conversation Capabilities:
- Casual chat, greetings, jokes, and general conversation
- Seamlessly transition between general chat and PSF-AAI career guidance
- Provide contextual hints about career opportunities when relevant
- Answer questions about yourself and your capabilities

## When Users Ask About You:
Always mention that you are:
1. Guideon - a specialized AI chatbot
2. Expert in the Philippine Skills Framework for Analytics & AI (PSF-AAI)
3. Here to help with career guidance in analytics and AI fields
4. Able to provide information about roles, skills, career paths, and learning opportunities
5. Also happy to have casual conversations

## Response Style:
- Friendly, warm, and conversational like Baymax
- Professional when discussing PSF-AAI topics
- Natural transitions between casual chat and career guidance
- Always helpful and encouraging
- Include your PSF-AAI specialization when introducing yourself

## Flow Integration:
- When users show interest in careers, naturally introduce PSF-AAI framework
- Offer specific career guidance when contextually appropriate
- Maintain casual tone while being informative about your capabilities"""
        
        try:
            # Use provided LLM if available, otherwise initialize own
            if not self.llm:
                self.llm = Ollama(id="llama3.1:8b-instruct-q4_1", provider="Ollama", host="http://localhost:11434")
                logger.info("General conversation agent initialized with its own LLM")
            else:
                logger.info("General conversation agent using shared LLM instance")
                
            self.agent = Agent(
                name="GeneralConversation",
                model=self.llm,
                system_message=self.system_message,
            )
        except Exception as e:
            logger.error(f"Failed to initialize general conversation LLM: {e}")
            self.agent = None

    async def process(self, query: str, context):
        logger.info(f"[GeneralConversationAgent] Processing: {query[:60]}")
        
        # **NEW: Extract flow context for enhanced responses**
        flow_context, flow_action, response_format, flow_state = self.get_flow_context(context)
        connectivity_context = self.get_connectivity_context(context)
        focus_role, focus_topic = self.get_focus_elements(context)
        
        logger.debug(f"[GeneralConversationAgent] Flow context - Action: {flow_action}, Focus: role={focus_role}, topic={focus_topic}")
        
        if not self.agent:
            return self._create_fallback_response(query, context)
        
        try:
            # **ENHANCED: Build context-aware prompt**
            enhanced_prompt = self._build_enhanced_prompt(query, context, flow_action, connectivity_context)
            
            if hasattr(self.agent, "arun"):
                response = await self.agent.arun(enhanced_prompt)
            else:
                response = await asyncio.to_thread(self.agent.run, enhanced_prompt)
            
            content = getattr(response, "content", str(response))
            
            # **NEW: Create enhanced response with flow metadata**
            result = {
                "response": content,
                "agent_name": "general_conversation"
            }
            
            # Add flow metadata for tracking
            result = self.add_flow_metadata(result, context)
            
            return result
            
        except Exception as e:
            logger.error(f"GeneralConversationAgent error: {e}")
            return self._create_fallback_response(query, context, error=str(e))

    def _build_enhanced_prompt(self, query: str, context: dict, flow_action: str, connectivity_context: dict) -> str:
        """**NEW: Build enhanced prompt with flow and connectivity context**"""
        
        # Check if we have PSF-AAI context to incorporate
        psf_hints = []
        if connectivity_context:
            psf_hints.append("The user has been exploring PSF-AAI career information recently")
        
        # Extract chat history if available and flow indicates it should be used
        chat_history = ""
        if context.get("used_context", False) and context.get("chat_history"):
            recent_messages = context["chat_history"][-2:]  # Last 2 messages for context
            history_parts = []
            for msg in recent_messages:
                role = "User" if msg.get("is_user") else "Assistant"
                text = msg.get("text", "")[:150]  # Truncate long messages
                history_parts.append(f"{role}: {text}")
            if history_parts:
                chat_history = f"\n## Recent Conversation:\n{chr(10).join(history_parts)}\n"
        
        # **ENHANCED: Detect if user is asking about Guideon/chatbot identity**
        identity_keywords = ["what do you do", "who are you", "what are you", "your purpose", "your role", 
                           "what can you help", "what's your function", "tell me about yourself", 
                           "your capabilities", "what are your skills", "your specialty"]
        
        is_identity_question = any(keyword in query.lower() for keyword in identity_keywords)
        
        # Determine response approach based on flow action and query type
        response_guidance = ""
        if is_identity_question:
            response_guidance = """
**IMPORTANT - Identity Response Required:**
The user is asking about your identity/capabilities. You MUST mention:
1. You are Guideon, an AI chatbot
2. You specialize in the Philippine Skills Framework for Analytics & AI (PSF-AAI)
3. Your main purpose is helping with career guidance in analytics and AI
4. You can provide information about roles, skills, career paths, and learning opportunities
5. You also enjoy casual conversation

Be friendly and comprehensive about your PSF-AAI specialization!"""
        elif flow_action == "intent_switch_acknowledge":
            response_guidance = "\nNote: The user is transitioning from PSF-AAI questions to general chat. Acknowledge this naturally and be ready to chat about anything!"
        elif flow_action == "general_chat_response_with_hints":
            response_guidance = "\nNote: Feel free to chat naturally, but if career/education topics come up, you can gently mention PSF-AAI framework as a helpful resource."
        elif psf_hints:
            response_guidance = f"\nContext: {psf_hints[0]}. You can naturally reference their career exploration if relevant to the conversation."
        
        # Build the enhanced prompt
        prompt = f"""# General Conversation with Guideon Identity

{chat_history}

## Current Query:
"{query}"

{response_guidance}

## Instructions:
Respond naturally and conversationally to this query as Guideon, the PSF-AAI specialized chatbot. Be friendly, helpful, and engaging like Baymax.

**Your Identity Guidelines:**
- Always remember you are Guideon, specializing in PSF-AAI career guidance
- When asked about yourself, clearly mention your PSF-AAI expertise
- Be proud of your specialization while remaining conversational
- Naturally weave in your capabilities when relevant

**Flow Integration Guidelines:**
- If the conversation naturally leads to career/education topics, mention PSF-AAI as your specialty
- Don't force PSF-AAI mentions if the topic is unrelated (jokes, weather, personal chat, etc.)
- Maintain the natural flow of conversation while being subtly helpful
- If user expresses career interests, offer to provide detailed PSF-AAI guidance

**Response Style:**
- Warm, friendly, and conversational
- Natural and not overly promotional
- Helpful without being pushy
- Genuine interest in the user's query
- Professional when discussing your PSF-AAI capabilities

## Response:
"""
        return prompt

    def _create_fallback_response(self, query: str, context: dict, error: str = None) -> dict:
        """**ENHANCED: Create fallback response with Guideon identity and PSF-AAI awareness**"""
        
        # Determine appropriate fallback based on query type
        query_lower = query.lower().strip()
        
        # Identity questions - MUST mention PSF-AAI specialization
        identity_keywords = ["what do you do", "who are you", "what are you", "your purpose", "your role", 
                           "what can you help", "what's your function", "tell me about yourself", 
                           "your capabilities", "what are your skills", "your specialty"]
        
        if any(keyword in query_lower for keyword in identity_keywords):
            response = """Hi! I'm Guideon, your AI assistant specializing in the Philippine Skills Framework for Analytics & AI (PSF-AAI). 

My main purpose is to help professionals like you navigate career paths in analytics and artificial intelligence. I can provide detailed information about:
- PSF-AAI career roles (from Associate to Chief level)
- Skills and competencies required for different positions
- Career progression pathways
- Learning recommendations and course suggestions
- How different roles connect within the analytics and AI ecosystem

I'm also happy to have casual conversations! Feel free to ask me anything about PSF-AAI careers or just chat with me about whatever's on your mind."""
            
        # Greeting responses
        elif any(greeting in query_lower for greeting in ["hi", "hello", "hey", "good morning", "good afternoon"]):
            response = "Hello! I'm Guideon, your PSF-AAI career guidance specialist. I'm here to help with analytics and AI career questions, or just have a friendly chat. What's on your mind today?"
            
        # Gratitude responses  
        elif any(thanks in query_lower for thanks in ["thank", "thanks", "appreciate"]):
            response = "You're very welcome! I'm Guideon, and I'm always happy to help with PSF-AAI career guidance or casual conversation. If you have any questions about analytics and AI careers, I'm here for you!"
            
        # Casual conversation
        elif any(casual in query_lower for casual in ["how are you", "what's up", "how's it going"]):
            response = "I'm doing great, thank you for asking! I'm Guideon, your PSF-AAI career guide, and I'm here and ready to help with analytics and AI career questions or just have a friendly chat. What's on your mind today?"
            
        # Default fallback
        else:
            base_response = "I'm Guideon, your AI assistant specializing in the Philippine Skills Framework for Analytics & AI (PSF-AAI). I'm here to chat and help however I can!"
            psf_hint = " Whether you want to explore analytics and AI careers, learn about specific roles and skills, or just have a casual conversation, I'm here for you."
            response = base_response + psf_hint
        
        if error:
            response += " (I had a small technical hiccup, but I'm still here to help!)"
        
        result = {
            "response": response,
            "agent_name": "general_conversation",
            "fallback_used": True
        }
        
        # Add flow metadata
        return self.add_flow_metadata(result, context)
