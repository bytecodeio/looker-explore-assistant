import logging
import json
import urllib.parse
from typing import Dict, Any, List, Tuple, Optional
from looker_sdk import init40, error
from langchain_core.messages import AIMessage

def init_looker_sdk():
    sdk = init40()
    return sdk

def execute_explore(sdk, explore_params: Dict[str, Any], result_format: str = "md") -> Tuple[Any, Optional[bytes]]:
    """
    Execute the explore with the given parameters
    
    Args:
        sdk: Looker SDK instance
        explore_params: Dictionary of explore parameters
        result_format: Result format (md for markdown, png for visualization)
        
    Returns:
        Tuple of (result_data, visualization_data)
    """
    try:
        # Extract parameters
        model = explore_params.get("model")
        view = explore_params.get("view")
        fields = explore_params.get("fields", [])
        filters = explore_params.get("filters", {})
        sorts = explore_params.get("sorts", [])
        limit = explore_params.get("limit", "500")
        
        if not model or not view or not fields:
            logging.error("Missing required explore parameters")
            return None, None
            
        # Create query
        query = sdk.create_query(
            model=model,
            view=view,
            fields=fields,
            filters=filters,
            sorts=sorts,
            limit=limit
        )
        
        if not query or not query.id:
            logging.error("Failed to create query")
            return None, None
            
        # Run query with requested format
        result = sdk.run_query(
            query_id=query.id,
            result_format=result_format
        )
        
        # For PNG format, get both visualization and text data
        visualization_data = None
        if result_format == "png":
            visualization_data = result
            # Also fetch the data in markdown format for the text response
            text_result = sdk.run_query(
                query_id=query.id,
                result_format="md"
            )
            result = text_result
        
        return result, visualization_data
        
    except error.SDKError as e:
        logging.error(f"Error executing explore: {e}")
        return None, None

def summarize_data(llm, result_data: str) -> str:
    """Summarize the data results using an LLM"""
    contents = f"""
    Data
    ----------

    {result_data}
    
    Task
    ----------
    Summarize the data above in a concise and informative way. Focus on key insights and patterns.
    """
    
    try:
        summary = llm.predict(contents)
        
        # Further refine the summary
        refinement_prompt = f"""
        The following text represents summaries of a given dashboard's data. 
        Summaries: {summary}

        Make this much more concise for a slide presentation using the following format. 
        The summary should be a markdown document that contains a list of sections, 
        each section should have the following details:
        1. A clear, informative section title
        2. A list of 3-5 key points highlighting important insights
        
        Format your response as proper Markdown. Include data values where relevant.
        """
        
        refined_summary = llm.predict(refinement_prompt)
        return refined_summary
        
    except Exception as e:
        logging.error(f"Error summarizing data: {e}")
        return "Could not generate summary of the data."

def build_explore_url(explore_params: Dict[str, Any], looker_instance_url: str = None) -> str:
    """
    Build a direct URL to the Looker explore
    
    Args:
        explore_params: The explore parameters
        looker_instance_url: Base URL for the Looker instance, if None uses a default
        
    Returns:
        URL to the explore
    """
    # Get base URL, either provided or default
    base_url = looker_instance_url or "https://your-looker-instance.cloud.looker.com"
    
    # Get model and explore names
    model_name = explore_params.get("model", "")
    explore_name = explore_params.get("view", "")
    
    if not model_name or not explore_name:
        return ""
    
    # Start building the URL parameters
    url_params = []
    
    # Add fields
    fields = explore_params.get("fields", [])
    if fields:
        url_params.append(f"fields={','.join(fields)}")
    
    # Add pivots
    pivots = explore_params.get("pivots", [])
    if pivots:
        url_params.append(f"pivots={','.join(pivots)}")
    
    # Add sorts
    sorts = explore_params.get("sorts", [])
    if sorts:
        url_params.append(f"sorts={','.join(sorts)}")
    
    # Add limit
    limit = explore_params.get("limit", "500")
    if limit:
        url_params.append(f"limit={limit}")
    
    # Add filters
    filters = explore_params.get("filters", {})
    for key, values in filters.items():
        if isinstance(values, list):
            for value in values:
                encoded_value = urllib.parse.quote(value)
                url_params.append(f"f[{key}]={encoded_value}")
        else:
            encoded_value = urllib.parse.quote(str(values))
            url_params.append(f"f[{key}]={encoded_value}")
    
    # Combine URL with parameters
    url = f"{base_url}/explore/{model_name}/{explore_name}?{('&').join(url_params)}"
    
    return url

def execute_explore_node(state: Dict) -> Dict:
    """
    Execute the explore with generated parameters and summarize results
    """
    if "explore_params" not in state:
        logging.error("Missing explore parameters in state")
        return state
        
    explore_params = state["explore_params"]
    
    # Initialize SDK
    sdk = init_looker_sdk()
    
    # Check if visualization is requested
    request_visualization = state.get("request_visualization", False)
    result_format = "png" if request_visualization else "md"
    
    # Execute explore
    result, visualization_data = execute_explore(sdk, explore_params, result_format)
    
    if not result:
        return {
            **state,
            "messages": state.get("messages", []) + [
                AIMessage(content="Failed to execute explore query.")
            ]
        }
    
    # Get the model from state, or use the model manager to get a summary model
    llm = state.get("llm")
    if not llm:
        model_manager = state.get("model_manager")
        if model_manager:
            llm = model_manager.get_model_for_task("summarization")
        else:
            # Fallback if no model is provided
            from langchain.llms import VertexAI
            llm = VertexAI(
                model_name="gemini-pro",
                max_output_tokens=1024,
                temperature=0
            )
    
    # Summarize results
    summary = summarize_data(llm, result)
    
    # Extract query details for display
    model_name = explore_params.get("model", "")
    explore_name = explore_params.get("view", "")
    fields = explore_params.get("fields", [])
    filters = explore_params.get("filters", {})
    
    # Format a user-friendly description of the query
    fields_description = ", ".join(fields)
    filters_description = ", ".join([f"{k}: {v}" for k, v in filters.items()])
    
    # Build explore URL
    looker_instance_url = state.get("looker_instance_url", "https://your-looker-instance.cloud.looker.com")
    explore_url = build_explore_url(explore_params, looker_instance_url)
    
    # Format the response with both summary and URL
    query_description = f"""
## Data Summary
{summary}

## Query Details
- Model: {model_name}
- Explore: {explore_name}
- Fields: {fields_description}
- Filters: {filters_description}
    """
    
    # Update state with results
    updated_state = {
        **state,
        "explore_result": result,
        "explore_summary": summary,
        "explore_url": explore_url,
        "messages": state.get("messages", []) + [
            AIMessage(content=query_description),
            AIMessage(content=f"## Explore URL\nYou can view and modify this explore directly in Looker by clicking this link:\n\n[Open in Looker]({explore_url})")
        ]
    }
    
    # Add visualization data if available
    if visualization_data:
        updated_state["visualization_data"] = visualization_data
    
    return updated_state
