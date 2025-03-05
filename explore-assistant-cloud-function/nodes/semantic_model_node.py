import logging
from typing import Dict
from looker_sdk import init40, error

def init_looker_sdk():
    sdk = init40()
    return sdk

def fetch_semantic_model(sdk, model_name, explore_name):
    """
    Fetch semantic model information for the specified explore
    Similar to useLookerFields.ts functionality
    """
    try:
        response = sdk.lookml_model_explore(
            lookml_model_name=model_name,
            explore_name=explore_name,
            fields="fields"
        )
        
        if not response or not hasattr(response, 'fields'):
            logging.error(f"No fields found for {model_name}.{explore_name}")
            return None
        
        fields = response.fields
        
        if not fields or not hasattr(fields, 'dimensions') or not hasattr(fields, 'measures'):
            logging.error(f"Invalid field structure for {model_name}.{explore_name}")
            return None
        
        dimensions = [
            {
                "name": dim.name,
                "type": dim.type,
                "label": dim.label,
                "description": dim.description,
                "tags": dim.tags
            }
            for dim in fields.dimensions if not dim.hidden
        ]
        
        measures = [
            {
                "name": meas.name,
                "type": meas.type,
                "label": meas.label,
                "description": meas.description,
                "tags": meas.tags
            }
            for meas in fields.measures if not meas.hidden
        ]
        
        return {
            "exploreId": explore_name,
            "modelName": model_name,
            "exploreKey": f"{model_name}:{explore_name}",
            "dimensions": dimensions,
            "measures": measures
        }
        
    except error.SDKError as e:
        logging.error(f"Error fetching semantic model for {model_name}.{explore_name}: {e}")
        return None

def semantic_model_node(state: Dict) -> Dict:
    """
    Load semantic model information for the selected explore
    Similar to useLookerFields hook functionality
    """
    if "selected_explore" not in state:
        logging.error("No selected explore in state")
        return state
    
    selected_explore = state["selected_explore"]
    model_name = selected_explore.get("model_name")
    explore_name = selected_explore.get("name")
    
    if not model_name or not explore_name:
        logging.error("Invalid selected explore information")
        return state
    
    sdk = init_looker_sdk()
    semantic_model = fetch_semantic_model(sdk, model_name, explore_name)
    
    if not semantic_model:
        logging.error(f"Failed to fetch semantic model for {model_name}.{explore_name}")
        return state
    
    # Update state with semantic model information
    return {
        **state,
        "semantic_model": semantic_model
    }
