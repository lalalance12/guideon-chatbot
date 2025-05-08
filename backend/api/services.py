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
from .utils.postgres_memory import PostgresMemoryStorage
from agno.embedder import OllamaEmbedder

logger = logging.getLogger(__name__)

class GuideonChatService:
    """Main service for handling chat interactions with Guideon"""
    
    def __init__(self):
        self.intent_agent = IntentClassifierAgent()
        self.orchestrator = OrchestratorAgent()
        self.synthesizer = ResponseSynthesizerAgent()
        
        # Initialize custom PostgreSQL storage for AGNO memory
        embedder = OllamaEmbedder(
            model="llama3.2:latest",
            base_url="http://localhost:11434"
        )
        self.storage = PostgresMemoryStorage(embedder=embedder)
        
        # Initialize AGNO memory with PostgreSQL storage
        self.memory = Memory(storage_driver=self.storage)
        
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
                
                # First, add current query to memory with enhanced metadata
                self.memory.add(
                    session_id=session_id,
                    content=user_query,
                    metadata={
                        "type": "user_query", 
                        "timestamp": str(asyncio.get_event_loop().time()),
                        "content_type": "question",
                        "entities": self._extract_entities(user_query)
                    }
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
                        msg_metadata = {
                            "type": "message", 
                            "role": msg.role,
                            "timestamp": str(msg.timestamp) if hasattr(msg, 'timestamp') else "",
                            "content_type": "question" if msg.role == "user" else "answer",
                        }
                        
                        # Add entity extraction for user messages to improve retrieval
                        if msg.role == "user":
                            msg_metadata["entities"] = self._extract_entities(msg.content)
                            
                        self.memory.add(
                            session_id=session_id,
                            content=msg.content,
                            metadata=msg_metadata
                        )
                
                # Enhanced context building with more targeted queries
                memory_context = {}
                
                # 1. Get conversation topics with semantic search
                conversation_context = self.memory.search(
                    session_id=session_id,
                    query="What are the main topics and concepts in this conversation?",
                    search_type="semantic",
                    limit=3
                )
                if conversation_context:
                    memory_context['conversation_topics'] = [mem.content for mem in conversation_context]
                
                # 2. Get user preferences with entity focus
                user_preferences = self.memory.search(
                    session_id=session_id,
                    query="What specific roles, skills, or career interests has the user mentioned?",
                    search_type="semantic",
                    limit=2,
                    metadata_filter={"role": "user"}  # Only look at user messages
                )
                if user_preferences:
                    memory_context['user_preferences'] = [mem.content for mem in user_preferences]
                
                # 3. Enhanced follow-up detection for short queries
                if len(user_query.split()) <= 5:
                    # Get most recent messages
                    recent_context = self.memory.search(
                        session_id=session_id,
                        query="most recent conversation",
                        search_type="last_n",
                        limit=2
                    )
                    
                    # Also try to find semantically relevant context from earlier
                    semantic_context = self.memory.search(
                        session_id=session_id,
                        query=user_query,  # Use the user's short query directly
                        search_type="semantic",
                        limit=2
                    )
                    
                    # Combine both for better follow-up handling
                    follow_up_context = list(recent_context)
                    for ctx in semantic_context:
                        if ctx not in follow_up_context:
                            follow_up_context.append(ctx)
                    
                    if follow_up_context:
                        memory_context['recent_context'] = [mem.content for mem in follow_up_context]
                
                # 4. Add session summaries if available (for long conversations)
                if len(messages) > 20:
                    # Run memory maintenance to ensure summaries exist
                    await self._run_memory_maintenance(session_id)
                    
                    # Try to fetch summaries from the storage directly
                    with self.storage._get_connection() as cursor:
                        cursor.execute(
                            "SELECT summary FROM agno_summaries WHERE session_id = %s ORDER BY created_at DESC LIMIT 1",
                            [session_id]
                        )
                        summary_results = cursor.fetchall()
                        if summary_results:
                            memory_context['conversation_summary'] = [row[0] for row in summary_results]
                
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
            
            # Store response in memory with enhanced metadata for future context
            if chat_id:
                intent_value = getattr(context.get('intent'), 'value', str(context.get('intent')))
                self.memory.add(
                    session_id=f"chat_{chat_id}",
                    content=response,
                    metadata={
                        "type": "assistant_response", 
                        "role": "assistant",
                        "intent": intent_value,
                        "source": synthesis_result.get('source', 'unknown'),
                        "content_type": "answer",
                        "topics": self._extract_entities(response),
                        "has_course_info": bool(context.get("course_search", {}).get("found", False)),
                        "has_pathway_info": bool(context.get("learning_path", {}).get("found", False))
                    }
                )
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return self._fallback_response(user_query)
    
    def _extract_entities(self, text):
        """
        Extract named entities from text to improve memory retrieval
        
        This is a simple implementation - in production, use a proper NER model
        """
        entities = []
        
        # Look for skill levels
        if "level" in text.lower():
            import re
            level_matches = re.findall(r'level\s*(\d+)', text.lower())
            if level_matches:
                entities.append(f"level_{level_matches[0]}")
        
        # Extract key terms based on PSF-AAI domain knowledge
        key_terms = [
            "data", "analytics", "AI", "artificial intelligence", "machine learning",
            "career", "path", "role", "skill", "competency", "framework",
            "junior", "senior", "lead", "manager", "director",
            "analyst", "scientist", "engineer", "developer"
        ]
        
        for term in key_terms:
            if term.lower() in text.lower():
                entities.append(term.lower())
        
        return entities
    
    async def _run_memory_maintenance(self, session_id):
        """Run memory maintenance tasks in the background"""
        try:
            # Prune and summarize old memories
            # Run in a separate thread to avoid blocking
            await asyncio.to_thread(
                self.storage.summarize_and_prune,
                session_id=session_id,
                max_items=100,
                older_than_hours=24
            )
            logger.debug(f"Memory maintenance completed for session {session_id}")
        except Exception as e:
            logger.error(f"Error in memory maintenance: {e}")
    
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