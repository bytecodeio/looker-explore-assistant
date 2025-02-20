import logging
from typing import Dict
from google.cloud import bigquery
from looker_sdk import init40, error

def init_looker_sdk():
    sdk = init40()
    return sdk

def fetch_explores(sdk):
    try:
        explores = sdk.all_lookml_models()
        return explores
    except error.SDKError as e:
        logging.error(f"Error fetching explores: {e}")
        return []

def check_table_data(project_id, dataset_id, table_id):
    client = bigquery.Client(project=project_id)
    query = f"SELECT COUNT(*) as count FROM `{project_id}.{dataset_id}.{table_id}`"
    query_job = client.query(query)
    result = query_job.result()
    count = [row['count'] for row in result][0]
    return count > 0

def get_explores_node(state: Dict) -> Dict:
    project_id = "combined-genai-bi"
    dataset_id = "explore_assistant"
    table_id = "explore_descriptions"
    if check_table_data(project_id, dataset_id, table_id):
        logging.info("Table contains data. Transitioning to fetch_and_return_data node.")
        return {"transition_to": "fetch_and_return_data"}
    
    sdk = init_looker_sdk()
    explores = fetch_explores(sdk)
    if not explores:
        logging.error("No explores found.")
    # filter to only explores in the model "popular_names"
    explores = [explore for explore in explores if explore['model_name'] == "popular_names"]
    logging.info(f"Filtered explores: {explores}")
    return {"explores": explores[:10], "current_explore_index": 0, "processed_explores": set(), "user_query": state.get("user_query", "")}  # Initialize user_query
