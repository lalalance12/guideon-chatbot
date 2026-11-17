from django.conf import settings
from agno.agent import Agent
from agno.models.ollama import Ollama
from .agents.intent_classifier_agent import IntentClassifierAgent
from .agents.orchestrator_agent import OrchestratorAgent
from .agents.response_synthesizer_agent import ResponseSynthesizerAgent
from .agents.course_search_agent import CourseSearchAgent
from .models import Chat, Message
from .utils.embeddings import generate_embedding
from .utils.chat_history_manager import ChatHistoryManager
from .agents.flow_manager_agent import FlowManagerAgent
import logging
import asyncio
import uuid

logger = logging.getLogger(__name__)

class GuideonChatService:
    def __init__(self):
        # Initialize a centralized LLM first
        self.llm = None
        self.agno_agent = None
        self._init_llm()
        
        # Initialize agents with the centralized LLM
        self.intent_agent = IntentClassifierAgent(llm=self.llm)
        self.orchestrator = OrchestratorAgent(llm=self.llm)
        self.synthesizer = ResponseSynthesizerAgent(llm=self.llm)
        self.course_search_agent = CourseSearchAgent(llm=self.llm)
        # FlowManager doesn't need LLM for its core functionality
        self.flow_manager = FlowManagerAgent()

    def _init_llm(self):
        """Initialize a centralized LLM for all agents to use"""
        try:
            self.llm = Ollama(id="llama3.1:8b-instruct-q4_1", provider="Ollama", host="http://localhost:11434")
            self.agno_agent = Agent(
                name="ServicesAGNOAgent",
                model=self.llm,
            )
            logger.info("Centralized LLM initialized successfully with Llama 3.1")
        except Exception as e:
            logger.error(f"Failed to initialize Llama model: {e}", exc_info=True)
            self.llm = None
            self.agno_agent = None
            logger.warning("Centralized LLM not available - agents will use fallback mechanisms")
            
    async def process_message(self, user_query: str, chat_id=None, user_id=None):
        """
        Process a user message through the complete agent pipeline:
        Intent Classification → (Course Search Flow) → Course Search Agent (if needed)
        """
        context = {'chat_id': chat_id, 'user_id': user_id}
        logger.info(f"[Service] Processing message: {user_query[:60]}...")
        
        # Validate and log user_id type for debugging
        if user_id is not None:
            logger.info(f"User ID type: {type(user_id)}, value: {user_id}")
        else:
            logger.warning("No user_id provided in process_message call")
        
        # Get or create chat
        chat = None
        if chat_id:
            try:
                chat = await self._get_or_create_chat(chat_id)
                # Save user message
                await self._save_message(chat, 'user', user_query)
                
                # Get chat history for context
                chat_history = await self._get_chat_history(chat_id, user_query)
                context['chat_history'] = chat_history
                logger.info(f"Retrieved chat history for chat ID {chat_id}: {len(chat_history)} messages")
            except Exception as e:
                logger.error(f"Error retrieving chat history: {e}", exc_info=True)
                context['chat_history'] = []

        try:
            # Step 1: Determine user intent using the IntentClassifierAgent
            intent_result = await self.intent_agent.process(user_query, context)
            context.update(intent_result)
            intent_name = getattr(intent_result.get('intent'), 'value', None)
            if not intent_name and isinstance(intent_result.get('intent'), str):
                intent_name = intent_result.get('intent')
            confidence = intent_result.get('confidence', 0.0)
            logger.info(f"[Service] Intent classification result: {intent_name}")

            # Always use orchestrator for all intents (including course_search)
            logger.info(f"Processing with orchestrator using intent: {intent_name}")
            orchestrator_result = await self.orchestrator.process(user_query, context)
            # Update context with results from the orchestrator.
            # If orchestrator decided on a direct response (e.g., from LearningPathAgent),
            # those flags and data will be in orchestrator_result.
            # Otherwise, orchestrator_result contains the payload for the synthesizer.
            context.update(orchestrator_result)

            # Check for direct action flags now present in 'context' (merged from orchestrator_result)
            # Log what we received from the orchestrator to debug
            logger.info(f"[Service] Orchestrator result keys: {list(orchestrator_result.keys())}")

            # Handle direct action responses
            if self._is_direct_action_response(orchestrator_result):
                logger.info(f"[Service] Direct action detected: {self._get_direct_action_type(orchestrator_result)}")
                return await self._handle_direct_action_response(orchestrator_result, chat, user_query)

            # If no direct action flags were handled, proceed to synthesizer.
            # 'context' now contains the full payload from orchestrator intended for the synthesizer.
            logger.info(f"[Service] No direct action from specialized agents via orchestrator. Proceeding to synthesizer. Intent: {intent_name}")
            synthesizer_result = await self.synthesizer.process(user_query, context) # Pass the updated context
            response_text = synthesizer_result.get('response') or synthesizer_result.get('response_text') or 'I apologize, but I could not generate a proper response.'
            
            # **SAFETY CHECK: Ensure response_text is not None or empty**
            if not response_text or response_text.strip() == '':
                logger.warning("[Service] Empty response text from synthesizer, using fallback")
                response_text = self._get_fallback_response_text(intent_result.get('intent'))
            
            # Save assistant response if we have a chat
            if chat_id and chat:
                await self._save_message(chat, 'assistant', response_text)
            
            # Return final response
            return {
                'response': response_text,
                'chat_id': str(chat.id) if chat else None,
                'intent': intent_name
            }
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            fallback_response = self._fallback_response(user_query)
            if chat_id and chat:
                try:
                    await self._save_message(chat, 'assistant', fallback_response['response'])
                except Exception as save_error:
                    logger.error(f"Error saving fallback message: {save_error}")
            return fallback_response

    def _is_direct_action_response(self, orchestrator_result: dict) -> bool:
        """Check if orchestrator result is a direct action response"""
        # Check for direct action indicators
        direct_action_keys = [
            'show_goto_career_button',
            'show_role_selection_button', 
            'show_course_suggestions',
            'courses',
            'needs_clarification',
            'goto_career_role',
            'available_roles'
        ]
        
        return any(key in orchestrator_result for key in direct_action_keys)

    def _get_direct_action_type(self, orchestrator_result: dict) -> str:
        """Get the type of direct action"""
        if orchestrator_result.get('show_goto_career_button'):
            return 'show_goto_career_button'
        elif orchestrator_result.get('show_role_selection_button'):
            return 'show_role_selection_button'
        elif orchestrator_result.get('show_course_suggestions') or orchestrator_result.get('courses'):
            return 'show_course_suggestions'
        elif orchestrator_result.get('needs_clarification'):
            return 'needs_clarification'
        else:
            return 'unknown_direct_action'

    async def _handle_direct_action_response(self, orchestrator_result: dict, chat, user_query: str) -> dict:
        """Handle direct action responses properly"""
        # Extract response text with fallback
        response_text = orchestrator_result.get('response', '')
        
        # **SAFETY CHECK: Ensure we have response text for direct actions**
        if not response_text or response_text.strip() == '':
            if orchestrator_result.get('show_goto_career_button'):
                role = orchestrator_result.get('goto_career_role', 'the role')
                response_text = f"Here's the detailed information for the {role} role. Click below to explore career pathways and requirements."
            elif orchestrator_result.get('show_role_selection_button'):
                response_text = "Please select which career role you'd like to explore in detail."
            elif orchestrator_result.get('courses'):
                response_text = "I found some relevant courses for you. Here are the recommendations:"
            elif orchestrator_result.get('needs_clarification'):
                response_text = orchestrator_result.get('message', "Could you please provide more details?")
            else:
                response_text = "I found some options for you. Please see the suggestions below."
        
        # Save assistant response if we have a chat
        if chat:
            await self._save_message(chat, 'assistant', response_text)
        
        # Return the complete direct action response
        result = {
            'response': response_text,
            'chat_id': str(chat.id) if chat else None,
            'intent': orchestrator_result.get('intent')
        }
        
        # Add all direct action fields
        direct_action_fields = [
            'show_goto_career_button', 'goto_career_role',
            'show_role_selection_button', 'available_roles',
            'show_course_suggestions', 'courses',
            'needs_clarification', 'clarification_options'
        ]
        
        for field in direct_action_fields:
            if field in orchestrator_result:
                result[field] = orchestrator_result[field]
        
        logger.info(f"[Service] Direct action response prepared: {self._get_direct_action_type(orchestrator_result)}")
        return result

    def _get_fallback_response_text(self, intent) -> str:
        """Generate fallback response text based on intent"""
        intent_str = str(intent).lower() if intent else ''
        
        if 'learning_pathway' in intent_str:
            return "I can help you explore career pathways in the PSF-AAI framework. Which role interests you?"
        elif 'course_search' in intent_str:
            return "I can help you find relevant courses. What topic would you like to learn about?"
        elif 'knowledge_base' in intent_str:
            return "I can provide information about PSF-AAI roles, skills, and career paths. What would you like to know?"
        elif 'general_conversation' in intent_str:
            return "I'm here to help with both PSF-AAI career guidance and general conversation. How can I assist you?"
        else:
            return "I'm here to help with PSF-AAI career guidance. What would you like to know about analytics and AI careers?"

    # Helper methods
    async def _get_or_create_chat(self, chat_id):
        """Get or create a chat object by its ID"""
        from django.db import transaction
        from asgiref.sync import sync_to_async
        
        @sync_to_async
        def get_or_create():
            with transaction.atomic():
                try:
                    return Chat.objects.get(id=chat_id)
                except Chat.DoesNotExist:
                    # Create a new chat with the given ID if possible
                    return Chat.objects.create(id=chat_id)
        
        return await get_or_create()

    async def _save_message(self, chat, role, content):
        """Save a message to the chat"""
        from asgiref.sync import sync_to_async
        
        # **SAFETY CHECK: Ensure content is not None or empty**
        if not content or (isinstance(content, str) and content.strip() == ''):
            logger.warning(f"[Service] Attempting to save empty message content for role: {role}")
            content = "[System message - no content]"  # Fallback content
        
        @sync_to_async
        def save():
            message = Message(chat=chat, role=role, content=str(content))  # Ensure it's a string
            message.save()
            return message
        
        return await save()

    async def _get_chat_history(self, chat_id, user_query=None):
        """Retrieve chat history for context building from database"""
        try:
            # Use simple history
            return await ChatHistoryManager.get_simple_history(chat_id)
        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            return []

    def _fallback_response(self, query):
        """Generate fallback response when processing fails."""
        return {
            'response': f"""I apologize, but I encountered an issue while processing your question about "{query}".

I'm Guideon, specialized in the Philippine Skills Framework for Analytics & AI (PSF-AAI), and I can help with:
- Information about analytics and AI career roles
- Details about skills and competencies in the PSF-AAI framework
- Career progression pathways and learning recommendations

Please try asking your question in a different way, or ask me about specific aspects of the PSF-AAI framework.""",
            'error': True,
            'chat_id': str(uuid.uuid4())
        }

_service = GuideonChatService()

def query_ollama(user_prompt: str, chat_id=None, user_id=None):
    """Main entry point for the chat service."""
    try:
        return asyncio.run(_service.process_message(user_prompt, chat_id=chat_id, user_id=user_id))
    except Exception as e:
        logging.exception("query_ollama failed")
        return {
            'response': f"Sorry, I encountered an error while processing your query: {str(e)}"
        }