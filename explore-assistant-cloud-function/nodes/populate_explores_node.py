import logging
import os
from typing import Dict
from google.cloud import bigquery
from utils.looker_sdk_utils import init_looker_sdk
from utils.bigquery_utils import check_table_exists, ensure_table_exists
from utils.looker_history_utils import populate_explores_from_history
from utils.model_manager import ModelManager

def populate_explores_node(state: Dict) -> Dict:
    """
    Node that ensures the explores table exists and is populated
    with data from Looker's history and metadata.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with a success indicator and Looker SDK
    """
    project_id = os.environ.get("PROJECT", "combined-genai-bi")
    dataset_id = os.environ.get("DATASET", "bytecode")
    table_id = "explores"
    
    logging.info(f"Checking and populating explores table in {project_id}.{dataset_id}.{table_id}")
    
    # Initialize clients
    client = bigquery.Client(project=project_id)
    sdk = init_looker_sdk()
    
    # Initialize ModelManager for LLM access
    try:
        model_name = os.environ.get("MODEL_NAME", "gemini-2.0-flash-lite")
        model_manager = ModelManager(model_name=model_name)
        logging.info(f"Initialized ModelManager with model: {model_name}")
    except Exception as e:
        logging.error(f"Error initializing ModelManager: {e}")
        # Add SDK to state even on error
        return {**state, "explores_table_populated": False, "looker_sdk": sdk}
    
    # Check if table exists and has data
    table_exists = check_table_exists(client, project_id, dataset_id, table_id)
    if table_exists:
        # Check if there's data
        query = f"SELECT COUNT(*) as count FROM `{project_id}.{dataset_id}.{table_id}`"
        try:
            query_job = client.query(query)
            result = query_job.result()
            count = [row['count'] for row in result][0]
            if count > 0:
                logging.info(f"Explores table already exists with {count} rows")
                # Add SDK to state
                return {**state, "explores_table_populated": True, "looker_sdk": sdk}
        except Exception as e:
            logging.error(f"Error checking explores table data: {e}")
    
    # If we get here, we need to populate the table using Looker History
    success = populate_explores_from_history(client, project_id, dataset_id, table_id, sdk, model_manager)
    
    if success:
        logging.info("Successfully populated explores table from Looker history")
        # Add SDK to state
        return {**state, "explores_table_populated": True, "looker_sdk": sdk}
    else:
        logging.error("Failed to populate explores table")
        # Add SDK to state even on failure
        return {**state, "explores_table_populated": False, "looker_sdk": sdk}
