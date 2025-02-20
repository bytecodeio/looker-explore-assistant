from typing import Annotated, Dict, List
import json
import os
import logging
from google.cloud import bigquery
from looker_sdk import init40, error
from langchain_google_vertexai import ChatVertexAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage
from typing_extensions import TypedDict
from langgraph.checkpoint.memory import MemorySaver
from nodes import (
    get_explores_node,
    get_system_activity_node,
    get_lookml_metadata_node,
    ask_llm_and_store_node,
    fetch_and_return_data_node
)
from utils import (
    add_explores,
    add_metadata
)

logging.basicConfig(level=logging.INFO)

# Define the state for the LangGraph workflow
class State(TypedDict):
    messages: Annotated[list, add_messages]
    explores: Annotated[List[Dict], add_explores]
    metadata: Annotated[Dict[str, Dict[str, List[str]]], add_metadata]
    potential_queries: str
    current_explore_index: int
    processed_explores: set
    user_query: str  # Add user_query to the state

# Initialize MemorySaver for logging
memory = MemorySaver()

# Define the LangGraph workflow
graph_builder = StateGraph(State)
graph_builder.add_node("get_explores", get_explores_node)
graph_builder.add_node("get_system_activity", get_system_activity_node)
graph_builder.add_node("get_lookml_metadata", get_lookml_metadata_node)
graph_builder.add_node("ask_llm_and_store", ask_llm_and_store_node)
graph_builder.add_node("find_the_explores_to_use", fetch_and_return_data_node)

graph_builder.add_edge(START, "get_explores")
graph_builder.add_edge("get_explores", "get_system_activity")
graph_builder.add_edge("get_system_activity", "get_lookml_metadata")
graph_builder.add_edge("get_lookml_metadata", "ask_llm_and_store")

# Use add_conditional_edges for conditional transitions
graph_builder.add_conditional_edges(
    "ask_llm_and_store",
    lambda state: "ask_llm_and_store" if state["current_explore_index"] < len(state["explores"]) else "find_the_explores_to_use",
    {"ask_llm_and_store": "ask_llm_and_store", "find_the_explores_to_use": "find_the_explores_to_use"}
)

graph_builder.add_edge("find_the_explores_to_use", END)

# Compile the graph with MemorySaver for logging
graph = graph_builder.compile(checkpointer=memory)

def run_graph():
    logging.info("Starting the graph execution.")
    config = {
        "configurable": {"thread_id": "1"},
        "recursion_limit": 100  # Increase the recursion limit
    }
    user_query = input("Please enter your query: ")  # Get the user's query
    events = graph.stream({"messages": [{"role": "user", "content": user_query}], "user_query": user_query}, config, stream_mode="values")
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
