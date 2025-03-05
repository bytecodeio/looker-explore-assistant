import json
import logging
import re
import base64
from typing import Dict, Any, Optional

from utils.model_manager import ModelManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Evaluation schema definition
EVALUATION_SCHEMA = {
    "correctness_score": {
        "description": "Numerical score (0.0-1.0) indicating how correctly the response answers the question",
        "type": "float"
    },
    "filters_score": {
        "description": "Numerical score (0.0-1.0) indicating how appropriate the filters are for the question",
        "type": "float"
    },
    "dimensions_score": {
        "description": "Numerical score (0.0-1.0) indicating how appropriate the selected dimensions are",
        "type": "float"
    },
    "visualization_score": {
        "description": "Numerical score (0.0-1.0) indicating how appropriate the visualization is for the question",
        "type": "float"
    },
    "overall_score": {
        "description": "Numerical score (0.0-1.0) indicating the overall quality of the response",
        "type": "float"
    },
    "correctness_feedback": {
        "description": "Detailed feedback on whether the response correctly answers the question",
        "type": "string"
    },
    "filters_feedback": {
        "description": "Detailed feedback on the filters used in the explore",
        "type": "string"
    },
    "dimensions_feedback": {
        "description": "Detailed feedback on the dimensions selected in the explore",
        "type": "string"
    },
    "visualization_feedback": {
        "description": "Detailed feedback on the appropriateness of the visualization",
        "type": "string"
    },
    "improvement_suggestions": {
        "description": "Suggestions for improving the response and explore configuration",
        "type": "string"
    }
}

