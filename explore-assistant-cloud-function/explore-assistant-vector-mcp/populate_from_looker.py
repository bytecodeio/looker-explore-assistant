#!/usr/bin/env python3
"""
Populate vector database with actual dimension values from Looker explores.

This script fetches dimension metadata from your Looker instance and populates
the vector database with real field references for semantic search.
"""

import os
import sys
import json
import logging
from typing import Dict, List, Any, Optional
import looker_sdk
from server import add_dimension_values, get_collection_stats, initialize_vector_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_looker_sdk():
    """Initialize Looker SDK using environment variables"""
    required_env_vars = ["LOOKERSDK_BASE_URL", "LOOKERSDK_CLIENT_ID", "LOOKERSDK_CLIENT_SECRET"]
    for var in required_env_vars:
        if not os.getenv(var):
            raise EnvironmentError(f"Environment variable {var} is not set")
    
    return looker_sdk.init40()

def extract_dimension_values_from_explore(sdk, model_name: str, explore_name: str) -> List[Dict[str, Any]]:
    """
    Extract dimension metadata from a Looker explore.
    
    Args:
        sdk: Looker SDK instance
        model_name: Name of the Looker model
        explore_name: Name of the explore
        
    Returns:
        List of dimension value records for vector database
    """
    try:
        # Get explore metadata including dimensions and dimension groups
        explore_data = sdk.lookml_model_explore(
            model_name, 
            explore_name,
            fields='dimensions,dimension_groups'
        )
        
        dimension_records = []
        explore_key = f"{model_name}:{explore_name}"
        
        # Process regular dimensions
        if explore_data.fields and explore_data.fields.dimensions:
            for dim in explore_data.fields.dimensions:
                if dim.name and dim.view_label:
                    # Create field reference in format: model.explore.view.field
                    field_reference = f"{model_name}.{explore_name}.{dim.view_label.lower().replace(' ', '_')}.{dim.name}"
                    
                    record = {
                        "value": dim.label or dim.name,
                        "field_reference": field_reference,
                        "explore_key": explore_key,
                        "field_type": "dimension",
                        "description": dim.description or f"{dim.label or dim.name} dimension from {explore_name} explore"
                    }
                    dimension_records.append(record)
                    
                    # Also add the field name itself as a searchable value
                    if dim.name != (dim.label or dim.name):
                        field_name_record = {
                            "value": dim.name,
                            "field_reference": field_reference,
                            "explore_key": explore_key,
                            "field_type": "dimension",
                            "description": f"Field name: {dim.name} from {explore_name} explore"
                        }
                        dimension_records.append(field_name_record)
        
        # Process dimension groups (date/time dimensions)
        if explore_data.fields and explore_data.fields.dimension_groups:
            for dim_group in explore_data.fields.dimension_groups:
                if dim_group.name and dim_group.view_label:
                    # Create field reference for dimension group
                    field_reference = f"{model_name}.{explore_name}.{dim_group.view_label.lower().replace(' ', '_')}.{dim_group.name}"
                    
                    record = {
                        "value": dim_group.label or dim_group.name,
                        "field_reference": field_reference,
                        "explore_key": explore_key,
                        "field_type": "dimension_group",
                        "description": dim_group.description or f"{dim_group.label or dim_group.name} dimension group from {explore_name} explore"
                    }
                    dimension_records.append(record)
        
        logger.info(f"Extracted {len(dimension_records)} dimension records from {model_name}:{explore_name}")
        return dimension_records
        
    except Exception as e:
        logger.error(f"Failed to extract dimensions from {model_name}:{explore_name}: {e}")
        return []

def get_available_explores(sdk) -> List[Dict[str, str]]:
    """Get list of available explores from Looker"""
    try:
        # Get all models
        models = sdk.all_lookml_models()
        explores = []
        
        for model in models:
            if model.explores:
                for explore in model.explores:
                    explores.append({
                        "model": model.name,
                        "explore": explore.name,
                        "label": explore.label or explore.name
                    })
        
        logger.info(f"Found {len(explores)} explores across {len(models)} models")
        return explores
        
    except Exception as e:
        logger.error(f"Failed to get available explores: {e}")
        return []

def populate_vector_db_from_looker(explore_limit: Optional[int] = None):
    """
    Populate vector database with dimension values from Looker explores.
    
    Args:
        explore_limit: Maximum number of explores to process (None for all)
    """
    try:
        # Initialize components
        logger.info("🔧 Initializing vector database...")
        initialize_vector_db()
        
        logger.info("🔗 Connecting to Looker...")
        sdk = init_looker_sdk()
        
        # Get available explores
        logger.info("🔍 Discovering available explores...")
        explores = get_available_explores(sdk)
        
        if not explores:
            logger.error("❌ No explores found in Looker instance")
            return
        
        # Limit explores if specified
        if explore_limit:
            explores = explores[:explore_limit]
            logger.info(f"📊 Processing first {len(explores)} explores...")
        else:
            logger.info(f"📊 Processing all {len(explores)} explores...")
        
        # Get initial stats
        initial_stats = get_collection_stats()
        logger.info(f"Initial vector DB stats: {initial_stats}")
        
        # Extract and add dimension values from each explore
        total_added = 0
        successful_explores = 0
        
        for i, explore_info in enumerate(explores, 1):
            model_name = explore_info["model"]
            explore_name = explore_info["explore"]
            
            logger.info(f"[{i}/{len(explores)}] Processing {model_name}:{explore_name}...")
            
            # Extract dimensions from this explore
            dimension_records = extract_dimension_values_from_explore(sdk, model_name, explore_name)
            
            if dimension_records:
                # Add to vector database
                result = add_dimension_values(dimension_records)
                
                if "status" in result and result["status"] == "success":
                    added_count = result.get("added_count", 0)
                    total_added += added_count
                    successful_explores += 1
                    logger.info(f"✅ Added {added_count} dimensions from {model_name}:{explore_name}")
                else:
                    logger.error(f"❌ Failed to add dimensions from {model_name}:{explore_name}: {result}")
            else:
                logger.warning(f"⚠️ No dimensions found in {model_name}:{explore_name}")
        
        # Get final stats
        final_stats = get_collection_stats()
        logger.info(f"Final vector DB stats: {final_stats}")
        
        logger.info(f"""
🎉 Population complete!
✅ Successfully processed {successful_explores}/{len(explores)} explores
📊 Total dimensions added: {total_added}
🔍 Total values in vector DB: {final_stats.get('total_values', 0)}
        """)
        
    except Exception as e:
        logger.error(f"Failed to populate vector database: {e}")
        raise

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Populate vector database with Looker dimension values")
    parser.add_argument("--limit", type=int, help="Limit number of explores to process (for testing)")
    parser.add_argument("--stats-only", action="store_true", help="Only show current vector DB stats")
    
    args = parser.parse_args()
    
    if args.stats_only:
        # Just show current stats
        try:
            initialize_vector_db()
            stats = get_collection_stats()
            print(f"Current vector database stats:")
            print(json.dumps(stats, indent=2))
        except Exception as e:
            print(f"Error getting stats: {e}")
    else:
        # Run full population
        populate_vector_db_from_looker(args.limit)