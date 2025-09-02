"""
Explore parameter generation

Core logic for generating Looker query parameters from natural language queries
with vector search enhancement and semantic field discovery.
"""

import json
import logging
from typing import Dict, Any, Optional, List

from vertex.client import call_vertex_ai_with_retry
from vector_search.client import VectorSearchClient
from core.config import get_model_generation_defaults, VERTEX_MODEL
from core.exceptions import ParameterGenerationError
from core.models import GenerationResult, QueryParameters

logger = logging.getLogger(__name__)


def generate_explore_params_from_query(auth_header: str, query: str, explore_key: str, 
                                     golden_queries: Dict[str, Any], semantic_models: Dict[str, Any],
                                     conversation_context: Dict[str, Any],
                                     current_explore: Dict[str, Any], debug_mode: bool = False) -> Optional[Dict[str, Any]]:
    """
    Generate explore parameters from a clear, synthesized query with vector search enhancement
    
    Args:
        auth_header: Authorization header
        query: Synthesized user query
        explore_key: Target explore key (model:explore)
        golden_queries: Golden query examples
        semantic_models: Semantic models for field information
        conversation_context: Conversation context for the current query
        current_explore: Current explore context
        
    Returns:
        Dictionary containing explore parameters and metadata
        
    Raises:
        ParameterGenerationError: If parameter generation fails
    """
    try:
        logger.info(f"🚀 Generating parameters for query: {query}")
        logger.info(f"🎯 Target explore: {explore_key}")
        
        # Debug golden queries structure
        if golden_queries:
            gq_keys = list(golden_queries.keys())
            logger.info(f"🔍 Golden queries structure keys: {gq_keys}")
            if 'exploreGenerationExamples' in golden_queries:
                example_keys = list(golden_queries['exploreGenerationExamples'].keys())
                logger.info(f"🔍 exploreGenerationExamples keys: {example_keys}")
            if 'exploreEntries' in golden_queries:
                entries_count = len(golden_queries['exploreEntries']) if isinstance(golden_queries['exploreEntries'], list) else 'not_list'
                logger.info(f"🔍 exploreEntries count: {entries_count}")
        else:
            logger.warning(f"⚠️ No golden queries provided")
        
        # Step 1: Get semantic model for this specific explore
        explore_semantic_model = semantic_models.get(explore_key, {})
        if not explore_semantic_model:
            logger.warning(f"⚠️ No semantic model found for explore: {explore_key}")
        
        # Step 2: Enhance query with vector search
        logger.info(f"🚀 Starting vector search for query: {query}")
        vector_client = VectorSearchClient()
        
        # Use asyncio.run to call async vector search from sync context
        import asyncio
        try:
            param_context, explore_context, search_results = asyncio.run(
                vector_client.enhance_query_for_parameters(
                    query, 
                    lambda req: call_vertex_ai_with_retry(req, context="vector_search", process_response=False, debug_mode=debug_mode)
                )
            )
            logger.info(f"🔍 Vector search completed - search_results keys: {list(search_results.keys())}")
            logger.info(f"🔍 Vector search results: semantic_fields={len(search_results.get('semantic_fields', []))}, field_values={len(search_results.get('field_values', []))}")
            if search_results.get('semantic_fields'):
                logger.info(f"🔍 Sample semantic fields: {[f.get('field_location') for f in search_results['semantic_fields'][:3]]}")
            if search_results.get('field_values'):  
                logger.info(f"🔍 Sample field values: {[f.get('value') for f in search_results['field_values'][:3]]}")
        except Exception as e:
            logger.error(f"❌ Vector search enhancement failed with exception: {str(e)}")
            import traceback
            logger.error(f"❌ Vector search traceback: {traceback.format_exc()}")
            # Fallback without vector search
            param_context = f"Query: {query}\n\nPlease generate appropriate parameters."
            explore_context = ""
            search_results = {}
        
        # Step 3: Build comprehensive system prompt
        system_prompt = _build_parameter_generation_prompt(
            query, explore_key, explore_semantic_model, golden_queries, 
            param_context, conversation_context, explore_context
        )
        
        # Step 4: Call Vertex AI for parameter generation
        explore_params = _generate_parameters_with_ai(system_prompt, explore_key, debug_mode=debug_mode)
        
        if not explore_params or not isinstance(explore_params, dict):
            logger.error(f"❌ Invalid AI response - got {type(explore_params)}: {explore_params}")
            raise ParameterGenerationError(f"AI failed to generate valid parameters", explore_key)
        
        # Step 5: Validate and format parameters
        from parameter_generation.validator import validate_explore_parameters, format_parameters_for_looker
        
        validated_params = validate_explore_parameters(explore_params, explore_key)
        formatted_params = format_parameters_for_looker(validated_params)
        
        # Defensive check: ensure formatted_params is not None
        if not formatted_params or not isinstance(formatted_params, dict):
            logger.error(f"❌ Parameter formatting failed - got {type(formatted_params)}: {formatted_params}")
            raise ParameterGenerationError(f"Parameter formatting returned invalid result", explore_key)
        
        # Step 6: Build comprehensive result
        # Debug vector search results structure
        logger.info(f"🔍 Raw search_results structure: {search_results}")
        if search_results.get('semantic_fields'):
            logger.info(f"🔍 semantic_fields sample: {search_results['semantic_fields'][:2]}")
        if search_results.get('field_values'):
            logger.info(f"🔍 field_values sample: {search_results['field_values'][:2]}")
        
        formatted_vector_results = _format_vector_search_results(search_results)
        logger.info(f"🔍 Formatted vector_search_used length: {len(formatted_vector_results)}")
        
        result = {
            "explore_params": formatted_params,
            "explore_key": explore_key,
            "original_query": query,
            "vector_search_used": formatted_vector_results,
            "generation_method": "vector_search_enhanced",
            "model_used": VERTEX_MODEL,
            "field_context_available": bool(explore_semantic_model),
            "golden_examples_used": _count_golden_examples(golden_queries, explore_key)
        }
        
        # Add vector search summary if available
        if search_results:
            result["vector_search_summary"] = _generate_vector_search_summary(search_results)
        
        # Final summary of what was used in parameter generation
        final_params = result.get("explore_params", {})
        golden_examples_count = result.get("golden_examples_used", 0)
        
        logger.info(f"✅ Successfully generated parameters for {explore_key}")
        logger.info(f"🎯 Final generation summary:")
        logger.info(f"   📊 Golden examples used: {golden_examples_count}")
        logger.info(f"   🔧 Fields generated: {len(final_params.get('fields', []))}")
        logger.info(f"   🎛️  Filters generated: {len(final_params.get('filters', {}))}")
        
        # Log if key patterns from golden queries appear in final result
        if final_params.get('fields'):
            if 'order_items.created_month' in final_params['fields'] and 'order_items.total_sale_price' in final_params['fields']:
                logger.info(f"   ✅ Generated standard monthly sales pattern (matches gold-tier examples)")
        
        # Detailed vis_config logging with pattern detection
        vis_config = final_params.get('vis_config', {})
        
        # Check if this query should have visualization config based on patterns
        query_lower = query.lower()
        should_have_vis = any(keyword in query_lower for keyword in [
            'sales', 'revenue', 'product', 'brand', 'category', 'sku', 
            'department', 'monthly', 'trends', 'nike', 'adidas', 'calvin'
        ])
        
        # Also check filters for product-related patterns
        filters = final_params.get('filters', {})
        has_product_filters = any(filter_key in ['products.brand', 'products.category', 'products.sku', 'products.department', 'products.name'] 
                                for filter_key in filters.keys())
        
        if should_have_vis or has_product_filters:
            if vis_config:
                logger.info(f"   🎨 vis_config present in final params: {json.dumps(vis_config)}")
                if vis_config.get('type') == 'looker_column':
                    logger.info(f"   ✅ Generated looker_column visualization (matches gold-tier examples)")
                if vis_config.get('show_value_labels'):
                    logger.info(f"   ✅ Generated show_value_labels setting (matches enhanced gold-tier examples)")
            else:
                logger.warning(f"   ❌ Query pattern suggests vis_config needed but missing!")
                logger.warning(f"   🔍 Query: '{query}' has pattern indicators: sales/product keywords or product filters")
                logger.warning(f"   💡 Should include: {{'type': 'looker_column', 'show_value_labels': true}}")
        else:
            if vis_config:
                logger.info(f"   🎨 vis_config present: {json.dumps(vis_config)}")
            else:
                logger.info(f"   ℹ️  No vis_config (may be appropriate for this query type)")
        
        if not vis_config:
            logger.info(f"   🔍 Final params keys: {list(final_params.keys())}")
            logger.info(f"   🔍 Full final params: {json.dumps(final_params, indent=2)[:500]}...")
        
        return result
        
    except ParameterGenerationError:
        raise
    except Exception as e:
        logger.error(f"Parameter generation failed: {e}")
        raise ParameterGenerationError(f"Parameter generation failed: {e}", explore_key)


