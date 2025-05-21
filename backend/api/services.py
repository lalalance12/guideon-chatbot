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
        self.intent_agent = IntentClassifierAgent()
        self.orchestrator = OrchestratorAgent()
        self.synthesizer = ResponseSynthesizerAgent()
        self.course_search_agent = CourseSearchAgent()
        self.flow_manager = FlowManagerAgent()
        self.agno_agent = None
        self._init_agent()

    def _init_agent(self):
        # Initialization code remains unchanged
        try:
            llama_model = Ollama(id="llama3.1:8b-instruct-q8_0", provider="Ollama", host="http://localhost:11434")
            self.agno_agent = Agent(
                name="ServicesAGNOAgent",
                model=llama_model,
            )
            logger.info("AGNO agent initialized successfully with Llama 3.1")
        except Exception as e:
            logger.error(f"Failed to initialize Llama model: {e}", exc_info=True)
            self.agno_agent = None
            logger.warning("AGNO agent not available - will use fallback responses")

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
            context.update(orchestrator_result)

            # If the flow is course_search and the flow action is clarification, return the clarification prompt directly
            flow = context.get('flow', {})
            flow_action = flow.get('flow_action')
            response_format = flow.get('response_format', {})
            if intent_name == "course_search":
                # If clarification is needed
                if flow_action in ('clarify_course_topic', 'request_course_topic_details'):
                    prompt = response_format.get('prompt_message', "What specific skill or topic are you looking for courses on?")
                    if chat_id:
                        chat = await self._get_or_create_chat(chat_id)
                        await self._save_message(chat, 'user', user_query)
                        await self._save_message(chat, 'assistant', prompt)
                    return {
                        'response': prompt,
                        'clarification': True
                    }
                # If we have course cards, return them directly (skip synthesis)
                agent_responses = context.get('agent_responses', {})
                course_result = agent_responses.get('course_search', {})
                if course_result.get('found', False) and course_result.get('courses', []):
                    courses = course_result.get('courses', [])
                    response_text = "Based on your query, here are some recommended courses that might help you:"
                    if chat_id:
                        chat = await self._get_or_create_chat(chat_id)
                        await self._save_message(chat, 'user', user_query)
                        await self._save_message(chat, 'assistant', response_text)
                    return {
                        'response': response_text,
                        'courses': courses
                    }
                # If no courses found, return the message from the agent
                if course_result.get('message'):
                    if chat_id:
                        chat = await self._get_or_create_chat(chat_id)
                        await self._save_message(chat, 'user', user_query)
                        await self._save_message(chat, 'assistant', course_result['message'])
                    return {
                        'response': course_result['message']
                    }

            # For all other intents, use the synthesizer
            logger.info("Generating final response with synthesizer")
            synthesizer_result = await self.synthesizer.process(user_query, context)
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