import os
import json
from typing import Dict
from google.cloud import bigquery
from langchain_core.messages import AIMessage

def fetch_data_from_bigquery(project_id, dataset_id, table_id):
    client = bigquery.Client(project=project_id)
    query = f"SELECT * FROM `{project_id}.{dataset_id}.{table_id}`"
    query_job = client.query(query)
    results = query_job.result()
    rows = [dict(row) for row in results]
    return rows

def ask_llm_for_relevant_explores(user_query, explores, query_results):
    explore_descriptions = [
        f"{explore['name']} in model {explore['model_name']}" 
        for explore in explores 
        if 'name' in explore and 'model_name' in explore
    ]
    query_results_json = json.dumps(query_results)
    prompt = (
        f"Given the following explores and the user query '{user_query}', which explores can answer the query? "
        "Please return ONLY a JSON object with the relevant explores."
    )
    # Placeholder for LLM interaction
    return {"relevant_explores": explore_descriptions}

def fetch_and_return_data_node(state: Dict) -> Dict:
    project_id = "combined-genai-bi"
    dataset_id = "explore_assistant"
    table_id = "explore_descriptions"
    rows = fetch_data_from_bigquery(project_id, dataset_id, table_id)
    
    # Call LLM to determine relevant explores
    relevant_explores = ask_llm_for_relevant_explores(state["user_query"], rows, rows)
    
    return {"messages": [AIMessage(content=json.dumps(relevant_explores))]}