def _build_parameter_generation_prompt(query: str, explore_key: str, semantic_model: Dict[str, Any],
                                     golden_queries: Dict[str, Any], param_context: str, 
                                     conversation_context: Dict[str, Any], explore_context: str) -> str:
    """Build comprehensive system prompt for parameter generation"""
    
    # Extract model and explore names
    model_name, explore_name = explore_key.split(':', 1) if ':' in explore_key else ('unknown', explore_key)
    
    # Build field context
    field_context = ""  
    if semantic_model:
        dimensions = semantic_model.get('dimensions', [])
        measures = semantic_model.get('measures', [])
        
        if dimensions:
            field_context += f"\n## Available Dimensions ({len(dimensions)}):\n"
            for dim in dimensions[:50]:  # Limit for token efficiency
                name = dim.get('name', '')
                label = dim.get('label', '')
                description = dim.get('description', '')
                field_context += f"- {name}: {label}"
                if description:
                    field_context += f" ({description})"
                field_context += "\n"
        
        if measures:
            field_context += f"\n## Available Measures ({len(measures)}):\n"
            for measure in measures[:30]:  # Limit for token efficiency  
                name = measure.get('name', '')
                label = measure.get('label', '')
                description = measure.get('description', '')
                field_context += f"- {name}: {label}"
                if description:
                    field_context += f" ({description})"
                field_context += "\n"
    
    # Add golden query examples if available
    example_context = ""
    examples = []
    
    # Try multiple possible structures for golden queries, prioritizing exploreEntries
    if golden_queries:
        # First priority: exploreEntries (contains the latest BigQuery golden queries including gold-tier)
        if 'exploreEntries' in golden_queries and isinstance(golden_queries['exploreEntries'], list):
            raw_entries = golden_queries['exploreEntries']
            
            # Filter for this explore
            filtered_entries = [
                entry for entry in raw_entries 
                if entry.get('golden_queries.explore_id') == explore_key
            ]
            
            examples = [
                {
                    'input': entry.get('golden_queries.input', ''),
                    'output': entry.get('golden_queries.output', '')
                }
                for entry in filtered_entries
                if entry.get('golden_queries.input') and entry.get('golden_queries.output')
            ]
            
            if examples:
                logger.info(f"Found {len(examples)} examples in exploreEntries for {explore_key}")
            
        # Second priority: exploreGenerationExamples structure (processed frontend format)
        elif 'exploreGenerationExamples' in golden_queries and explore_key in golden_queries['exploreGenerationExamples']:
            examples = [
                {
                    'input': ex.get('input', ''),
                    'output': ex.get('output', '')
                }
                for ex in golden_queries['exploreGenerationExamples'][explore_key][:3]
            ]
            logger.info(f"Found {len(examples)} examples in exploreGenerationExamples for {explore_key}")
            
        # Third priority: direct explore_key lookup (legacy format)
        elif explore_key in golden_queries:
            examples = [
                {
                    'input': ex.get('input', ''),
                    'output': ex.get('output', '')
                }
                for ex in golden_queries[explore_key][:3] if isinstance(ex, dict)
            ]
            logger.info(f"Found {len(examples)} examples in direct golden_queries for {explore_key}")
        
        if not examples:
            logger.warning(f"No golden query examples found for {explore_key} in structure: {list(golden_queries.keys())}")
    
    if examples:
        logger.info(f"✅ Using {len(examples)} golden query examples for {explore_key}")
        example_context = f"\n## Example Queries for {explore_key}:\n"
        
        for i, example in enumerate(examples, 1):
            if isinstance(example, dict):
                example_query = example.get('input', '')
                example_params = example.get('output', '')
                if example_query and example_params:
                    example_context += f"{i}. Query: {example_query}\n   Parameters: {example_params}\n\n"
                    # Log the specific examples being used for debugging
                    logger.info(f"📝 Golden example {i}: '{example_query[:50]}...' → {example_params[:100]}...")
                    
                    # Check for specific patterns we care about
                    if 'vis_config' in example_params:
                        if 'looker_column' in example_params:
                            logger.info(f"   🎨 Contains looker_column visualization")
                        if 'show_value_labels' in example_params:
                            logger.info(f"   🏷️  Contains show_value_labels setting")
                    if 'order_items.created_month' in example_params and 'order_items.total_sale_price' in example_params:
                        logger.info(f"   📊 Contains standard monthly sales pattern")
                    if 'products.brand' in example_params or 'products.category' in example_params or 'products.sku' in example_params:
                        logger.info(f"   🏪 Contains product filter pattern")
        
        logger.info(f"🎯 Golden query examples successfully added to parameter generation context")
    else:
        logger.warning(f"❌ No golden query examples will be used for {explore_key}")
        logger.info(f"💡 This means the AI will generate parameters without example guidance")
    
    # log the context as json
    logger.info(f"Building parameter generation prompt for {conversation_context}, {json.dumps(conversation_context)[:500]}")

    # Build the comprehensive prompt

    system_prompt = f"""You are an expert Looker query builder. Generate JSON parameters for a Looker inline query.

EXPLORE: {explore_key}
QUERY: {query}
PREVIOUS CONTEXT: {json.dumps(conversation_context)} 

Fields: {field_context}

Parameters: {param_context}

Examples: {example_context}

CRITICAL VISUALIZATION REQUIREMENTS:
The golden query examples above show the required pattern for sales/product queries.
- ALL sales, revenue, product, brand, category, SKU, or department queries MUST include vis_config
- Standard pattern: {{"type": "looker_column", "show_value_labels": true}}
- This ensures consistent visualization across the system

Generate a JSON object with these fields:
- "model": "{model_name}"
- "view": "{explore_name}"  
- "fields": array of field names to select
- "filters": object with field filters (field_name: "filter_value")
- "sorts": array of sort specifications ("field_name desc/asc")
- "pivots": array of pivot field names (optional)
- "limit": number (default 500)
- "vis_config": object with visualization settings (REQUIRED for sales/product/SKU queries)

Visualization Rules:
- For sales, revenue, product, or SKU queries: ALWAYS include vis_config
- Standard sales visualization: {{"type": "looker_column", "show_value_labels": true}}
- For time series (monthly/daily): use "looker_column" or "looker_line"
- For categorical breakdowns: use "looker_column" or "looker_bar"
- For single metrics: use "single_value"

Field Rules:
1. Use exact field names from the available fields above
2. Include relevant dimensions and measures based on the query
3. Add appropriate filters based on query requirements
4. Include sorts for logical ordering
5. Use vector search discoveries if available
6. Return only valid JSON
7. CRITICAL: Use simple field references like "view_name.field_name" - never duplicate view names like "order_items.order_items.field" 
8. For filters, use proper view prefixes: products.brand, products.category, products.sku (not order_items.products.brand)
9. ALWAYS include vis_config for product, sales, brand, category, or SKU-related queries

JSON Response:"""
    return system_prompt


