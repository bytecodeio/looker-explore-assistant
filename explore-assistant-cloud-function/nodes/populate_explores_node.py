import logging
import os
from typing import Dict
from google.cloud import bigquery
from utils.looker_sdk_utils import init_looker_sdk
from utils.bigquery_utils import populate_explores_from_looker, check_table_exists

def populate_explores_node(state: Dict) -> Dict:
    """
    Node that ensures the explores table exists and is populated
    with data from Looker's history and metadata.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with a success indicator
    """
    project_id = os.environ.get("PROJECT", "combined-genai-bi")
    dataset_id = os.environ.get("DATASET", "bytecode")
    table_id = "explores"
    
    logging.info(f"Checking and populating explores table in {project_id}.{dataset_id}.{table_id}")
    
    # Initialize clients
    client = bigquery.Client(project=project_id)
    sdk = init_looker_sdk()
    
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
                return {**state, "explores_table_populated": True}
        except Exception as e:
            logging.error(f"Error checking explores table data: {e}")
    
    # If we get here, we need to populate the table
    success = populate_explores_from_looker(client, project_id, dataset_id, sdk)
    
    if success:
        logging.info("Successfully populated explores table")
        return {**state, "explores_table_populated": True}
    else:
        logging.error("Failed to populate explores table")
        # Create a minimal default entry to prevent repeated failures
        try:
            populate_minimal_default(client, project_id, dataset_id, table_id)
            return {**state, "explores_table_populated": False, "explores_table_has_defaults": True}
        except Exception as e:
            logging.error(f"Error creating default entry: {e}")
            return {**state, "explores_table_populated": False, "explores_table_has_defaults": False}

def populate_minimal_default(client, project_id, dataset_id, table_id):
    """Create a minimal default entry in the explores table to prevent failures"""
    from utils.bigquery_utils import ensure_table_exists
    import time
    
    # Ensure the table exists
    if not ensure_table_exists(client, project_id, dataset_id, table_id, "explores"):
        raise Exception(f"Failed to create explores table {project_id}.{dataset_id}.{table_id}")
    
    # Create a default entry
    default_entry = [{
        'explore_name': 'default_explore',
        'model_name': 'default_model',
        'description': 'Default explore created automatically',
        'usage_count': 1,
        'last_used': time.strftime('%Y-%m-%d %H:%M:%S'),
        'popularity_score': 1.0,
        'fields_json': '{"dimensions": ["default_dimension"], "measures": ["default_measure"], "filters": []}'
    }]
    
    table_ref = client.dataset(dataset_id).table(table_id)
    errors = client.insert_rows_json(table_ref, default_entry)
    if errors:
        raise Exception(f"Error inserting default row: {errors}")
    logging.info(f"Created default entry in {project_id}.{dataset_id}.{table_id}")
    return True
