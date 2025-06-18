from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """Enhanced base class with comprehensive flow context support"""
    
    def __init__(self, llm=None):
        self.llm = llm
    
    @abstractmethod
    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        pass
    
    def get_flow_context(self, context: Dict[str, Any]) -> Tuple[Dict[str, Any], str, Dict[str, Any], Dict[str, Any]]:
        """
        **ENHANCED: Extract comprehensive flow-related information from context**
        Returns: (flow_context, flow_action, response_format, flow_state)
        """
        # Primary flow context
        flow_context = context.get("flow_context", context.get("flow", {}))
        flow_action = flow_context.get("flow_action", "general_response")
        response_format = flow_context.get("response_format", {"format": "conversational"})
        
        # Current flow state
        flow_state = context.get("current_flow_state", {})
        
        return flow_context, flow_action, response_format, flow_state
    
    def get_flow_preserved_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        **NEW: Extract preserved context from previous flow stages**
        This contains role, topic, and other context that flows have built up
        """
        return context.get("flow_preserved_context", {})
    
    def get_connectivity_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        **NEW: Extract connectivity context for cross-referencing**
        """
        return context.get("connectivity_context", {})
    
    def is_flow_enhanced(self, context: Dict[str, Any]) -> bool:
        """
        **NEW: Check if this request has flow enhancement**
        """
        return context.get("flow_enhanced", False)
    
    def get_focus_elements(self, context: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """
        **NEW: Get focus role and topic from flow context**
        Returns: (focus_role, focus_topic)
        """
        focus_role = context.get("focus_role") or context.get("detected_role")
        focus_topic = context.get("focus_topic") or context.get("search_topic")
        return focus_role, focus_topic
    
    def add_flow_metadata(self, result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """**ENHANCED: Add comprehensive flow metadata to agent results**"""
        flow_context, flow_action, response_format, flow_state = self.get_flow_context(context)
        
        if "metadata" not in result:
            result["metadata"] = {}
            
        # Add flow information
        result["metadata"].update({
            "flow_action": flow_action,
            "flow_stage": flow_state.get("current_stage"),
            "flow_enhanced": self.is_flow_enhanced(context),
            "response_format_requested": response_format.get("format")
        })
        
        # Add focus elements
        focus_role, focus_topic = self.get_focus_elements(context)
        if focus_role:
            result["metadata"]["focus_role"] = focus_role
        if focus_topic:
            result["metadata"]["focus_topic"] = focus_topic
            
        return result