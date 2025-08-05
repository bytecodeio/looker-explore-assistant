"""
Enhanced MCP Functions with Vector Search Integration

These functions replace the existing determine_explore_from_prompt and generate_explore_params
functions to include vector search capabilities for better field discovery.
"""

import logging
from typing import Dict, Any, Optional
from vector_integration import (
    integrate_vector_search_into_prompt_processing,
    enhance_explore_selection_with_vector_context,
    enhance_parameter_generation_with_vector_context
)

logger = logging.getLogger(__name__)

def determine_explore_from_prompt_enhanced(
    auth_header: str, 
    prompt: str, 
    golden_queries: Dict[str, Any], 
    conversation_context: str = "", 
    restricted_explore_keys: list = None
) -> Optional[str]:
    """
    Enhanced explore determination with vector search integration.
    
    This function now:
    1. Extracts nouns from the user prompt
    2. Searches vector database for relevant field matches
    3. Uses field matches to inform explore selection
    4. Falls back to original logic if needed
    """
    try:
        logging.info("=== ENHANCED EXPLORE DETERMINATION START ===")
        logging.info(f"Determining best explore for prompt: {prompt}")
        logging.info(f"Has conversation context: {bool(conversation_context)}")
        logging.info(f"Restricted explore keys: {restricted_explore_keys}")
        
        # Filter golden queries by restricted explore keys (same as original)
        filtered_golden_queries = golden_queries
        if restricted_explore_keys:
            logging.info(f"Filtering golden queries by restricted keys: {restricted_explore_keys}")
            filtered_golden_queries = {}
            for key, value in golden_queries.items():
                if key == 'exploreEntries':
                    filtered_entries = [
                        entry for entry in value 
                        if entry.get('golden_queries.explore_id') in restricted_explore_keys
                    ]
                    filtered_golden_queries[key] = filtered_entries
                    logging.info(f"Filtered {key}: {len(filtered_entries)} entries after filtering")
                else:
                    if isinstance(value, dict):
                        filtered_value = {
                            k: v for k, v in value.items() 
                            if k in restricted_explore_keys
                        }
                        filtered_golden_queries[key] = filtered_value
                        logging.info(f"Filtered {key}: {len(filtered_value)} entries after filtering")
                    else:
                        filtered_golden_queries[key] = value
        
        # Extract available explores (same as original logic)
        available_explores = []
        
        if 'exploreEntries' in filtered_golden_queries:
            entries = filtered_golden_queries['exploreEntries']
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        explore_id = entry.get('golden_queries.explore_id') or entry.get('explore_id')
                        if explore_id:
                            available_explores.append(explore_id)
            elif isinstance(entries, dict):
                available_explores.extend(list(entries.keys()))
        
        for key in ['exploreGenerationExamples', 'exploreRefinementExamples', 'exploreSamples']:
            if key in filtered_golden_queries and isinstance(filtered_golden_queries[key], dict):
                available_explores.extend(list(filtered_golden_queries[key].keys()))
        
        available_explores = list(set(available_explores))
        
        if not available_explores:
            logging.warning("❌ No available explores found")
            if restricted_explore_keys:
                available_explores = restricted_explore_keys
            else:
                logging.error("❌ No explores available for selection")
                return None
        
        logging.info(f"🔍 Available explores for selection: {available_explores}")
        
        # Optimization: If only one explore, return it directly
        if len(available_explores) == 1:
            single_explore = available_explores[0]
            logging.info(f"✅ Only one explore available ({single_explore}) - skipping LLM call")
            return single_explore
        
        # NEW: Vector search integration
        try:
            logging.info("🔍 Integrating vector search for enhanced explore selection...")
            nouns, vector_matches, vector_context, _ = integrate_vector_search_into_prompt_processing(
                prompt, available_explores
            )
            
            if vector_matches:
                logging.info(f"✅ Vector search found matches for: {list(vector_matches.keys())}")
                
                # Check if vector search provides a clear winner
                explore_scores = {}
                for noun, matches in vector_matches.items():
                    for match in matches:
                        explore_key = match.get('explore_key', '')
                        if explore_key in available_explores:
                            score = match.get('similarity', 0.0)
                            explore_scores[explore_key] = explore_scores.get(explore_key, 0) + score
                
                # If one explore has significantly higher vector score, use it
                if explore_scores:
                    best_explore = max(explore_scores.items(), key=lambda x: x[1])
                    max_score = best_explore[1]
                    second_best_score = sorted(explore_scores.values(), reverse=True)[1] if len(explore_scores) > 1 else 0
                    
                    # If the best explore has >2x the score of the second best, use it directly
                    if max_score > 0.7 and max_score > second_best_score * 2:
                        logging.info(f"✅ Vector search clear winner: {best_explore[0]} (score: {max_score:.3f})")
                        return best_explore[0]
                
            else:
                logging.info("ℹ️ Vector search found no matches, proceeding with standard LLM selection")
                vector_context = ""
                
        except Exception as e:
            logging.warning(f"Vector search failed, proceeding without: {e}")
            vector_context = ""
        
        # Continue with LLM-based selection, enhanced with vector context
        newline_char = "\n"
        restriction_text = ""
        if restricted_explore_keys:
            restriction_text = f"{newline_char}IMPORTANT: You must only select explores from this restricted list: {restricted_explore_keys}{newline_char}"
        
        explores_text = "\n".join([f"- {explore}" for explore in available_explores])
        
        # Build enhanced system prompt
        system_prompt = f"""You are a Looker Explore Assistant. Your job is to determine which Looker explore is most appropriate for answering a user's question.

IMPORTANT: You must analyze the user's question independently and select the BEST explore for their needs, regardless of any previous explore selections or model information.
{restriction_text}

Available explores:
{explores_text}

{vector_context}

Guidelines:
1. Choose the explore that contains the most relevant data for the user's question
2. Consider the main subject/topic of the question  
3. If semantic field analysis is provided above, heavily weight explores that contain matching fields
4. Return ONLY the explore key (e.g., "ecommerce:order_items")
5. Do not include any explanation or additional text

User's conversation context:
{conversation_context}

User's current question: {prompt}

Select the best explore:"""

        # Make LLM call (reuse existing vertex AI logic)
        from llm_utils import call_vertex_ai_api_with_service_account
        
        request_body = {
            "contents": [{
                "role": "user", 
                "parts": [{"text": system_prompt}]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "topP": 0.8,
                "topK": 40,
                "maxOutputTokens": 100
            }
        }
        
        vertex_response = call_vertex_ai_api_with_service_account(request_body)
        
        if vertex_response:
            from llm_utils import extract_vertex_response_text
            response_text = extract_vertex_response_text(vertex_response)
            
            if response_text:
                # Clean the response 
                determined_explore = response_text.strip().replace('"', '').replace("'", "")
                
                # Validate the response is one of our available explores
                if determined_explore in available_explores:
                    logging.info(f"✅ ENHANCED LLM selected explore: {determined_explore}")
                    return determined_explore
                else:
                    logging.warning(f"❌ LLM returned invalid explore: {determined_explore}")
        
        # Fallback to first available explore
        logging.warning("❌ LLM selection failed, using fallback")
        return available_explores[0] if available_explores else None
        
    except Exception as e:
        logging.error(f"Error in enhanced explore determination: {e}")
        return None

def generate_explore_params_enhanced(
    auth_header: str, 
    prompt: str, 
    explore_key: str, 
    golden_queries: Dict[str, Any], 
    semantic_models: Dict[str, Any],
    current_explore: Dict[str, Any], 
    conversation_context: str = ""
) -> Optional[Dict[str, Any]]:
    """
    Enhanced parameter generation with vector search integration.
    
    This function now:
    1. Extracts nouns from the user prompt
    2. Searches for relevant field matches for the selected explore
    3. Provides field suggestions to the LLM for parameter generation
    """
    try:
        logging.info(f"=== ENHANCED GENERATE_EXPLORE_PARAMS START ===")
        logging.info(f"Original prompt: {prompt}")
        logging.info(f"Selected explore: {explore_key}")
        logging.info(f"Has conversation context: {bool(conversation_context)}")
        
        # Handle conversation synthesis (same as original)
        if not conversation_context or conversation_context.strip() == "":
            logging.info("✅ No conversation context - skipping synthesis step")
            synthesized_query = prompt
        else:
            context_lines = [line.strip() for line in conversation_context.split('\n') if line.strip()]
            meaningful_lines = [line for line in context_lines if not line.startswith(('Previous prompts', 'Current prompt is', 'The user\'s current', 'Recent conversation'))]
            
            if len(meaningful_lines) == 0:
                logging.info("✅ No meaningful context - skipping synthesis step")
                synthesized_query = prompt
            else:
                logging.info(f"📝 Found {len(meaningful_lines)} meaningful context lines - proceeding with synthesis")
                # Import and use the existing synthesis function
                from mcp_server import synthesize_conversation_context
                synthesized_query = synthesize_conversation_context(auth_header, prompt, conversation_context)
        
        if synthesized_query and synthesized_query != prompt:
            logging.info(f"✅ SYNTHESIS SUCCESS - Original: '{prompt}' -> Synthesized: '{synthesized_query}'")
        else:
            logging.info(f"✅ Using original prompt: '{prompt}'")
            synthesized_query = prompt
        
        # NEW: Vector search integration for parameter generation
        vector_context = ""
        try:
            logging.info("🔍 Integrating vector search for enhanced parameter generation...")
            nouns, vector_matches, _, _ = integrate_vector_search_into_prompt_processing(synthesized_query)
            
            if vector_matches:
                vector_context = enhance_parameter_generation_with_vector_context(
                    synthesized_query, explore_key, vector_matches
                )
                
                if vector_context:
                    logging.info("✅ Vector search provided field suggestions for parameter generation")
                else:
                    logging.info("ℹ️ Vector search found matches but none for selected explore")
            else:
                logging.info("ℹ️ Vector search found no field matches")
                
        except Exception as e:
            logging.warning(f"Vector search for parameters failed: {e}")
            vector_context = ""
        
        # Call the existing generate_explore_params_from_query with enhanced context
        from mcp_server import generate_explore_params_from_query
        
        # We'll need to enhance the system prompt in generate_explore_params_from_query
        # For now, call the existing function and add our context
        result = generate_explore_params_from_query(
            auth_header, synthesized_query, explore_key, 
            golden_queries, semantic_models, current_explore,
            vector_context  # Pass vector context as additional parameter
        )
        
        logging.info(f"=== ENHANCED GENERATE_EXPLORE_PARAMS RESULT ===")
        if result:
            keys_log = list(result.keys()) if isinstance(result, dict) else 'Not a dict'
            logging.info(f"Result keys: {keys_log}")
            if isinstance(result, dict) and 'explore_params' in result:
                logging.info(f"Explore params fields: {result['explore_params'].get('fields', [])}")
        else:
            logging.warning("No result from enhanced parameter generation")
            
        return result
        
    except Exception as e:
        logging.error(f"Error in enhanced parameter generation: {e}")
        return None