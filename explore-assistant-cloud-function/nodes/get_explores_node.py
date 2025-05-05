import logging
import os
import ssl
from typing import Dict
from google.cloud import bigquery
from looker_sdk import error

# Import the centralized SDK initialization function
from utils.looker_sdk_utils import init_looker_sdk
from utils.bigquery_utils import ensure_table_exists

def fetch_explores(sdk):
    try:
        explores = sdk.all_lookml_models()
        return explores
    except error.SDKError as e:
        logging.error(f"Error fetching explores: {e}")
        return []

def check_table_data(client, project_id, dataset_id, table_id):
    try:
        # First ensure the table exists
        if not ensure_table_exists(client, project_id, dataset_id, table_id, "explore_descriptions"):
            logging.error(f"Failed to create or verify table {project_id}.{dataset_id}.{table_id}")
            return False
            
        # Then check if it has data
        query = f"SELECT COUNT(*) as count FROM `{project_id}.{dataset_id}.{table_id}`"
        query_job = client.query(query)
        result = query_job.result()
        count = [row['count'] for row in result][0]
        return count > 0
    except Exception as e:
        logging.error(f"Error checking table data: {e}")
        return False

def get_explores_node(state: Dict) -> Dict:
    project_id = os.environ.get("PROJECT", "combined-genai-bi")
    dataset_id = os.environ.get("DATASET", "bytecode")
    table_id = "explore_descriptions"
    
    # Create BigQuery client
    client = bigquery.Client(project=project_id)
    
    if check_table_data(client, project_id, dataset_id, table_id):
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
