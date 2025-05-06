import logging
import json
from typing import Dict, Any
from langchain_core.messages import AIMessage
from langchain_core.language_models import BaseLLM

def regenerate_explore_params(
    llm: BaseLLM, 
    original_query: str,
    user_feedback: str,
    feedback_analysis: Dict[str, Any],
    original_params: Dict[str, Any],
    semantic_model: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Regenerate explore parameters based on user feedback
    
    Args:
        llm: Language model to use for regeneration
        original_query: Original user query
        user_feedback: Feedback provided by the user
        feedback_analysis: Analysis of the feedback
        original_params: Original explore parameters
        semantic_model: Semantic model containing field information
        
    Returns:
        Updated explore parameters
    """
    # Extract fields metadata
    dimensions = semantic_model.get("dimensions", [])
    measures = semantic_model.get("measures", [])
    
    # Format field information
    dimension_info = "\n".join([f"- {d.get('name')}: {d.get('description') or 'No description'} ({d.get('type')})" 
                              for d in dimensions[:20]])  # Limit to avoid token issues
    measure_info = "\n".join([f"- {m.get('name')}: {m.get('description') or 'No description'} ({m.get('type')})" 
                           for m in measures[:20]])     # Limit to avoid token issues
    
    # Convert original params to formatted string
    original_params_str = json.dumps(original_params, indent=2)
    
    prompt = f"""
    You are an expert Looker query generator. A user has indicated that the previous explore is not correct.
    You need to regenerate an improved version based on their feedback.
    
    Original user question: "{original_query}"
    
    User feedback: "{user_feedback}"
    
    Original explore parameters:
    ```json
    {original_params_str}
    ```
    
    Feedback analysis:
    ```json
    {json.dumps(feedback_analysis, indent=2)}
    ```
    
    Available dimensions:
    {dimension_info}
    
    Available measures:
    {measure_info}
    
    Generate new explore parameters that address the user's feedback. Return ONLY a valid JSON object
    compatible with the Looker API explore format (like the original explore parameters but with appropriate modifications).
    """
    
    try:
        response = llm.invoke(prompt)
        
        # Clean up the response to extract just the JSON
        response = response.strip()
        if response.startswith('```json'):
            response = response[7:]
        if response.endswith('```'):
            response = response[:-3]
        
        new_params = json.loads(response.strip())
        
        # Ensure required fields are present
        if "model" not in new_params:
            new_params["model"] = original_params.get("model", "")
        if "view" not in new_params:
            new_params["view"] = original_params.get("view", "")
        
        return new_params
    except Exception as e:
        logging.error(f"Error regenerating explore parameters: {e}")
        # If something goes wrong, return the original params
        return original_params

def explore_regeneration_node(state: Dict) -> Dict:
    """
    Regenerate explore based on user feedback
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with regenerated explore parameters
    """
    # Check if regeneration is needed
    if not state.get("requires_regeneration", False):
        return state
    
    # Get required values from state
    user_feedback = state.get("user_feedback", "")
    original_query = state.get("user_query", "")
    feedback_analysis = state.get("feedback_analysis", {})
    original_params = state.get("explore_params", {})
    semantic_model = state.get("semantic_model", {})
    
    # Get the appropriate LLM model - use the thinking model for this complex task
    llm = state.get("llm")
    if not llm:
        model_manager = state.get("model_manager")
        if model_manager:
            llm = model_manager.get_model_for_task("explore_params_generation")
        else:
            # Default to the most powerful model available
            from utils.model_manager import ModelManager
            llm = ModelManager().get_thinking_model()
    
    # Regenerate the explore parameters
    new_params = regenerate_explore_params(
        llm, 
        original_query, 
        user_feedback, 
        feedback_analysis, 
        original_params, 
        semantic_model
    )
    
    # Store both the original and regenerated parameters
    return {
        **state,
        "original_explore_params": original_params,
        "explore_params": new_params,
        "is_regenerated": True,
        "messages": state.get("messages", []) + [
            AIMessage(content="I've generated an improved explore based on your feedback. Let me run the updated query for you.")
        ]
    }
