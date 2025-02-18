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
from IPython.display import Image, display

# Initialize Looker SDK using environment variables
def init_looker_sdk():
    required_env_vars = ["LOOKERSDK_BASE_URL", "LOOKERSDK_CLIENT_ID", "LOOKERSDK_CLIENT_SECRET"]
    for var in required_env_vars:
        if not os.getenv(var):
            raise EnvironmentError(f"Environment variable {var} is not set")
    return init40()

# Fetch Looker explores
def fetch_explores(sdk):
    return sdk.all_lookml_models(fields="name,explores")

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
        print(e.message)
        return []

# Fetch LookML dimensions and measures
def fetch_lookml_metadata(sdk, model, explore):
    data = sdk.lookml_model_explore(model, explore)
    dimensions = [f"name: {field.name}, type: {field.type}, description: {field.description}" for field in data.fields.dimensions]
    measures = [f"name: {field.name}, type: {field.type}, description: {field.description}" for field in data.fields.measures]
    return {"dimensions": dimensions, "measures": measures}

# Ask LLM about queries each explore can answer
def ask_llm_about_queries(model, explore, metadata):
    prompt = f"Given the following LookML metadata for the explore '{explore}' in model '{model}', what kind of queries can this explore answer?\n\nDimensions:\n{', '.join(metadata['dimensions'])}\n\nMeasures:\n{', '.join(metadata['measures'])}"
    llm = ChatVertexAI(model="gemini-1.5-flash")
    response = llm.generate_content(contents=prompt)
    return response.text

# Store information in BigQuery
def store_in_bigquery(project_id, dataset_id, table_id, data):
    client = bigquery.Client(project=project_id)
    table_ref = client.dataset(dataset_id).table(table_id)
    errors = client.insert_rows_json(table_ref, [data])
    if errors:
        print(f"Encountered errors while inserting rows: {errors}")

# Define the state for the LangGraph workflow
class State(TypedDict):
    messages: Annotated[list, add_messages]
    explores: List[str]
    metadata: Dict[str, Dict[str, List[str]]]

# Define the nodes for the LangGraph workflow
def get_explores_node(state: Dict) -> Dict:
    sdk = init_looker_sdk()
    explores = fetch_explores(sdk)
    explores_dict = [explore.__dict__ for explore in explores[:2]]  # Limit to 2 explores
    return {"explores": explores_dict}

def get_system_activity_node(state: Dict) -> Dict:
    sdk = init_looker_sdk()
    explore = state["explores"].pop(0)
    system_activity = fetch_system_activity(sdk, explore['name'])  # Use 'name' from dictionary
    return {"messages": [AIMessage(content=json.dumps(system_activity))]}

def get_lookml_metadata_node(state: Dict) -> Dict:
    sdk = init_looker_sdk()
    explore = state["explores"].pop(0)
    model = explore.model_name  # Replace with the actual model name if needed
    metadata = fetch_lookml_metadata(sdk, model, explore)  # Use 'name' from dictionary
    return {"metadata": {explore['name']: metadata}}

def ask_llm_node(state: Dict) -> Dict:
    explore = state["explores"].pop(0)
    metadata = state["metadata"][explore]
    llm_response = ask_llm_about_queries("model_name", explore, metadata)
    return {"messages": [AIMessage(content=llm_response)]}

def store_in_bigquery_node(state: Dict) -> Dict:
    project_id = "your-project-id"
    dataset_id = "explore_assistant"
    table_id = "explore_assistant_examples"
    data = {"explore": state["explores"].pop(0), "metadata": state["metadata"]}
    store_in_bigquery(project_id, dataset_id, table_id, data)
    return {"messages": [AIMessage(content="Data stored in BigQuery")]}

# Define the LangGraph workflow
graph_builder = StateGraph(State)
graph_builder.add_node("get_explores", get_explores_node)
graph_builder.add_node("get_system_activity", get_system_activity_node)
graph_builder.add_node("get_lookml_metadata", get_lookml_metadata_node)
graph_builder.add_node("ask_llm_to_describe_queries", ask_llm_node)
graph_builder.add_node("store_in_bigquery", store_in_bigquery_node)

graph_builder.add_edge(START, "get_explores")
graph_builder.add_edge("get_explores", "get_system_activity")
graph_builder.add_edge("get_system_activity", "get_lookml_metadata")
graph_builder.add_edge("get_lookml_metadata", "ask_llm_to_describe_queries")
graph_builder.add_edge("ask_llm_to_describe_queries", "store_in_bigquery")
graph_builder.add_edge("store_in_bigquery", END)

graph = graph_builder.compile()

def run_graph(user_input: str = "What were sales in 2022?"):
    config = {"configurable": {"thread_id": "1"}}
    events = graph.stream({"messages": [{"role": "user", "content": user_input}]}, config, stream_mode="values")
    for event in events:
        print(event["messages"][-1].content)

if __name__ == "__main__":
    # Generate and save the graph image
    image_bytes = graph.get_graph().draw_mermaid_png()
    image_path = "/home/colin/looker-explore-assistant/explore-assistant-cloud-function/graph_output.png"
    with open(image_path, "wb") as f:
        f.write(image_bytes)
    print(f"Graph image saved to {image_path}")

    run_graph()  # Auto-issue the query when the script is run
    while True:
        user_input = input("User: ")
        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break
        run_graph(user_input)
