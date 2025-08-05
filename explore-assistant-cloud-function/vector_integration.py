"""
Vector Search Integration for Looker Explore Assistant

This module integrates the vector MCP tool into the existing LLM pipeline
to enhance explore selection and parameter generation with semantic field matching.
"""

import re
import logging
import requests
import json
from typing import List, Dict, Any, Optional, Tuple
import nltk
from nltk.tokenize import word_tokenize
from nltk.tag import pos_tag
from nltk.corpus import stopwords

# Download required NLTK data (run once)
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('taggers/averaged_perceptron_tagger')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt')
    nltk.download('averaged_perceptron_tagger')
    nltk.download('stopwords')

logger = logging.getLogger(__name__)

# Configuration for vector MCP server
VECTOR_MCP_BASE_URL = "http://localhost:8000"  # Adjust to your MCP server URL

def extract_nouns_from_prompt(prompt: str) -> List[str]:
    """
    Extract meaningful nouns from user prompt for vector search.
    
    Args:
        prompt: User's natural language query
        
    Returns:
        List of nouns that might correspond to dimension values
    """
    try:
        # Tokenize and get part-of-speech tags
        tokens = word_tokenize(prompt.lower())
        pos_tags = pos_tag(tokens)
        
        # Get English stopwords
        stop_words = set(stopwords.words('english'))
        
        # Extract nouns (NN, NNS, NNP, NNPS) that aren't stopwords
        nouns = []
        for word, pos in pos_tags:
            if (pos.startswith('NN') and 
                word not in stop_words and 
                len(word) > 2 and  # Skip very short words
                word.isalpha()):   # Skip numbers/punctuation
                nouns.append(word)
        
        # Also extract quoted strings and capitalized words (often entity names)
        quoted_pattern = r'"([^"]*)"'
        quoted_matches = re.findall(quoted_pattern, prompt)
        nouns.extend([match.lower() for match in quoted_matches if len(match) > 2])
        
        # Extract capitalized words that might be proper nouns
        cap_pattern = r'\b[A-Z][a-z]+\b'
        cap_matches = re.findall(cap_pattern, prompt)
        nouns.extend([match.lower() for match in cap_matches if match.lower() not in stop_words])
        
        # Remove duplicates and return
        unique_nouns = list(set(nouns))
        logger.info(f"Extracted nouns from '{prompt}': {unique_nouns}")
        return unique_nouns
        
    except Exception as e:
        logger.error(f"Error extracting nouns: {e}")
        return []

