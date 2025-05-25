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
    SYSTEM_PROMPT = (
        "You are an AI assistant specialized in topic extraction for a learning platform. "
        "Your goal is to identify the specific subject, skill, or concept a user wants to learn about from their query. "
        "Focus on extracting the core learning topic, omitting conversational fluff or generic phrases like 'I want to learn about'. "
        "If the query is too vague or doesn't specify a clear topic, return an empty string. "
        "For example, if the query is 'Tell me about data science courses', extract 'data science'. "
        "If the query is 'What is Python?', extract 'Python'. "
        "If the query is 'courses' or 'something to learn', return an empty string."
    )

    def __init__(self) -> None:
        """Initialize with LLM for topic extraction."""
        try:
            self.llm = Ollama(id="llama3.1:8b-instruct-q4_1",
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
        llm_extracted_topic = "" # Store LLM's direct output

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

                # If LLM explicitly returns empty, it likely means the query was generic as per prompt instructions.
                if not llm_extracted_topic:
                    logger.info(f"LLM returned empty string for query '{query}', indicating a generic request. Returning empty for clarification.")
                    return "" # Trust LLM's empty output for generic queries

            except Exception as e:
                logger.exception(f"Error during LLM topic extraction: {e}")
                # llm_extracted_topic will remain empty, allowing fallback
        
        # If LLM extraction resulted in a topic, use it after validation
        if llm_extracted_topic:
            topic_candidate = llm_extracted_topic
        else: # Fallback to rule-based if LLM failed or wasn't used
            topic_candidate = self._rule_based_extraction(query)
            logger.debug(f"Rule-based topic extraction candidate: '{topic_candidate}'")

        # Final validation for the chosen candidate (either from LLM or rule-based)
        cleaned_topic_candidate = topic_candidate.lower().strip()
        
        # More robust check for generic queries, especially if they are very similar to the original query
        # when the original query itself was generic.
        generic_phrases = ["course", "courses", "some courses", "any courses", "give me courses", "find courses"]
        is_generic_phrase = any(phrase == cleaned_topic_candidate for phrase in generic_phrases)
        
        # Check if the cleaned topic is one of the generic phrases or too short (e.g., less than 3 chars like "AI", "SQL" are okay)
        if is_generic_phrase or \
           cleaned_topic_candidate == "" or \
           (len(cleaned_topic_candidate) > 0 and len(cleaned_topic_candidate) < 3 and cleaned_topic_candidate not in ['ai', 'r', 'go', 'c#', 'c++']): # Allow specific short topics
            logger.info(f"Final topic candidate '{topic_candidate}' (cleaned: '{cleaned_topic_candidate}') is generic or too short. Returning empty string for clarification.")
            return ""
                
        logger.info(f"Successfully extracted topic: '{topic_candidate}' from query: '{query}'")
        return topic_candidate.strip()

    def _create_extraction_prompt(self, query: str) -> str:
        """Create a prompt for topic extraction."""
        # Keep your existing prompt, it's good.
        # It correctly instructs the LLM to return "" for generic course requests.
        return f"""# Topic Extraction Task

## Query:
"{query}"

## Instructions:
Extract the specific subject or topic the user wants to learn about from this query.
Return ONLY the topic name, nothing else. No explanations, preambles, or additional text.
"Courses" or "course" itself is not a specific learning topic, so if the query is just asking for courses in general (e.g., "I want to learn about courses", "give me courses"), return an empty string.
If the query is too generic or doesn't specify a topic, return an empty string.

For example:
- For "I want to learn about Python programming", return only "Python programming"
- For "Find me courses about data analysis", return only "data analysis"
- For "Show me some resources on machine learning", return only "machine learning"
- For "courses", return ""
- For "give me courses", return ""
Topic:
"""

    def _rule_based_extraction(self, query: str) -> str:
        """
        Simple rule-based topic extraction when LLM is unavailable or fails.
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
                topic_candidate_lower = query_lower.split(pattern, 1)[1].strip()
                
                # Attempt to get original casing from the original query
                # Find the start index of the topic in the original query
                try:
                    original_query_topic_start_index = query_lower.find(topic_candidate_lower, len(pattern))
                    if original_query_topic_start_index != -1:
                        # Extract the substring from the original query
                        topic_original_casing = query[original_query_topic_start_index : original_query_topic_start_index + len(topic_candidate_lower)]
                        topic_to_return = topic_original_casing.split("please")[0].strip().rstrip(".!?,;")
                    else: # Fallback if precise original casing can't be found
                        topic_to_return = topic_candidate_lower.split("please")[0].strip().rstrip(".!?,;")
                except: # Fallback if any error occurs
                     topic_to_return = topic_candidate_lower.split("please")[0].strip().rstrip(".!?,;")


                if topic_to_return: # Check if topic is not empty after stripping
                    logger.info(f"Rule-based extraction found topic candidate: '{topic_to_return}'")
                    return topic_to_return
        
        logger.warning(f"No rule-based pattern matched for '{query}'. Using full query as candidate for final validation.")
        return query # Return the original query for the final validation step