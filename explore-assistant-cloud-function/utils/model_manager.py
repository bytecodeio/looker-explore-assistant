import logging
from typing import Dict, Any, Optional
from langchain.llms import VertexAI
from langchain_anthropic import AnthropicLLM
from langchain_core.language_models import BaseLLM

class ModelManager:
    """
    Manager for different LLM models used throughout the application.
    Provides appropriate models for different tasks based on complexity.
    """
    
    def __init__(self):
        """Initialize the model manager with different LLM instances"""
        # Initialize models
        self._fast_model = None
        self._thinking_model = None
        self._summary_model = None
        self._filter_model = None
        
    def get_fast_model(self) -> BaseLLM:
        """
        Get a fast, efficient model for simpler tasks like classification
        and basic text generation.
        """
        if self._fast_model is None:
            logging.info("Initializing fast model (Gemini Pro)")
            self._fast_model = VertexAI(
                model_name="gemini-pro",
                max_output_tokens=1024,
                temperature=0
            )
        return self._fast_model
        
    def get_thinking_model(self) -> BaseLLM:
        """
        Get a powerful model with reasoning capabilities for complex tasks
        like explore parameter generation.
        """
        if self._thinking_model is None:
            logging.info("Initializing thinking model (Claude 3.7 Sonnet)")
            self._thinking_model = AnthropicLLM(
                model_name="claude-3-sonnet-20240229",
                temperature=0,
                max_tokens_to_sample=4096,
                anthropic_api_key="YOUR_API_KEY_HERE"  # Replace with environment variable or secret
            )
        return self._thinking_model
        
    def get_summary_model(self) -> BaseLLM:
        """
        Get a model optimized for summarization tasks.
        """
        if self._summary_model is None:
            logging.info("Initializing summary model (Gemini Pro)")
            self._summary_model = VertexAI(
                model_name="gemini-pro",
                max_output_tokens=2048,
                temperature=0.1  # Slightly higher temperature for creative summaries
            )
        return self._summary_model
    
    def get_filter_model(self) -> BaseLLM:
        """
        Get a lightweight model for filter value selection.
        """
        if self._filter_model is None:
            logging.info("Initializing filter selection model (Gemini Pro)")
            self._filter_model = VertexAI(
                model_name="gemini-pro",
                max_output_tokens=256,  # Lower token limit for simple selection tasks
                temperature=0
            )
        return self._filter_model

    def get_model_for_task(self, task_name: str) -> BaseLLM:
        """
        Get the appropriate model for a given task.
        
        Args:
            task_name: The name of the task (explore_selection, params_generation, etc.)
            
        Returns:
            The appropriate LLM for the task
        """
        if task_name == "explore_params_generation":
            return self.get_thinking_model()
        elif task_name == "summarization":
            return self.get_summary_model()
        elif task_name == "filter_selection":
            return self.get_filter_model()
        else:
            return self.get_fast_model()
