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
import logging
import asyncio
import json
from .agents.flow_manager_agent import FlowManagerAgent


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
            self.llm = Ollama(id="llama3.1:8b-instruct-q2_K", provider="Ollama", host="http://localhost:11434")
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

    async def process_message(self, user_query: str, chat_id=None):
        """
        Process a user message through the complete agent pipeline:
        Intent Classification → (Course Search Flow) → Course Search Agent (if needed)
        """
        context = {'chat_id': chat_id}
        if chat_id:
            try:
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
            logger.info(f"[Service] Orchestrator result: {orchestrator_result}")

            if orchestrator_result.get("show_goto_career_button"):
                logger.info("[Service] Direct action from Orchestrator/LearningPathAgent: show_goto_career_button")
                response_text = orchestrator_result.get("response") 
                goto_career_role = orchestrator_result.get("goto_career_role")
                
                if chat_id:
                    chat = await self._get_or_create_chat(chat_id)
                    await self._save_message(chat, 'user', user_query)
                    await self._save_message(chat, 'assistant', response_text)
                
                # Make sure to return these values at the TOP LEVEL of the response
                return {
                    'response': response_text,
                    'goto_career_role': goto_career_role,
                    'show_goto_career_button': True,
                    'chat_id': chat_id
                }

            if context.get("show_role_selection_button"):
                logger.info("[Service] Direct action from Orchestrator/LearningPathAgent: show_role_selection_button")
                response_text = context.get("response") # Message from LearningPathAgent via Orchestrator
                available_roles = context.get("available_roles")
                if chat_id:
                    chat = await self._get_or_create_chat(chat_id)
                    await self._save_message(chat, 'user', user_query)
                    await self._save_message(chat, 'assistant', response_text)
                return {
                    'response': response_text,
                    'available_roles': available_roles,
                    'show_role_selection_button': True
                }

            if context.get("show_course_suggestions") or (
                context.get("courses") and isinstance(context.get("courses"), list) and len(context.get("courses")) > 0
            ):
                logger.info("[Service] Direct action from Orchestrator/CourseSearchAgent: show_course_suggestions")
                response_text = context.get("response", "Based on your query, here are some recommended courses:")
                courses = context.get("courses", [])
                if chat_id:
                    chat = await self._get_or_create_chat(chat_id)
                    await self._save_message(chat, 'user', user_query)
                    await self._save_message(chat, 'assistant', response_text)
                return {
                    'response': response_text,
                    'courses': courses,
                    'show_course_suggestions': True
                }
            
            if context.get("needs_clarification"): # This is for course agent's clarification
                logger.info("[Service] Direct action from Orchestrator/CourseSearchAgent: needs_clarification")
                response_text = context.get("response") # Message from CourseSearchAgent via Orchestrator
                clarification_options = context.get("clarification_options")
                if chat_id:
                    chat = await self._get_or_create_chat(chat_id)
                    await self._save_message(chat, 'user', user_query)
                    await self._save_message(chat, 'assistant', response_text)
                return {
                    'response': response_text,
                    'needs_clarification': True, 
                    'clarification_options': clarification_options
                }

            # If no direct action flags were handled, proceed to synthesizer.
            # 'context' now contains the full payload from orchestrator intended for the synthesizer.
            logger.info(f"[Service] No direct action from specialized agents via orchestrator. Proceeding to synthesizer. Intent: {intent_name}")
            synthesizer_result = await self.synthesizer.process(user_query, context) # Pass the updated context
            response_text = synthesizer_result.get('response') or synthesizer_result.get('response_text') or 'I apologize, but I could not generate a proper response.'
            if chat_id:
                chat = await self._get_or_create_chat(chat_id)
                await self._save_message(chat, 'user', user_query)
                await self._save_message(chat, 'assistant', response_text)
            return {
                'response': response_text
            }
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            fallback_response = self._fallback_response(user_query)
            if chat_id:
                try:
                    chat = await self._get_or_create_chat(chat_id)
                    await self._save_message(chat, 'user', user_query)
                    await self._save_message(chat, 'assistant', fallback_response)
                except Exception as save_error:
                    logger.error(f"Error saving fallback message: {save_error}")
            return {
                'response': fallback_response
            }

    # Helper methods remain the same
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
        
        @sync_to_async
        def save():
            message = Message(chat=chat, role=role, content=content)
            message.save()
            return message
        
        return await save()

    async def _get_chat_history(self, chat_id, user_query=None):
        """Retrieve last 4 chat messages (user, assistant, user, assistant) for context building from database"""
        try:
            # Get the last 4 turns (excluding the latest user prompt)
            return await ChatHistoryManager.get_last_n_turns(chat_id, n=4)
        except Exception as e:
            logger.error(f"Error retrieving chat history: {e}", exc_info=True)
            return []

    def _fallback_response(self, query):
        # Existing fallback method unchanged
        return f"""I apologize, but I encountered an issue while processing your question about "{query}".

I'm Guideon, specialized in the Philippine Skills Framework for Analytics & AI (PSF-AAI), and I can help with:
- Information about analytics and AI career roles
- Details about skills and competencies in the PSF-AAI framework
- Career progression pathways and learning recommendations

Please try asking your question in a different way, or ask me about specific aspects of the PSF-AAI framework."""

_service = GuideonChatService()

def query_ollama(user_prompt: str, chat_id=None):
    """
    Process a user message through the GuideonChatService
    
    Returns a dict with response and optionally courses
    """
    try:
        return asyncio.run(_service.process_message(user_prompt, chat_id=chat_id))
    except Exception as e:
        logging.exception("query_ollama failed")
        return {
            'response': f"Sorry, I encountered an error while processing your query: {str(e)}"
        }