def _generate_parameters_with_ai(system_prompt: str, explore_key: str, debug_mode: bool = False) -> Optional[Dict[str, Any]]:
    """Generate parameters using Vertex AI"""
    
    # Build Vertex AI request
    defaults = get_model_generation_defaults(VERTEX_MODEL)
    
    vertex_request = {
        "contents": [{
            "role": "user",
            "parts": [{"text": system_prompt}]
        }],
        "generationConfig": {
            "maxOutputTokens": 2000,  # Enough for complex parameters
            "temperature": defaults["temperature"],
            "topP": defaults["topP"],
            "topK": defaults["topK"]
        }
    }
    
    try:
        # Call Vertex AI
        vertex_response = call_vertex_ai_with_retry(
            vertex_request, 
            context=f"parameter_generation_{explore_key}", 
            process_response=False,
            debug_mode=debug_mode
        )
        
        if not vertex_response:
            logger.error("❌ No response from Vertex AI")
            return None
        
        # Extract and parse response
        from vertex.response_parser import extract_vertex_response_text
        response_text = extract_vertex_response_text(vertex_response)
        
        if not response_text:
            logger.error("❌ No text extracted from Vertex AI response")
            return None
        
        # Try to parse JSON response
        try:
            if isinstance(response_text, dict):
                # Already parsed - validate it has required structure
                if not response_text:
                    logger.warning("⚠️ AI returned empty dictionary")
                    return None
                return response_text
            elif isinstance(response_text, str):
                # Extract JSON from text
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    parsed_json = json.loads(json_str)
                    
                    # Validate the parsed JSON has some content
                    if not parsed_json:
                        logger.warning("⚠️ AI returned empty JSON object")
                        return None
                    
                    return parsed_json
                else:
                    logger.error(f"❌ No valid JSON structure found in response")
                    logger.error(f"Response text: {response_text[:300]}")
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse JSON response: {e}")
            logger.error(f"Raw response: {response_text[:500]}")
        
        logger.error("❌ All JSON parsing attempts failed")
        return None
        
    except Exception as e:
        logger.error(f"Error generating parameters with AI: {e}")
        return None


