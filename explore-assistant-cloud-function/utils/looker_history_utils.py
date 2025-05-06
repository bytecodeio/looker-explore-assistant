import logging
import json
import os  # Add os import
from typing import Dict, List
from looker_sdk import models

def get_query_history(sdk, limit=100):
    """
    Query the Looker History explore to get recent query history
    
    Args:
        sdk: Initialized Looker SDK
        limit: Maximum number of history entries to fetch
        
    Returns:
        List of query history entries
    """
    try:
        # Define a query against history.query to get recent queries
        query = models.WriteQuery(
            model="system__activity",
            view="history",
            fields=[
                "query.model",
                "query.view",
                "query.formatted_fields",
                "query.formatted_filters",
                "query.formatted_pivots",
                "query.formatted_sorts",
                "query.runtime", 
                "query.client_id",
                "history.created_date",
                "history.dashboard_id"
            ],
            filters={
                "history.created_date": "90 days",
                "query.model": "-system__activity,-system__embed,-system__internal,-system__lookml_dashboard",
                "query.view": "-NULL"
            },
            sorts=["history.created_date desc"],
            limit=limit
        )
        
        # Run the query
        logging.info(f"Querying Looker history for recent queries (limit {limit})")
        result = sdk.run_inline_query("json", query)
        history_data = json.loads(result)
        logging.info(f"Retrieved {len(history_data)} query history entries")
        return history_data
    
    except Exception as e:
        logging.error(f"Error fetching query history: {e}")
        return []

def group_queries_by_explore(history_data):
    """
    Group query history by model and explore
    
    Args:
        history_data: List of query history entries
        
    Returns:
        Dict mapping "model.explore" to list of query details
    """
    explore_queries = {}
    
    for entry in history_data:
        model = entry.get("query.model")
        view = entry.get("query.view")
        
        if not model or not view:
            continue
            
        key = f"{model}.{view}"
        
        query_details = {
            "fields": entry.get("query.formatted_fields", ""),
            "filters": entry.get("query.formatted_filters", ""),
            "pivots": entry.get("query.formatted_pivots", ""),
            "sorts": entry.get("query.formatted_sorts", ""),
            "created_date": entry.get("history.created_date")
        }
        
        if key not in explore_queries:
            explore_queries[key] = []
            
        explore_queries[key].append(query_details)
    
    # Log the distribution of queries
    logging.info(f"Grouped queries across {len(explore_queries)} explores")
    return explore_queries

