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
        
        embedder = OllamaEmbedder()
        
        # Initialize new Agno memory components with proper database connection
        db_settings = settings.DATABASES['default']
        dsn = f"postgresql://{db_settings['USER']}:{db_settings['PASSWORD']}@{db_settings['HOST']}:{db_settings['PORT']}/{db_settings['NAME']}"
        
        # Create SQLAlchemy engine for AGNO
        db_engine = create_engine(dsn)
        
        # Initialize PgMemoryDb with required parameters
        pg_db = PgMemoryDb(
            table_name="guideon_chat_memory",
            db_engine=db_engine,
            embedder=embedder
        )

        # Store the db instance if needed elsewhere
        self.agent_db = pg_db
        
        # Initialize AGNO AgentMemory
        # The user's example shows AgentMemory(db=PgMemoryDb(), ...),
        # it might take other params like history config.
        self.memory = AgentMemory(db=self.agent_db)
        
        # Initialize AGNO agent with the new memory system
        self.agno_agent = Agent(
            name="ServicesAGNOAgent",
            model=None, # Still a placeholder, needs a proper model
            memory=self.memory # Using the new AgentMemory instance
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
                chat = await Chat.objects.aget(id=chat_id)
                messages = [msg async for msg in chat.messages.all().order_by('timestamp')]
                context['chat_history'] = messages
                
                session_id = f"chat_{chat_id}"
                
                # NOTE: The API for self.memory.add and self.memory.search might have changed
                # with AgentMemory. This section will likely need review and updates
                # based on the new Agno API.

                # Add current query to memory
                # Assuming AgentMemory has an 'add' method similar to the old one.
                # It might now require different parameters or structure.
                await self.memory.add( # Assuming add is now async or we need to wrap it
                    session_id=session_id,
                    texts=[user_query], # AgentMemory might expect a list of texts
                    metadata=[{ # And a list of metadata
                        "type": "user_query", 
                        "timestamp": str(asyncio.get_event_loop().time()),
                        "content_type": "question",
                        "entities": self._extract_entities(user_query)
                    }]
                )
                
                # Add chat history to memory
                # This loop also needs to be checked against AgentMemory's API
                history_texts = []
                history_metadata = []
                for msg in messages:
                    # Simplified check, assuming AgentMemory's search might be different
                    # existing_messages = await self.memory.search(session_id=session_id, query=msg.content[:50], limit=1)
                    # if not any(mem.content == msg.content for mem in existing_messages): # This comparison might fail
                    
                    msg_meta = {
                        "type": "message", 
                        "role": msg.role,
                        "timestamp": str(msg.timestamp) if hasattr(msg, 'timestamp') else "",
                        "content_type": "question" if msg.role == "user" else "answer",
                    }
                    if msg.role == "user":
                        msg_meta["entities"] = self._extract_entities(msg.content)
                    
                    history_texts.append(msg.content)
                    history_metadata.append(msg_meta)

                if history_texts:
                    await self.memory.add(
                        session_id=session_id,
                        texts=history_texts,
                        metadata=history_metadata
                    )
                
                memory_context = {}
                
                # Semantic search calls also need to be updated for AgentMemory's API
                # Example:
                # conversation_context_results = await self.memory.search(
                #     session_id=session_id,
                #     query="What are the main topics...",
                #     limit=3
                # )
                # if conversation_context_results:
                #    memory_context['conversation_topics'] = [res.text for res in conversation_context_results] # or res.content

                # For now, commenting out the memory search part as it needs API verification
                # conversation_context = self.memory.search(...)
                # if conversation_context:
                #     memory_context['conversation_topics'] = [mem.content for mem in conversation_context]
                
                # user_preferences = self.memory.search(...)
                # if user_preferences:
                #     memory_context['user_preferences'] = [mem.content for mem in user_preferences]

                # if len(user_query.split()) <= 5:
                #    recent_context = self.memory.search(...)
                #    semantic_context = self.memory.search(...)
                #    ...
                #    if follow_up_context:
                #        memory_context['recent_context'] = [mem.content for mem in follow_up_context]
                
                # Summary fetching might also change if AgentMemory handles it internally or via PgMemoryDb
                # if len(messages) > 20:
                #     await self._run_memory_maintenance(session_id) # This called self.storage which is gone
                #     # Direct DB query might still work if PgMemoryDb creates similar tables,
                #     # but ideally AgentMemory provides an API for summaries.
                #     # with self.agent_db._get_connection() as cursor: # This is an assumption
                #     # ...

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
            
            if chat_id:
                intent_value = getattr(context.get('intent'), 'value', str(context.get('intent')))
                # Adding response to memory - check AgentMemory API
                await self.memory.add( # Assuming add is async
                    session_id=f"chat_{chat_id}",
                    texts=[response],
                    metadata=[{
                        "type": "assistant_response", 
                        "role": "assistant",
                        "intent": intent_value,
                        "source": synthesis_result.get('source', 'unknown'),
                        "content_type": "answer",
                        "topics": self._extract_entities(response),
                        "has_course_info": bool(context.get("course_search", {}).get("found", False)),
                        "has_pathway_info": bool(context.get("learning_path", {}).get("found", False))
                    }]
                )
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True) # Added exc_info
            return self._fallback_response(user_query)
    
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
    
    async def _run_memory_maintenance(self, session_id):
        """Run memory maintenance tasks in the background"""
        # This method needs to be re-evaluated.
        # The old self.storage.summarize_and_prune is gone.
        # PgMemoryDb or AgentMemory might have their own maintenance/pruning methods.
        logger.warning(f"_run_memory_maintenance for session {session_id} needs to be updated for new Agno memory API.")
        # try:
        #     await asyncio.to_thread(
        #         self.agent_db.summarize_and_prune, # This is a guess, API unknown
        #         session_id=session_id,
        #         max_items=100,
        #         older_than_hours=24
        #     )
        #     logger.debug(f"Memory maintenance completed for session {session_id}")
        # except Exception as e:
        #     logger.error(f"Error in memory maintenance: {e}", exc_info=True)
    
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