import logging
import os
from typing import Dict
from looker_sdk import error
from utils.looker_sdk_utils import init_looker_sdk

def fetch_lookml_metadata(sdk, model, explore_name):
    try:
        metadata = sdk.lookml_model_explore(model, explore_name)
        return metadata
    except error.SDKError as e:
        logging.error(f"Error fetching LookML metadata: {e}")
        return {}

def get_lookml_metadata_node(state: Dict) -> Dict:
    if state["current_explore_index"] >= len(state["explores"]):
        logging.error("Explores list is empty in get_lookml_metadata_node.")
        return state  # Return state as is if explores list is empty
    
    # Use SDK from state if available, otherwise initialize it
    if "looker_sdk" in state and state["looker_sdk"]:
        sdk = state["looker_sdk"]
        logging.debug("Using Looker SDK from state")
    else:
        logging.debug("Initializing Looker SDK in get_lookml_metadata_node")
        sdk = init_looker_sdk()
    
    while state["current_explore_index"] < len(state["explores"]):
        explore = state["explores"][state["current_explore_index"]]
        model = explore['model_name']  # Use 'model_name' from dictionary
        try:
            metadata = fetch_lookml_metadata(sdk, model, explore['name'])  # Use 'name' from dictionary
            if "metadata" not in state:
                state["metadata"] = {}  # Initialize metadata if it doesn't exist
            state["metadata"][explore['name']] = metadata  # Store metadata in state
            logging.info(f"Fetched metadata for explore: {explore['name']}")
        except error.SDKError as e:
            logging.error(f"Error fetching LookML metadata for explore {explore['name']}: {e}")
            state["current_explore_index"] += 1
            continue  # Skip to the next explore
        state["current_explore_index"] += 1
    
    # Add or keep SDK in state
    return {
        "metadata": state.get("metadata", {}), 
        "explores": state["explores"], 
        "current_explore_index": state["current_explore_index"], 
        "processed_explores": state["processed_explores"],
        "looker_sdk": sdk
    }
