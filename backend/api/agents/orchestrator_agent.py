from __future__ import annotations
from typing import Dict, Any, List
import asyncio
import logging
import time
import json

from ..utils.chat_history_manager import ChatHistoryManager
from .intent_classifier_agent import IntentClassifierAgent 
from .base_agent import BaseAgent
from .psf_knowledge_agent import PSFKnowledgeAgent
from .course_search_agent import CourseSearchAgent
from .learning_path_agent import LearningPathAgent
from ..utils.intent_classifier import QueryIntent
from ..flows.intent_flows import FlowController
from agno.agent import Agent

logger = logging.getLogger(__name__)

class OrchestratorAgent(BaseAgent):
    """Coordinates the execution of specialised agents based on intent."""

    def __init__(self) -> None:
        self.knowledge_agent = PSFKnowledgeAgent()
        self.course_agent = CourseSearchAgent()
        self.learning_path_agent = LearningPathAgent()
        self.flow_controller = FlowController()

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Coordinate the execution of multiple agents based on the user's intent."""
        start_time = time.time()
        logger.info(f"OrchestratorAgent processing query: {query[:50]}...")
        
        # Store the chat ID for later use
        self.chat_id = context.get("chat_id")
        
        # Track the previous intent for transition detection
        previous_intent = None
        if self.chat_id:
            chat = await self._get_chat(self.chat_id)
            if chat and hasattr(chat, 'metadata') and chat.metadata:
                try:
                    metadata = json.loads(chat.metadata) if isinstance(chat.metadata, str) else chat.metadata
                    if isinstance(metadata, dict):
                        # Get previous intent from metadata
                        previous_intent = metadata.get('last_intent')
                        context['previous_intent'] = previous_intent
                        
                        # Check for awaiting topic selection
                        if metadata.get('awaiting_topic_selection') and metadata.get('topics'):
                            # Add topics to context for the flow to use
                            context['multiple_topics'] = metadata.get('topics')
                            logger.info(f"Retrieved topics from chat metadata: {context['multiple_topics']}")
                            
                            # Only set force course search if we can identify that the user
                            # is directly responding to the topic selection and not changing topics
                            if not self._appears_to_change_topic(query):
                                # Force course search intent if we're expecting a topic selection
                                context["intent"] = QueryIntent.COURSE_SEARCH
                                logger.info("Set intent to COURSE_SEARCH based on awaiting_topic_selection flag")
                except (json.JSONDecodeError, AttributeError) as e:
                    logger.warning(f"Failed to process chat metadata: {e}")

        # Determine intent if not already provided
        intent = context.get("intent")
        if not intent:
            try:
                # Use IntentClassifierAgent to determine intent with LLM
                intent_agent = IntentClassifierAgent()
                intent_result = await intent_agent.process(query, context)
                intent = intent_result.get("intent")
                confidence = intent_result.get("confidence", 0.0)
                
                # Check if this is a transition detected by the LLM
                is_transition = intent_result.get("is_transition", False)
                if is_transition:
                    # Mark context as transitioning for flow controller
                    context["is_transition"] = True
                    logger.info(f"LLM detected intent transition to {intent}")
                    
                    # If we were awaiting topic selection but user changed topics, clear that state
                    if self.chat_id and context.get('multiple_topics'):
                        await self._update_chat_metadata(self.chat_id, {
                            'awaiting_topic_selection': False,
                            'topics': []
                        })
                        logger.info("Cleared topic selection state due to topic change")
                
                # Add intent to context
                context["intent"] = intent
                context["intent_confidence"] = confidence
                context.update(intent_result)  # Add any other intent details to context
                
                logger.info(f"Classified intent: {intent} with confidence {confidence}")
            except Exception as e:
                logger.error(f"Error classifying intent: {e}")
                intent = None
        
        # Store the current intent in metadata for future reference
        if self.chat_id and intent:
            await self._update_chat_metadata(self.chat_id, {
                'last_intent': str(intent)
            })
        
        # Process with appropriate flow controller
        flow_instructions = self.flow_controller.process_query(
            query, intent, context
        )
        
        # Update context with flow instructions
        if flow_instructions:
            context["flow"] = flow_instructions
        
        # If this is a topic selection request, store the topics in chat metadata
        if flow_instructions.get("flow_action") == "request_topic_selection" and "topics" in flow_instructions and self.chat_id:
            await self._update_chat_metadata(self.chat_id, {
                'awaiting_topic_selection': True,
                'topics': flow_instructions['topics']
            })
            logger.info(f"Stored topics in chat metadata: {flow_instructions['topics']}")
        
        # Clear the awaiting_topic_selection flag if we're doing a course search
        if flow_instructions.get("flow_action") == "course_search" and self.chat_id:
            await self._update_chat_metadata(self.chat_id, {
                'awaiting_topic_selection': False
            })
            logger.info("Cleared awaiting_topic_selection flag in chat metadata")
        
        # Add transition info to context for response synthesizer
        if context.get("is_transition", False) and previous_intent:
            context["transition_info"] = {
                "from_intent": previous_intent,
                "to_intent": str(intent)
            }
            
        # Determine which agents to activate based on flow instructions
        agents_to_activate = flow_instructions.get("activate_agents", ["knowledge_agent"])
        
        results = {}
        
        # Always run the PSF Knowledge Agent for domain knowledge
        if "knowledge_agent" in agents_to_activate:
            kb_result = await self._execute_agent(
                self.knowledge_agent, 
                query, 
                context, 
                "knowledge_base"
            )
            if kb_result:
                results["knowledge_base"] = kb_result
        
        # Run additional agents based on flow and intent
        if "course_agent" in agents_to_activate:
            course_result = await self._execute_agent(
                self.course_agent, 
                query, 
                context, 
                "course_search"
            )
            if course_result:
                results["course_search"] = course_result
                
                # Special handling for multiple topics case
                if course_result.get('multiple_topics', []):
                    logger.info(f"Multiple topics found: {course_result.get('multiple_topics')}")
                    # Store topics in chat metadata for future reference
                    if self.chat_id:
                        await self._update_chat_metadata(self.chat_id, {
                            'awaiting_topic_selection': True,
                            'topics': course_result.get('multiple_topics')
                        })
        
        if "learning_path_agent" in agents_to_activate:
            path_result = await self._execute_agent(
                self.learning_path_agent, 
                query, 
                context, 
                "learning_path"
            )
            if path_result:
                results["learning_path"] = path_result
        
        # Add runtime metadata
        results["metadata"] = {
            "intent": getattr(intent, "value", str(intent)) if intent else "unknown",
            "processing_time": time.time() - start_time,
            "flow": flow_instructions.get("flow_action", "general_response"),
            "is_transition": context.get("is_transition", False)
        }
        
        # Add transition info to results for response synthesizer
        if context.get("transition_info"):
            results["metadata"]["transition_info"] = context["transition_info"]
        
        return results

    async def _execute_agent(self, agent, query, context, key):
        """Execute an agent with the given query and context."""
        try:
            # Make sure chat history and flow information is passed to all agents
            full_context = context.copy()
            
            # This is critical - pass chat history to topic extractor via agents
            if "chat_history" not in full_context and hasattr(self, "chat_id"):
                # Get chat history if not already in context
                chat_history = await ChatHistoryManager.get_simple_history(self.chat_id)
                full_context["chat_history"] = chat_history
            
            result = await agent.process(query, full_context)
            return result
        except Exception as e:
            logger.error(f"Error executing {key} agent: {e}")
            return None
            
    async def _get_chat(self, chat_id):
        """Retrieve a chat object by ID."""
        try:
            from ..models import Chat
            return await Chat.objects.aget(id=chat_id)
        except Exception as e:
            logger.error(f"Error retrieving chat: {e}")
            return None

    async def _update_chat_metadata(self, chat_id, metadata_update):
        """Update the metadata field of a chat object."""
        try:
            from ..models import Chat
            chat = await Chat.objects.aget(id=chat_id)
            
            # Initialize or update existing metadata
            current_metadata = {}
            if chat.metadata:
                try:
                    if isinstance(chat.metadata, str):
                        current_metadata = json.loads(chat.metadata) 
                    else:
                        current_metadata = chat.metadata
                except json.JSONDecodeError:
                    logger.warning(f"Invalid metadata JSON, resetting: {chat.metadata}")
                    current_metadata = {}
                    
            # Ensure current_metadata is a dict
            if not isinstance(current_metadata, dict):
                current_metadata = {}
                
            # Update with new values
            current_metadata.update(metadata_update)
            
            # Save the updated metadata
            chat.metadata = json.dumps(current_metadata)
            await chat.asave()
            logger.info(f"Updated chat metadata for chat {chat_id}")
        except Exception as e:
            logger.error(f"Error updating chat metadata: {e}")

    def _appears_to_change_topic(self, query: str) -> bool:
        """
        Use a lightweight heuristic to quickly check if the query appears to be changing topics.
        This is only used as a fast pre-check before the LLM makes the full determination.
        """
        # Simple logic - if the query is very short, it's likely a direct topic selection
        # If it's longer and more complex, we'll let the LLM decide
        return len(query.split()) > 5 and any(char in query for char in "?.,")