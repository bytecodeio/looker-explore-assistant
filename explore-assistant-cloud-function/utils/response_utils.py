import json
import re
import logging
from typing import Dict, Any, Optional, List
from langchain_core.messages import AIMessage

def extract_json_from_response(response: str) -> str:
    """
    Extract JSON content from a response that may contain markdown code blocks
    
    Args:
        response: Response string that may include markdown formatting
        
    Returns:
        Clean JSON string without markdown formatting
    """
    # Check if the response has a code block
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response, re.MULTILINE)
    if json_match:
        return json_match.group(1).strip()
    
    # No code block found, return the response as is
    return response.strip()

def parse_json_response(response: str, default_value: Any = None) -> Any:
    """
    Parse a JSON response with error handling
    
    Args:
        response: String containing JSON data
        default_value: Default value to return if parsing fails
        
    Returns:
        Parsed JSON object or default_value if parsing fails
    """
    try:
        # First extract JSON from any markdown formatting
        clean_json_str = extract_json_from_response(response)
        
        # Parse the JSON
        return json.loads(clean_json_str)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON: {e}")
        logging.debug(f"Raw JSON string: {clean_json_str[:500]}...")
        return default_value
    except Exception as e:
        logging.error(f"Error processing response: {e}")
        return default_value

def add_message_to_state(state: Dict[str, Any], content: str) -> Dict[str, Any]:
    """
    Add an AI message to the state's message list
    
    Args:
        state: Current state dictionary
        content: Text content for the message
        
    Returns:
        Updated state with the new message added
    """
    messages = state.get("messages", [])
    messages.append(AIMessage(content=content))
    
    return {
        **state,
        "messages": messages
    }

def validate_output_format(state: Dict[str, Any], required_fields: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Validates and ensures the output state meets the expected format structure
    
    Args:
        state: Current workflow state
        required_fields: Dictionary of field names and their default values
        
    Returns:
        Validated state with standardized format
    """
    # Use default required fields if none provided
    if required_fields is None:
        required_fields = {
            "explore_url": "",
            "looker_url_parts": {},
            "query_results": [],
            "visualization_data": None,
        }
    
    # Ensure all required fields exist
    for field, default_value in required_fields.items():
        if field not in state:
            state[field] = default_value
            logging.warning(f"Missing required field '{field}' in state - adding default value")
    
    # Ensure messages field is properly formatted
    if "messages" not in state:
        state["messages"] = []
        logging.warning("Missing 'messages' field in state - adding empty list")
    
    return state

def ensure_complete_response(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensures that the state contains a complete response including explore URL
    and query results if they exist but aren't in the messages.
    
    Args:
        state: The current workflow state
        
    Returns:
        Updated state with complete response
    """
    # Skip if there are no messages
    if "messages" not in state or not state["messages"]:
        return state
        
    # Check if explore URL exists but isn't in the last message
    last_message_content = state["messages"][-1].content if state["messages"] else ""
    
    if state.get("explore_url") and state["explore_url"] not in last_message_content:
        # Add explore URL to the response
        updated_message = last_message_content + f"\n\nExplore URL: {state['explore_url']}"
        state["messages"][-1] = AIMessage(content=updated_message)
    
    # Check if query results exist but aren't mentioned
    if state.get("query_results") and "query results" not in last_message_content.lower():
        # Add a summary of results to the response
        result_count = len(state["query_results"])
        result_summary = f"\n\nQuery found {result_count} results."
        
        # If there are results, add a sample
        if result_count > 0:
            sample_size = min(3, result_count)
            result_summary += f" Here's a sample: {state['query_results'][:sample_size]}"
            
        updated_message = state["messages"][-1].content + result_summary
        state["messages"][-1] = AIMessage(content=updated_message)
    
    return state
