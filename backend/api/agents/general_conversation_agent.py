from .base_agent import BaseAgent
import logging
from agno.agent import Agent
from agno.models.ollama import Ollama

logger = logging.getLogger(__name__)

class GeneralConversationAgent(BaseAgent):
    """
    Handles general conversation, chit-chat, jokes, greetings, and non-PSF-AAI queries.
    """
    def __init__(self):
        try:
            self.llm = Ollama(id="llama3.1:8b-instruct-q2_K", provider="Ollama", host="http://localhost:11434")
            self.agent = Agent(
                name="GeneralConversation",
                model=self.llm,
                system_message="You are a helpful, friendly AI assistant for general conversation. Respond naturally and conversationally."
            )
            logger.info("General conversation agent initialized with LLM")
        except Exception as e:
            logger.error(f"Failed to initialize general conversation LLM: {e}")
            self.agent = None

    async def process(self, query: str, context):
        logger.info(f"[GeneralConversationAgent] Processing: {query[:60]}")
        if not self.agent:
            return {"response": "Sorry, I'm unable to chat right now.", "agent_name": "general_conversation"}
        try:
            if hasattr(self.agent, "arun"):
                response = await self.agent.arun(query)
            else:
                import asyncio
                response = await asyncio.to_thread(self.agent.run, query)
            content = getattr(response, "content", str(response))
            return {"response": content, "agent_name": "general_conversation"}
        except Exception as e:
            logger.error(f"GeneralConversationAgent error: {e}")
            return {"response": "Sorry, I had trouble responding.", "agent_name": "general_conversation", "error": str(e)}
