import logging
import json
from datetime import datetime
from typing import Dict, List, Any, Tuple
from langchain_core.messages import AIMessage
from langchain_core.language_models import BaseLLM

# Import utility functions
from utils.document_loader import DocumentLoader
from utils.query_analyzer import QueryAnalyzer
from utils.response_utils import extract_json_from_response, parse_json_response, add_message_to_state
from utils.field_utils import ExploreFieldValidator

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

def generate_filter_params_with_retry(
    llm: BaseLLM, 
    user_query: str, 
    semantic_model: Dict[str, Any], 
    dimensions: List[Dict], 
    measures: List[Dict],
    invalid_filters: Dict[str, str] = None,
    max_retries: int = 1
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Generate filter parameters for Looker explore with retry mechanism for invalid filters
    
    Args:
        llm: Language model to generate filters
        user_query: User's original query
        semantic_model: Semantic model containing field information
        dimensions: List of dimension fields
        measures: List of measure fields
        invalid_filters: Dictionary of invalid filters from previous attempts with reasons
        max_retries: Maximum number of retry attempts
        
    Returns:
        Tuple of (valid_filters, remaining_invalid_filters)
    """
    attempt = 0
    valid_filters = {}
    remaining_invalid_filters = {}
    
    # Format dimensions and measures for prompt
    dimension_str = "\n".join([
        f"- {d.get('name')}: {d.get('label', '')} ({d.get('type', '')}) - {d.get('description', 'No description')}"
        for d in dimensions[:20]
    ])
    
    measure_str = "\n".join([
        f"- {m.get('name')}: {m.get('label', '')} ({m.get('type', '')}) - {m.get('description', 'No description')}"
        for m in measures[:20]
    ])
    
    while attempt <= max_retries:
        # Provide feedback on invalid filters for retry attempts
        feedback_str = ""
        if invalid_filters and attempt > 0:
            feedback_str = "Previous filter generation had the following invalid filters:\n"
            for field, reason in invalid_filters.items():
                feedback_str += f"- {field}: {reason}\n"
            feedback_str += "\nPlease correct these issues in your response."
        
        # Create prompt for filter generation
        filter_prompt = f"""
        You are a Looker query expert. Given a user's question, generate appropriate filter expressions for a Looker explore.
        
        User Question: {user_query}
        
        Available dimensions:
        {dimension_str}
        
        Available measures:
        {measure_str}
        
        {feedback_str}
        
        For each filter, provide:
        1. The exact field name from the available fields
        2. A valid filter expression according to Looker's filter syntax:
           - For dates: 'today', 'yesterday', 'last 7 days', 'this month', etc.
           - For strings: Use '%' for wildcards, '-' for negation
           - For numbers: Use comparison operators like '>', '<', '=', 'between X and Y'
           - For booleans: Use 'yes'/'no' or 'true'/'false'
        
        Return your response as a JSON object with field names as keys and filter expressions as values:
        {{
          "field_name1": "filter_expression1",
          "field_name2": "filter_expression2"
        }}
        
        DO NOT make up field names - only use fields from the list provided.
        """
        
        try:
            # Generate filter response
            response = llm.predict(filter_prompt)
            filters = parse_json_response(response, default_value={})
            
            if not filters:
                logging.warning("Failed to parse filter response as JSON or empty response")
                break
                
            # Validate the generated filters
            valid_filters, remaining_invalid_filters = ExploreFieldValidator.validate_filters_with_feedback(
                filters, semantic_model
            )
            
            # If no invalid filters or reached max retries, break the loop
            if not remaining_invalid_filters or attempt >= max_retries:
                break
                
            # Update invalid filters for next attempt
            invalid_filters = remaining_invalid_filters
            
        except Exception as e:
            logging.error(f"Error generating filter parameters (attempt {attempt+1}): {e}")
            break
            
        attempt += 1
    
    return valid_filters, remaining_invalid_filters

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

def find_matching_field(field_name: str, semantic_model: Dict, field_mapping: Dict) -> str:
    """
    Find a matching field in the semantic model, considering aliases from field_mapping
    
    Args:
        field_name: The field name to look for
        semantic_model: The semantic model containing dimensions and measures
        field_mapping: Dictionary mapping user terms to standard field names
        
    Returns:
        The actual field name in the semantic model, or empty string if not found
    """
    field_name_lower = field_name.lower()
    
    # Check if this field name appears in our mapping
    mapped_name = None
    for alias, std_field in field_mapping.items():
        if alias.lower() in field_name_lower:
            mapped_name = std_field
            break
    
    # Search in dimensions
    for dimension in semantic_model.get('dimensions', []):
        dim_name = dimension.get('name', '').lower()
        dim_label = dimension.get('label', '').lower()
        
        # Direct match
        if field_name_lower == dim_name or field_name_lower == dim_label:
            return dimension.get('name', '')
            
        # Match through alias/mapping
        if mapped_name and (mapped_name.lower() in dim_name or mapped_name.lower() in dim_label):
            return dimension.get('name', '')
    
    # Search in measures
    for measure in semantic_model.get('measures', []):
        measure_name = measure.get('name', '').lower()
        measure_label = measure.get('label', '').lower()
        
        # Direct match
        if field_name_lower == measure_name or field_name_lower == measure_label:
            return measure.get('name', '')
            
        # Match through alias/mapping
        if mapped_name and (mapped_name.lower() in measure_name or mapped_name.lower() in measure_label):
            return measure.get('name', '')
    
    return ""

def explore_params_generator_node(state: Dict) -> Dict:
    """
    Generate Looker explore parameters based on the user query and semantic model
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with explore parameters
    """
    if "semantic_model" not in state or "user_query" not in state:
        logging.error("Missing semantic_model or user_query in state")
        return state
    
    llm = state.get("llm")
    if not llm:
        logging.error("Missing LLM in state")
        return state
    
    semantic_model = state["semantic_model"]
    user_query = state["user_query"]
    
    # Extract model name and explore ID from semantic model
    model_name = semantic_model.get("modelName")
    explore_id = semantic_model.get("exploreId")
    
    if not model_name or not explore_id:
        logging.error(f"Missing modelName or exploreId in semantic model: {semantic_model}")
        return add_message_to_state(state, "I couldn't generate a valid query because the model information is missing.")
    
    # Get available dimensions and measures from the semantic model
    dimensions = semantic_model.get("dimensions", [])
    measures = semantic_model.get("measures", [])
    
    dimension_names, measure_names = ExploreFieldValidator.get_field_names_by_type(semantic_model)
    
    if not dimension_names and not measure_names:
        logging.error("No dimensions or measures found in semantic model")
        return add_message_to_state(state, f"I couldn't find any fields in the {model_name}.{explore_id} explore.")
    
    logging.info(f"Available dimensions: {dimension_names[:5]}...")
    logging.info(f"Available measures: {measure_names[:5]}...")
    
    # Format field information for the LLM prompt
    dimensions_str = "\n".join([
        f"- {d.get('name')}: {d.get('label', '')} ({d.get('type', '')}) - {d.get('description', 'No description')}"
        for d in dimensions[:30]  # Limit to first 30 to avoid token limits
    ])
    
    measures_str = "\n".join([
        f"- {m.get('name')}: {m.get('label', '')} ({m.get('type', '')}) - {m.get('description', 'No description')}"
        for m in measures[:30]  # Limit to first 30 to avoid token limits
    ])
    
    # Generate explore parameters using LLM
    prompt = f"""
    You are an expert Looker query builder. Your task is to create a Looker query to answer this question:
    
    "{user_query}"
    
    The query should use the Looker explore "{model_name}.{explore_id}".
    
    Available dimensions:
    {dimensions_str}
    
    Available measures:
    {measures_str}
    
    Return a JSON object with these fields:
    - model: The model name ("{model_name}")
    - view: The explore name ("{explore_id}")
    - fields: Array of field names to include (must be valid dimension or measure names from the lists above)
    - sorts: Array of fields to sort by with direction (e.g. ["field_name desc"])
    - limit: Number of results to return (default: 500)
    
    IMPORTANT:
    1. Only use field names that exist in the lists above
    2. Do not make up field names
    3. Do not include "field1", "field2", etc. - use real field names
    4. Include at least one dimension and one measure in the fields
    5. Return ONLY the valid JSON object with no additional text or explanation
    """
    
    try:
        # Get LLM response
        logging.info(f"Sending explore params generation prompt to LLM, length: {len(prompt)}")
        response = llm.predict(prompt)
        logging.info(f"Received LLM response for explore params, length: {len(response)}")
        
        # Parse and validate JSON response using utility function
        params = parse_json_response(response, default_value={})
        
        if not params:
            logging.warning("Failed to parse or empty response from LLM, using fallback params")
            fallback_params = {
                "model": model_name,
                "view": explore_id,
                "fields": dimension_names[:1] + measure_names[:1],  # Take first dimension and measure
                "filters": {},
                "limit": "500"
            }
            
            return {
                **state,
                "explore_params": fallback_params,
                "messages": state.get("messages", []) + [
                    AIMessage(content=f"I'll analyze {model_name}.{explore_id} data with a simple query to help answer your question.")
                ]
            }
        
        # Generate filters with retry mechanism
        filters, invalid_filters = generate_filter_params_with_retry(
            llm, user_query, semantic_model, dimensions, measures, max_retries=1
        )
        
        # Add filters to params
        params["filters"] = filters
        
        # Validate the explore parameters
        validated_params = ExploreFieldValidator.validate_explore_params(params, semantic_model)
        
        # Add warning about invalid filters if any
        messages = state.get("messages", [])
        if invalid_filters:
            invalid_filter_msg = "Note: Some filters couldn't be applied: " + ", ".join(invalid_filters.keys())
            messages.append(AIMessage(content=invalid_filter_msg))
        
        messages.append(AIMessage(content=f"I'll analyze {model_name}.{explore_id} data to answer your question."))
        
        # Log the final params
        logging.info(f"Final explore params: {json.dumps(validated_params)}")
        
        # Return updated state with validated explore parameters
        return {
            **state,
            "explore_params": validated_params,
            "invalid_filters": invalid_filters,  # Store invalid filters in state for reference
            "messages": messages
        }
            
    except Exception as e:
        logging.error(f"Error generating explore parameters: {str(e)}")
        
        # Provide minimal fallback parameters
        return {
            **state,
            "explore_params": {
                "model": model_name,
                "view": explore_id,
                "fields": dimension_names[:1] + measure_names[:1],  # Take first dimension and measure
                "limit": "500"
            },
            "messages": state.get("messages", []) + [
                AIMessage(content=f"I encountered an issue while creating your query, but I'll try to answer with a basic analysis of {model_name}.{explore_id} data.")
            ]
        }
