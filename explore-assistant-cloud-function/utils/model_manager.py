import os
import logging
from typing import Dict, Any, Optional

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ModelManager:
    """
    Manages LLM models for different tasks in the workflow and testing framework
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the model manager with configuration
        
        Args:
            config: Optional configuration for models
        """
        self.config = config or {}
        self._models = {}
        self._task_model_mapping = {
            "evaluation": self.config.get("evaluation_model", "claude-3-5-sonnet-20240620"),
            "explore_selection": self.config.get("explore_selection_model", "claude-3-5-sonnet-20240620"),
            "explore_params_generation": self.config.get("explore_params_model", "claude-3-5-sonnet-20240620"),
            "filter_selection": self.config.get("filter_selection_model", "claude-3-5-sonnet-20240620"),
            "summarization": self.config.get("summarization_model", "claude-3-5-sonnet-20240620"),
            "image_evaluation": self.config.get("image_evaluation_model", "claude-3-5-sonnet-20240620"),
            "default": "claude-3-5-sonnet-20240620"
        }
    
    def get_fast_model(self) -> BaseChatModel:
        """
        Get a fast model for quick reasoning tasks
        
        Returns:
            A fast LLM instance
        """
        return self._get_or_create_model(
            model_name=self.config.get("fast_model", "gpt-3.5-turbo")
        )
    
    def get_model_for_task(self, task: str) -> BaseChatModel:
        """
        Get a model specifically suited for a particular task
        
        Args:
            task: Task identifier string
            
        Returns:
            LLM instance for the specified task
        """
        model_name = self._task_model_mapping.get(task, self._task_model_mapping["default"])
        return self._get_or_create_model(model_name)
    
    def _get_or_create_model(self, model_name: str) -> BaseChatModel:
        """
        Get an existing model instance or create a new one
        
        Args:
            model_name: Name of the model to get or create
            
        Returns:
            LLM instance
        """
        if model_name in self._models:
            return self._models[model_name]
        
        # Create model based on name prefix
        if model_name.startswith("claude"):
            model = ChatAnthropic(
                model=model_name,
                anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
                temperature=self.config.get("temperature", 0.2)
            )
        elif model_name.startswith("gpt"):
            model = ChatOpenAI(
                model=model_name,
                openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
                temperature=self.config.get("temperature", 0.2)
            )
        else:
            logger.warning(f"Unknown model type: {model_name}, using Claude as default")
            model = ChatAnthropic(
                model="claude-3-5-sonnet-20240620",
                anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
                temperature=self.config.get("temperature", 0.2)
            )
        
        # Cache model for reuse
        self._models[model_name] = model
        return model
    
    def configure_model_for_task(self, task: str, model_name: str) -> None:
        """
        Update the model mapping for a specific task
        
        Args:
            task: Task identifier string
            model_name: Model name to use for the task
        """
        self._task_model_mapping[task] = model_name
        # Clear cache if it exists
        if model_name in self._models:
            del self._models[model_name]
