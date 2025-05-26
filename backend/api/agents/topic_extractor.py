from __future__ import annotations
from typing import Dict, Any, Optional
import logging
import asyncio
import re

from agno.agent import Agent
from agno.models.ollama import Ollama

logger = logging.getLogger(__name__)

class TopicExtractor:
    """
    Extracts the specific topic that a user wants to learn about from their query.
    This is used to pass a clean topic string to the CourseSearchAgent.
    """
    SYSTEM_PROMPT = (
        "You are an AI assistant specialized in topic extraction for a learning platform. "
        "Your goal is to identify the specific subject, skill, or concept a user wants to learn about from their query. "
        "ONLY RETURN THE EXACT TOPIC - nothing else. NO explanations, NO commentary, NO introduction phrases. "
        "Focus on extracting the core learning topic, omitting conversational fluff or generic phrases like 'I want to learn about'. "
        "If the query is too vague or doesn't specify a clear topic, return an empty string. "
        "For example, if the query is 'Tell me about data science courses', extract ONLY 'data science'. "
        "If the query is 'What is Python?', extract ONLY 'Python'. "
        "If the query is 'courses' or 'something to learn', return an empty string."
    )

    def __init__(self) -> None:
        """Initialize with LLM for topic extraction."""
        try:
            self.llm = Ollama(id="llama3.1:8b-instruct-q2_K",
                              provider="Ollama", 
                              host="http://localhost:11434")
            self.agent = Agent(
                name="TopicExtractor", 
                model=self.llm,
                system_message=self.SYSTEM_PROMPT
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
            The extracted topic (e.g., "python programming") or an empty string if too generic or unextractable.
        """
        # First try with direct pattern matching for common "courses for X" patterns
        direct_topic = self._direct_pattern_extraction(query)
        if direct_topic:
            logger.info(f"Direct pattern extraction found topic: '{direct_topic}' from query: '{query}'")
            return direct_topic

        # Then try with LLM
        if self.agent:
            prompt = self._create_extraction_prompt(query)
            try:
                if hasattr(self.agent, "arun"):
                    run_response = await self.agent.arun(prompt)
                else:
                    run_response = await asyncio.to_thread(self.agent.run, prompt)
                
                response_text = getattr(run_response, "content", str(run_response))
                
                # Clean up the response
                llm_extracted_topic = response_text.strip()
                if ":" in llm_extracted_topic:
                    llm_extracted_topic = llm_extracted_topic.split(":", 1)[1].strip()
                if "\n" in llm_extracted_topic:
                    llm_extracted_topic = llm_extracted_topic.split("\n", 1)[0].strip()
                llm_extracted_topic = llm_extracted_topic.strip('"\'')
                
                logger.debug(f"LLM topic extraction candidate: '{llm_extracted_topic}' from query: '{query}'")

                # VALIDATION: Check if response looks like explanatory text
                if self._is_explanatory_text(llm_extracted_topic):
                    logger.warning(f"LLM returned explanatory text instead of a topic: '{llm_extracted_topic}'")
                    # Try the direct pattern extraction again as a fallback
                    direct_topic = self._direct_pattern_extraction(query)
                    if direct_topic:
                        return direct_topic
                    # If that fails too, try the rule-based extraction
                    return self._rule_based_extraction(query)
                
                # Verify the topic is reasonable (not too long, not explanatory)
                if len(llm_extracted_topic.split()) > 6:
                    logger.warning(f"LLM returned overly long topic: '{llm_extracted_topic}'")
                    # Try the direct pattern extraction as a fallback
                    direct_topic = self._direct_pattern_extraction(query)
                    if direct_topic:
                        return direct_topic
                    return self._rule_based_extraction(query)

                # If LLM explicitly returns empty, it likely means the query was generic.
                if not llm_extracted_topic:
                    logger.info(f"LLM returned empty string for query '{query}', indicating a generic request. Returning empty for clarification.")
                    return "" # Trust LLM's empty output for generic queries

                return llm_extracted_topic

            except Exception as e:
                logger.exception(f"Error during LLM topic extraction: {e}")
                # Fallback to rule-based extraction
                return self._rule_based_extraction(query)
        
        # If LLM is not available, fall back to rule-based extraction
        return self._rule_based_extraction(query)

    def _is_explanatory_text(self, text: str) -> bool:
        """Check if the text appears to be explanatory rather than a direct topic."""
        explanatory_patterns = [
            "this is", "i've extracted", "the answer", "the topic", 
            "please let me know", "would like", "i can", "identified", 
            "from your query", "response", "should be", "here's", "here is",
            "specific topic", "extracted", "as the answer", "if you'd like"
        ]
        
        # Check for common explanatory phrases
        if any(pattern in text.lower() for pattern in explanatory_patterns):
            return True
            
        # Check if it's too long to be a topic
        if len(text.split()) > 8:
            return True
            
        # Check for sentence structures with subjects and verbs
        if re.search(r'\b(I|you|we|they|he|she|it)\b.*\b(is|am|are|was|were|will|can|could|would|should)\b', text, re.IGNORECASE):
            return True
            
        return False

    def _create_extraction_prompt(self, query: str) -> str:
        """Create a prompt for topic extraction."""
        return f"""# Topic Extraction Task

## Query:
"{query}"

## Instructions:
Extract the specific subject or topic the user wants to learn about from this query.
Return ONLY the topic name, NOTHING ELSE. No explanations, no preambles, no analysis.
Your entire response must be ONLY the extracted topic - a single phrase or word.

For "Give me courses for data analyst", return ONLY: data analyst
For "I want to learn Python programming", return ONLY: Python programming
For "Tell me about artificial intelligence", return ONLY: artificial intelligence

If the query is too generic, return an empty string.

Topic:"""

    def _direct_pattern_extraction(self, query: str) -> str:
        """Extract topics from common query patterns."""
        query_lower = query.lower()
        
        # For "Give me courses for X" pattern
        if "courses for " in query_lower:
            topic = query_lower.split("courses for ", 1)[1].strip().rstrip("?!.,;:")
            return topic
        
        # For "Show me X courses" pattern
        match = re.search(r"show me (.*?) courses", query_lower)
        if match:
            return match.group(1).strip()
            
        # For "I want to learn X" pattern
        if "learn " in query_lower:
            topic = query_lower.split("learn ", 1)[1].strip().rstrip("?!.,;:")
            return topic
        
        return ""  # No direct pattern matched

    def _rule_based_extraction(self, query: str) -> str:
        """
        Rule-based topic extraction when LLM is unavailable or fails.
        Uses keyword matching to identify topics.
        """
        query_lower = query.lower()
        
        patterns = [
            "learn about ", "courses on ", "courses about ", "course on ", "course about ",
            "learn ", "study ", "resources on ", "resources for ",
            "find me courses on ", "find me courses about ",
            "interested in learning ", "want to know about "
        ]
        
        for pattern in patterns:
            if pattern in query_lower:
                # Extract the part after the pattern
                topic_candidate = query_lower.split(pattern, 1)[1].strip().rstrip("?!.,;:")
                
                if topic_candidate: # Check if topic is not empty after stripping
                    logger.info(f"Rule-based extraction found topic candidate: '{topic_candidate}'")
                    return topic_candidate
        
        logger.warning(f"No rule-based pattern matched for '{query}'.")
        return ""  # Return empty string if no pattern matched