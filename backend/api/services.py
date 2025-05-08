import logging
import asyncio
from asgiref.sync import sync_to_async
import traceback
from .agents.intent_classifier_agent import IntentClassifierAgent
from .agents.orchestrator_agent import OrchestratorAgent
from .agents.response_synthesizer_agent import ResponseSynthesizerAgent
from .models import Chat
from agno import AGNOAgent
from agno.memory import Memory

logger = logging.getLogger(__name__)

class GuideonChatService:
    """Main service for handling chat interactions with Guideon"""
    
    def __init__(self):
        self.intent_agent = IntentClassifierAgent()
        self.orchestrator = OrchestratorAgent()
        self.synthesizer = ResponseSynthesizerAgent()
        
        # Initialize AGNO memory for chat history context
        self.memory = Memory()
        # Initialize AGNO agent with memory and chat history enabled
        self.agno_agent = AGNOAgent(
            add_history_to_messages=True,
            num_history_runs=5,  # Include 5 previous interactions
            read_chat_history=True,
            memory=self.memory
        )
    
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
                # Replace with Django's native async query methods
                chat = await Chat.objects.aget(id=chat_id)
                messages = [msg async for msg in chat.messages.all().order_by('timestamp')]
                context['chat_history'] = messages
                
                # Store messages in AGNO memory for semantic retrieval
                session_id = f"chat_{chat_id}"
                
                # First, add current query to memory
                self.memory.add(
                    session_id=session_id,
                    content=user_query,
                    metadata={"type": "user_query", "timestamp": str(asyncio.get_event_loop().time())}
                )
                
                # Add chat history to memory if not already present
                for msg in messages:
                    # Check if this message is already in memory to avoid duplicates
                    existing_messages = self.memory.search(
                        session_id=session_id,
                        query=msg.content[:50],  # Use start of message as search query
                        limit=1
                    )
                    
                    if not any(mem.content == msg.content for mem in existing_messages):
                        self.memory.add(
                            session_id=session_id,
                            content=msg.content,
                            metadata={
                                "type": "message", 
                                "role": msg.role,
                                "timestamp": str(msg.timestamp) if hasattr(msg, 'timestamp') else "",
                            }
                        )
                
                # Enhance context with semantic memory insights
                memory_context = {}
                
                # 1. Get conversation summary 
                conversation_context = self.memory.search(
                    session_id=session_id,
                    query="What has the conversation been about? What are the main topics?",
                    search_type="agentic",
                    limit=3
                )
                if conversation_context:
                    memory_context['conversation_topics'] = [mem.content for mem in conversation_context]
                
                # 2. Get user preferences
                user_preferences = self.memory.search(
                    session_id=session_id,
                    query="What are the user's interests, preferences, or specific roles mentioned?",
                    search_type="agentic",
                    limit=2
                )
                if user_preferences:
                    memory_context['user_preferences'] = [mem.content for mem in user_preferences]
                
                # 3. Get follow-up context if query is short
                if len(user_query.split()) <= 5:
                    recent_context = self.memory.search(
                        session_id=session_id,
                        query="most recent conversation context",
                        search_type="last_n",
                        limit=2
                    )
                    if recent_context:
                        memory_context['recent_context'] = [mem.content for mem in recent_context]
                
                # Add memory context to main context
                if memory_context:
                    context['memory_context'] = memory_context
                    
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
            
            # Store response in memory for future context
            if chat_id:
                self.memory.add(
                    session_id=f"chat_{chat_id}",
                    content=response,
                    metadata={
                        "type": "assistant_response", 
                        "intent": str(context.get('intent')),
                        "source": synthesis_result.get('source', 'unknown')
                    }
                )
            
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