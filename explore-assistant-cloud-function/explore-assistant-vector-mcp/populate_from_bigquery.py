#!/usr/bin/env python3
"""
Populate vector database with dimension values extracted from BigQuery golden queries.

This script analyzes your existing golden queries to extract common dimension values
and field references, providing a faster alternative to direct Looker API access.
"""

import os
import json
import logging
import re
from typing import Dict, List, Any, Set
from google.cloud import bigquery
from server import add_dimension_values, get_collection_stats, initialize_vector_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# BigQuery configuration from environment
BQ_PROJECT_ID = os.environ.get("BQ_PROJECT_ID", "ml-accelerator-dbarr")
BQ_DATASET_ID = os.environ.get("BQ_DATASET_ID", "explore_assistant")
BQ_GOLDEN_TABLE = os.environ.get("BQ_GOLDEN_TABLE", "golden_queries")

def init_bigquery_client():
    """Initialize BigQuery client"""
    try:
        client = bigquery.Client(project=BQ_PROJECT_ID)
        logger.info(f"Connected to BigQuery project: {BQ_PROJECT_ID}")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize BigQuery client: {e}")
        raise

def extract_dimension_values_from_queries(client) -> List[Dict[str, Any]]:
    """
    Extract dimension values from golden queries in BigQuery.
    
    This analyzes the query outputs to find common dimension values and 
    maps them to their field references.
    """
    try:
        # Query to get golden queries with their explore info
        query = f"""
        SELECT 
            id,
            explore_id,
            input,
            output,
            link
        FROM `{BQ_PROJECT_ID}.{BQ_DATASET_ID}.{BQ_GOLDEN_TABLE}`
        WHERE output IS NOT NULL 
        AND explore_id IS NOT NULL
        LIMIT 100
        """
        
        logger.info(f"Querying golden queries from {BQ_PROJECT_ID}.{BQ_DATASET_ID}.{BQ_GOLDEN_TABLE}")
        query_job = client.query(query)
        results = query_job.result()
        
        dimension_records = []
        explore_field_map = {}  # Track fields per explore
        
        for row in results:
            explore_id = row.explore_id
            input_text = row.input or ""
            output_json = row.output or "{}"
            
            try:
                # Parse the output JSON to extract field references
                output_data = json.loads(output_json)
                
                # Extract dimensions from the query output
                dimensions = output_data.get("dimensions", [])
                measures = output_data.get("measures", [])
                filters = output_data.get("filters", {})
                
                # Process dimensions
                for dim in dimensions:
                    if isinstance(dim, str) and "." in dim:
                        # Extract meaningful values from the input text
                        input_words = extract_meaningful_terms(input_text)
                        
                        for word in input_words:
                            if len(word) >= 3:  # Skip very short words
                                record = {
                                    "value": word,
                                    "field_reference": dim,
                                    "explore_key": explore_id,
                                    "field_type": "dimension",
                                    "description": f"Dimension value '{word}' commonly used with field {dim}"
                                }
                                dimension_records.append(record)
                
                # Process filters (these often contain actual dimension values)
                for field_ref, filter_conditions in filters.items():
                    if isinstance(filter_conditions, dict):
                        for condition, values in filter_conditions.items():
                            if isinstance(values, list):
                                for value in values:
                                    if isinstance(value, str) and len(value) >= 2:
                                        record = {
                                            "value": value,
                                            "field_reference": field_ref,
                                            "explore_key": explore_id,
                                            "field_type": "dimension",
                                            "description": f"Filter value for {field_ref}"
                                        }
                                        dimension_records.append(record)
                            elif isinstance(values, str) and len(values) >= 2:
                                record = {
                                    "value": values,
                                    "field_reference": field_ref,
                                    "explore_key": explore_id,
                                    "field_type": "dimension",
                                    "description": f"Filter value for {field_ref}"
                                }
                                dimension_records.append(record)
            
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse output JSON for query {row.id}")
                continue
            except Exception as e:
                logger.warning(f"Error processing query {row.id}: {e}")
                continue
        
        # Remove duplicates while preserving order
        unique_records = []
        seen = set()
        for record in dimension_records:
            key = (record["value"].lower(), record["field_reference"], record["explore_key"])
            if key not in seen:
                seen.add(key)
                unique_records.append(record)
        
        logger.info(f"Extracted {len(unique_records)} unique dimension value mappings from golden queries")
        return unique_records
        
    except Exception as e:
        logger.error(f"Failed to extract dimension values from BigQuery: {e}")
        return []

