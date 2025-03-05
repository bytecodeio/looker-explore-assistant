import logging
from typing import Dict, Any
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage
from langsmith import trace
from langchain.chains.base import Chain

# Import nodes
from nodes.user_query_node import user_query_node
from nodes.explore_selector_node import explore_selector_node
from nodes.semantic_model_node import semantic_model_node
from nodes.explore_params_generator_node import explore_params_generator_node
from nodes.filter_value_fetcher_node import filter_value_fetcher_node
from nodes.execute_explore_node import execute_explore_node

# Import utils
from utils.model_manager import ModelManager

class LookerExploreWorkflow(Chain):
    """
    A workflow that processes user queries and generates Looker explores
    """
    
    def __init__(self, model_manager: ModelManager = None, looker_instance_url: str = None):
        super().__init__()
        self.model_manager = model_manager or ModelManager()
        self.looker_instance_url = looker_instance_url or "https://your-looker-instance.cloud.looker.com"
        
    @property
    def input_keys(self) -> list:
        return ["query"]
        
    @property
    def output_keys(self) -> list:
        return ["response", "explore_url"]

    @trace
    def _call(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the workflow pipeline"""
        # Initialize state with user query
        state = {
            "user_query": inputs["query"],
            "model_manager": self.model_manager,
            "looker_instance_url": self.looker_instance_url
        }
        
        # Process user query
        with trace("user_query_processing") as span:
            state = user_query_node(state)
            span.add_outputs({"state": state})
        
        # Select relevant explore
        with trace("explore_selection") as span:
            # Get the appropriate model for explore selection
            explore_selection_model = self.model_manager.get_model_for_task("explore_selection")
            state["llm"] = explore_selection_model
            state = explore_selector_node(state)
            span.add_outputs({"state": state})
            
        # If no explore was selected, return early
        if "selected_explore" not in state:
            return {"response": "I couldn't determine which data explore to use for your question.", "explore_url": ""}
        
        # Fetch semantic model for selected explore
        with trace("semantic_model_loading") as span:
            state = semantic_model_node(state)
            span.add_outputs({"state": state})
            
        # If semantic model failed to load, return early
        if "semantic_model" not in state:
            return {"response": "I couldn't load the necessary data model to answer your question.", "explore_url": ""}
        
        # Generate explore parameters
        with trace("explore_params_generation") as span:
            # Get the powerful thinking model for parameter generation
            params_model = self.model_manager.get_model_for_task("explore_params_generation")
            state["llm"] = params_model
            state = explore_params_generator_node(state)
            span.add_outputs({"state": state})
        
        # Fetch filter values if needed
        with trace("filter_value_fetching") as span:
            # Use a fast model for filter value selection
            filter_model = self.model_manager.get_model_for_task("filter_selection")
            state["llm"] = filter_model
            state = filter_value_fetcher_node(state)
            span.add_outputs({"state": state})
            
        # Execute explore and get results
        with trace("explore_execution") as span:
            # Get the summary model for data summarization
            summary_model = self.model_manager.get_model_for_task("summarization")
            state["llm"] = summary_model
            state = execute_explore_node(state)
            span.add_outputs({"state": state})
            
        # Compile final response
        # Get all content messages except the last one (URL message)
        content_messages = [msg.content for msg in state.get("messages", []) if hasattr(msg, "content")]
        text_response = "\n\n".join(content_messages[:-1] if len(content_messages) > 1 else content_messages)
        
        # Return both text response and URL
        return {
            "response": text_response,
            "explore_url": state.get("explore_url", "")
        }