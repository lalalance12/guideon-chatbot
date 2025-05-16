import logging
import asyncio
from django.conf import settings
from agno.agent import Agent
from agno.memory.v2.memory import Memory
from agno.memory.v2.db.postgres import PostgresMemoryDb
from agno.storage.postgres import PostgresStorage
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
        self.memory_db = None
        self.storage = None
        self.agno_agent = None
        self._init_memory_and_storage()
        self._init_agent()

    def _init_memory_and_storage(self):
        """Initialize the memory and storage system for AGNO v1.4.5"""
        try:
            # Get database connection parameters from Django settings
            db_settings = settings.DATABASES['default']
            db_url = f"postgresql://{db_settings['USER']}:{db_settings['PASSWORD']}@{db_settings['HOST']}:{db_settings['PORT']}/{db_settings['NAME']}"
            
            # Initialize memory database
            self.memory_db = PostgresMemoryDb(
                table_name="guideon_user_memories",
                db_url=db_url,
                schema=db_settings.get('SCHEMA', 'public')  # Use schema from settings or default to 'public'
            )
            
            # Initialize storage for session history
            self.storage = PostgresStorage(
                table_name="guideon_agent_sessions",
                db_url=db_url,
                schema=db_settings.get('SCHEMA', 'public')
            )
            
            # Initialize the memory manager with Ollama model
            try:
                from agno.models.ollama import Ollama
                llama_model = Ollama(id="llama3.2:latest", provider="Ollama", host="http://localhost:11434")
                self.memory = Memory(
                    model=llama_model,
                    db=self.memory_db
                )
                logger.info("AGNO memory system initialized successfully with Llama 3.2")
            except Exception as model_e:
                logger.error(f"Failed to initialize memory with Llama model: {model_e}", exc_info=True)
                # Try to initialize memory without a model
                self.memory = Memory(db=self.memory_db)
                logger.info("AGNO memory system initialized WITHOUT model")
                
            return True
        except Exception as e:
            logger.error(f"Failed to initialize AGNO memory and storage: {e}", exc_info=True)
            self.memory = None
            self.memory_db = None
            self.storage = None
            return False

    def is_memory_ready(self):
        """Utility to check if memory is initialized and ready."""
        return self.memory is not None

    def _init_agent(self):
        try:
            from agno.models.ollama import Ollama
            # Initialize Ollama model for the agent
            llama_model = Ollama(id="llama3.2:latest", provider="Ollama", host="http://localhost:11434")
            
            # Create the agent with memory and storage configured
            self.agno_agent = Agent(
                name="ServicesAGNOAgent",
                model=llama_model,
                memory=self.memory,
                storage=self.storage,
                enable_agentic_memory=True,
                enable_user_memories=True,
                enable_session_summaries=True,
                add_history_to_messages=True,
                num_history_runs=3,
                markdown=True
            )
            logger.info("AGNO agent initialized successfully with Llama 3.2")
        except Exception as e:
            logger.error(f"Failed to initialize Llama 3.2 model: {e}", exc_info=True)
            try:
                # Fallback initialization with minimal parameters
                self.agno_agent = Agent(
                    name="ServicesAGNOAgent",
                    model=None,
                    memory=self.memory,
                    storage=self.storage
                )
                logger.info("AGNO agent initialized with minimal configuration")
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
        if chat_id and self.is_memory_ready():
            try:
                # Retrieve chat history using the new v1.4.5 API
                user_id = str(chat_id)  # Convert UUID to string
                if isinstance(user_id, str) and user_id.startswith('chat_'):
                    user_id = user_id.replace('chat_', '')
                    
                # Get stored memories for this user
                if self.memory and hasattr(self.memory, 'get_user_memories'):
                    chat_history = self.memory.get_user_memories(user_id=user_id)
                    context['chat_history'] = chat_history
            except Exception as e:
                logger.error(f"Error retrieving chat history: {e}")
        
        try:
            # Step 1: Determine user intent using the LLM-based classifier
            intent_result = await self.intent_agent.process(user_query, context)
            
            # Update context with intent classification results
            context['intent'] = intent_result['intent']
            context['intent_confidence'] = intent_result['confidence']
            context['entities'] = intent_result.get('extracted_entities', {})
            
            logger.info(f"Classified intent: {context['intent']} (confidence: {context['intent_confidence']})")
            
            # Step 2: Orchestrate specialized agents based on intent
            orchestrator_result = await self.orchestrator.process(user_query, context)
            context.update(orchestrator_result)
            
            # Step 3: Synthesize the final response
            response = await self.synthesizer.process(user_query, context)
            
            # Store conversation in memory using v1.4.5 API
            if chat_id and self.is_memory_ready() and self.agno_agent:
                user_id = str(chat_id)  # Convert UUID to string
                if isinstance(user_id, str) and user_id.startswith('chat_'):
                    user_id = user_id.replace('chat_', '')
                
                # Store the interaction in memory
                try:
                    # Use the agent's API to store the interaction
                    asyncio.create_task(self._store_interaction(user_id, user_query, response))
                except Exception as mem_e:
                    logger.error(f"Error storing memory: {mem_e}", exc_info=True)
            
            return response
            
        except Exception as e:  
            logger.error(f"Error processing message: {e}")
            return self._fallback_response(user_query)

    async def _store_interaction(self, user_id, user_query, response):
        """Store an interaction in the agent's memory system"""
        try:
            # Ensure user_id is a string
            user_id = str(user_id)
            
            if self.agno_agent:
                # Use the agent's API to process the message and store it
                # This will handle storing in both memory and storage
                await self.agno_agent.generate_response(
                    user_query,
                    user_id=user_id,
                    stream=False
                )
                
                # If the agent's response is different from our synthesized response,
                # we may want to explicitly store our synthesized response
                if hasattr(self.memory, 'add_memory'):
                    self.memory.add_memory(
                        user_id=user_id,
                        content=f"User asked: {user_query}\nGuideon responded: {response}"
                    )
            elif self.memory and hasattr(self.memory, 'add_memory'):
                # Direct memory storage if agent isn't available
                self.memory.add_memory(
                    user_id=user_id,
                    content=f"User asked: {user_query}\nGuideon responded: {response}"
                )
        except Exception as e:
            logger.error(f"Error storing interaction: {e}", exc_info=True)

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

