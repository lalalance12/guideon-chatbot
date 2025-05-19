from __future__ import annotations
from typing import Dict, Any, Optional
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

    async def extract_topic(self, query: str, context=None) -> str:
        """Extract the main topic from a search query with context handling."""
        # Check for context references ("that", "it", etc.)
        query_lower = query.lower()
        has_context_reference = any(word in query_lower for word in ["that", "it", "this", "those", "them"])
        
        # If we have context references and context is provided, try to find previous topic
        previous_topic = None
        if has_context_reference and context and "chat_history" in context:
            logger.debug("Detected context reference. Searching chat history for previous topic.")
            chat_history = context.get("chat_history", [])
            
            # Look for previous conversation about skills or topics
            for i, msg in enumerate(chat_history):
                # Skip the current query
                if i == 0 and msg.get("is_user", False):
                    continue
                    
                msg_text = msg.get("text", "")
                
                # Skip empty messages
                if not msg_text:
                    continue
                    
                logger.debug(f"Examining message: {msg_text[:50]}...")
                
                # Check for skill names in assistant messages
                if not msg.get("is_user", True):
                    # Look for mentions of skills in the assistant's messages
                    skill_mentions = re.findall(r'(data\s+science|machine\s+learning|ai|programming|python|statistics|visualization|analytics|communication|problem\s+solving)', msg_text.lower())
                    if skill_mentions:
                        previous_topic = skill_mentions[0]
                        logger.info(f"Found previous topic in assistant message: {previous_topic}")
                        break
                    
                    # Look for "about X" patterns in assistant response
                    about_match = re.search(r'about\s+([a-z\s]+skill|[a-z\s]+course|[a-z\s]+programming|[a-z\s]+analytics)', msg_text.lower())
                    if about_match:
                        previous_topic = about_match.group(1)
                        logger.info(f"Found previous topic in assistant message: {previous_topic}")
                        break
                
                # Look for skill mention in user messages
                skill_mentions = re.findall(r'(data\s+science|machine\s+learning|ai|programming|python|statistics|visualization|analytics|communication|problem\s+solving)', msg_text.lower())
                if skill_mentions:
                    previous_topic = skill_mentions[0]
                    logger.info(f"Found previous topic in user message: {previous_topic}")
                    break
        
        # If found previous topic, return it
        if previous_topic:
            logger.info(f"Using previously discussed topic: {previous_topic}")
            return previous_topic.strip()
        
        # Proceed with standard LLM topic extraction
        try:
            # Set up system prompt
            system_prompt = """You are a topic extraction tool. Your task is to identify the main subject
            or skill the user is interested in learning about. Return ONLY the topic name, nothing else.
            If the query doesn't specify a clear topic, return an empty string."""
            
            # Create user prompt
            user_prompt = f"""Extract the main topic from this course search query: "{query}"
            
            Return ONLY the topic name (1-5 words max). If no clear topic is specified, return an empty string.
            """
            
            # Initialize agent if needed
            if not self.agent:
                self.agent = await self._initialize_agent(system_prompt)
                
            if not self.agent:
                logger.error("Failed to initialize LLM for topic extraction")
                return ""
            
            # Get topic from LLM
            response = await self.agent.arun(user_prompt)
            
            # Extract and clean response
            extracted_topic = response.content if hasattr(response, 'content') else str(response)
            extracted_topic = extracted_topic.strip().strip('"\'').strip()
            
            logger.debug(f"LLM topic extraction candidate: '{extracted_topic}' from query: '{query}'")
            
            # If empty or invalid, return empty string
            if not extracted_topic or extracted_topic.lower() in ["none", "unclear", "not specified", "n/a"]:
                logger.info(f"LLM returned empty string for query '{query}', indicating a generic request. Returning empty for clarification.")
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