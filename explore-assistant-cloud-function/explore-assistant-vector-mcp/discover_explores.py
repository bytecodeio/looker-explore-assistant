#!/usr/bin/env python3
"""
Discover and filter Looker explores to find ones with rich dimension data.
"""

import os
import logging
import looker_sdk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_looker_sdk():
    """Initialize Looker SDK using environment variables"""
    return looker_sdk.init40()

def discover_explores_with_dimensions():
    """Find explores that likely have dimension data"""
    try:
        sdk = init_looker_sdk()
        
        # Get all models
        models = sdk.all_lookml_models()
        
        interesting_explores = []
        
        for model in models:
            if model.explores:
                for explore in model.explores:
                    # Skip test models and look for business-oriented explores
                    model_name = model.name.lower()
                    explore_name = explore.name.lower()
                    
                    # Filter for more business-oriented explores
                    business_keywords = [
                        'order', 'customer', 'product', 'sales', 'revenue', 'user',
                        'event', 'transaction', 'account', 'campaign', 'lead',
                        'inventory', 'warehouse', 'shipping', 'finance', 'employee',
                        'department', 'region', 'category', 'item', 'subscription'
                    ]
                    
                    skip_keywords = [
                        'test', 'temp', 'debug', 'sample', 'demo', 'example'
                    ]
                    
                    # Check if explore name contains business keywords
                    has_business_keyword = any(keyword in explore_name for keyword in business_keywords)
                    has_skip_keyword = any(keyword in model_name or keyword in explore_name for keyword in skip_keywords)
                    
                    if has_business_keyword and not has_skip_keyword:
                        interesting_explores.append({
                            "model": model.name,
                            "explore": explore.name,
                            "label": explore.label or explore.name,
                            "description": explore.description or "",
                            "priority": "high"
                        })
                    elif not has_skip_keyword:
                        interesting_explores.append({
                            "model": model.name,
                            "explore": explore.name,
                            "label": explore.label or explore.name,
                            "description": explore.description or "",
                            "priority": "medium"
                        })
        
        # Sort by priority (high first) and then by name
        interesting_explores.sort(key=lambda x: (x["priority"] != "high", x["model"], x["explore"]))
        
        logger.info(f"Found {len(interesting_explores)} potentially interesting explores")
        
        # Print top 20 high-priority explores
        high_priority = [e for e in interesting_explores if e["priority"] == "high"]
        
        print(f"\n🔍 Top {min(20, len(high_priority))} High-Priority Explores (likely to have rich dimension data):")
        print("=" * 80)
        
        for i, explore in enumerate(high_priority[:20], 1):
            print(f"{i:2d}. {explore['model']}:{explore['explore']}")
            if explore['label'] != explore['explore']:
                print(f"    Label: {explore['label']}")
            if explore['description']:
                print(f"    Description: {explore['description'][:100]}...")
            print()
        
        return interesting_explores
        
    except Exception as e:
        logger.error(f"Failed to discover explores: {e}")
        return []

if __name__ == "__main__":
    # Set environment variables
    os.environ["LOOKERSDK_BASE_URL"] = "https://bytecodeef.looker.com"
    os.environ["LOOKERSDK_CLIENT_ID"] = "s7nrmy8k5smB9qft7X8S"
    os.environ["LOOKERSDK_CLIENT_SECRET"] = "CVzCYpFwKF6RMT7KwsxGp4X6"
    os.environ["LOOKERSDK_VERIFY_SSL"] = "true"
    os.environ["LOOKERSDK_TIMEOUT"] = "120"
    
    discover_explores_with_dimensions()