import logging
import json
from datetime import datetime
from typing import Dict, Any
from google.cloud import bigquery

def is_positive_confirmation(user_response: str) -> bool:
    """
    Check if user response is a positive confirmation
    
    Args:
        user_response: The user's response text
        
    Returns:
        True if the response is a confirmation
    """
    positive_phrases = [
        "yes", "yeah", "yep", "correct", "right", "good", 
        "perfect", "better", "fixed", "works", "great", "awesome",
        "that's it", "that is it", "that works", "looks good"
    ]
    
    user_response_lower = user_response.lower()
    return any(phrase in user_response_lower for phrase in positive_phrases)

def store_example_in_bigquery(
    project_id: str,
    dataset_id: str,
    table_id: str,
    example_data: Dict[str, Any]
) -> bool:
    """
    Store the successful example in BigQuery
    
    Args:
        project_id: GCP project ID
        dataset_id: BigQuery dataset ID
        table_id: BigQuery table ID
        example_data: Example data to store
        
    Returns:
        True if storage was successful
    """
    try:
        client = bigquery.Client(project=project_id)
        table_ref = client.dataset(dataset_id).table(table_id)
        
        # Check if table exists, if not create it
        try:
            client.get_table(table_ref)
        except Exception:
            # Table doesn't exist, create it
            schema = [
                bigquery.SchemaField("original_query", "STRING"),
                bigquery.SchemaField("user_feedback", "STRING"),
                bigquery.SchemaField("original_params", "STRING"),
                bigquery.SchemaField("improved_params", "STRING"),
                bigquery.SchemaField("timestamp", "TIMESTAMP")
            ]
            
            table = bigquery.Table(table_ref, schema=schema)
            client.create_table(table)
            logging.info(f"Created table {project_id}.{dataset_id}.{table_id}")
        
        # Insert the row
        rows_to_insert = [{
            "original_query": example_data.get("original_query", ""),
            "user_feedback": example_data.get("user_feedback", ""),
            "original_params": json.dumps(example_data.get("original_params", {})),
            "improved_params": json.dumps(example_data.get("improved_params", {})),
            "timestamp": datetime.now().isoformat()
        }]
        
        errors = client.insert_rows_json(table_ref, rows_to_insert)
        
        if not errors:
            logging.info("Successfully stored example in BigQuery")
            return True
        else:
            logging.error(f"Errors inserting rows: {errors}")
            return False
            
    except Exception as e:
        logging.error(f"Error storing example in BigQuery: {e}")
        return False

def example_storage_node(state: Dict) -> Dict:
    """
    Store successful examples in BigQuery for future learning
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state
    """
    # Check if we're awaiting verification and if there's a user response
    if not state.get("awaiting_verification", False) or not state.get("user_response", ""):
        return state
    
    user_response = state.get("user_response", "")
    
    # Check if the response is positive
    if not is_positive_confirmation(user_response):
        return {
            **state,
            "awaiting_verification": False,
            "messages": state.get("messages", []) + [
                AIMessage(content="I understand this still doesn't meet your needs. Please provide more details about what's missing or incorrect.")
            ]
        }
    
    # This is a confirmed good example, store it in BigQuery
    example_data = {
        "original_query": state.get("user_query", ""),
        "user_feedback": state.get("user_feedback", ""),
        "original_params": state.get("original_explore_params", {}),
        "improved_params": state.get("explore_params", {})
    }
    
    # Store in BigQuery
    project_id = "your-project-id"  # Replace with your actual project ID
    dataset_id = "explore_assistant"
    table_id = "feedback_examples"
    
    storage_success = store_example_in_bigquery(
        project_id, 
        dataset_id, 
        table_id, 
        example_data
    )
    
    # Update state
    return {
        **state,
        "awaiting_verification": False,
        "example_stored": storage_success,
        "messages": state.get("messages", []) + [
            AIMessage(content="Great! I'm glad the improved explore works for you. I've saved this example to help improve future recommendations.")
        ]
    }
