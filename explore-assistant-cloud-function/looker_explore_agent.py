from typing import Annotated, Dict, List
import json
import os
import re
from google.cloud import bigquery
from looker_sdk import init40, models40 as models, error
from langchain_google_vertexai import ChatVertexAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from typing_extensions import TypedDict
from google.cloud.exceptions import NotFound
import logging
import time
from langgraph.checkpoint.memory import MemorySaver

logging.basicConfig(level=logging.INFO)

# Initialize Looker SDK using environment variables
def init_looker_sdk():
    required_env_vars = ["LOOKERSDK_BASE_URL", "LOOKERSDK_CLIENT_ID", "LOOKERSDK_CLIENT_SECRET"]
    for var in required_env_vars:
        if not os.getenv(var):
            raise EnvironmentError(f"Environment variable {var} is not set")
    return init40()

# Fetch Looker explores
def fetch_explores(sdk):
    try:
        models = sdk.all_lookml_models(fields="name,explores")
        explores = []
        for model in models:
            for explore in model.explores:
                explore_dict = explore.__dict__
                explore_dict['model_name'] = model.name  # Add model_name attribute
                explores.append(explore_dict)
        logging.info(f"Fetched explores: {explores}")
        return explores
    except error.SDKError as e:
        logging.error(f"Error fetching explores: {e}")
        return []

# Fetch Looker system activity
def fetch_system_activity(sdk, explore):
    try:
        response = sdk.run_inline_query(
            result_format='json',
            cache=True,
            body=models.WriteQuery(
                model="system__activity",
                view="history",
                fields=["query.slug", "query.view", "query.dynamic_fields", "query.formatted_fields", "query.filters", "query.filter_expression", "query.formatted_pivots", "query.sorts", "query.limit", "query.column_limit", "query.count"],
                filters={"query.view": explore, "history.status": "complete"},
                sorts=["history.completed_time desc", "query.view"],
                limit="30",
            )
        )
        return json.loads(response)[0:10]
    except error.SDKError as e:
        logging.error(e.message)
        return []

# Fetch LookML dimensions and measures
def fetch_lookml_metadata(sdk, model, explore):
    data = sdk.lookml_model_explore(model, explore)
    dimensions = [
        {
            "label": field.label,
            "name": field.name,
            "description": field.description,
            "type": field.type
        }
        for field in data.fields.dimensions
    ]
    measures = [
        {
            "label": field.label,
            "name": field.name,
            "description": field.description,
            "type": field.type
        }
        for field in data.fields.measures
    ]
    return {"dimensions": dimensions, "measures": measures}

def ask_llm_about_queries(model, explore, metadata):
    dimensions = [f"{dim['label']} ({dim['name']}): {dim['description']} [{dim['type']}]" for dim in metadata.get('dimensions', [])]
    measures = [f"{meas['label']} ({meas['name']}): {meas['description']} [{meas['type']}]" for meas in metadata.get('measures', [])]
    prompt = f"Given the following LookML metadata for the explore '{explore}' in model '{model}', what kind of queries can this explore answer? Please don't reply with sql, just the name of the explore and a list of some sample natural language questions it can answer.\n\nDimensions:\n{', '.join(dimensions)}\n\nMeasures:\n{', '.join(measures)}"
    llm = ChatVertexAI(model_name="gemini-pro")
    response = llm.invoke(prompt)
    return response.content

