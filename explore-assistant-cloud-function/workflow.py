import logging
from typing import Dict, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage
from langsmith import trace
from langchain.chains.base import Chain

# Import existing nodes
from nodes.user_query_node import user_query_node
from nodes.explore_selector_node import explore_selector_node
from nodes.semantic_model_node import semantic_model_node
from nodes.explore_params_generator_node import explore_params_generator_node
from nodes.filter_value_fetcher_node import filter_value_fetcher_node
from nodes.execute_explore_node import execute_explore_node

# Import new feedback handling nodes
from nodes.feedback_detection_node import feedback_detection_node
from nodes.explore_regeneration_node import explore_regeneration_node
from nodes.user_verification_node import user_verification_node
from nodes.example_storage_node import example_storage_node

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
        self._conversation_state = {}
        
    @property
    def input_keys(self) -> list:
        return ["query", "request_visualization"]
        
    @property
    def output_keys(self) -> list:
        return ["response", "explore_url", "visualization_data"]

    def _process_feedback(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process feedback after an initial explore has been generated
        
        Args:
            inputs: Input containing user feedback
            
        Returns:
            Response with regenerated explore
        """
        # Start with previous state + new user feedback
        state = {
            **self._conversation_state,
            "user_feedback": inputs["query"]
        }
        
        # Detect if the feedback indicates the need for regeneration
        with trace("feedback_detection") as span:
            fast_model = self.model_manager.get_fast_model()
            state["llm"] = fast_model
            state = feedback_detection_node(state)
            span.add_outputs({"state": state})
        
        # If regeneration is needed, regenerate the explore
        if state.get("requires_regeneration", False):
            # Regenerate explore parameters
            with trace("explore_regeneration") as span:
                thinking_model = self.model_manager.get_model_for_task("explore_params_generation")
                state["llm"] = thinking_model
                state = explore_regeneration_node(state)
                span.add_outputs({"state": state})
                
            # Fetch filter values if needed
            with trace("filter_value_fetching") as span:
                filter_model = self.model_manager.get_model_for_task("filter_selection")
                state["llm"] = filter_model
                state = filter_value_fetcher_node(state)
                span.add_outputs({"state": state})
                
            # Execute explore and get results
            with trace("explore_execution") as span:
                summary_model = self.model_manager.get_model_for_task("summarization")
                state["llm"] = summary_model
                state = execute_explore_node(state)
                span.add_outputs({"state": state})
                
            # Add verification request
            with trace("user_verification") as span:
                state = user_verification_node(state)
                span.add_outputs({"state": state})
        else:
            # No regeneration needed, just acknowledge the feedback
            state["messages"].append(AIMessage(content="Thank you for your feedback!"))
            
        # Update conversation state
        self._conversation_state = state
        
        # Compile final response
        content_messages = [msg.content for msg in state.get("messages", []) if hasattr(msg, "content")]
        response = "\n\n".join(content_messages)
        
        return {
            "response": response,
            "explore_url": state.get("explore_url", ""),
            "visualization_data": state.get("visualization_data", None)
        }
        
    def _process_verification(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process verification response after a regenerated explore
        
        Args:
            inputs: Input containing user verification response
            
        Returns:
            Response with acknowledgment and potentially stored example
        """
        # Start with previous state + user response
        state = {
            **self._conversation_state,
            "user_response": inputs["query"]
        }
        
        # Process verification and store example if positive
        with trace("example_storage") as span:
            state = example_storage_node(state)
            span.add_outputs({"state": state})
            
        # Update conversation state
        self._conversation_state = state
        
        # Compile final response
        content_messages = [msg.content for msg in state.get("messages", []) if hasattr(msg, "content")]
        response = "\n\n".join(content_messages)
        
        return {
            "response": response,
            "explore_url": state.get("explore_url", ""),
            "visualization_data": state.get("visualization_data", None)
        }

    @trace
    def _call(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the workflow pipeline"""
        # Check if this is feedback on a previous explore or verification of a regenerated explore
        if hasattr(self, '_conversation_state') and self._conversation_state:
            if self._conversation_state.get("awaiting_verification", False):
                # This is a verification response
                return self._process_verification(inputs)
            elif self._conversation_state.get("explore_url"):
                # This is feedback on the previous explore
                return self._process_feedback(inputs)
        
        # This is a new query - initialize state
        state = {
            "user_query": inputs["query"],
            "model_manager": self.model_manager,
            "looker_instance_url": self.looker_instance_url,
            "request_visualization": inputs.get("request_visualization", False)
        }
        
        # Process user query
        with trace("user_query_processing") as span:
            state = user_query_node(state)
            span.add_outputs({"state": state})
        
        # Select relevant explore
        with trace("explore_selection") as span:
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
            params_model = self.model_manager.get_model_for_task("explore_params_generation")
            state["llm"] = params_model
            state = explore_params_generator_node(state)
            span.add_outputs({"state": state})
        
        # Fetch filter values if needed
        with trace("filter_value_fetching") as span:
            filter_model = self.model_manager.get_model_for_task("filter_selection")
            state["llm"] = filter_model
            state = filter_value_fetcher_node(state)
            span.add_outputs({"state": state})
            
        # Execute explore and get results
        with trace("explore_execution") as span:
            summary_model = self.model_manager.get_model_for_task("summarization")
            state["llm"] = summary_model
            state = execute_explore_node(state)
            span.add_outputs({"state": state})
            
        # Store the state for potential future feedback
        self._conversation_state = state
            
        # Compile final response
        content_messages = [msg.content for msg in state.get("messages", []) if hasattr(msg, "content")]
        text_response = "\n\n".join(content_messages[:-1] if len(content_messages) > 1 else content_messages)
        
        # Return both text response and URL
        return {
            "response": text_response,
            "explore_url": state.get("explore_url", ""),
            "visualization_data": state.get("visualization_data", None)
        }