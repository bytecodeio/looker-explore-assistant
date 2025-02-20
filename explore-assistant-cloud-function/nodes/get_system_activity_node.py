import logging
import json
from typing import Dict
from looker_sdk import init40, error
from langchain_core.messages import AIMessage

def init_looker_sdk():
    sdk = init40()
    return sdk

def fetch_system_activity(sdk, explore_name):
    try:
        activity = sdk.run_inline_query(
            result_format="json",
            body={
                "model": "system__activity",
                "view": "history",
                "fields": ["history.created_time", "history.query_run_time"],
                "filters": {"history.explore": explore_name},
                "limit": "10"
            }
        )
        return json.loads(activity)
    except error.SDKError as e:
        logging.error(f"Error fetching system activity: {e}")
        return []

def get_system_activity_node(state: Dict) -> Dict:
    if "current_explore_index" not in state:
        state["current_explore_index"] = 0  # Initialize current_explore_index if it doesn't exist
    if state["current_explore_index"] >= len(state["explores"]):
        logging.error("Explores list is empty in get_system_activity_node.")
        return state  # Return state as is if explores list is empty
    sdk = init_looker_sdk()
    explore = state["explores"][state["current_explore_index"]]
    logging.info(f"Processing explore: {explore['name']} in get_system_activity_node.")
    system_activity = fetch_system_activity(sdk, explore['name'])  # Use 'name' from dictionary
    return {"messages": [AIMessage(content=json.dumps(system_activity))], "explores": state["explores"], "current_explore_index": state["current_explore_index"] + 1, "processed_explores": state["processed_explores"]}
