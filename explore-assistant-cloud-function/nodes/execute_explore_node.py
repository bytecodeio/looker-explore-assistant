import logging
import json
import urllib.parse
from typing import Dict, Any, List, Tuple, Optional
from looker_sdk import init40, error
from langchain_core.messages import AIMessage
from looker_sdk.sdk.api40 import models as looker_models

logger = logging.getLogger(__name__)

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
        query = looker_models.WriteQuery(
            model=model,
            view=view,
            fields=fields,
            filters=filters,
            sorts=sorts,
            limit=limit
        )
        
        query_obj = sdk.create_query(query)
        query_id = query_obj.id
        
        if not query_obj or not query_id:
            logging.error("Failed to create query")
            return None, None
            
        # Run query with requested format
        result = sdk.run_query(
            query_id=query_id,
            result_format=result_format
        )
        
        # For PNG format, get both visualization and text data
        visualization_data = None
        if result_format == "png":
            visualization_data = result
            # Also fetch the data in markdown format for the text response
            text_result = sdk.run_query(
                query_id=query_id,
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

def generate_explore_url(looker_instance_url: str, explore_params: Dict[str, Any]) -> str:
    """
    Generate a Looker explore URL from the explore parameters
    
    Args:
        looker_instance_url: Base URL of the Looker instance
        explore_params: Dictionary of explore parameters
        
    Returns:
        Complete URL to the Looker explore
    """
    if not explore_params:
        return ""
    
    model = explore_params.get("model", "")
    explore = explore_params.get("view", "")
    
    if not model or not explore:
        logger.error("Missing model or explore in explore_params")
        return ""
    
    # Start building URL parameters
    url_params = []
    
    # Add fields
    fields = explore_params.get("fields", [])
    if fields:
        url_params.append(f"fields={','.join(fields)}")
    
    # Add filters
    filters = explore_params.get("filters", {})
    for field, values in filters.items():
        if isinstance(values, list):
            value = values[0]  # Take the first value if multiple are provided
        else:
            value = values
        url_params.append(f"f[{field}]={value}")
    
    # Add pivots
    pivots = explore_params.get("pivots", [])
    if pivots:
        url_params.append(f"pivots={','.join(pivots)}")
    
    # Add sorts
    sorts = explore_params.get("sorts", [])
    if sorts:
        url_params.append(f"sorts={','.join(sorts)}")
    
    # Add limit
    limit = explore_params.get("limit")
    if limit:
        url_params.append(f"limit={limit}")
    
    # Add vis_config if provided
    vis_config = explore_params.get("vis_config")
    if vis_config:
        vis_config_str = json.dumps(vis_config)
        url_params.append(f"vis_config={vis_config_str}")
    
    # Combine URL parts
    url = f"{looker_instance_url}/explore/{model}/{explore}?{('&').join(url_params)}"
    logger.info(f"Generated explore URL: {url}")
    
    return url

def generate_response_summary(llm, user_query: str, explore_params: Dict[str, Any], results: Any) -> str:
    """
    Generate a summary of the query results using LLM
    
    Args:
        llm: LLM instance to use for generating the summary
        user_query: Original user query
        explore_params: The explore parameters used
        results: Query results from Looker
        
    Returns:
        A natural language summary of the results
    """
    try:
        # Convert query results to JSON for the LLM
        if isinstance(results, list) and results:
            # Take only first 5 rows for summary to avoid token limits
            sample_results = results[:5]
            results_json = json.dumps(sample_results, indent=2)
        else:
            results_json = "{}"
        
        # Create the prompt
        prompt = f"""
        User Query: {user_query}
        
        Query Parameters: {json.dumps(explore_params, indent=2)}
        
        Sample Results: {results_json}
        
        Please provide a clear and concise summary of the query results that answers the user's question. 
        Highlight the most important insights and include specific numbers or trends if relevant.
        Respond directly to the user's query without mentioning that you're summarizing results.
        """
        
        # Generate summary
        summary = llm.predict(prompt)
        return summary
    except Exception as e:
        logger.error(f"Error generating response summary: {e}")
        return "I ran the query, but couldn't generate a summary of the results."

def capture_visualization(sdk, query_id: str) -> bytes:
    """
    Capture visualization as PNG image
    
    Args:
        sdk: Looker SDK instance
        query_id: ID of the query to render
        
    Returns:
        PNG image data as bytes
    """
    try:
        # Get the visualization as PNG
        result = sdk.run_query(query_id=query_id, result_format="png")
        return result
    except Exception as e:
        logger.error(f"Error capturing visualization: {e}")
        return None

def execute_explore_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the Looker explore query and return results
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with query results and visualization data
    """
    # Check for required state keys gracefully
    explore_params = state.get("explore_params", {})
    if not explore_params:
        logger.warning("Missing explore_params in state")
        return {
            **state,
            "messages": state.get("messages", []) + [
                AIMessage(content="I couldn't generate explore parameters to answer your question.")
            ]
        }
        
    # Try to get the SDK from state or initialize it
    sdk = state.get("looker_sdk")
    if not sdk:
        logger.warning("Missing looker_sdk in state - trying to initialize")
        try:
            sdk = init40()
            # Test connection
            sdk.me()
            logger.info("Successfully initialized Looker SDK")
            # Update state with the SDK
            state["looker_sdk"] = sdk
        except error.SDKError as e:
            logger.error(f"Failed to initialize Looker SDK: {e}")
            return {
                **state,
                "messages": state.get("messages", []) + [
                    AIMessage(content="I couldn't connect to Looker to run your query.")
                ]
            }
    
    looker_instance_url = state.get("looker_instance_url", "")
    request_visualization = state.get("request_visualization", False)
    user_query = state.get("user_query", "")
    
    try:
        # Generate the explore URL
        explore_url = generate_explore_url(looker_instance_url, explore_params)
        
        # Print the explore parameters for debugging
        logger.info(f"Executing explore with parameters: {json.dumps(explore_params)}")
        
        # Prepare the query for execution
        # Make sure we have all the required fields for the query
        if not explore_params.get("model") or not explore_params.get("view"):
            logger.error("Missing model or view in explore_params")
            return {
                **state,
                "messages": state.get("messages", []) + [
                    AIMessage(content="I couldn't generate a valid query because the model or view information is missing.")
                ]
            }
            
        if not explore_params.get("fields"):
            logger.warning("No fields specified in explore_params")
            explore_params["fields"] = []  # Ensure fields is at least an empty list
        
        # Use proper WriteQuery object instead of keyword arguments
        query = looker_models.WriteQuery(
            model=explore_params.get("model"),
            view=explore_params.get("view"),
            fields=explore_params.get("fields", []),
            filters=explore_params.get("filters", {}),
            pivots=explore_params.get("pivots", []),
            sorts=explore_params.get("sorts", []),
            limit=explore_params.get("limit"),
            vis_config=explore_params.get("vis_config", {}),
            filter_expression=explore_params.get("filter_expression", None)
        )
        
        # Log the query before execution
        logger.info(f"Creating query for {explore_params.get('model')}.{explore_params.get('view')}")
        
        # Create and run the query
        query_obj = sdk.create_query(query)
        query_id = query_obj.id
        
        if not query_id:
            logger.error("Failed to create query object")
            return {
                **state,
                "messages": state.get("messages", []) + [
                    AIMessage(content="I couldn't create a valid query in Looker.")
                ]
            }
        
        # Run the query and get JSON results
        logger.info(f"Executing query with ID: {query_id}")
        results = sdk.run_query(query_id=query_id, result_format="json")
        
        # Parse JSON results if needed
        if isinstance(results, bytes) or isinstance(results, str):
            try:
                parsed_results = json.loads(results)
                logger.info(f"Query returned {len(parsed_results)} results")
            except json.JSONDecodeError:
                logger.error("Failed to parse JSON results")
                parsed_results = []
        else:
            parsed_results = results
        
        # Get visualization if requested
        visualization_data = None
        if request_visualization:
            logger.info("Requesting visualization")
            visualization_data = capture_visualization(sdk, query_id)
        
        # Generate result summary using LLM
        llm = state.get("llm")
        if llm and parsed_results:
            logger.info("Generating summary of query results")
            summary = generate_response_summary(llm, user_query, explore_params, parsed_results)
        else:
            if not parsed_results:
                summary = "I ran the query, but no data was returned. You might want to check your filters."
            else:
                summary = "I ran the query successfully, but couldn't generate a summary."
        
        # Update state with results and provide explore URL in the message
        updated_state = {
            **state,
            "explore_url": explore_url,
            "query_results": parsed_results,
            "visualization_data": visualization_data,
            "messages": state.get("messages", []) + [
                AIMessage(content=f"{summary}\n\nYou can view and explore this data further here: {explore_url}")
            ]
        }
        
        return updated_state
        
    except Exception as e:
        logger.error(f"Error executing explore: {e}")
        return {
            **state,
            "error": str(e),
            "messages": state.get("messages", []) + [
                AIMessage(content=f"I encountered an error while running your query: {str(e)}")
            ]
        }