def analyze_explore_queries_with_llm(model_manager, explore_name, model_name, queries, max_queries=5):
    """
    Use LLM to analyze what types of questions an explore can answer based on query history
    
    Args:
        model_manager: The ModelManager instance for LLM access
        explore_name: Name of the explore
        model_name: Name of the model
        queries: List of query details for this explore
        max_queries: Maximum number of queries to analyze
        
    Returns:
        Summary of question types this explore can answer
    """
    if not queries:
        return f"No historical queries found for {model_name}.{explore_name}"
    
    # Limit to most recent queries
    sample_queries = queries[:max_queries]
    
    # Format the query details for the LLM
    query_text = ""
    for i, query in enumerate(sample_queries):
        query_text += f"Query {i+1}:\n"
        query_text += f"Fields: {query.get('fields', 'None')}\n"
        query_text += f"Filters: {query.get('filters', 'None')}\n"
        query_text += f"Sorts: {query.get('sorts', 'None')}\n\n"
    
    # Create prompt for the LLM
    prompt = f"""
    Analyze the following {len(sample_queries)} historical Looker queries from the explore "{model_name}.{explore_name}":
    
    {query_text}
    
    Based on these queries, provide a concise summary (max 200 words) of:
    1. What business questions this explore can answer
    2. The main dimensions and measures people typically analyze
    3. Common filtering patterns
    
    Format the response as a paragraph that would help an analyst understand when to use this explore.
    """
    
    try:
        # Correctly use ModelManager to get a model instance
        llm = model_manager.get_thinking_model()
        logging.info(f"Got thinking model for analyzing explore {model_name}.{explore_name}")
        
        # Use the model to generate text
        if hasattr(llm, 'invoke'):
            response = llm.invoke(prompt)
        elif hasattr(llm, 'predict'):
            response = llm.invoke(prompt)
        elif hasattr(llm, 'generate'):
            response = llm.generate(prompt)
        elif hasattr(llm, '__call__'):
            response = llm(prompt)
        else:
            logging.error(f"LLM model doesn't have standard generation methods: {type(llm)}")
            return f"Explore {model_name}.{explore_name} contains data related to {explore_name.replace('_', ' ')}."
        
        logging.info(f"Generated explore description for {model_name}.{explore_name}")
        
        # Extract text from response which might be an object
        if not isinstance(response, str):
            if hasattr(response, 'content'):
                return response.content
            elif hasattr(response, 'text'):
                return response.text
            elif hasattr(response, 'generations') and response.generations:
                return response.generations[0][0].text
            else:
                return str(response)
        return response
        
    except Exception as e:
        logging.error(f"Error analyzing queries with LLM for {model_name}.{explore_name}: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return f"Explore {model_name}.{explore_name} contains data related to {explore_name.replace('_', ' ')}."

def populate_explores_from_history(client, project_id, dataset_id, table_id, sdk, model_manager):
    """
    Populate the explores table using Looker query history and LLM analysis
    
    Args:
        client: BigQuery client
        project_id: GCP project ID
        dataset_id: BigQuery dataset ID
        table_id: BigQuery table name ("explores")
        sdk: Initialized Looker SDK
        model_manager: ModelManager for LLM access
        
    Returns:
        True if successful, False otherwise
    """
    from utils.bigquery_utils import ensure_dataset_exists, ensure_table_exists
    import time
    from datetime import datetime
    
    try:
        # Ensure dataset and table exist
        if not ensure_dataset_exists(client, project_id, dataset_id):
            logging.error(f"Failed to create or verify dataset {project_id}.{dataset_id}")
            return False    
            
        if not ensure_table_exists(client, project_id, dataset_id, table_id, "explores"):
            logging.error(f"Failed to create or verify table {project_id}.{dataset_id}.{table_id}")
            return False
            
        # Get query history
        history_data = get_query_history(sdk, limit=500)
        if not history_data:
            logging.warning("No query history found, using model metadata only")
        
        # Group queries by explore
        explore_queries = group_queries_by_explore(history_data)
        logging.info(f"Found query history for {len(explore_queries)} explores")
        
        # Get all LookML models for complete coverage
        models = sdk.all_lookml_models()
        logging.info(f"Retrieved {len(models)} LookML models")
        
        # Prepare rows for insertion
        rows_to_insert = []
        
        for model in models:
            model_name = model.get('name')
            if not model_name:
                continue
                
            # Skip system models
            if model_name.startswith(('system__', 'i__')):
                continue
                
            # Get all explores for this model
            try:
                model_detail = sdk.lookml_model(model_name)
                explores = model_detail.explores or []
                
                for explore in explores:
                    explore_name = explore.name
                    if not explore_name:
                        continue
                    
                    # Skip if this is a system explore
                    if explore_name.startswith(('system__', 'i__')):
                        continue
                        
                    # Get the explore's historical queries
                    key = f"{model_name}.{explore_name}"
                    queries = explore_queries.get(key, [])
                    
                    # Fetch detailed explore metadata
                    try:
                        explore_detail = sdk.lookml_model_explore(model_name, explore_name)
                        
                        # Extract fields as JSON
                        fields = {}
                        if hasattr(explore_detail, 'fields'):
                            if hasattr(explore_detail.fields, 'dimensions'):
                                fields['dimensions'] = [d.name for d in explore_detail.fields.dimensions]
                            if hasattr(explore_detail.fields, 'measures'):
                                fields['measures'] = [m.name for m in explore_detail.fields.measures]
                            if hasattr(explore_detail.fields, 'filters'):
                                fields['filters'] = [f.name for f in explore_detail.fields.filters]
                        
                        # Get LLM-generated description based on query history
                        description = getattr(explore_detail, 'description', '') or ''
                        
                        # If we have query history, analyze it with the LLM
                        if queries:
                            llm_description = analyze_explore_queries_with_llm(
                                model_manager, 
                                explore_name, 
                                model_name, 
                                queries
                            )
                            
                            # Combine existing description with LLM analysis
                            if description:
                                description = f"{description}\n\nBased on query history: {llm_description}"
                            else:
                                description = f"Based on query history: {llm_description}"
                        
                        # Create row with usage statistics
                        # Format the timestamp properly for BigQuery
                        last_used = None
                        if queries:
                            # Try to parse the created_date as datetime
                            try:
                                created_date = queries[0].get('created_date')
                                if created_date:
                                    # If it's already a properly formatted timestamp string
                                    if isinstance(created_date, str) and 'T' in created_date:
                                        last_used = created_date
                                    else:
                                        # Format current time as ISO format
                                        last_used = datetime.now().isoformat()
                                else:
                                    last_used = datetime.now().isoformat()
                            except Exception as e:
                                logging.warning(f"Error formatting timestamp: {e}, using current time")
                                last_used = datetime.now().isoformat()
                        
                        row = {
                            'explore_name': explore_name,
                            'model_name': model_name,
                            'description': description[:1000],  # Limit description length
                            'usage_count': len(queries),
                            'last_used': last_used,
                            'popularity_score': len(queries),  # Simple score based on usage count
                            'fields_json': json.dumps(fields)
                        }
                        rows_to_insert.append(row)
                        
                    except Exception as e:
                        logging.warning(f"Error processing explore {model_name}.{explore_name}: {e}")
                        continue
                        
            except Exception as e:
                logging.warning(f"Error processing model {model_name}: {e}")
                continue
        
        # Insert rows into BigQuery
        if rows_to_insert:
            table_ref = client.dataset(dataset_id).table(table_id)
            errors = client.insert_rows_json(table_ref, rows_to_insert)
            if errors:
                logging.error(f"Errors inserting rows into {project_id}.{dataset_id}.{table_id}: {errors}")
                return False
            
            logging.info(f"Successfully populated {len(rows_to_insert)} explores into {project_id}.{dataset_id}.{table_id}")
            return True
        else:
            logging.warning("No explores found to insert")
            # Create a minimal default entry to prevent repeated failures
            default_entry = [{
                'explore_name': 'default_explore',
                'model_name': 'default_model',
                'description': 'Default explore created automatically because no explores were found',
                'usage_count': 0,
                'last_used': datetime.now().isoformat(),  # Use proper ISO format
                'popularity_score': 0,
                'fields_json': '{"dimensions": ["default_dimension"], "measures": ["default_measure"], "filters": []}'
            }]
            
            table_ref = client.dataset(dataset_id).table(table_id)
            errors = client.insert_rows_json(table_ref, default_entry)
            if errors:
                logging.error(f"Error inserting default row: {errors}")
                return False
            return True
            
    except Exception as e:
        logging.error(f"Error populating explores table from history: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False
