import logging
from typing import Dict
from langchain_core.messages import HumanMessage, AIMessage

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
    
    return {
        "user_query": formatted_query,
        "messages": [HumanMessage(content=formatted_query)],
        "processed_queries": [formatted_query]  # Keep track of processed queries for potential refinement
    }