def _format_vector_search_results(search_results: Dict[str, List]) -> List[Dict[str, Any]]:
    """Format vector search results for inclusion in response"""
    
    formatted = []
    
    if "semantic_fields" in search_results:
        for field in search_results["semantic_fields"]:
            formatted.append({
                "function": "search_semantic_fields",
                "args": {"field_location": field["field_location"]},
                "phase": "parameter_generation_preprocessing",
                "results_summary": f"Found field: {field['field_location']}"
            })
    
    if "field_values" in search_results:
        for value in search_results["field_values"]:
            formatted.append({
                "function": "lookup_field_values", 
                "args": {"field_location": value["field_location"], "value": value["value"]},
                "phase": "parameter_generation_preprocessing",
                "results_summary": f"Found value: {value['value']} in {value['field_location']}"
            })
    
    return formatted


def _generate_vector_search_summary(search_results: Dict[str, List]) -> Dict[str, Any]:
    """Generate user-friendly summary of vector search usage"""
    
    field_count = len(search_results.get("semantic_fields", []))
    value_count = len(search_results.get("field_values", []))
    
    messages = []
    if field_count > 0:
        messages.append(f"Discovered {field_count} relevant fields using semantic search")
    if value_count > 0:
        messages.append(f"Found {value_count} matching values in database fields")
    
    return {
        "total_vector_searches": field_count + value_count,
        "search_semantic_fields_count": field_count,
        "lookup_field_values_count": value_count,
        "user_messages": messages,
        "detailed_usage": _format_vector_search_results(search_results)
    }


