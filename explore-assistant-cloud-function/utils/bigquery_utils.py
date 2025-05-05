import os
import logging
import json
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from looker_sdk import error

def check_table_exists(client, project_id, dataset_id, table_id):
    """Check if a table exists in BigQuery"""
    try:
        table_ref = f"{project_id}.{dataset_id}.{table_id}"
        client.get_table(table_ref)
        logging.info(f"Table {table_ref} exists")
        return True
    except Exception as e:
        logging.info(f"Table {table_ref} does not exist: {e}")
        return False

def create_explores_table(client, project_id, dataset_id, table_id):
    """Create the explores table in BigQuery"""
    table_ref = f"{project_id}.{dataset_id}.{table_id}"
    
    # Define schema for explores table
    schema = [
        bigquery.SchemaField("explore_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("model_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("description", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("usage_count", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("last_used", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("popularity_score", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("fields_json", "STRING", mode="NULLABLE"),
    ]
    
    # Create table
    table = bigquery.Table(table_ref, schema=schema)
    try:
        client.create_table(table)
        logging.info(f"Created table {table_ref}")
        return True
    except Exception as e:
        logging.error(f"Error creating table {table_ref}: {e}")
        return False

def create_explore_descriptions_table(client, project_id, dataset_id, table_id):
    """Create the explore_descriptions table in BigQuery"""
    table_ref = f"{project_id}.{dataset_id}.{table_id}"
    
    # Define schema for explore_descriptions table
    schema = [
        bigquery.SchemaField("explore", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("model", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("metadata", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("potential_queries", "STRING", mode="NULLABLE"),
    ]
    
    # Create table
    table = bigquery.Table(table_ref, schema=schema)
    try:
        client.create_table(table)
        logging.info(f"Created table {table_ref}")
        return True
    except Exception as e:
        logging.error(f"Error creating table {table_ref}: {e}")
        return False

def create_feedback_examples_table(client, project_id, dataset_id, table_id):
    """Create the feedback_examples table in BigQuery"""
    table_ref = f"{project_id}.{dataset_id}.{table_id}"
    
    # Define schema for feedback_examples table
    schema = [
        bigquery.SchemaField("original_query", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("user_feedback", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("original_params", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("improved_params", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="NULLABLE"),
    ]
    
    # Create table
    table = bigquery.Table(table_ref, schema=schema)
    try:
        client.create_table(table)
        logging.info(f"Created table {table_ref}")
        return True
    except Exception as e:
        logging.error(f"Error creating table {table_ref}: {e}")
        return False

def ensure_table_exists(client, project_id, dataset_id, table_id, table_type="explores"):
    """Check if table exists and create it if not"""
    if check_table_exists(client, project_id, dataset_id, table_id):
        return True
    
    # Create appropriate table based on type
    if table_type == "explores":
        return create_explores_table(client, project_id, dataset_id, table_id)
    elif table_type == "explore_descriptions":
        return create_explore_descriptions_table(client, project_id, dataset_id, table_id)
    elif table_type == "feedback_examples":
        return create_feedback_examples_table(client, project_id, dataset_id, table_id)
    else:
        logging.error(f"Unknown table type: {table_type}")
        return False

def ensure_dataset_exists(client, project_id, dataset_id):
    """Ensure the dataset exists, create it if it doesn't"""
    dataset_ref = f"{project_id}.{dataset_id}"
    try:
        client.get_dataset(dataset_ref)
        logging.info(f"Dataset {dataset_ref} exists")
        return True
    except NotFound:
        logging.info(f"Dataset {dataset_ref} does not exist, creating it")
        dataset = bigquery.Dataset(f"{project_id}.{dataset_id}")
        dataset.location = "US"  # Set the dataset location
        try:
            client.create_dataset(dataset)
            logging.info(f"Created dataset {dataset_ref}")
            return True
        except Exception as e:
            logging.error(f"Error creating dataset {dataset_ref}: {e}")
            return False
    except Exception as e:
        logging.error(f"Error checking dataset {dataset_ref}: {e}")
        return False

def populate_explores_from_looker(client, project_id, dataset_id, sdk, models=None):
    """Populate the explores table with data from Looker"""
    try:
        table_id = "explores"
        
        # Ensure dataset and table exist
        if not ensure_dataset_exists(client, project_id, dataset_id):
            logging.error(f"Failed to create or verify dataset {project_id}.{dataset_id}")
            return False
            
        if not ensure_table_exists(client, project_id, dataset_id, table_id, "explores"):
            logging.error(f"Failed to create or verify table {project_id}.{dataset_id}.{table_id}")
            return False
            
        # Get all models if none specified
        if not models:
            try:
                models = sdk.all_lookml_models()
                logging.info(f"Found {len(models)} models from Looker")
            except error.SDKError as e:
                logging.error(f"Error fetching models from Looker: {e}")
                return False
        
        # Prepare rows for insertion
        rows_to_insert = []
        
        for model in models:
            model_name = model.get('name')
            if not model_name:
                continue
                
            # Get all explores for this model
            try:
                model_detail = sdk.lookml_model(model_name)
                explores = model_detail.explores or []
                
                for explore in explores:
                    explore_name = explore.name
                    if not explore_name:
                        continue
                        
                    # Fetch detailed explore metadata
                    try:
                        explore_detail = sdk.lookml_model_explore(model_name, explore_name)
                        
                        # Extract fields as JSON
                        fields = {}
                        if hasattr(explore_detail, 'fields'):
                            if hasattr(explore_detail.fields, 'dimensions'):
                                fields['dimensions'] = [d.name for d in explore_detail.fields.dimensions]
                            if hasattr(explore_detail.fields, 'measures'):
                                fields['measures'] = [m.name for m in explore_detail.fields.measures]
                            if hasattr(explore_detail.fields, 'filters'):
                                fields['filters'] = [f.name for f in explore_detail.fields.filters]
                        
                        # Create row
                        row = {
                            'explore_name': explore_name,
                            'model_name': model_name,
                            'description': getattr(explore_detail, 'description', ''),
                            'usage_count': 0,  # Default until we get actual usage
                            'last_used': None, # Default until we get actual usage
                            'popularity_score': 0.0, # Default until we calculate
                            'fields_json': json.dumps(fields)
                        }
                        rows_to_insert.append(row)
                        
                    except error.SDKError as e:
                        logging.warning(f"Error fetching explore details for {model_name}.{explore_name}: {e}")
                        continue
                        
            except error.SDKError as e:
                logging.warning(f"Error fetching model details for {model_name}: {e}")
                continue
        
        # Insert rows into BigQuery
        if rows_to_insert:
            table_ref = client.dataset(dataset_id).table(table_id)
            errors = client.insert_rows_json(table_ref, rows_to_insert)
            if errors:
                logging.error(f"Errors inserting rows into {project_id}.{dataset_id}.{table_id}: {errors}")
                return False
            
            logging.info(f"Successfully populated {len(rows_to_insert)} explores into {project_id}.{dataset_id}.{table_id}")
            return True
        else:
            logging.warning("No explores found to insert")
            return False
            
    except Exception as e:
        logging.error(f"Error populating explores table: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False
