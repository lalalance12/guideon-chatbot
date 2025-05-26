from typing import Dict, Any, Optional
import logging
from .base_agent import BaseAgent
from ..flows.intent_flows import FlowController, QueryIntent, FlowStage

logger = logging.getLogger(__name__)

class FlowManagerAgent(BaseAgent):
    """
    Agent that manages conversation flows across sessions.
    Acts as a stateful interface to the FlowController.
    """
    
    # Class variable to store flow controllers by chat ID
    _flow_controllers = {}  # Map of chat_id -> FlowController
    
    def __init__(self, llm=None) -> None:
        super().__init__(llm=llm)
        self.name = "FlowManagerAgent"
    
    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process the query and manage flow state"""
        chat_id = context.get('chat_id', 'default')
        logger.info(f"[FlowManagerAgent] Processing query for chat {chat_id}")
        
        # Get or create flow controller for this chat
        flow_controller = self._get_flow_controller(chat_id)
        
        # Get intent from context
        intent = context.get("intent")
        if not intent:
            logger.warning("[FlowManagerAgent] No intent provided, defaulting to general conversation")
            intent = QueryIntent.GENERAL_CONVERSATION
        
        # Get flow instructions using the FlowController from intent_flows.py
        flow_instructions = flow_controller.process_query(query, intent, context)
        
        # Only add current flow state to the response
        current_flow_state = self._get_flow_state(flow_controller)
        
        # Ensure we only have one primary agent in the instructions
        if "activate_agents" in flow_instructions and len(flow_instructions["activate_agents"]) > 1:
            primary_agent = flow_instructions["activate_agents"][0]
            logger.info(f"[FlowManagerAgent] Multiple agents found, selecting primary agent: {primary_agent}")
            flow_instructions["activate_agents"] = [primary_agent]
        
        return {
            "flow_instructions": flow_instructions,
            "current_flow": current_flow_state,
            "agent_name": self.name
        }
    
    def _get_flow_controller(self, chat_id: str) -> FlowController:
        """Get or create a flow controller for the given chat ID"""
        if chat_id not in self._flow_controllers:
            logger.info(f"[FlowManagerAgent] Creating new flow controller for chat {chat_id}")
            self._flow_controllers[chat_id] = FlowController()
        
        return self._flow_controllers[chat_id]
    
    def _get_flow_state(self, flow_controller: FlowController) -> Dict[str, Any]:
        """Get the current flow state"""
        if not flow_controller.active_flow:
            return {
                "has_active_flow": False,
                "current_stage": None,
                "intent": None
            }
            
        return {
            "has_active_flow": True,
            "current_stage": flow_controller.active_flow.current_stage.value,
            "intent": flow_controller.active_intent.value if flow_controller.active_intent else None,
            "context": flow_controller.active_flow.context
        }
    
    def reset_flow(self, chat_id: str) -> None:
        """Reset the flow for a chat ID - can be called externally"""
        if chat_id in self._flow_controllers:
            logger.info(f"[FlowManagerAgent] Resetting flow for chat {chat_id}")
            del self._flow_controllers[chat_id]
    
    async def check_flow_transition(self, query: str, intent: QueryIntent, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if we should transition between flows or continue existing flow.
        Can be called by the IntentClassifierAgent to improve classification.
        """
        chat_id = context.get('chat_id', 'default')
        flow_controller = self._get_flow_controller(chat_id)
        
        # If no active flow, always use the new intent
        if not flow_controller.active_flow:
            return {
                "should_continue_flow": False,
                "recommended_intent": intent
            }
        
        current_intent = flow_controller.active_intent
        current_stage = flow_controller.active_flow.current_stage
        
        # If intent is the same, continue the flow
        if intent == current_intent:
            return {
                "should_continue_flow": True,
                "recommended_intent": current_intent
            }
        
        # Check for exit signals
        exit_signals = ["switch topic", "different question", "new topic", "change subject"]
        if any(signal in query.lower() for signal in exit_signals):
            return {
                "should_continue_flow": False,
                "recommended_intent": intent
            }
        
        # Flow-specific continuity rules
        if current_intent == QueryIntent.COURSE_SEARCH:
            if current_stage in [FlowStage.INITIAL, FlowStage.CLARIFICATION]:
                # During early stages of course search, stick with it
                return {
                    "should_continue_flow": True,
                    "recommended_intent": current_intent
                }
        
        # Default to the new intent
        return {
            "should_continue_flow": False,
            "recommended_intent": intent
        }