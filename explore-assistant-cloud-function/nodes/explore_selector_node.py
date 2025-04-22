import logging
import json
from typing import Dict, List
from looker_sdk import init40, error
from langchain_core.messages import AIMessage

def init_looker_sdk():
    sdk = init40()
    return sdk

def get_available_explores(sdk):
    """Fetch all available explores from Looker"""
    try:
        models = sdk.all_lookml_models()
        
        explores = []
        for model in models:
            model_name = model.name
            if not model.explores:
                continue
                
            for explore in model.explores:
                explores.append({
                    "model_name": model_name,
                    "name": explore.name,
                    "description": explore.description or "",
                    "label": explore.label or explore.name
                })
                
        return explores
    except error.SDKError as e:
        logging.error(f"Error fetching explores: {e}")
        return []

def rank_explores_by_relevance(user_query: str, explores: List[Dict], llm=None) -> List[Dict]:
    """Rank explores by relevance to the user query using the provided LLM"""
    
    # If no LLM is provided, create a default fast model
    if llm is None:
        from langchain_community.llms import VertexAI
        llm = VertexAI(
            model_name="gemini-pro",
            max_output_tokens=1024,
            temperature=0
        )
    
    explore_descriptions = "\n".join([
        f"- Model: {explore['model_name']}, Explore: {explore['name']}, " +
        f"Label: {explore['label']}, Description: {explore['description']}"
        for explore in explores
    ])
    
    prompt = f"""
    Given a user's data question and a list of available Looker explores, 
    determine which explore would be most appropriate for answering the question.
    
    User question: {user_query}
    
    Available Explores:
    {explore_descriptions}
    
    Return your answer as a JSON object with the following structure:
    {{
        "selected_explore": {{
            "model_name": "name_of_the_model",
            "name": "name_of_the_explore"
        }},
        "explanation": "Brief explanation of why this explore was selected"
    }}
    """
    
    try:
        response = llm.predict(prompt)
        result = json.loads(response)
        
        # Verify the selected explore exists in our list
        selected = result["selected_explore"]
        matching_explores = [
            e for e in explores 
            if e["model_name"] == selected["model_name"] and e["name"] == selected["name"]
        ]
        
        if not matching_explores:
            logging.warning(f"Selected explore {selected} not found in available explores")
            return explores[:1]  # Return first explore as fallback
            
        return matching_explores
    except Exception as e:
        logging.error(f"Error ranking explores: {e}")
        return explores[:1]  # Return first explore as fallback

def explore_selector_node(state: Dict) -> Dict:
    """Select the most appropriate explore for the user's question"""
    if "user_query" not in state:
        return {"messages": [AIMessage(content="No user query found.")]}
        
    user_query = state["user_query"]
    
    # Get the LLM from state or fallback to default
    llm = state.get("llm")
    if not llm:
        model_manager = state.get("model_manager")
        if model_manager:
            llm = model_manager.get_model_for_task("explore_selection")
    
    # Initialize Looker SDK
    sdk = init_looker_sdk()
    
    # Fetch all available explores
    explores = get_available_explores(sdk)
    
    if not explores:
        return {
            "messages": [
                AIMessage(content="Could not find any available explores in Looker.")
            ]
        }
    
    # Rank explores by relevance to user query
    ranked_explores = rank_explores_by_relevance(user_query, explores, llm)
    selected_explore = ranked_explores[0]
    
    logging.info(f"Selected explore: {selected_explore['model_name']}.{selected_explore['name']}")
    
    # Update state with selected explore
    return {
        **state,
        "selected_explore": selected_explore,
        "messages": state.get("messages", []) + [
            AIMessage(content=f"Using explore {selected_explore['label']} to answer your question.")
        ]
    }
