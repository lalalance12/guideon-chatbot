import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class ContextManager:
    """Manages context size to prevent LLM context window overflow"""
    
    # Constants for token estimation (approximations)
    CHARS_PER_TOKEN = 4  # Rough approximation for most LLMs
    MAX_TOKENS = 4000    # Conservative limit for context window
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimate token count from text length"""
        return len(text) // ContextManager.CHARS_PER_TOKEN
    
    @staticmethod
    def truncate_context(context: Dict[str, Any]) -> Dict[str, Any]:
        """Truncate context to fit within token limits"""
        truncated = context.copy()
        estimated_tokens = ContextManager.estimate_context_tokens(truncated)
        
        logger.info(f"Estimated context tokens: {estimated_tokens}/{ContextManager.MAX_TOKENS}")
        
        if estimated_tokens <= ContextManager.MAX_TOKENS:
            return truncated
        
        # Start truncating in priority order
        if "psf_knowledge" in truncated and truncated["psf_knowledge"].get("found", False):
            truncated["psf_knowledge"] = ContextManager._truncate_kb_items(
                truncated["psf_knowledge"], 
                estimated_tokens - ContextManager.MAX_TOKENS
            )
            
        estimated_tokens = ContextManager.estimate_context_tokens(truncated)
        if estimated_tokens <= ContextManager.MAX_TOKENS:
            return truncated
            
        if "courses" in truncated and truncated["courses"].get("found", False):
            truncated["courses"] = ContextManager._truncate_courses(
                truncated["courses"],
                estimated_tokens - ContextManager.MAX_TOKENS
            )
            
        estimated_tokens = ContextManager.estimate_context_tokens(truncated)
        if estimated_tokens <= ContextManager.MAX_TOKENS:
            return truncated
            
        if "learning_path" in truncated and truncated["learning_path"].get("found", False):
            truncated["learning_path"] = ContextManager._truncate_path(truncated["learning_path"])
            
        return truncated
    
    @staticmethod
    def estimate_context_tokens(context: Dict[str, Any]) -> int:
        """Estimate total tokens in the context dictionary"""
        import json
        serialized = json.dumps(context)
        return ContextManager.estimate_tokens(serialized)
    
    @staticmethod
    def _truncate_kb_items(kb_data: Dict[str, Any], tokens_to_reduce: int) -> Dict[str, Any]:
        """Truncate knowledge base items to reduce context size"""
        if not kb_data.get("items"):
            return kb_data
            
        result = kb_data.copy()
        items = result.get("items", [])
        
        # Sort by relevance (if available)
        items.sort(key=lambda x: float(x.get("relevance", "0").strip("%")) if isinstance(x.get("relevance"), str) else 0, 
                  reverse=True)
        
        # Keep only top 3 items
        result["items"] = items[:min(3, len(items))]
        
        # Truncate content of remaining items if needed
        for item in result["items"]:
            if "content" in item and len(item["content"]) > 500:
                item["content"] = item["content"][:500] + "..."
                
        result["count"] = len(result["items"])
        return result
    
    @staticmethod
    def _truncate_courses(course_data: Dict[str, Any], tokens_to_reduce: int) -> Dict[str, Any]:
        """Truncate course recommendations to reduce context size"""
        if not course_data.get("courses"):
            return course_data
            
        result = course_data.copy()
        # Keep only top 3 courses
        result["courses"] = result["courses"][:min(3, len(result["courses"]))]
        result["count"] = len(result["courses"])
        return result
    
    @staticmethod
    def _truncate_path(path_data: Dict[str, Any]) -> Dict[str, Any]:
        """Truncate learning path to reduce context size"""
        if not path_data.get("path"):
            return path_data
            
        result = path_data.copy()
        # Keep only essential path information
        path = result.get("path", [])
        truncated_path = []
        
        for step in path:
            truncated_step = {
                "name": step.get("name", ""),
                "type": step.get("type", "")
            }
            truncated_path.append(truncated_step)
            
        result["path"] = truncated_path
        return result