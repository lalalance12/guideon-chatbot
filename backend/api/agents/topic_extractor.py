from __future__ import annotations
from typing import Dict, Any, Optional
import logging
import asyncio

from agno.agent import Agent
from agno.models.ollama import Ollama

logger = logging.getLogger(__name__)

class TopicExtractor:
    """
    Extracts the specific topic that a user wants to learn about from their query.
    This is used to pass a clean topic string to the CourseSearchAgent.
    """

    def __init__(self) -> None:
        """Initialize with LLM for topic extraction."""
        try:
            self.llm = Ollama(id="llama3.1:8b-instruct-q8_0",
                              provider="Ollama", 
                              host="http://localhost:11434")
            self.agent = Agent(
                name="TopicExtractor", 
                model=self.llm,
                system_message="You are an assistant that extracts learning topics from user queries."
            )
            logger.info("Topic extractor initialized with LLM")
        except Exception as e:
            logger.error(f"Failed to initialize topic extractor LLM: {e}")
            self.agent = None
            logger.warning("Will fall back to rule-based topic extraction")

    async def extract_topic(self, query: str) -> str:
        """
        Extract the specific learning topic from a user query.
        
        Args:
            query: The raw user query (e.g., "I want to learn about python programming")
            
        Returns:
            The extracted topic (e.g., "python programming")
        """
        if not self.agent:
            return self._rule_based_extraction(query)
            
        prompt = self._create_extraction_prompt(query)
        
        try:
            # Generate extraction with LLM
            if hasattr(self.agent, "arun"):
                run_response = await self.agent.arun(prompt)
            else:
                # Fall back to threaded run() if arun() isn't available
                run_response = await asyncio.to_thread(self.agent.run, prompt)
                
            # Extract content safely
            response = getattr(run_response, "content", str(run_response))
            logger.debug(f"LLM topic extraction response: {response}")
            
            # Clean up the response - we want just the topic
            topic = response.strip()
            # Remove any formatting or explanations
            if ":" in topic:
                topic = topic.split(":", 1)[1].strip()
            if "\n" in topic:
                topic = topic.split("\n", 1)[0].strip()
                
            # Remove quotes if present
            topic = topic.strip('"\'')
            
            if not topic or len(topic) < 2:
                logger.warning(f"Failed to extract meaningful topic, falling back to rule-based")
                return self._rule_based_extraction(query)
                
            logger.info(f"Extracted topic: '{topic}' from query: '{query}'")
            return topic
            
        except Exception as e:
            logger.exception(f"Error during topic extraction: {e}")
            return self._rule_based_extraction(query)
    
    def _create_extraction_prompt(self, query: str) -> str:
        """Create a prompt for topic extraction."""
        return f"""# Topic Extraction Task

## Query:
"{query}"

## Instructions:
Extract the specific subject or topic the user wants to learn about from this query. 
Return ONLY the topic name, nothing else. No explanations, preambles, or additional text.

For example:
- For "I want to learn about Python programming", return only "Python programming"
- For "Find me courses about data analysis", return only "data analysis"
- For "Show me some resources on machine learning", return only "machine learning"
Topic:
"""

    def _rule_based_extraction(self, query: str) -> str:
        """
        Simple rule-based topic extraction when LLM is unavailable.
        Uses keyword matching to identify topics.
        """
        query = query.lower()
        
        # List of patterns to search for
        patterns = [
            "learn about ", 
            "courses on ", 
            "courses about ",
            "learn ", 
            "study ",
            "resources on ",
            "resources for ",
            "find me courses on ",
            "find me courses about ",
            "interested in learning ",
            "want to know about "
        ]
        
        for pattern in patterns:
            if pattern in query:
                # Extract the text after the pattern
                topic = query.split(pattern, 1)[1].strip()
                # Remove trailing punctuation and words like "please"
                topic = topic.split("please")[0].strip().rstrip(".!?,;")
                if topic:
                    logger.info(f"Rule-based extraction found topic: '{topic}'")
                    return topic
        
        # If no clear pattern is found, return the full query as a fallback
        logger.warning(f"Could not extract topic with rules, using full query")
        return query