def search_vector_database(nouns: List[str], min_similarity: float = 0.3) -> Dict[str, List[Dict[str, Any]]]:
    """
    Search the vector database for field references matching the nouns.
    
    Args:
        nouns: List of extracted nouns to search for
        min_similarity: Minimum similarity threshold
        
    Returns:
        Dictionary mapping nouns to their field matches
    """
    if not nouns:
        return {}
    
    results = {}
    
    for noun in nouns:
        try:
            # Call the vector MCP server
            response = requests.post(
                f"{VECTOR_MCP_BASE_URL}/search_dimension_values",
                json={
                    "query": noun,
                    "limit": 5,
                    "min_similarity": min_similarity
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if not data.get('error') and data.get('matches'):
                    results[noun] = data['matches']
                    logger.info(f"Vector search for '{noun}': found {len(data['matches'])} matches")
                else:
                    logger.info(f"Vector search for '{noun}': no matches found")
            else:
                logger.warning(f"Vector search failed for '{noun}': HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"Vector search error for '{noun}': {e}")
    
    return results

def enhance_explore_selection_with_vector_context(
    prompt: str, 
    available_explores: List[str],
    vector_matches: Dict[str, List[Dict[str, Any]]]
) -> str:
    """
    Create enhanced context for explore selection using vector search results.
    
    Args:
        prompt: Original user prompt
        available_explores: List of available explore keys
        vector_matches: Results from vector search
        
    Returns:
        Enhanced context string for LLM explore selection
    """
    if not vector_matches:
        return ""
    
    context_parts = []
    context_parts.append("SEMANTIC FIELD ANALYSIS:")
    context_parts.append("Based on the terms in your query, I found these relevant fields:")
    
    # Group matches by explore
    explore_matches = {}
    for noun, matches in vector_matches.items():
        for match in matches:
            explore_key = match.get('explore_key', '')
            if explore_key not in explore_matches:
                explore_matches[explore_key] = []
            explore_matches[explore_key].append({
                'noun': noun,
                'value': match.get('value', ''),
                'field_reference': match.get('field_reference', ''),
                'similarity': match.get('similarity', 0.0)
            })
    
    # Create explore recommendations based on field matches
    for explore_key, matches in explore_matches.items():
        if explore_key in available_explores:
            context_parts.append(f"\n• {explore_key}:")
            for match in matches[:3]:  # Top 3 matches per explore
                context_parts.append(f"  - '{match['noun']}' → {match['field_reference']} (similarity: {match['similarity']})")
    
    context_parts.append("\nConsider these field matches when selecting the most appropriate explore.")
    
    return "\n".join(context_parts)

def enhance_parameter_generation_with_vector_context(
    prompt: str,
    explore_key: str, 
    vector_matches: Dict[str, List[Dict[str, Any]]]
) -> str:
    """
    Create enhanced context for parameter generation using vector search results.
    
    Args:
        prompt: Original user prompt
        explore_key: Selected explore key
        vector_matches: Results from vector search
        
    Returns:
        Enhanced context string for LLM parameter generation
    """
    if not vector_matches:
        return ""
    
    # Filter matches for the selected explore
    relevant_matches = []
    for noun, matches in vector_matches.items():
        for match in matches:
            if match.get('explore_key') == explore_key:
                relevant_matches.append({
                    'noun': noun,
                    'value': match.get('value', ''),
                    'field_reference': match.get('field_reference', ''),
                    'similarity': match.get('similarity', 0.0),
                    'description': match.get('description', '')
                })
    
    if not relevant_matches:
        return ""
    
    context_parts = []
    context_parts.append("SEMANTIC FIELD MAPPINGS for this explore:")
    context_parts.append("The following fields are semantically related to terms in the user's query:")
    
    for match in sorted(relevant_matches, key=lambda x: x['similarity'], reverse=True):
        field_name = match['field_reference'].split('.')[-1]  # Extract just the field name
        context_parts.append(f"• User mentioned '{match['noun']}' → consider field '{field_name}' ({match['field_reference']})")
        if match['description']:
            context_parts.append(f"  Description: {match['description']}")
    
    context_parts.append("\nUse these semantic mappings to select the most relevant fields for the query.")
    
    return "\n".join(context_parts)

def integrate_vector_search_into_prompt_processing(
    prompt: str, 
    available_explores: List[str] = None
) -> Tuple[List[str], Dict[str, List[Dict[str, Any]]], str, str]:
    """
    Main integration function that processes a prompt with vector search enhancement.
    
    Args:
        prompt: User's natural language query
        available_explores: List of available explore keys (optional)
        
    Returns:
        Tuple of (extracted_nouns, vector_matches, explore_context, param_context)
    """
    try:
        # Step 1: Extract nouns from the prompt
        nouns = extract_nouns_from_prompt(prompt)
        
        # Step 2: Search vector database for field matches
        vector_matches = search_vector_database(nouns)
        
        # Step 3: Create enhanced contexts
        explore_context = ""
        if available_explores:
            explore_context = enhance_explore_selection_with_vector_context(
                prompt, available_explores, vector_matches
            )
        
        # Note: param_context will be generated later when we know the selected explore
        param_context = ""
        
        return nouns, vector_matches, explore_context, param_context
        
    except Exception as e:
        logger.error(f"Error in vector search integration: {e}")
        return [], {}, "", ""

# Test function
def test_vector_integration():
    """Test the vector integration with sample prompts"""
    test_prompts = [
        "Show me electronics sales by region",
        "What are the top managers in San Francisco?", 
        "Premium subscription revenue for Q4",
        "Product categories with highest returns"
    ]
    
    for prompt in test_prompts:
        print(f"\n=== Testing: '{prompt}' ===")
        nouns, matches, explore_ctx, param_ctx = integrate_vector_search_into_prompt_processing(
            prompt, 
            ['ecommerce:order_items', 'hr:employees', 'products:subscriptions']
        )
        
        print(f"Nouns: {nouns}")
        print(f"Matches: {matches}")
        if explore_ctx:
            print(f"Explore context:\n{explore_ctx}")

if __name__ == "__main__":
    test_vector_integration()