import logging
from typing import Dict
from langchain_core.messages import AIMessage

def user_verification_node(state: Dict) -> Dict:
    """
    Add a verification request to the response for regenerated explores
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with verification request
    """
    # Check if this is a regenerated explore
    if not state.get("is_regenerated", False):
        return state
    
    # Add verification request to messages
    verification_message = """
## Is this better?

Is this improved explore addressing your feedback? Please let me know if this is now correct or if it needs further adjustments.

- If this is correct, please respond with "Yes" or "That's correct"
- If this still needs improvements, please provide additional feedback
"""
    
    return {
        **state,
        "awaiting_verification": True,
        "messages": state.get("messages", []) + [
            AIMessage(content=verification_message)
        ]
    }