def _count_golden_examples(golden_queries: Dict[str, Any], explore_key: str) -> int:
    """Count available golden examples for the explore"""
    
    if not golden_queries:
        logger.info(f"📊 Golden examples summary: 0 total (no golden queries provided)")
        return 0
    
    count = 0
    breakdown = {}
    
    # Count from different golden query sections
    for key in ['exploreGenerationExamples', 'exploreRefinementExamples', 'exploreSamples']:
        section_count = 0
        if key in golden_queries and isinstance(golden_queries[key], dict):
            if explore_key in golden_queries[key]:
                examples = golden_queries[key][explore_key]
                if isinstance(examples, list):
                    section_count = len(examples)
                elif isinstance(examples, dict):
                    section_count = len(examples)
                else:
                    section_count = 1
                count += section_count
        breakdown[key] = section_count
    
    # Count exploreEntries (this is now the primary source)
    if 'exploreEntries' in golden_queries and isinstance(golden_queries['exploreEntries'], list):
        entries_for_explore = [
            entry for entry in golden_queries['exploreEntries']
            if entry.get('golden_queries.explore_id') == explore_key
        ]
        
        breakdown['exploreEntries'] = len(entries_for_explore)
        
        # If no other sources found, this becomes the primary count
        if not count:
            count = len(entries_for_explore)
    
    # Log detailed breakdown
    logger.info(f"📊 Golden examples summary for {explore_key}: {count} total")
    for section, section_count in breakdown.items():
        if isinstance(section_count, int) and section_count > 0:
            logger.info(f"   📝 {section}: {section_count} examples")
    
    return count