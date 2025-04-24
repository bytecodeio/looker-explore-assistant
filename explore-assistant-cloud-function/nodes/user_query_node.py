import logging
from typing import Dict
from langchain_core.messages import HumanMessage, AIMessage

def map_query_to_standard_fields(query: str, standard_fields: Dict) -> Dict:
    """
    Map user query terms to standard field names using provided aliases
    
    Args:
        query: The user's query
        standard_fields: Dictionary of standard field names with their aliases
        
    Returns:
        Dictionary with recognized fields and their standard names
    """
    query_lower = query.lower()
    recognized_fields = {}
    
    # For each field in our standard fields dictionary
    for field_name, aliases in standard_fields.items():
        # Split aliases if it's a comma-separated string
        if isinstance(aliases, str):
            alias_list = [a.strip().lower() for a in aliases.split(',')]
        elif isinstance(aliases, list):
            alias_list = [a.lower() for a in aliases]
        else:
            # If it's just a single value, convert to list
            alias_list = [str(aliases).lower()]
            
        # Check if any alias is mentioned in the query
        for alias in alias_list:
            if alias.lower() in query_lower:
                recognized_fields[alias] = field_name
                logging.info(f"Recognized field alias '{alias}' as standard field '{field_name}'")
    
    return recognized_fields

def user_query_node(state: Dict) -> Dict:
    """
    Process the initial user query and prepare it for explore selection.
    
    Args:
        state: The current state containing the user's query
        
    Returns:
        Updated state with formatted user query
    """
    logging.info("Processing user query in user_query_node")
    
    if "user_query" not in state or not state["user_query"]:
        return {"messages": [AIMessage(content="No question provided. Please ask a data question.")]}
    
    user_query = state["user_query"]
    logging.info(f"User query: {user_query}")
    
    # Format the query for the next steps
    formatted_query = user_query.strip()
    
    # Map query terms to standard field names if standard_fields are provided
    field_mapping = {}
    if "standard_fields" in state and state["standard_fields"]:
        field_mapping = map_query_to_standard_fields(formatted_query, state["standard_fields"])
        logging.info(f"Identified field mappings: {field_mapping}")
    
    return {
        "user_query": formatted_query,
        "messages": [HumanMessage(content=formatted_query)],
        "processed_queries": [formatted_query],  # Keep track of processed queries for potential refinement
        "field_mapping": field_mapping  # Add the field mapping to the state
    }