# Store information in BigQuery
def store_in_bigquery(project_id, dataset_id, table_id, data):
    client = bigquery.Client(project=project_id)
    table_ref = client.dataset(dataset_id).table(table_id)
    
    # Create the table if it doesn't exist
    try:
        client.get_table(table_ref)
        logging.info(f"Table {table_id} already exists in dataset {dataset_id}.")
    except NotFound:
        schema = [
            bigquery.SchemaField("explore", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("model", "STRING", mode="REQUIRED"),  # Add model field
            bigquery.SchemaField("metadata", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("potential_queries", "STRING", mode="REQUIRED"),
        ]
        table = bigquery.Table(table_ref, schema=schema)
        client.create_table(table)
        logging.info(f"Created table {table_id} in dataset {dataset_id}.")
        time.sleep(2)  # Wait for 2 seconds to allow the change to propagate

    # Convert metadata to JSON string
    data["metadata"] = json.dumps(data["metadata"])
    data["potential_queries"] = data["potential_queries"]  # Store the LLM generated summary

    errors = client.insert_rows_json(table_ref, [data])
    if errors:
        logging.error(f"Encountered errors while inserting rows: {errors}")
    else:
        logging.info("Data inserted successfully into BigQuery.")

# Fetch data from BigQuery table
def fetch_data_from_bigquery(project_id, dataset_id, table_id):
    client = bigquery.Client(project=project_id)
    query = f"SELECT * FROM `{project_id}.{dataset_id}.{table_id}`"
    query_job = client.query(query)
    results = query_job.result()
    rows = [dict(row) for row in results]
    return rows

# Check if the table contains any data
def check_table_data(project_id, dataset_id, table_id):
    client = bigquery.Client(project=project_id)
    query = f"SELECT COUNT(*) as count FROM `{project_id}.{dataset_id}.{table_id}`"
    query_job = client.query(query)
    results = query_job.result()
    for row in results:
        if row["count"] > 0:
            return True
    return False

# Custom reducer function to handle multiple values for explores
def add_explores(existing_explores, new_explores):
    return existing_explores + new_explores

# Custom reducer function to handle multiple values for metadata
def add_metadata(existing_metadata, new_metadata):
    for key, value in new_metadata.items():
        if key in existing_metadata:
            existing_metadata[key].update(value)
        else:
            existing_metadata[key] = value
    return existing_metadata

# Define the state for the LangGraph workflow
class State(TypedDict):
    messages: Annotated[list, add_messages]
    explores: Annotated[List[Dict], add_explores]
    metadata: Annotated[Dict[str, Dict[str, List[str]]], add_metadata]
    potential_queries: str
    current_explore_index: int  # Add an index to keep track of the current explore
    processed_explores: set  # Add a set to track processed explores

# Define the nodes for the LangGraph workflow
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
    return {"explores": explores[:10], "current_explore_index": 0, "processed_explores": set()}  # Initialize the index and processed_explores set

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

def get_lookml_metadata_node(state: Dict) -> Dict:
    if state["current_explore_index"] >= len(state["explores"]):
        logging.error("Explores list is empty in get_lookml_metadata_node.")
        return state  # Return state as is if explores list is empty
    sdk = init_looker_sdk()
    while state["current_explore_index"] < len(state["explores"]):
        explore = state["explores"][state["current_explore_index"]]
        model = explore['model_name']  # Use 'model_name' from dictionary
        try:
            metadata = fetch_lookml_metadata(sdk, model, explore['name'])  # Use 'name' from dictionary
            if "metadata" not in state:
                state["metadata"] = {}  # Initialize metadata if it doesn't exist
            state["metadata"][explore['name']] = metadata  # Store metadata in state
            logging.info(f"Fetched metadata for explore: {explore['name']}")
        except error.SDKError as e:
            logging.error(f"Error fetching LookML metadata for explore {explore['name']}: {e}")
            state["current_explore_index"] += 1
            continue  # Skip to the next explore
        state["current_explore_index"] += 1
    return {"metadata": state["metadata"], "explores": state["explores"], "current_explore_index": state["current_explore_index"], "processed_explores": state["processed_explores"]}  # Ensure explores is returned

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

def fetch_and_return_data_node(state: Dict) -> Dict:
    project_id = "combined-genai-bi"
    dataset_id = "explore_assistant"
    table_id = "explore_descriptions"
    rows = fetch_data_from_bigquery(project_id, dataset_id, table_id)
    return {"messages": [AIMessage(content=json.dumps(rows))]}

# Initialize MemorySaver for logging
memory = MemorySaver()

# Define the LangGraph workflow
graph_builder = StateGraph(State)
graph_builder.add_node("get_explores", get_explores_node)
graph_builder.add_node("get_system_activity", get_system_activity_node)
graph_builder.add_node("get_lookml_metadata", get_lookml_metadata_node)
graph_builder.add_node("ask_llm_and_store", ask_llm_and_store_node)
graph_builder.add_node("fetch_and_return_data", fetch_and_return_data_node)

graph_builder.add_edge(START, "get_explores")
graph_builder.add_edge("get_explores", "get_system_activity")
graph_builder.add_edge("get_system_activity", "get_lookml_metadata")
graph_builder.add_edge("get_lookml_metadata", "ask_llm_and_store")

# Use add_conditional_edges for conditional transitions
graph_builder.add_conditional_edges(
    "ask_llm_and_store",
    lambda state: "ask_llm_and_store" if state["current_explore_index"] < len(state["explores"]) else "fetch_and_return_data",
    {"ask_llm_and_store": "ask_llm_and_store", "fetch_and_return_data": "fetch_and_return_data"}
)

graph_builder.add_edge("fetch_and_return_data", END)

# Compile the graph with MemorySaver for logging
graph = graph_builder.compile(checkpointer=memory)

def run_graph():
    logging.info("Starting the graph execution.")
    config = {
        "configurable": {"thread_id": "1"},
        "recursion_limit": 100  # Increase the recursion limit
    }
    events = graph.stream({"messages": [{"role": "user", "content": "start"}]}, config, stream_mode="values")
    for event in events:
        logging.info(f"Event: {event}")
        logging.info(event["messages"][-1].content)

if __name__ == "__main__":
    # Generate and save the graph image
    logging.info("Generating the graph image.")
    image_bytes = graph.get_graph().draw_mermaid_png()
    image_path = "/home/colin/looker-explore-assistant/explore-assistant-cloud-function/graph_output.png"
    with open(image_path, "wb") as f:
        f.write(image_bytes)
    logging.info(f"Graph image saved to {image_path}")

    run_graph()
    logging.info("Graph execution completed.")
