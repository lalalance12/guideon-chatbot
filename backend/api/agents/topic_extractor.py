from __future__ import annotations
from typing import Dict, Any, Optional, List, Union
import logging
import asyncio, re

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

    async def extract_topic(self, query: str, context=None) -> Union[str, List[str]]:
        """Extract the main topic from a search query with context handling."""
        query_lower = query.lower()
        has_context_reference = any(word in query_lower for word in ["that", "it", "this", "those", "them"])
        
        # If we have context references and context is provided, try to find previous topic
        if has_context_reference and context and "chat_history" in context:
            logger.info("Detected context reference. Analyzing chat history for topics.")
            chat_history = context.get("chat_history", [])
            
            # Find most recent assistant message
            for msg in chat_history:
                # Focus on assistant messages
                if not msg.get("is_user", True):
                    msg_text = msg.get("text", "")
                    
                    # Skip empty messages
                    if not msg_text:
                        continue
                        
                    logger.debug(f"Analyzing assistant message for topics: {msg_text[:50]}...")
                    
                    # Use LLM to extract topics from the message
                    from ..utils.chat_history_manager import extract_topics_from_text
                    previous_topics = await extract_topics_from_text(msg_text)
                    
                    if previous_topics:
                        logger.info(f"Found topics in assistant message: {previous_topics}")
                        
                        # If multiple topics found, return the list for further handling
                        if len(previous_topics) > 1:
                            logger.info(f"Multiple topics found in context: {previous_topics}")
                            return previous_topics
                        
                        # If one topic found, return it
                        elif len(previous_topics) == 1:
                            logger.info(f"Using previous topic from context: {previous_topics[0]}")
                            return previous_topics[0]
                    break
        
        # If no context or no topics found in context, proceed with LLM-based extraction
        try:
            # Create a topic extraction prompt
            system_prompt = """You are an expert at extracting learning topics from user queries.
            When a user asks about courses or learning materials, identify the specific topic they want to learn.
            Return ONLY the topic name, no explanation. If no specific topic is mentioned, return an empty string."""
            
            user_prompt = f"""Extract the specific learning topic from this query: "{query}"
            
            Return ONLY the topic name as a single word or short phrase. If no clear topic, return an empty string."""
            
            # Initialize agent if needed
            if not self.agent:
                logger.warning("TopicExtractor agent not initialized, falling back to simple extraction")
                return query.replace("courses", "").replace("about", "").strip()
            
            # Get topic from LLM
            response = await self.agent.arun(user_prompt)
            
            # Extract and clean response
            extracted_topic = response.content if hasattr(response, 'content') else str(response)
            extracted_topic = extracted_topic.strip().strip('"\'').strip()
            
            logger.debug(f"LLM topic extraction result: '{extracted_topic}' from query: '{query}'")
            
            # If empty or invalid, return empty string
            if not extracted_topic or extracted_topic.lower() in ["none", "unclear", "not specified", "n/a"]:
                logger.info("No specific topic found in query")
                return ""
            
            return extracted_topic
        except Exception as e:
            logger.error(f"Error extracting topic: {e}")
            return ""

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