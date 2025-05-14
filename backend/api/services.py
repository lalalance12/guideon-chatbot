import logging
import asyncio
from django.conf import settings
from agno.agent import Agent
from agno.memory import AgentMemory
from agno.memory.db.postgres import PgMemoryDb
from agno.embedder.ollama import OllamaEmbedder
from sqlalchemy import create_engine, text
from .agents.intent_classifier_agent import IntentClassifierAgent
from .agents.orchestrator_agent import OrchestratorAgent
from .agents.response_synthesizer_agent import ResponseSynthesizerAgent
from .models import Chat

logger = logging.getLogger(__name__)

class GuideonChatService:
    def __init__(self):
        self.intent_agent = IntentClassifierAgent()
        self.orchestrator = OrchestratorAgent()
        self.synthesizer = ResponseSynthesizerAgent()
        self.memory = None
        self.agent_db = None
        self.agno_agent = None
        self._init_memory()
        self._init_agent()

    def _init_memory(self):
        """Initialize the memory system with proper error handling for AGNO v1.4.5"""
        try:
            embedder = OllamaEmbedder()
            db_settings = settings.DATABASES['default']
            dsn = f"postgresql://{db_settings['USER']}:{db_settings['PASSWORD']}@{db_settings['HOST']}:{db_settings['PORT']}/{db_settings['NAME']}"
            db_engine = create_engine(dsn)
            self.agent_db = PgMemoryDb(
                table_name="guideon_chat_memory",
                db_engine=db_engine
            )
            try:
                if hasattr(self.agent_db, 'initialize'):
                    try:
                        self.agent_db.initialize()
                        logger.info("Memory tables initialized")
                    except Exception as e:
                        logger.info(f"Memory tables already exist: {e}")
                # Use SQLAlchemy's connection for raw SQL, not db_engine.execute()
                try:
                    with db_engine.connect() as conn:
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {self.agent_db.table_name}")).fetchone()
                        logger.info(f"Memory database connected successfully. Current record count: {result[0] if result else 0}")
                except Exception as db_e:
                    logger.warning(f"Database connection test failed: {db_e}")
            except Exception as table_e:
                logger.warning(f"Error during table initialization check: {table_e}")
            try:
                mem_args = {'db': self.agent_db}
                import inspect
                if 'embedder' in inspect.signature(AgentMemory.__init__).parameters:
                    mem_args['embedder'] = embedder
                self.memory = AgentMemory(**mem_args)
                logger.info("AGNO memory system initialized successfully")
                if hasattr(self.memory, 'get_messages'):
                    try:
                        _ = self.memory.get_messages()
                        logger.info("Memory.get_messages() working correctly")
                    except Exception as e:
                        logger.warning(f"Memory.get_messages() test failed: {e}")
                return True
            except Exception as mem_e:
                logger.error(f"Failed to initialize AgentMemory: {mem_e}", exc_info=True)
                self.memory = None
                self.agent_db = None
                return False
        except Exception as e:
            logger.error(f"Failed to initialize AGNO memory: {e}", exc_info=True)
            self.memory = None
            self.agent_db = None
            return False

    def is_memory_ready(self):
        """Utility to check if memory is initialized and ready."""
        return self.memory is not None

    def _init_agent(self):
        try:
            from agno.models.ollama import Ollama
            # AGNO v1.4.5 does not support 'temperature' in Agent or Ollama
            llama_model = Ollama(id="llama3.2:latest", provider="Ollama", host="http://localhost:11434")
            self.agno_agent = Agent(
                name="ServicesAGNOAgent",
                model=llama_model,
                memory=self.memory
            )
            logger.info("AGNO agent initialized successfully with Llama 3.2")
        except Exception as e:
            logger.error(f"Failed to initialize Llama 3.2 model: {e}", exc_info=True)
            try:
                self.agno_agent = Agent(
                    name="ServicesAGNOAgent",
                    model=None,
                    memory=self.memory
                )
                logger.info("AGNO agent initialized without model")
            except Exception as e2:
                logger.error(f"Failed to initialize AGNO agent: {e2}", exc_info=True)
                self.agno_agent = None

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
                if self.is_memory_ready():
                    user_message = [{
                        "role": "user",
                        "content": user_query,
                        "metadata": {
                            "session_id": session_id,
                            "type": "user_query", 
                            "timestamp": str(asyncio.get_event_loop().time()),
                            "content_type": "question",
                            "entities": self._extract_entities(user_query)
                        }
                    }]
                    
                    result = await self._add_to_memory(user_message, "User query")
                    if not result:
                        logger.warning("Failed to add user message to memory")
                
                # Format chat history with metadata included in each message
                formatted_messages = []
                for msg in messages:
                    formatted_msg = {
                        "role": msg.role,
                        "content": msg.content,
                        "metadata": {
                            "session_id": session_id,
                            "type": "chat_history",
                            "timestamp": str(asyncio.get_event_loop().time()),
                            "content_type": "conversation_history"
                        }
                    }
                    formatted_messages.append(formatted_msg)
                
                # Add chat history to memory if available
                if formatted_messages and self.is_memory_ready():
                    result = await self._add_to_memory(formatted_messages, "Chat history")
                    if not result:
                        logger.warning("Failed to add chat history to memory")
                
                # Semantic search with compatible approach
                memory_context = {}
                if self.is_memory_ready():
                    conversation_messages = await self._get_from_memory(
                        limit=20, 
                        metadata_filter={"session_id": session_id}
                    )
                    
                    conversation_messages = conversation_messages[:5]
                    
                    if conversation_messages:
                        memory_context['conversation_topics'] = [
                            msg.get("content", "") for msg in conversation_messages 
                            if msg.get("role") == "user"
                        ]
                        
                        if len(user_query.split()) <= 5:
                            memory_context['recent_context'] = [
                                msg.get("content", "") for msg in conversation_messages
                            ]
                
                if self.is_memory_ready() and len(messages) > 20:
                    asyncio.create_task(self._run_memory_maintenance(session_id))

                if memory_context:
                    context['memory_context'] = memory_context
                    
            except Chat.DoesNotExist:
                logger.warning(f"Chat with id {chat_id} not found")
            except Exception as e:
                logger.error(f"Error processing chat history or memory: {e}", exc_info=True)
        try:
            logger.info(f"Classifying intent for: {user_query[:50]}..." if len(user_query) > 50 else user_query)
            intent_result = await self.intent_agent.process(user_query, context)
            context.update(intent_result)
            
            logger.info(f"Orchestrating specialized agents for query with intent: {intent_result.get('intent')}")
            orchestration_result = await self.orchestrator.process(user_query, context)
            context.update(orchestration_result)
            
            logger.info("Synthesizing final response")
            synthesis_result = await self.synthesizer.process(user_query, context)
            
            response = synthesis_result.get('response', 'I apologize, but I was unable to generate a response.')
            logger.info(f"Response generated successfully (source: {synthesis_result.get('source', 'unknown')})")
            
            if chat_id and self.is_memory_ready():
                intent_value = getattr(context.get('intent'), 'value', str(context.get('intent')))
                assistant_message = [{
                    "role": "assistant",
                    "content": response,
                    "metadata": {
                        "session_id": f"chat_{chat_id}",
                        "type": "assistant_response", 
                        "intent": intent_value,
                        "source": synthesis_result.get('source', 'unknown'),
                        "content_type": "answer",
                        "topics": self._extract_entities(response),
                        "has_course_info": bool(context.get("course_search", {}).get("found", False)),
                        "has_pathway_info": bool(context.get("learning_path", {}).get("found", False))
                    }
                }]
                
                result = await self._add_to_memory(assistant_message, "Assistant response")
                if not result:
                    logger.warning("Failed to add assistant response to memory")
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            return self._fallback_response(user_query)

    async def _run_memory_maintenance(self, session_id):
        """Run memory maintenance tasks in the background with AGNO v1.4.5 compatibility"""
        if not self.is_memory_ready():
            logger.warning("Memory maintenance skipped - memory system not available")
            return
            
        try:
            all_messages = await self._get_from_memory(
                limit=1000, 
                metadata_filter={"session_id": session_id}
            )
            
            if len(all_messages) > 100:
                logger.info(f"Pruning memory for session {session_id}, found {len(all_messages)} messages")
                logger.info(f"Memory maintenance would prune {len(all_messages) - 100} messages")
            
            logger.debug(f"Memory maintenance completed for session {session_id}")
        except Exception as e:
            logger.error(f"Error in memory maintenance: {e}", exc_info=True)

    async def _add_to_memory(self, messages, log_prefix=""):
        """
        Safe wrapper for memory operations with AGNO v1.4.5 compatibility
        
        Args:
            messages: List of message objects to add to memory
            log_prefix: Prefix for log messages
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_memory_ready():
            logger.warning(f"{log_prefix}: Memory system is not initialized; skipping memory operation.")
            return False
            
        try:
            if not isinstance(messages, list):
                logger.warning(f"{log_prefix}: Messages must be a list, got {type(messages)}")
                if isinstance(messages, dict):
                    messages = [messages]
                else:
                    return False
            
            validated_messages = []
            for msg in messages:
                if not isinstance(msg, dict):
                    logger.warning(f"{log_prefix}: Skipping non-dict message: {msg}")
                    continue
                    
                if 'role' not in msg or 'content' not in msg:
                    logger.warning(f"{log_prefix}: Message missing role or content: {msg}")
                    continue
                
                if 'metadata' not in msg:
                    metadata = {k: v for k, v in msg.items() if k not in ['role', 'content']}
                    if metadata:
                        msg['metadata'] = metadata
                
                validated_messages.append(msg)
                
            if not validated_messages:
                logger.warning(f"{log_prefix}: No valid messages to add")
                return False
                
            success = False
            
            if hasattr(self.memory, 'add_messages'):
                try:
                    self.memory.add_messages(messages=validated_messages)
                    success = True
                except Exception as e:
                    logger.warning(f"{log_prefix}: Error using add_messages: {e}")
            
            if not success and hasattr(self.memory, 'messages') and isinstance(self.memory.messages, list):
                try:
                    self.memory.messages.extend(validated_messages)
                    success = True
                except Exception as e:
                    logger.warning(f"{log_prefix}: Error extending memory.messages: {e}")
            
            if not success and hasattr(self.memory, 'add_message'):
                errors = 0
                for msg in validated_messages:
                    try:
                        self.memory.add_message(msg)
                    except Exception as e:
                        errors += 1
                        logger.warning(f"{log_prefix}: Error adding individual message: {e}")
                
                if errors < len(validated_messages):
                    success = True
            
            if success:
                logger.debug(f"{log_prefix}: Added {len(validated_messages)} messages to memory")
                return True
            else:
                logger.warning(f"{log_prefix}: Failed to add messages through any available method")
                return False
                
        except Exception as e:
            logger.error(f"Error adding messages to memory ({log_prefix}): {e}", exc_info=True)
            return False

    async def _get_from_memory(self, limit=20, metadata_filter=None):
        """
        Safe wrapper for memory retrieval with AGNO v1.4.5 compatibility
        
        Args:
            limit: Maximum number of messages to retrieve (may not be used in v1.4.5)
            metadata_filter: Dictionary of metadata key-value pairs to filter by
            
        Returns:
            List of messages, or empty list if no memory or error
        """
        if not self.is_memory_ready():
            logger.warning("Memory system is not initialized; skipping memory retrieval.")
            return []
        try:
            if hasattr(self.memory, 'get_messages'):
                try:
                    all_messages = self.memory.get_messages()
                except AttributeError as e:
                    # AGNO expects message objects with model_dump, but found dicts
                    logger.warning(f"model_dump missing on message objects, returning raw messages: {e}")
                    if hasattr(self.memory, 'messages'):
                        all_messages = self.memory.messages
                    else:
                        all_messages = []
                if metadata_filter:
                    filtered_messages = []
                    for msg in all_messages:
                        msg_metadata = msg.get('metadata', {})
                        if not msg_metadata and isinstance(msg, dict):
                            msg_metadata = {k: v for k, v in msg.items() if k not in ['role', 'content']}
                        matches = True
                        for key, value in metadata_filter.items():
                            if key not in msg_metadata or msg_metadata[key] != value:
                                matches = False
                                break
                        if matches:
                            filtered_messages.append(msg)
                    return filtered_messages[:limit] if filtered_messages else []
                else:
                    return all_messages[:limit] if all_messages else []
            elif hasattr(self.memory, 'messages'):
                all_messages = self.memory.messages
                if metadata_filter:
                    messages = []
                    for msg in all_messages:
                        msg_metadata = msg.get('metadata', {})
                        if not msg_metadata and 'role' in msg and 'content' in msg:
                            msg_metadata = {k: v for k, v in msg.items() if k not in ['role', 'content']}
                        matches = True
                        for key, value in metadata_filter.items():
                            if key not in msg_metadata or msg_metadata[key] != value:
                                matches = False
                                break
                        if matches:
                            messages.append(msg)
                else:
                    messages = all_messages
                return messages[:limit] if messages else []
            elif hasattr(self.memory, 'get_user_memories') and metadata_filter and 'session_id' in metadata_filter:
                try:
                    session_id = metadata_filter.get('session_id')
                    user_id = session_id.replace('chat_', '') if session_id.startswith('chat_') else session_id
                    user_memories = self.memory.get_user_memories(user_id=user_id)
                    formatted_memories = []
                    for memory in user_memories:
                        if isinstance(memory, dict):
                            if 'content' in memory and 'role' not in memory:
                                formatted_memory = {
                                    'role': 'system',
                                    'content': memory.get('content', ''),
                                    'metadata': {
                                        'session_id': session_id,
                                        'type': 'memory',
                                        'timestamp': memory.get('timestamp', str(asyncio.get_event_loop().time()))
                                    }
                                }
                                formatted_memories.append(formatted_memory)
                            else:
                                formatted_memories.append(memory)
                    return formatted_memories[:limit] if formatted_memories else []
                except Exception as e:
                    logger.warning(f"Error getting user memories: {e}")
                    return []
            logger.warning("No compatible memory retrieval method found")
            return []
        except Exception as e:
            logger.error(f"Error retrieving messages from memory: {e}", exc_info=True)
            return []

    def _extract_entities(self, text):
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
        return f"""I apologize, but I encountered an issue while processing your question about "{query}".

I'm Guideon, specialized in the Philippine Skills Framework for Analytics & AI (PSF-AAI), and I can help with:
- Information about analytics and AI career roles
- Details about skills and competencies in the PSF-AAI framework
- Career progression pathways and learning recommendations

Please try asking your question in a different way, or ask me about specific aspects of the PSF-AAI framework."""

def query_ollama(user_prompt: str, chat_id=None) -> str:
    service = GuideonChatService()
    try:
        response = asyncio.run(service.process_message(user_prompt, chat_id=chat_id))
        return response
    except Exception as e:
        logging.error(f"Failed to process query via query_ollama: {e}", exc_info=True)
        return "Sorry, I encountered an error while processing your query."