class LLMEvaluator:
    """
    Uses an LLM to evaluate the quality of responses and visualizations from the Looker Explore Assistant
    """
    
    def __init__(self, model_manager: ModelManager = None):
        """
        Initialize the LLM evaluator
        
        Args:
            model_manager: ModelManager instance for accessing LLMs
        """
        self.model_manager = model_manager or ModelManager()
    
    def _extract_explore_details(self, explore_url: str) -> Dict[str, Any]:
        """
        Extract explore parameters from the URL
        
        Args:
            explore_url: URL to the Looker explore
            
        Returns:
            Dictionary with explore parameters
        """
        if not explore_url:
            return {}
            
        try:
            # Extract model and explore name from URL
            model_explore_match = re.search(r"/explore/([^/]+)/([^?]+)", explore_url)
            
            # Extract query parameters
            query_params = {}
            if '?' in explore_url:
                query_string = explore_url.split('?', 1)[1]
                for param in query_string.split('&'):
                    if '=' in param:
                        key, value = param.split('=', 1)
                        query_params[key] = value
            
            # Extract specific parameters
            fields = query_params.get('fields', '').split(',')
            filters = {}
            for key, value in query_params.items():
                if key.startswith('f['):
                    filter_name = key[2:-1]  # Remove the 'f[' and ']'
                    filters[filter_name] = value
                    
            vis_config = {}
            if 'vis_config' in query_params:
                try:
                    vis_config = json.loads(query_params['vis_config'])
                except:
                    vis_config = {'error': 'Could not parse vis_config'}
            
            return {
                "model": model_explore_match.group(1) if model_explore_match else None,
                "explore": model_explore_match.group(2) if model_explore_match else None,
                "fields": fields,
                "filters": filters,
                "vis_config": vis_config
            }
        except Exception as e:
            logger.error(f"Error parsing explore URL: {e}")
            return {"error": str(e)}
    
    def evaluate_response(self, question: str, response_text: str, 
                         explore_url: str, question_type: str,
                         visualization_data: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Evaluate the quality of a response and visualization using an LLM
        
        Args:
            question: The original question
            response_text: The text response from the assistant
            explore_url: URL to the Looker explore, if generated
            question_type: The type of question (Simple, Complex, Abstract)
            visualization_data: Optional PNG image data of the visualization
            
        Returns:
            Dictionary with evaluation results
        """
        if not response_text:
            return {
                "status": "failed",
                "error": "No response text provided"
            }
        
        # Extract explore details if URL is provided
        explore_details = self._extract_explore_details(explore_url)
        
        # Create prompt for LLM evaluation
        prompt = self._create_evaluation_prompt(
            question=question,
            response_text=response_text,
            explore_details=explore_details,
            question_type=question_type,
            has_visualization=visualization_data is not None
        )
        
        try:
            # Get the right model for evaluation
            # For visualization evaluation, use a multimodal model that can process images
            if visualization_data:
                llm = self.model_manager.get_model_for_task("multimodal_evaluation")
                
                # Encode the image for the multimodal LLM
                base64_image = base64.b64encode(visualization_data).decode('utf-8')
                
                # Invoke with both text and image
                llm_response = llm.invoke_with_image(prompt, base64_image)
            else:
                # For text-only evaluation
                llm = self.model_manager.get_model_for_task("evaluation")
                llm_response = llm.invoke(prompt)
            
            # Parse the evaluation results
            evaluation_result = self._parse_llm_evaluation(llm_response)
            evaluation_result["status"] = "completed"
            evaluation_result["visualization_evaluated"] = visualization_data is not None
            
            return evaluation_result
        
        except Exception as e:
            logger.error(f"Error during evaluation: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def _create_evaluation_prompt(self, question: str, response_text: str, 
                                explore_details: Dict[str, Any], 
                                question_type: str,
                                has_visualization: bool = False) -> str:
        """
        Create a prompt for the LLM to evaluate a response and visualization
        
        Args:
            question: The original question
            response_text: The text response from the assistant
            explore_details: Dictionary with explore parameters
            question_type: The type of question (Simple, Complex, Abstract)
            has_visualization: Whether a visualization image is provided
            
        Returns:
            Prompt for the LLM
        """
        schema_json = json.dumps(EVALUATION_SCHEMA, indent=2)
        explore_json = json.dumps(explore_details, indent=2)
        
        visualization_section = """
Additionally, I'm providing a visualization image that was generated for this query.
Carefully analyze the visualization to evaluate:
1. Is the visualization type appropriate for the data and question?
2. Does the visualization clearly present the data needed to answer the question?
3. Are the relevant filters and dimensions visible in the visualization?
4. Is the visualization formatted effectively (labels, colors, layout)?
""" if has_visualization else ""

        prompt = f"""You are an expert evaluator for data analytics and visualization. 
Evaluate the quality of a response to a business intelligence question.

QUESTION: {question}
QUESTION TYPE: {question_type}

RESPONSE: 
{response_text}

LOOKER EXPLORE DETAILS:
{explore_json}

{visualization_section}

EVALUATION TASK:
Evaluate the response based on the following criteria:
1. Correctness: Does the response correctly address the question?
2. Filters: Are appropriate filters used for the given question?
3. Dimensions: Are appropriate dimensions selected for the question?
4. Visualization: Is the visualization type appropriate for the data and question?
5. Overall quality: Considering all factors, how would you rate the overall quality?

For each criterion, provide:
- A numerical score from 0.0 (poor) to 1.0 (excellent)
- Detailed feedback explaining your reasoning

EVALUATION SCHEMA:
{schema_json}

Provide your evaluation as valid JSON that follows the schema exactly.
Include specific reasons for your scores and actionable suggestions for improvement.
"""

        return prompt
    
    def _parse_llm_evaluation(self, llm_response: str) -> Dict[str, Any]:
        """
        Parse the evaluation response from the LLM
        
        Args:
            llm_response: Response string from the LLM
            
        Returns:
            Dictionary with parsed evaluation results
        """
        try:
            # Extract JSON from the LLM response
            json_match = re.search(r'```json\s*(.*?)\s*```', llm_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON without code blocks
                json_match = re.search(r'({[\s\S]*})', llm_response)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = llm_response
            
            # Parse the JSON
            evaluation = json.loads(json_str)
            
            # Ensure required fields are present with default values
            for field, details in EVALUATION_SCHEMA.items():
                if details["type"] == "float" and field not in evaluation:
                    evaluation[field] = 0.0
                elif details["type"] == "string" and field not in evaluation:
                    evaluation[field] = ""
            
            return evaluation
        
        except Exception as e:
            logger.error(f"Error parsing LLM evaluation: {e}")
            return {
                "error": f"Failed to parse evaluation: {str(e)}",
                "correctness_score": 0.0,
                "filters_score": 0.0,
                "dimensions_score": 0.0,
                "visualization_score": 0.0,
                "overall_score": 0.0
            }
