import logging
import json
import re
import os
from datetime import datetime
from typing import Dict, List, Any
from langchain_core.messages import AIMessage
from langchain_core.language_models import BaseLLM
# Update import to use the correct package
from langchain_google_vertexai import VertexAI

from utils.document_loader import DocumentLoader
from utils.query_analyzer import QueryAnalyzer

# Field type validation constants
FIELD_TYPES = {
    "dimension": "dimension",
    "measure": "measure"
}

class ExploreFilterValidator:
    @staticmethod
    def is_filter_valid(field_type: str, filter_expression: str) -> bool:
        """Simple validation of filter expressions based on field type"""
        if not field_type or not filter_expression:
            return False
            
        # Basic validation - could be expanded with more sophisticated rules
        if field_type.lower() == "date" or field_type.lower() == "date_time":
            valid_date_terms = ["today", "yesterday", "this", "last", "before", "after", "year", "month", "week", "day"]
            return any(term in filter_expression.lower() for term in valid_date_terms)
        
        return True

def format_row(field: Dict[str, Any]) -> str:
    """Format field information as a Markdown row"""
    name = field.get('name', '')
    field_type = field.get('type', '')
    label = field.get('label', '')
    description = field.get('description', '')
    tags = ', '.join(field.get('tags', []) or [])
    
    return f"| {name} | {field_type} | {label} | {description} | {tags} |"

def generate_shared_context(dimensions: List[Dict], measures: List[Dict], user_query: str) -> str:
    """Generate the shared context for prompts to the LLM, conditionally including documentation"""
    if not dimensions or not measures:
        logging.error("Dimensions or measures are empty")
        return ""
    
    # Load required documentation
    looker_filter_doc = DocumentLoader.get_filter_doc()
    looker_filters_interval_tf = DocumentLoader.get_intervals_doc()
    
    # Remove the model initialization attempt - we'll use the model provided in state
    
    # Analyze the query to determine doc requirements
    needs_visualization = QueryAnalyzer.needs_visualization(user_query)
    needs_pivots, suggested_pivot = QueryAnalyzer.needs_pivots(user_query, dimensions)
    
    logging.info(f"Query analysis - needs_visualization: {needs_visualization}, needs_pivots: {needs_pivots}")
    
    # Load docs based on analysis
    looker_visualization_doc = DocumentLoader.get_visualization_doc() if needs_visualization else "Not needed for this query."
    looker_pivots_url_parameters_doc = DocumentLoader.get_pivots_doc() if needs_pivots else "Not needed for this query."
    
    # Format dimensions and measures
    dimensions_section = "\n".join([format_row(dim) for dim in dimensions])
    measures_section = "\n".join([format_row(meas) for meas in measures])
    
    # Pivot suggestion
    pivot_suggestion = f"\n\nBased on the query, consider using '{suggested_pivot}' as a pivot field." if needs_pivots and suggested_pivot else ""
    
    return f"""
      # Documentation
      Here is general documentation about filters:
        {looker_filter_doc}
      Here is general documentation on how intervals and timeframes are applied in Looker
       {looker_filters_interval_tf}   
      
      {"Here is general documentation on visualizations:" if needs_visualization else "# Visualizations documentation not needed for this query"}
       {looker_visualization_doc if needs_visualization else ""}
      
      {"Here is general documentation on Looker JSON fields and pivots" if needs_pivots else "# Pivots documentation not needed for this query"}
       {looker_pivots_url_parameters_doc if needs_pivots else ""}
       {pivot_suggestion}
             
      ## Format of query object
      
      | Field              | Type   | Description                                                                                                                                                                                                                                                                          |
      |--------------------|--------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
      | model              | string | Model                                                                                                                                                                                                                                                                                |
      | view               | string | Explore Name                                                                                                                                                                                                                                                                         |
      | fields             | string[] | Fields                                                                                                                                                                                                                                                                                |
      | pivots             | string[] | Pivots                                                                                                                                                                                                                                                                                |
      | fill_fields        | string[] | Fill Fields                                                                                                                                                                                                                                                                           |
      | filters            | object | Filters                                                                                                                                                                                                                                                                               |
      | filter_expression  | string | Filter Expression                                                                                                                                                                                                                                                                     |
      | sorts              | string[] | Sorts                                                                                                                                                                                                                                                                                 |
      | limit              | string | Limit                                                                                                                                                                                                                                                                                 |
      | column_limit       | string | Column Limit                                                                                                                                                                                                                                                                          |
      | total              | boolean | Total                                                                                                                                                                                                                                                                                 |
      | row_total          | string | Raw Total                                                                                                                                                                                                                                                                             |
      | subtotals          | string[] | Subtotals                                                                                                                                                                                                                                                                             |
      | vis_config         | object | Visualization configuration properties. These properties are typically opaque and differ based on the type of visualization used. There is no specified set of allowed keys. The values can be any type supported by JSON. A "type" key with a string value is often present, and is used by Looker to determine which visualization to present. Visualizations ignore unknown vis_config properties. |
      | filter_config      | object | The filter_config represents the state of the filter UI on the explore page for a given query. When running a query via the Looker UI, this parameter takes precedence over "filters". When creating a query or modifying an existing query, "filter_config" should be set to null. Setting it to any other value could cause unexpected filtering behavior. The format should be considered opaque. |
          
      # End Documentation
      
      # Metadata
      This information is particular to the current Looker instance and data model. The fields below can be used in the response.
      
      Dimensions Used to group by information (follow the instructions in tags when using a specific field; if map used include a location or lat long dimension;):
      
      | Field Id | Field Type | LookML Type | Label | Description | Tags |
      |------------|------------|-------------|-------|-------------|------|
      {dimensions_section}
                
      Measures are used to perform calculations (if top, bottom, total, sum, etc. are used include a measure):
      
      | Field Id | Field Type | LookML Type | Label | Description | Tags |
      |------------|------------|-------------|-------|-------------|------|
      {measures_section}
      # End LookML Metadata
    """

