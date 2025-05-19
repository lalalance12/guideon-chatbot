import logging
import asyncio
from django.conf import settings
from agno.agent import Agent
from agno.models.ollama import Ollama
from .agents.intent_classifier_agent import IntentClassifierAgent
from .agents.orchestrator_agent import OrchestratorAgent
from .agents.response_synthesizer_agent import ResponseSynthesizerAgent
from .models import Chat, Message
from .utils.embeddings import generate_embedding
# Import the ChatHistoryManager at the top of the file
from .utils.chat_history_manager import ChatHistoryManager
logger = logging.getLogger(__name__)

class GuideonChatService:
    def __init__(self):
        self.intent_agent = IntentClassifierAgent()
        self.orchestrator = OrchestratorAgent()
        self.synthesizer = ResponseSynthesizerAgent()
        self.agno_agent = None
        self._init_agent()

    def _init_agent(self):
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
                # Pass the user_query to get semantically relevant history
                chat_history = await self._get_chat_history(chat_id, user_query)
                if chat_history:
                    context['chat_history'] = chat_history
                    logger.info(f"Retrieved {len(chat_history)} message(s) for chat history")
                    # Log a sample to help debugging
                    if len(chat_history) > 0:
                        logger.debug(f"First message: {chat_history[0].get('text')[:50]}...")
                else:
                    logger.info("No chat history found")
            except Exception as e:
                logger.error(f"Error retrieving chat history: {e}")
        
        try:
            # Step 1: Determine user intent using the LLM-based classifier
            intent_result = await self.intent_agent.process(user_query, context)
            
            # Update context with intent classification results
            context['intent'] = intent_result['intent']
            context['intent_confidence'] = intent_result['confidence']
            context['extracted_entities'] = intent_result.get('extracted_entities', {})
            
            logger.info(f"Classified intent: {context['intent']} (confidence: {context['intent_confidence']})")
            
            # Step 2: Orchestrate specialized agents based on intent
            orchestrator_result = await self.orchestrator.process(user_query, context)
            
            # Make sure we have the updated context with flow information
            if isinstance(orchestrator_result, dict) and 'context' in orchestrator_result:
                context = orchestrator_result['context']
            else:
                # Just update context with whatever we got
                context.update(orchestrator_result)
            
            # Step 3: Synthesize the final response
            response_result = await self.synthesizer.process(user_query, context)
            
            # Extract the actual response text
            if isinstance(response_result, dict):
                response_text = response_result.get('response_text', str(response_result))
            else:
                response_text = str(response_result)

            # Save messages to database if chat_id provided
            if chat_id:
                try:
                    # Get or create chat
                    chat, created = await Chat.objects.aget_or_create(id=chat_id)
                    
                    # Generate embeddings for both messages
                    user_embedding = await generate_embedding(user_query)
                    response_embedding = await generate_embedding(response_text)
                    
                    # Create user message with embedding
                    await Message.objects.acreate(
                        chat=chat,
                        content=user_query,
                        role="user",
                        embedding=user_embedding
                    )
                    
                    # Create assistant message with embedding
                    await Message.objects.acreate(
                        chat=chat,
                        content=response_text,
                        role="assistant",
                        embedding=response_embedding
                    )
                    
                    logger.info(f"Stored messages with embeddings in database for chat {chat_id}")
                except Exception as e:
                    logger.error(f"Failed to store messages in database: {e}")
            
            return response_text
            
        except Exception as e:  
            logger.error(f"Error processing message: {e}", exc_info=True)
            return self._fallback_response(user_query)


    async def _get_chat_history(self, chat_id, user_query=None):
        """Retrieve chat history for context building from database"""
        try:
            if not chat_id:
                return []
                
            # Use simple history approach instead of semantic/hybrid
            chat_history = await ChatHistoryManager.get_simple_history(chat_id=chat_id)
            logger.info(f"Retrieved {len(chat_history)} messages using simple history approach")
            return chat_history
            
        except Exception as e:
            logger.error(f"Error retrieving chat history: {e}")
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

_service = GuideonChatService()

def query_ollama(user_prompt: str, chat_id=None) -> str:
    try:
        return asyncio.run(_service.process_message(user_prompt, chat_id=chat_id))
    except Exception as e:
        logging.exception("query_ollama failed")
        return f"Sorry, I encountered an error while processing your query: {str(e)}"