def extract_meaningful_terms(text: str) -> List[str]:
    """Extract meaningful terms from query text that might be dimension values"""
    if not text:
        return []
    
    # Common stop words to filter out
    stop_words = {
        'show', 'me', 'get', 'find', 'the', 'and', 'or', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before',
        'after', 'above', 'below', 'over', 'under', 'again', 'further', 'then', 'once',
        'what', 'where', 'when', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more',
        'most', 'other', 'some', 'such', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
        'can', 'will', 'just', 'should', 'now', 'total', 'sum', 'count', 'average', 'avg',
        'max', 'min', 'sales', 'revenue', 'data', 'analysis', 'report', 'query', 'explore'
    }
    
    # Extract words and quoted phrases
    terms = []
    
    # Find quoted phrases first
    quoted_matches = re.findall(r'"([^"]*)"', text)
    for match in quoted_matches:
        if len(match.strip()) >= 3:
            terms.append(match.strip())
    
    # Find individual capitalized words (proper nouns)
    capitalized_matches = re.findall(r'\b[A-Z][a-z]+\b', text)
    for match in capitalized_matches:
        if match.lower() not in stop_words and len(match) >= 3:
            terms.append(match)
    
    # Find other meaningful words
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    for word in words:
        if word not in stop_words and word not in [t.lower() for t in terms]:
            terms.append(word)
    
    return terms[:10]  # Limit to top 10 terms to avoid noise

def add_common_dimension_values():
    """Add some common dimension values that are frequently searched for"""
    common_values = [
        # Time periods
        {"value": "Q1", "field_type": "dimension", "description": "First quarter time period"},
        {"value": "Q2", "field_type": "dimension", "description": "Second quarter time period"},
        {"value": "Q3", "field_type": "dimension", "description": "Third quarter time period"},
        {"value": "Q4", "field_type": "dimension", "description": "Fourth quarter time period"},
        {"value": "January", "field_type": "dimension", "description": "January month"},
        {"value": "February", "field_type": "dimension", "description": "February month"},
        {"value": "March", "field_type": "dimension", "description": "March month"},
        {"value": "2024", "field_type": "dimension", "description": "Year 2024"},
        {"value": "2023", "field_type": "dimension", "description": "Year 2023"},
        
        # Geographic
        {"value": "United States", "field_type": "dimension", "description": "Country name"},
        {"value": "California", "field_type": "dimension", "description": "State name"},
        {"value": "New York", "field_type": "dimension", "description": "State/city name"},
        {"value": "Texas", "field_type": "dimension", "description": "State name"},
        
        # Business categories
        {"value": "Enterprise", "field_type": "dimension", "description": "Business tier"},
        {"value": "Professional", "field_type": "dimension", "description": "Service tier"},
        {"value": "Standard", "field_type": "dimension", "description": "Service tier"},
        {"value": "Basic", "field_type": "dimension", "description": "Service tier"},
        
        # Status values
        {"value": "Active", "field_type": "dimension", "description": "Active status"},
        {"value": "Inactive", "field_type": "dimension", "description": "Inactive status"},
        {"value": "Pending", "field_type": "dimension", "description": "Pending status"},
        {"value": "Complete", "field_type": "dimension", "description": "Complete status"},
    ]
    
    # Add generic field references for common values
    records = []
    for value_info in common_values:
        record = {
            "value": value_info["value"],
            "field_reference": "common.generic.dimension",  # Generic reference
            "explore_key": "common:values",
            "field_type": value_info["field_type"],
            "description": value_info["description"]
        }
        records.append(record)
    
    return records

def populate_vector_db_from_bigquery():
    """Populate vector database with dimension values from BigQuery golden queries"""
    try:
        # Initialize components
        logger.info("🔧 Initializing vector database...")
        initialize_vector_db()
        
        # Get initial stats
        initial_stats = get_collection_stats()
        logger.info(f"Initial vector DB stats: {initial_stats}")
        
        # Extract dimension values from BigQuery
        logger.info("🔍 Analyzing golden queries in BigQuery...")
        client = init_bigquery_client()
        dimension_records = extract_dimension_values_from_queries(client)
        
        # Add common dimension values
        logger.info("📝 Adding common dimension values...")
        common_records = add_common_dimension_values()
        dimension_records.extend(common_records)
        
        if dimension_records:
            logger.info(f"📥 Adding {len(dimension_records)} dimension value mappings to vector database...")
            result = add_dimension_values(dimension_records)
            
            if "status" in result and result["status"] == "success":
                added_count = result.get("added_count", 0)
                logger.info(f"✅ Successfully added {added_count} dimension value mappings")
            else:
                logger.error(f"❌ Failed to add dimension values: {result}")
                return
        else:
            logger.warning("⚠️ No dimension values extracted from golden queries")
            return
        
        # Get final stats
        final_stats = get_collection_stats()
        logger.info(f"Final vector DB stats: {final_stats}")
        
        logger.info(f"""
🎉 Population complete!
📊 Total values in vector DB: {final_stats.get('total_values', 0)}
🚀 Vector database is ready for semantic search!

To test the search functionality, run:
python test_server.py
        """)
        
    except Exception as e:
        logger.error(f"Failed to populate vector database from BigQuery: {e}")
        raise

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Populate vector database from BigQuery golden queries")
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
        # Run BigQuery population
        populate_vector_db_from_bigquery()