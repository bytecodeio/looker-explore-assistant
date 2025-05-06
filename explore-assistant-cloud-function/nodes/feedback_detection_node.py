import logging
import json
from typing import Dict, Any
from langchain_core.messages import AIMessage
from langchain_core.language_models import BaseLLM

def analyze_feedback(llm: BaseLLM, user_feedback: str, original_query: str) -> Dict[str, Any]:
    """
    Analyze user feedback to determine if they're complaining about the explore
    
    Args:
        llm: Language model to use for analysis
        user_feedback: The feedback message from the user
        original_query: The original user query
        
    Returns:
        Dict containing feedback analysis
    """
    prompt = f"""
    Analyze the following user feedback about a data visualization or Looker explore.
    Determine if the user is expressing dissatisfaction or suggesting the visualization is incorrect.
    
    Original query: "{original_query}"
    
    User feedback: "{user_feedback}"
    
    Return your analysis as a JSON object with these fields:
    {{
        "is_complaint": true/false,
        "complaint_type": "visualization_type" | "missing_data" | "wrong_fields" | "filters" | "timeframe" | "other",
        "specific_issues": ["list", "of", "specific", "issues"],
        "suggested_changes": {{
            "fields_to_add": [],
            "fields_to_remove": [],
            "filters_to_change": {{}},
            "visualization_type": ""
        }}
    }}
    
    Only set "is_complaint" to true if the user is clearly indicating something is wrong or needs improvement.
    """
    
    try:
        response = llm.invoke(prompt)
        return json.loads(response)
    except Exception as e:
        logging.error(f"Error analyzing feedback: {e}")
        return {
            "is_complaint": False,
            "complaint_type": "other",
            "specific_issues": [],
            "suggested_changes": {
                "fields_to_add": [],
                "fields_to_remove": [],
                "filters_to_change": {},
                "visualization_type": ""
            }
        }

def feedback_detection_node(state: Dict) -> Dict:
    """
    Detect if user feedback indicates the need to regenerate the explore
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with feedback analysis
    """
    # Get required values from state
    user_feedback = state.get("user_feedback", "")
    original_query = state.get("user_query", "")
    
    if not user_feedback:
        # No feedback to analyze
        return {
            **state,
            "requires_regeneration": False,
            "feedback_analysis": None
        }
    
    # Get the appropriate LLM model
    llm = state.get("llm")
    if not llm:
        model_manager = state.get("model_manager")
        if model_manager:
            llm = model_manager.get_fast_model()
        else:
            from langchain.llms import VertexAI
            llm = VertexAI(
                model_name="gemini-pro", 
                max_output_tokens=1024,
                temperature=0
            )
    
    # Analyze the feedback
    feedback_analysis = analyze_feedback(llm, user_feedback, original_query)
    
    # Determine if regeneration is needed
    requires_regeneration = feedback_analysis.get("is_complaint", False)
    
    # Update the state
    return {
        **state,
        "requires_regeneration": requires_regeneration,
        "feedback_analysis": feedback_analysis,
        "messages": state.get("messages", []) + ([
            AIMessage(content="I understand your feedback. Let me generate an improved explore that addresses your concerns.")
        ] if requires_regeneration else [])
    }
