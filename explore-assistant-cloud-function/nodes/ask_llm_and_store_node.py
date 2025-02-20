import logging
from typing import Dict
from google.cloud import bigquery
from looker_sdk import init40, error
from langchain_core.messages import AIMessage

def ask_llm_about_queries(model_name, explore_name, metadata):
    # Placeholder for LLM interaction
    return f"LLM response for {model_name}.{explore_name}"

def store_in_bigquery(project_id, dataset_id, table_id, data):
    client = bigquery.Client(project=project_id)
    table_ref = client.dataset(dataset_id).table(table_id)
    errors = client.insert_rows_json(table_ref, [data])
    if errors:
        logging.error(f"Error storing data in BigQuery: {errors}")

def ask_llm_and_store_node(state: Dict) -> Dict:
    if state["current_explore_index"] >= len(state["explores"]):
        logging.error("Explores list is empty in ask_llm_and_store_node.")
        return state  # Return state as is if explores list is empty
    explore = state["explores"][state["current_explore_index"]]
    explore_name = explore['name']  # Use 'name' from dictionary
    if explore_name in state["processed_explores"]:
        logging.info(f"Explore {explore_name} already processed. Skipping.")
        state["current_explore_index"] += 1
        return state  # Skip already processed explores
    metadata = state["metadata"].get(explore_name, {})  # Use explore_name as the key
    llm_response = ask_llm_about_queries(explore['model_name'], explore_name, metadata)  # Use 'model_name' and explore_name
    if "potential_queries" not in state:
        state["potential_queries"] = {}
    state["potential_queries"][explore_name] = llm_response  # Store the LLM generated summary
    logging.info(f"LLM response for explore: {explore_name}")

    project_id = "combined-genai-bi"
    dataset_id = "explore_assistant"
    table_id = "explore_descriptions"
    logging.info(f"Storing data for explore: {explore_name} using these potential queries: {state['potential_queries'][explore_name]}")
    if explore_name in state["potential_queries"]:
        logging.info(f"Potential queries found for explore: {explore_name}")
        data = {
            "explore": explore_name,
            "model": explore['model_name'],  # Add model field
            "metadata": explore,
            "potential_queries": state["potential_queries"][explore_name]
        }
        store_in_bigquery(project_id, dataset_id, table_id, data)
    state["processed_explores"].add(explore_name)  # Mark explore as processed
    state["current_explore_index"] += 1  # Increment the index after storing data
    logging.info(f"Updated current_explore_index: {state['current_explore_index']}")
    return {"messages": [AIMessage(content=llm_response)], "potential_queries": state["potential_queries"], "explores": state["explores"], "current_explore_index": state["current_explore_index"], "processed_explores": state["processed_explores"]}  # Ensure potential_queries and explores are returned