def extract_json_from_response(response: str) -> str:
    """
    Extract JSON content from a response that may contain markdown code blocks
    
    Args:
        response: Response string that may include markdown formatting
        
    Returns:
        Clean JSON string without markdown formatting
    """
    # Check if the response has a code block
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response, re.MULTILINE)
    if (json_match):
        return json_match.group(1).strip()
    
    # No code block found, return the response as is
    return response.strip()

def generate_filter_params(llm: BaseLLM, prompt: str, shared_context: str, dimensions: List[Dict], measures: List[Dict]) -> Dict:
    """Generate filter parameters for the explore using the provided LLM"""
    filter_contents = f"""
      {shared_context}
      
     # Instructions
     
     The user asked the following question:
     
     ```
     {prompt}
     ```
     
     Your job is to follow the steps below and generate a JSON object.
     
     * Step 1: Your task is to look at the following data question that the user is asking and determine the filter expression for it. You should return a JSON list of filters to apply. Each element in the list will be a pair of the field id and the filter expression. Your output will look like `[ {{ "field_id": "example_view.created_date", "filter_expression": "this year" }} ]`
     * Step 2: verify that you're only using valid expressions for the filter values. If you do not know what the valid expressions are, refer to the table above. If you are still unsure, don't use the filter.
     * Step 3: verify that the field ids are indeed Field Ids from the table. If they are not, you should return an empty list. There should be a period in the field id.
     
     Think carefully about the filters that should be applied based on the user's question.
     """

    try:
        filter_response = llm.predict(filter_contents)
        
        # Extract JSON from potentially markdown-formatted response
        clean_json_str = extract_json_from_response(filter_response)
        
        # Try to parse the cleaned JSON response
        try:
            filter_response_json = json.loads(clean_json_str)
            
            if not isinstance(filter_response_json, list):
                logging.warning("Filter response is not a list, returning empty dict")
                return {}
                
            # Convert the list format to the dictionary format expected by Looker
            filter_dict = {}
            for filter_item in filter_response_json:
                field_id = filter_item.get("field_id")
                filter_expression = filter_item.get("filter_expression")
                
                if not field_id or not filter_expression:
                    continue
                    
                # Validate the filter
                field = next((d for d in dimensions if d["name"] == field_id), None)
                if not field:
                    field = next((m for m in measures if m["name"] == field_id), None)
                
                if not field:
                    logging.warning(f"Field {field_id} not found in dimensions or measures")
                    continue
                    
                if not ExploreFilterValidator.is_filter_valid(field.get("type", ""), filter_expression):
                    logging.warning(f"Invalid filter expression for field {field_id}: {filter_expression}")
                    continue
                    
                # Add to filter dictionary
                if field_id not in filter_dict:
                    filter_dict[field_id] = []
                filter_dict[field_id].append(filter_expression)
                
            return filter_dict
                
        except json.JSONDecodeError:
            logging.error(f"Failed to parse filter response as JSON: {clean_json_str}")
            return {}
            
    except Exception as e:
        logging.error(f"Error generating filter parameters: {e}")
        return {}

