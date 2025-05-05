import os
import logging
from typing import Dict, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage
from langsmith import trace
from langchain.chains.base import Chain
from pydantic import BaseModel, Field
from looker_sdk.sdk.api40.methods import Looker40SDK
import looker_sdk
from looker_sdk import error as looker_error

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

# Configure logging
logger = logging.getLogger(__name__)

class LookerExploreWorkflow(Chain, BaseModel):
    """
    A workflow that processes user queries and generates Looker explores
    """
    model_manager: ModelManager = Field(default_factory=ModelManager)
    looker_instance_url: str = Field(default_factory=lambda: os.environ.get('LOOKERSDK_BASE_URL', 'https://your-looker-instance.cloud.looker.com'))
    conversation_state: Dict[str, Any] = Field(default_factory=dict, exclude=True)
    looker_sdk: Optional[Looker40SDK] = Field(default=None)
    
    class Config:
        arbitrary_types_allowed = True
        protected_namespaces = ()  # Disable protected namespaces to avoid warning
        
    @property
    def input_keys(self) -> list:
        return ["query", "request_visualization", "standard_fields"]
        
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
            **self.conversation_state,
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
        self.conversation_state = state
        
        # Compile final response
        content_messages = [msg.content for msg in state.get("messages", []) if hasattr(msg, "content")]
        response = "\n\n".join(content_messages)
        
        return {
            "response": response,
            "explore_url": state.get("explore_url", ""),
            "visualization_data": state.get("visualization_data", None),
            "looker_url": state.get("explore_url", ""),
            "summary": response,
            "looker_url_parts": state.get("looker_url_parts", {})
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
            **self.conversation_state,
            "user_response": inputs["query"]
        }
        
        # Process verification and store example if positive
        with trace("example_storage") as span:
            state = example_storage_node(state)
            span.add_outputs({"state": state})
            
        # Update conversation state
        self.conversation_state = state
        
        # Compile final response
        content_messages = [msg.content for msg in state.get("messages", []) if hasattr(msg, "content")]
        response = "\n\n".join(content_messages)
        
        return {
            "response": response,
            "explore_url": state.get("explore_url", ""),
            "visualization_data": state.get("visualization_data", None),
            "looker_url": state.get("explore_url", ""),
            "summary": response,
            "looker_url_parts": state.get("looker_url_parts", {})
        }

    def _call(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the workflow pipeline"""
        try:
            # Initialize SDK if it doesn't exist
            if not self.looker_sdk:
                try:
                    # Try to initialize the SDK
                    # This will use the environment variables LOOKERSDK_BASE_URL, LOOKERSDK_CLIENT_ID, LOOKERSDK_CLIENT_SECRET
                    self.looker_sdk = looker_sdk.init40()
                    # Test connection
                    self.looker_sdk.me()
                    logger.info(f"Successfully initialized Looker SDK using {os.environ.get('LOOKERSDK_BASE_URL')}")
                except looker_error.SDKError as e:
                    logger.error(f"Failed to initialize Looker SDK: {e}")
                    logger.error(f"LOOKERSDK_BASE_URL: {os.environ.get('LOOKERSDK_BASE_URL')}")
                    logger.error(f"LOOKERSDK_CLIENT_ID is set: {'Yes' if os.environ.get('LOOKERSDK_CLIENT_ID') else 'No'}")
                    logger.error(f"LOOKERSDK_CLIENT_SECRET is set: {'Yes' if os.environ.get('LOOKERSDK_CLIENT_SECRET') else 'No'}")
                    return {
                        "response": f"I couldn't connect to Looker: {str(e)}",
                        "explore_url": "",
                        "visualization_data": None
                    }
            
            # Extract standard fields if provided
            standard_fields = inputs.get("standard_fields", {})
            
            # Check if this is feedback on a previous explore
            if self.conversation_state:
                # Add standard_fields to the conversation state if they're provided
                if standard_fields and "standard_fields" not in self.conversation_state:
                    self.conversation_state["standard_fields"] = standard_fields
                
                if self.conversation_state.get("awaiting_verification", False):
                    # This is a verification response
                    return self._process_verification(inputs)
                elif self.conversation_state.get("explore_url"):
                    # This is feedback on the previous explore
                    return self._process_feedback(inputs)
            
            # Create initial state with SDK included
            state = {
                "user_query": inputs["query"],
                "standard_fields": standard_fields,
                "model_manager": self.model_manager,
                "looker_instance_url": self.looker_instance_url,
                "request_visualization": inputs.get("request_visualization", False),
                "messages": [],
                "looker_sdk": self.looker_sdk  # Ensure SDK is in state
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
                return {
                    "response": "I couldn't determine which data explore to use for your question.", 
                    "explore_url": "",
                    "visualization_data": None
                }
            
            # Fetch semantic model for selected explore
            with trace("semantic_model_loading") as span:
                state = semantic_model_node(state)
                span.add_outputs({"state": state})
                
            # If semantic model failed to load, return early
            if "semantic_model" not in state:
                return {
                    "response": "I couldn't load the necessary data model to answer your question.", 
                    "explore_url": "",
                    "visualization_data": None
                }
            
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
            self.conversation_state = state
                
            # Compile final response
            content_messages = [msg.content for msg in state.get("messages", []) if hasattr(msg, "content")]
            text_response = "\n\n".join(content_messages[:-1] if len(content_messages) > 1 else content_messages)
                
            # Return response with all required fields
            return {
                "response": text_response,
                "explore_url": state.get("explore_url", ""),
                "visualization_data": state.get("visualization_data", None),
                "looker_url": state.get("explore_url", ""),
                "summary": text_response,
                "looker_url_parts": state.get("looker_url_parts", {})
            }
            
        except Exception as e:
            logging.error(f"Error in workflow execution: {e}")
            return {
                "response": f"An error occurred while processing your request: {str(e)}",
                "explore_url": "",
                "visualization_data": None,
                "looker_url": "",
                "summary": f"An error occurred while processing your request: {str(e)}",
                "looker_url_parts": {}
            }