import os
import logging
from typing import Dict, Any, Optional, List
from vertexai.preview.generative_models import GenerativeModel, GenerationConfig
import vertexai
# Update import for VertexAI
from langchain_google_vertexai import VertexAI as GoogleVertexAI
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.llms import BaseLLM
from langchain.chains.base import Chain

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
        # Default models for each task
        self._task_model_mapping = {
            "evaluation": "vertex",
            "explore_selection": "vertex",
            "explore_params_generation": "vertex",
            "filter_selection": "vertex",
            "summarization": "vertex",
            "image_evaluation": "vertex",
            "default": "vertex",
            "multimodal_evaluation": "vertex"
        }
        
        # Initialize credentials
        self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.vertex_project = os.environ.get("PROJECT")
        self.vertex_location = os.environ.get("REGION", "us-central1")
        
        # Initialize Vertex AI once
        if self.vertex_project and self.vertex_location:
            try:
                vertexai.init(project=self.vertex_project, location=self.vertex_location)
                logger.info(f"Vertex AI initialized with project {self.vertex_project} and location {self.vertex_location}")
            except Exception as e:
                logger.error(f"Failed to initialize Vertex AI: {e}")
    
    def get_thinking_model(self) -> BaseLLM:
        """Get model for complex reasoning tasks"""
        return self.get_model_for_task("default")
    
    def get_fast_model(self) -> BaseLLM:
        """
        Get a fast model for quick reasoning tasks
        
        Returns:
            A fast LLM instance
        """
        # Default to vertex
        return self.get_model_for_task("default")
    
    def get_model_for_task(self, task: str) -> BaseLLM:
        """
        Get a model specifically suited for a particular task
        
        Args:
            task: Task identifier string
            
        Returns:
            LLM instance for the specified task
        """
        model_name = self._task_model_mapping.get(task, self._task_model_mapping["default"])
        return self._get_or_create_model(model_name)
    
    def _get_or_create_model(self, model_name: str) -> BaseLLM:
        """
        Get an existing model instance or create a new one
        
        Args:
            model_name: Name of the model to get or create
            
        Returns:
            LLM instance
        """
        # Return cached model if available
        if model_name in self._models:
            return self._models[model_name]
        
        try:
            # Create models based on provider
            if model_name == "vertex":
                # Initialize Vertex AI if not done yet
                if self.vertex_project and self.vertex_location:
                    try:
                        vertexai.init(project=self.vertex_project, location=self.vertex_location)
                    except Exception as e:
                        logger.warning(f"Failed to initialize Vertex AI: {e}")
                
                # Create standard Vertex AI model - simplified approach
                model = GoogleVertexAI(
                    model_name="gemini-pro",
                    project=self.vertex_project,
                    location=self.vertex_location,
                    max_output_tokens=1024,
                    temperature=0.2,
                )
            elif model_name.startswith("claude"):
                if not self.anthropic_api_key:
                    raise ValueError("ANTHROPIC_API_KEY not set in environment")
                model = ChatAnthropic(
                    model=model_name,
                    anthropic_api_key=self.anthropic_api_key,
                    temperature=self.config.get("temperature", 0.2)
                )
            elif model_name.startswith("gpt"):
                if not self.openai_api_key:
                    raise ValueError("OPENAI_API_KEY not set in environment")
                model = ChatOpenAI(
                    model=model_name,
                    openai_api_key=self.openai_api_key,
                    temperature=self.config.get("temperature", 0.2)
                )
            else:
                # Default to Vertex AI
                model = GoogleVertexAI(
                    model_name="gemini-pro",
                    project=self.vertex_project,
                    location=self.vertex_location,
                    max_output_tokens=1024,
                    temperature=0.2,
                    top_p=0.8,
                    top_k=40,
                    verbose=True
                )
            
            # Cache model for reuse
            self._models[model_name] = model
            return model
            
        except Exception as e:
            logger.error(f"Error creating model {model_name}: {e}")
            raise
    
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
    
    def invoke_with_image(self, prompt: str, image_data: str) -> str:
        """
        Invoke model with both text and image data
        
        Args:
            prompt: Text prompt
            image_data: Base64-encoded image data
            
        Returns:
            Model response
        """
        try:
            model = GenerativeModel("gemini-pro-vision")
            response = model.generate_content([prompt, {"image_bytes": image_data}])
            return response.text
        except Exception as e:
            logger.error(f"Error in multimodal invocation: {e}")
            return f"Error processing image: {str(e)}"
