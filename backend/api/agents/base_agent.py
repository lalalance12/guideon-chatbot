from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class BaseAgent:
    """Base class for all agents in the system"""
    
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