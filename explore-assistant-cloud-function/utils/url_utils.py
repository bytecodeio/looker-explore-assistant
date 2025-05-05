import json
import urllib.parse
import logging
from typing import Dict, Any, Optional, List

def generate_explore_url(looker_instance_url: str, explore_params: Dict[str, Any]) -> str:
    """
    Generate a Looker explore URL from the explore parameters
    
    Args:
        looker_instance_url: Base URL of the Looker instance
        explore_params: Dictionary of explore parameters
        
    Returns:
        Complete URL to the Looker explore
    """
    logger = logging.getLogger(__name__)
    
    if not explore_params:
        return ""
    
    model = explore_params.get("model", "")
    explore = explore_params.get("view", "")
    
    if not model or not explore:
        logger.error("Missing model or explore in explore_params")
        return ""
    
    # Start building URL parameters
    url_params = []
    
    # Add fields
    fields = explore_params.get("fields", [])
    if fields:
        url_params.append(f"fields={','.join(fields)}")
    
    # Add filters
    filters = explore_params.get("filters", {})
    for field, values in filters.items():
        if isinstance(values, list):
            value = values[0]  # Take the first value if multiple are provided
        else:
            value = values
        # Properly encode filter values for URLs
        encoded_value = urllib.parse.quote_plus(str(value))
        url_params.append(f"f[{field}]={encoded_value}")
    
    # Add pivots
    pivots = explore_params.get("pivots", [])
    if pivots:
        url_params.append(f"pivots={','.join(pivots)}")
    
    # Add sorts
    sorts = explore_params.get("sorts", [])
    if sorts:
        url_params.append(f"sorts={','.join(sorts)}")
    
    # Add limit
    limit = explore_params.get("limit")
    if limit:
        url_params.append(f"limit={limit}")
    
    # Add vis_config if provided
    vis_config = explore_params.get("vis_config")
    if vis_config:
        vis_config_str = json.dumps(vis_config)
        url_params.append(f"vis_config={urllib.parse.quote_plus(vis_config_str)}")
    
    # Combine URL parts
    url = f"{looker_instance_url}/explore/{model}/{explore}?{('&').join(url_params)}"
    logger.debug(f"Generated explore URL: {url}")
    
    return url
