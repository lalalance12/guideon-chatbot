from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """Base class for all Guideon agents"""
    
    @abstractmethod
    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a query with the given context and return a result
        
        Args:
            query: The user's query text
            context: Contextual information including intent, history, etc.
            
        Returns:
            Dict containing the agent's response and any metadata
        """
        pass