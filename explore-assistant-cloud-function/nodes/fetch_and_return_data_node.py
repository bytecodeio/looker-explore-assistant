import os
import json
import logging
from typing import Dict
from google.cloud import bigquery
from langchain_core.messages import AIMessage
from utils.response_utils import add_message_to_state, validate_output_format

def fetch_data_from_bigquery(project_id, dataset_id, table_id):
    client = bigquery.Client(project=project_id)
    query = f"SELECT * FROM `{project_id}.{dataset_id}.{table_id}`"
    query_job = client.query(query)
    results = query_job.result()
    rows = [dict(row) for row in results]
    return rows

def ask_llm_for_relevant_explores(user_query, explores, query_results, model_manager=None):
    explore_descriptions = [
        f"{explore['name']} in model {explore['model_name']}" 
        for explore in explores 
        if 'name' in explore and 'model_name' in explore
    ]
    
    if not model_manager:
        # Return simple response if no model manager
        return {"relevant_explores": explore_descriptions}
    
    try:
        # Get model for explore selection
        model = model_manager.get_model_for_task("explore_selection")
        
        # Create prompt for LLM
        prompt = (
            f"Given the following explores and the user query '{user_query}', which explores would be most relevant? "
            f"The available explores are: {', '.join(explore_descriptions)}.\n\n"
            "Please rank the top 3 most relevant explores for answering this query and explain why each one is relevant."
        )
        
        # Get LLM response
        response = model.invoke(prompt)
        
        # Log the response
        logging.info(f"LLM response for relevant explores: {response[:100]}...")
        
        return {
            "relevant_explores": explore_descriptions[:3],  # Default to first 3
            "llm_explanation": response
        }
    except Exception as e:
        logging.error(f"Error getting relevant explores from LLM: {e}")
        return {"relevant_explores": explore_descriptions}

def fetch_and_return_data_node(state: Dict) -> Dict:
    # Get environment variables with defaults
    project_id = os.environ.get("PROJECT", "combined-genai-bi")
    dataset_id = os.environ.get("DATASET", "bytecode")
    table_id = "explore_descriptions"
    
    # Fetch stored explore data
    try:
        rows = fetch_data_from_bigquery(project_id, dataset_id, table_id)
        logging.info(f"Fetched {len(rows)} rows from {project_id}.{dataset_id}.{table_id}")
    except Exception as e:
        logging.error(f"Error fetching data from BigQuery: {e}")
        rows = []
    
    # Get user query from state
    user_query = state.get("user_query", "")
    if not user_query:
        logging.warning("No user query found in state")
        return add_message_to_state(state, "I'm not sure what you're asking about. Could you please rephrase your question?")
        
    # Call LLM to determine relevant explores
    model_manager = state.get("model_manager")
    relevant_explores_info = ask_llm_for_relevant_explores(user_query, rows, rows, model_manager)
    
    # Get explore URL for the top relevant explore if available
    explore_url = ""
    if rows and "relevant_explores" in relevant_explores_info and relevant_explores_info["relevant_explores"]:
        # Find the first matching explore from the relevance list
        for explore_desc in relevant_explores_info["relevant_explores"]:
            parts = explore_desc.split(" in model ")
            if len(parts) == 2:
                explore_name, model_name = parts[0], parts[1]
                
                # Find the matching row
                for row in rows:
                    if row.get("explore") == explore_name and row.get("model") == model_name:
                        # Generate a Looker explore URL - this is a simplified version
                        looker_base_url = os.environ.get("LOOKERSDK_BASE_URL", "")
                        if looker_base_url:
                            explore_url = f"{looker_base_url}/explore/{model_name}/{explore_name}"
                            break
                
                if explore_url:
                    break
    
    # Create a comprehensive response to the user
    explanation = relevant_explores_info.get("llm_explanation", "")
    if not explanation and "relevant_explores" in relevant_explores_info:
        explanation = f"Based on your question, I found these relevant explores: {', '.join(relevant_explores_info['relevant_explores'][:3])}"
    
    # Add the response message
    response = f"{explanation}\n\n"
    
    # Add explore URL if available
    if explore_url:
        response += f"You can explore the data here: {explore_url}"
    
    # Update state with response and URL
    updated_state = add_message_to_state(state, response)
    updated_state["explore_url"] = explore_url
    
    # Ensure all required fields are present in the output
    return validate_output_format(updated_state)