def generate_base_explore_params(llm: BaseLLM, prompt: str, shared_context: str, model_name: str, explore_id: str) -> Dict:
    """Generate base explore parameters using the provided LLM"""
    current_datetime = datetime.now().isoformat()
    
    contents = f"""
    {shared_context}
    
    Output
    ----------
    
    Return a JSON that is compatible with the Looker API run_inline_query function as per the spec. Here is an example:
    
    {{
      "model":"{model_name}",
      "view":"{explore_id}",
      "fields":["category.name","inventory_items.days_in_inventory_tier","products.count"],
      "filters":{{"category.name":"socks"}},
      "sorts":["products.count desc 0"],
      "limit":"500",
    }}
    
    Instructions:
    - choose only the fields in the lookml metadata above
    - prioritize the field description, label, tags, and name for what field(s) to use for a given description
    - generate only one answer, no more.
    - try to avoid adding dynamic_fields
    - Always use the provided current date ({current_datetime}) when generating Looker URL queries that involve TIMEFRAMES.
    - only respond with a JSON object
    
    Think carefully about which fields to include based on the user's question. Choose fields that will provide the most relevant insights.
      
    User Request
    ----------
    {prompt}
    """
    
    try:
        response = llm.predict(contents)
        
        # Extract JSON from potentially markdown-formatted response
        clean_json_str = extract_json_from_response(response)
        
        try:
            response_json = json.loads(clean_json_str)
            return response_json
        except json.JSONDecodeError:
            logging.error(f"Failed to parse response as JSON: {clean_json_str}")
            return {}
            
    except Exception as e:
        logging.error(f"Error generating base explore parameters: {e}")
        return {}

def explore_params_generator_node(state: Dict) -> Dict:
    """
    Generate explore parameters from user query and semantic model
    Uses Claude 3.7 Sonnet for complex reasoning
    """
    if "user_query" not in state or "semantic_model" not in state:
        logging.error("Missing user query or semantic model in state")
        return state
        
    user_query = state["user_query"]
    semantic_model = state["semantic_model"]
    
    dimensions = semantic_model.get("dimensions", [])
    measures = semantic_model.get("measures", [])
    model_name = semantic_model.get("modelName")
    explore_id = semantic_model.get("exploreId")
    
    if not dimensions or not measures or not model_name or not explore_id:
        logging.error("Missing required semantic model information")
        return state
    
    # Get the thinking model (Claude) from state, or fall back to a default
    llm = state.get("llm")
    if not llm:
        # If no model in state, get from model manager or create a default
        model_manager = state.get("model_manager")
        if model_manager:
            llm = model_manager.get_model_for_task("explore_params_generation")
        else:
            # This is a fallback - ideally the model should always be provided
            from utils.model_manager import ModelManager
            llm = ModelManager().get_thinking_model()
    
    logging.info(f"Using model {llm.__class__.__name__} for explore params generation")
    
    # Generate shared context with conditional docs
    shared_context = generate_shared_context(dimensions, measures, user_query)
    
    # Generate filter parameters using Claude for complex reasoning
    filter_params = generate_filter_params(llm, user_query, shared_context, dimensions, measures)
    
    # Generate base explore parameters
    base_params = generate_base_explore_params(llm, user_query, shared_context, model_name, explore_id)
    
    # Analyze if pivot is needed 
    # This can use a simpler model since it's more of a classification task
    from utils.query_analyzer import QueryAnalyzer
    needs_pivots, pivot_field = QueryAnalyzer.needs_pivots(user_query, dimensions)
    if needs_pivots and pivot_field and "pivots" not in base_params:
        logging.info(f"Adding suggested pivot field: {pivot_field}")
        base_params["pivots"] = [pivot_field]
    
    # Combine parameters
    explore_params = {**base_params}
    explore_params["filters"] = filter_params
    
    logging.info(f"Generated explore parameters: {explore_params}")
    
    # Update state
    return {
        **state,
        "explore_params": explore_params,
        "messages": state.get("messages", []) + [
            AIMessage(content=f"Generated explore parameters for {model_name}.{explore_id}")
        ]
    }
