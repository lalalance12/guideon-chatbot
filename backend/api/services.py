import logging
import asyncio
from asgiref.sync import sync_to_async
from .agents.intent_classifier_agent import IntentClassifierAgent
from .agents.orchestrator_agent import OrchestratorAgent
from .agents.response_synthesizer_agent import ResponseSynthesizerAgent
from .models import Chat

logger = logging.getLogger(__name__)

class GuideonChatService:
    """Main service for handling chat interactions with Guideon"""
    
    def __init__(self):
        self.intent_agent = IntentClassifierAgent()
        self.orchestrator = OrchestratorAgent()
        self.synthesizer = ResponseSynthesizerAgent()
    
    async def process_message(self, user_query: str, chat_id=None) -> str:
        """
        Process a user message through the complete agent pipeline:
        Intent Classification → Orchestration → Response Synthesis
        
        Args:
            user_query: The user's message text
            chat_id: Optional ID to retrieve chat history
            
        Returns:
            Guideon's response text
        """
        # Initialize context
        context = {'chat_id': chat_id}
        
        # Get chat history if available
        if chat_id:
            try:
                chat = await sync_to_async(Chat.objects.get)(id=chat_id)
                messages = await sync_to_async(lambda: list(chat.messages.all().order_by('timestamp')))()
                context['chat_history'] = messages
            except Chat.DoesNotExist:
                logger.warning(f"Chat with id {chat_id} not found")
        
        try:
            # Step 1: Intent Classification
            logger.info(f"Classifying intent for: {user_query[:50]}..." if len(user_query) > 50 else user_query)
            intent_result = await self.intent_agent.process(user_query, context)
            context.update(intent_result)
            
            # Step 2: Orchestration
            logger.info(f"Orchestrating specialized agents for query with intent: {intent_result.get('intent')}")
            orchestration_result = await self.orchestrator.process(user_query, context)
            context.update(orchestration_result)
            
            # Step 3: Response Synthesis
            logger.info("Synthesizing final response")
            synthesis_result = await self.synthesizer.process(user_query, context)
            
            response = synthesis_result.get('response', 'I apologize, but I was unable to generate a response.')
            logger.info(f"Response generated successfully (source: {synthesis_result.get('source', 'unknown')})")
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return self._fallback_response(user_query)
    
    def _fallback_response(self, query):
        """Generate a fallback response when the main pipeline fails"""
        return f"""I apologize, but I encountered an issue while processing your question about "{query}".

I'm Guideon, specialized in the Philippine Skills Framework for Analytics & AI (PSF-AAI), and I can help with:
- Information about analytics and AI career roles
- Details about skills and competencies in the PSF-AAI framework
- Career progression pathways and learning recommendations

Please try asking your question in a different way, or ask me about specific aspects of the PSF-AAI framework."""
    
# Backward compatibility function to avoid breaking existing code
def query_ollama(user_prompt: str, chat_id=None) -> str:
    """
    Legacy entry point for query processing - calls the new implementation
    """
    service = GuideonChatService()
    return asyncio.run(service.process_message(user_prompt, chat_id))