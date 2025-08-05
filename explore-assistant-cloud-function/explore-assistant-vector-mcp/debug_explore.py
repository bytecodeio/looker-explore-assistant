#!/usr/bin/env python3
"""
Debug what data is available from Looker explores
"""

import os
import json
import logging
import looker_sdk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_explore(model_name: str, explore_name: str):
    """Debug what data is available from a specific explore"""
    
    # Set environment variables
    os.environ["LOOKERSDK_BASE_URL"] = "https://bytecodeef.looker.com"
    os.environ["LOOKERSDK_CLIENT_ID"] = "s7nrmy8k5smB9qft7X8S"
    os.environ["LOOKERSDK_CLIENT_SECRET"] = "CVzCYpFwKF6RMT7KwsxGp4X6"
    os.environ["LOOKERSDK_VERIFY_SSL"] = "true"
    os.environ["LOOKERSDK_TIMEOUT"] = "120"
    
    sdk = looker_sdk.init40()
    
    try:
        print(f"\n🔍 Debugging {model_name}:{explore_name}")
        print("=" * 60)
        
        # Get explore metadata with all available fields
        explore_data = sdk.lookml_model_explore(
            model_name, 
            explore_name,
            fields='*'  # Get all available fields
        )
        
        print(f"Explore Name: {explore_data.name}")
        print(f"Label: {explore_data.label}")
        print(f"Description: {explore_data.description}")
        
        # Check if fields exist
        if explore_data.fields:
            print(f"\n📊 Fields object exists")
            
            # Check dimensions
            if explore_data.fields.dimensions:
                print(f"✅ Found {len(explore_data.fields.dimensions)} dimensions:")
                for i, dim in enumerate(explore_data.fields.dimensions[:5]):  # Show first 5
                    print(f"  {i+1}. {dim.name} ({dim.type})")
                    print(f"     Label: {dim.label}")
                    print(f"     View: {dim.view}")
                    print(f"     View Label: {dim.view_label}")
                    print(f"     Description: {dim.description}")
                    print()
            else:
                print("❌ No dimensions found")
            
            # Check measures
            if explore_data.fields.measures:
                print(f"✅ Found {len(explore_data.fields.measures)} measures:")
                for i, measure in enumerate(explore_data.fields.measures[:3]):  # Show first 3
                    print(f"  {i+1}. {measure.name} ({measure.type})")
                    print(f"     Label: {measure.label}")
                    print(f"     View: {measure.view}")
                    print()
            else:
                print("❌ No measures found")
                
            # Check dimension groups
            if explore_data.fields.dimension_groups:
                print(f"✅ Found {len(explore_data.fields.dimension_groups)} dimension groups:")
                for i, dg in enumerate(explore_data.fields.dimension_groups[:3]):  # Show first 3
                    print(f"  {i+1}. {dg.name} ({dg.type})")
                    print(f"     Label: {dg.label}")
                    print(f"     View: {dg.view}")
                    print()
            else:
                print("❌ No dimension groups found")
        else:
            print("❌ No fields object found")
            
        # Try to see the raw structure
        print(f"\n🔧 Raw explore data structure:")
        explore_dict = explore_data.to_dict()
        
        # Print only the keys to see what's available
        print(f"Top-level keys: {list(explore_dict.keys())}")
        
        if 'fields' in explore_dict and explore_dict['fields']:
            print(f"Fields keys: {list(explore_dict['fields'].keys())}")
        
    except Exception as e:
        print(f"❌ Error debugging explore: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Test a few different explores
    test_explores = [
        ("ecommerce", "order_items"),
        ("ecommerce", "users"),
        ("dynamic_explore_model", "users")
    ]
    
    for model, explore in test_explores:
        debug_explore(model, explore)