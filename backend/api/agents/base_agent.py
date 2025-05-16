from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class BaseAgent:
    """Base class for all agents in the system"""
    
    @abstractmethod
    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a query with given context
        This method should be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement process method")
    
    def handle_error(self, error, default_response=None):
        """Common error handling for all agents"""
        logger.error(f"Error in {self.__class__.__name__}: {str(error)}")
        if default_response is None:
            default_response = {
                "found": False,
                "reason": "exception",
                "message": f"Error: {str(error)}"
            }
        return default_response
    
    def get_flow_context(self, context: Dict[str, Any]) -> Tuple[Dict[str, Any], str, Dict[str, Any]]:
        """
        Extract flow-related information from context
        Returns: (flow_context, flow_action, response_format)
        """
        flow_context = context.get("flow", {})
        flow_action = flow_context.get("flow_action", "general_response")
        response_format = flow_context.get("response_format", {"format": "conversational"})
        
        return flow_context, flow_action, response_format
    
    def add_flow_metadata(self, result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Add flow-related metadata to agent results"""
        flow_context, flow_action, _ = self.get_flow_context(context)
        
        if "metadata" not in result:
            result["metadata"] = {}
            
        result["metadata"]["flow_action"] = flow_action
        
        if "role" in flow_context:
            result["metadata"]["role"] = flow_context["role"]
            
        return result