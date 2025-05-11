import logging
import asyncio
import os
from django.conf import settings
from agno.agent import Agent
from agno.memory import AgentMemory
from agno.memory.db.postgres import PgMemoryDb
from agno.embedder.ollama import OllamaEmbedder
from sqlalchemy import create_engine
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
        
        # Initialize memory as None by default
        self.memory = None
        self.agent_db = None
        self.agno_agent = None
        
        # Try to initialize AGNO components
        self._init_memory()
        self._init_agent()
    
    def _init_memory(self):
        """Initialize the memory system with proper error handling"""
        try:
            embedder = OllamaEmbedder()
            
            # Get database settings
            db_settings = settings.DATABASES['default']
            dsn = f"postgresql://{db_settings['USER']}:{db_settings['PASSWORD']}@{db_settings['HOST']}:{db_settings['PORT']}/{db_settings['NAME']}"
            
            # Create SQLAlchemy engine
            db_engine = create_engine(dsn)
            
            # Initialize memory database
            self.agent_db = PgMemoryDb(
                table_name="guideon_chat_memory",
                db_engine=db_engine
            )
            
            # Initialize memory system with AGNO v1.4.5 compatible approach
            self.memory = AgentMemory(db=self.agent_db)
            logger.info("AGNO memory system initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize AGNO memory: {e}", exc_info=True)
            self.memory = None
            self.agent_db = None
            return False
    
    def _init_agent(self):
        """Initialize the AGNO agent with proper error handling"""
        try:
            from agno.models.ollama import Ollama
            # Initialize Llama model
            llama_model = Ollama(id="llama3.2:latest", provider="Ollama", host="http://localhost:11434")
            self.agno_agent = Agent(
                name="ServicesAGNOAgent",
                model=llama_model,
                memory=self.memory
            )
            logger.info("AGNO agent initialized successfully with Llama 3.2")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Llama 3.2 model: {e}", exc_info=True)
            try:
                # Fallback to agent without model
                self.agno_agent = Agent(
                    name="ServicesAGNOAgent",
                    model=None,
                    memory=self.memory
                )
                logger.info("AGNO agent initialized without model")
                return True
            except Exception as e2:
                logger.error(f"Failed to initialize AGNO agent: {e2}", exc_info=True)
                self.agno_agent = None
                return False
    
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
                chat = await Chat.objects.aget(id=chat_id)
                messages = [msg async for msg in chat.messages.all().order_by('timestamp')]
                context['chat_history'] = messages
                
                session_id = f"chat_{chat_id}"
                
                # Add current query to memory if available
                if self.memory:
                    user_message = [{
                        "role": "user",
                        "content": user_query
                    }]
                    
                    # Shared metadata for this message
                    user_metadata = {
                        "session_id": session_id,
                        "type": "user_query", 
                        "timestamp": str(asyncio.get_event_loop().time()),
                        "content_type": "question",
                        "entities": self._extract_entities(user_query)
                    }
                    
                    await self._add_to_memory(
                        user_message, 
                        "User query",
                        shared_metadata=user_metadata
                    )
                
                # Add chat history to memory using the correct AGNO v1.4.5 method
                formatted_messages = []
                for msg in messages:
                    # Format each message with only role and content 
                    # (metadata will be added as shared metadata)
                    formatted_msg = {
                        "role": msg.role,
                        "content": msg.content
                    }
                    formatted_messages.append(formatted_msg)
                
                # Add chat history to memory if available
                if formatted_messages:
                    # Create shared metadata for all history messages
                    history_metadata = {
                        "session_id": session_id,
                        "type": "chat_history",
                        "timestamp": str(asyncio.get_event_loop().time()),
                        "content_type": "conversation_history"
                    }
                    
                    await self._add_to_memory(
                        formatted_messages, 
                        "Chat history", 
                        shared_metadata=history_metadata
                    )
                
                # Semantic search - implement using memory API from AGNO v1.4.5
                memory_context = {}
                if self.memory:
                    # Use metadata filter to get messages for this session
                    conversation_messages = await self._get_from_memory(
                        limit=20, 
                        metadata_filter={"session_id": session_id}
                    )
                    
                    # Get the 5 most recent messages
                    conversation_messages = conversation_messages[:5]
                    
                    if conversation_messages:
                        # Extract user messages for conversation topics
                        memory_context['conversation_topics'] = [
                            msg.get("content", "") for msg in conversation_messages 
                            if msg.get("role") == "user"
                        ]
                        
                        # For short queries, get additional context
                        if len(user_query.split()) <= 5:
                            memory_context['recent_context'] = [
                                msg.get("content", "") for msg in conversation_messages
                            ]
                
                # Summary fetching and pruning if needed
                if self.memory and len(messages) > 20:
                    # Run memory maintenance in the background without blocking the main flow
                    asyncio.create_task(self._run_memory_maintenance(session_id))

                if memory_context: # This will be empty for now
                    context['memory_context'] = memory_context
                    
            except Chat.DoesNotExist:
                logger.warning(f"Chat with id {chat_id} not found")
            except Exception as e:
                logger.error(f"Error processing chat history or memory: {e}", exc_info=True)

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
            
            # Add response to memory
            if chat_id and self.memory:
                intent_value = getattr(context.get('intent'), 'value', str(context.get('intent')))
                assistant_message = [{
                    "role": "assistant",
                    "content": response
                }]
                
                # Create shared metadata for the assistant response
                assistant_metadata = {
                    "session_id": f"chat_{chat_id}",
                    "type": "assistant_response", 
                    "intent": intent_value,
                    "source": synthesis_result.get('source', 'unknown'),
                    "content_type": "answer",
                    "topics": self._extract_entities(response),
                    "has_course_info": bool(context.get("course_search", {}).get("found", False)),
                    "has_pathway_info": bool(context.get("learning_path", {}).get("found", False))
                }
                
                await self._add_to_memory(
                    assistant_message, 
                    "Assistant response", 
                    shared_metadata=assistant_metadata
                )
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True) # Added exc_info
            return self._fallback_response(user_query)
    
    async def _run_memory_maintenance(self, session_id):
        """Run memory maintenance tasks in the background"""
        if not self.memory:
            logger.warning("Memory maintenance skipped - memory system not available")
            return
            
        try:
            # Get all messages for the session using the metadata filter
            all_messages = await self._get_from_memory(
                limit=1000, 
                metadata_filter={"session_id": session_id}
            )
            
            if len(all_messages) > 100:
                logger.info(f"Pruning memory for session {session_id}, found {len(all_messages)} messages")
                
                # For now, just log that pruning would be needed
                logger.info(f"Memory maintenance would prune {len(all_messages) - 100} messages")
                
                # In a future implementation, you could delete old messages and add a summary
                # summary_message = [{
                #     "role": "system", 
                #     "content": "This is a summary of previous conversations..."
                # }]
                # summary_metadata = {
                #     "session_id": session_id,
                #     "type": "summary", 
                #     "timestamp": str(asyncio.get_event_loop().time())
                # }
                # await self._add_to_memory(summary_message, "Memory maintenance summary", shared_metadata=summary_metadata)
            
            logger.debug(f"Memory maintenance completed for session {session_id}")
        except Exception as e:
            logger.error(f"Error in memory maintenance: {e}", exc_info=True)
    
    async def _add_to_memory(self, messages, log_prefix="", shared_metadata=None):
        """
        Safe wrapper for memory operations
        
        Args:
            messages: List of message objects to add to memory
            log_prefix: Prefix for log messages
            shared_metadata: Common metadata that applies to all messages
            
        Returns:
            True if successful, False otherwise
        """
        if not self.memory:
            return False
            
        try:
            # Extract session_id and type from individual message metadata if they exist
            # and not already provided in shared_metadata
            if messages and not shared_metadata:
                # Get the first message's metadata as a baseline for shared metadata
                first_msg = messages[0]
                if isinstance(first_msg, dict) and "metadata" in first_msg:
                    metadata = first_msg.get("metadata", {})
                    shared_metadata = {
                        "session_id": metadata.get("session_id", "unknown_session"),
                        "type": metadata.get("type", "unknown_type")
                    }
            
            # Clean the messages by removing individual metadata since we'll use shared metadata
            cleaned_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    # Keep only role and content in the message objects
                    cleaned_msg = {
                        "role": msg.get("role", "unknown"),
                        "content": msg.get("content", "")
                    }
                    cleaned_messages.append(cleaned_msg)
            
            # Use the shared metadata approach from AGNO v1.4.5
            await self.memory.add_messages(
                messages=cleaned_messages,
                metadata=shared_metadata
            )
            
            if log_prefix:
                logger.debug(f"{log_prefix}: Added {len(messages)} messages to memory")
            return True
        except Exception as e:
            logger.error(f"Error adding messages to memory ({log_prefix}): {e}", exc_info=True)
            return False
            
    async def _get_from_memory(self, limit=20, filter_func=None, metadata_filter=None):
        """
        Safe wrapper for memory retrieval
        
        Args:
            limit: Maximum number of messages to retrieve
            filter_func: Optional function to filter messages (legacy approach)
            metadata_filter: Dictionary of metadata key-value pairs to filter by
            
        Returns:
            List of messages, or empty list if no memory or error
        """
        if not self.memory:
            return []
            
        try:
            # If metadata_filter is provided, use it directly with the API
            if metadata_filter:
                messages = await self.memory.get_messages(
                    limit=limit,
                    metadata_filter=metadata_filter
                )
            else:
                # Otherwise just get messages with limit
                messages = await self.memory.get_messages(limit=limit)
            
            # Apply filter_func if provided (legacy approach)
            if filter_func and callable(filter_func):
                messages = [msg for msg in messages if filter_func(msg)]
                
            return messages
        except Exception as e:
            logger.error(f"Error retrieving messages from memory: {e}", exc_info=True)
            return []
    
    def _extract_entities(self, text):
        """
        Extract named entities from text to improve memory retrieval
        
        This is a simple implementation - in production, use a proper NER model
        """
        entities = []
        
        if "level" in text.lower():
            import re
            level_matches = re.findall(r'level\s*(\d+)', text.lower())
            if level_matches:
                entities.append(f"level_{level_matches[0]}")
        
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
    # asyncio.run can cause issues if an event loop is already running.
    # If this is called from an async context, it should be awaited.
    # For Django, consider using asgiref.sync.async_to_sync if in a sync context.
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            # If called from an already running async context, create a new task
            # This is a simplification; proper async integration might be needed.
            logger.warning("query_ollama called from a running asyncio loop. Consider direct async usage.")
            future = asyncio.ensure_future(service.process_message(user_prompt, chat_id))
            # This is a blocking call to wait for the future in a sync function.
            # It's generally not ideal.
            return loop.run_until_complete(future)
        else: # pragma: no cover
            return asyncio.run(service.process_message(user_prompt, chat_id))
    except RuntimeError: # No running event loop
        return asyncio.run(service.process_message(user_prompt, chat_id))