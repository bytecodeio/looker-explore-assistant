import logging
import json
import os
import ssl
from typing import Dict, List
from looker_sdk import init40, error
from langchain_core.messages import AIMessage
from google.cloud import bigquery

# Import the centralized SDK initialization function
from utils.looker_sdk_utils import init_looker_sdk
# Import JSON parsing utilities
from utils.response_utils import parse_json_response, extract_json_from_response

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

def get_explores_from_bigquery():
    """Fetch explores from BigQuery table"""
    project_id = os.environ.get("PROJECT", "combined-genai-bi")
    dataset_id = os.environ.get("DATASET", "bytecode")
    table_id = "explores"
    
    try:
        client = bigquery.Client(project=project_id)
        query = f"""
            SELECT model_name, explore_name as name, description
            FROM `{project_id}.{dataset_id}.{table_id}`
            ORDER BY popularity_score DESC
            LIMIT 100
        """
        
        logging.info(f"Fetching explores from BigQuery: {project_id}.{dataset_id}.{table_id}")
        query_job = client.query(query)
        results = query_job.result()
        
        explores = []
        for row in results:
            explores.append({
                "model_name": row.model_name,
                "name": row.name,
                "description": row.description or "",
                "label": row.name.replace('_', ' ').title()
            })
            
        logging.info(f"Retrieved {len(explores)} explores from BigQuery")
        return explores
    except Exception as e:
        logging.error(f"Error fetching explores from BigQuery: {e}")
        return []

def rank_explores_by_relevance(user_query: str, explores: List[Dict], llm=None) -> List[Dict]:
    """Rank explores by relevance to the user query using the provided LLM"""
    
    # If no explores, return empty list
    if not explores:
        logging.error("No explores to rank")
        return []
    
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
        # Use invoke instead of predict
        response = llm.invoke(prompt)
        
        # Handle JSON parsing safely using our utility function
        result = parse_json_response(response)
        if not result:
            logging.warning(f"Failed to parse JSON response. Using first explore as fallback. Response: {response[:100]}...")
            return explores[:1]  # Return first explore as fallback
            
        # Verify the response has the expected structure
        if "selected_explore" not in result or "model_name" not in result["selected_explore"] or "name" not in result["selected_explore"]:
            logging.warning(f"Invalid response structure: {response}")
            return explores[:1]  # Return first explore as fallback
            
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
        logging.error(f"Response: {response[:500] if 'response' in locals() else 'No response'}")
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
        if (model_manager):
            llm = model_manager.get_model_for_task("explore_selection")
    
    # First try to get explores from BigQuery (prioritize populated table)
    explores = get_explores_from_bigquery()
    
    # If no explores found in BigQuery, fall back to getting from Looker API
    if not explores:
        # Initialize Looker SDK
        sdk = init_looker_sdk()
        explores = get_available_explores(sdk)
    
    if not explores:
        return {
            "messages": [
                AIMessage(content="Could not find any available explores in Looker or BigQuery.")
            ]
        }
    
    # Rank explores by relevance to user query
    ranked_explores = rank_explores_by_relevance(user_query, explores, llm)
    
    if not ranked_explores:
        return {
            "messages": [
                AIMessage(content="Could not find a relevant explore for your query.")
            ]
        }
        
    selected_explore = ranked_explores[0]
    
    logging.info(f"Selected explore: {selected_explore['model_name']}.{selected_explore['name']}")
    
    # Update state with selected explore
    return {
        **state,
        "selected_explore": selected_explore,
        "continue_workflow": True,  # Explicitly signal to continue the workflow
        "messages": state.get("messages", []) + [
            AIMessage(content=f"Using explore {selected_explore['label']} to answer your question.")
        ]
    }
