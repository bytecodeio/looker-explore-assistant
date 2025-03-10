import logging
from typing import Dict, List, Any
from looker_sdk import error as looker_error

logger = logging.getLogger(__name__)

def fetch_filter_values(sdk, model: str, explore: str, field: str, value: str = None) -> List[str]:
    """
    Fetch valid filter values for a field from Looker
    
    Args:
        sdk: Looker SDK instance
        model: Model name
        explore: Explore name
        field: Field name
        value: Optional value to filter suggestions
        
    Returns:
        List of valid filter values
    """
    try:
        response = sdk.run_inline_query(
            body={
                "model": model,
                "view": explore,
                "fields": [field],
                "limit": 100,
                "filters": {field: value} if value else {}
            },
            result_format="json"
        )
        
        # Extract unique values from response
        values = set()
        for row in response:
            if field in row and row[field]:
                values.add(str(row[field]))
                
        return sorted(list(values))
        
    except looker_error.SDKError as e:
        logger.error(f"Error fetching filter values for {field}: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching filter values: {e}")
        return []

def filter_value_fetcher_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node for fetching valid filter values for fields in the explore
    
    Args:
        state: Current workflow state containing:
            - explore_params: Generated explore parameters
            - semantic_model: Semantic model information
            - looker_sdk: Initialized Looker SDK instance
            
    Returns:
        Updated state with filter values
    """
    # Check for required keys but don't fail if they're missing
    if not all(key in state for key in ["explore_params", "semantic_model"]):
        logger.warning("Missing explore_params or semantic_model in state - skipping filter value fetching")
        return state
    
    # Check for Looker SDK specifically
    sdk = state.get("looker_sdk")
    if not sdk:
        logger.warning("Missing looker_sdk in state - skipping filter value fetching")
        return state
        
    explore_params = state.get("explore_params", {})
    semantic_model = state.get("semantic_model", {})
    
    model = semantic_model.get("modelName")
    explore = semantic_model.get("exploreId")
    
    if not model or not explore:
        logger.warning("Missing model or explore information")
        return state
        
    # Get filter fields that need validation
    filter_fields = explore_params.get("filters", {}).keys()
    
    if not filter_fields:
        logger.info("No filters to fetch values for")
        return state
        
    logger.info(f"Fetching filter values for {len(filter_fields)} fields")
    
    filter_values = {}
    for field in filter_fields:
        values = fetch_filter_values(sdk, model, explore, field)
        if values:
            filter_values[field] = values
            logger.info(f"Fetched {len(values)} values for filter {field}")
            
    # Update state with fetched filter values
    return {
        **state,
        "filter_values": filter_values
    }
