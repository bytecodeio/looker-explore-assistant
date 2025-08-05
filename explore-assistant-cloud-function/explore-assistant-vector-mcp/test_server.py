#!/usr/bin/env python3
"""
Test script for the Looker Vector MCP Server

This script demonstrates how to use the MCP tools and tests basic functionality.
"""

import json
from server import (
    initialize_vector_db, 
    search_dimension_values, 
    add_dimension_values,
    get_collection_stats,
    clear_collection
)

def test_vector_server():
    """Test the vector server functionality"""
    
    print("🔧 Initializing vector database...")
    try:
        initialize_vector_db()
        print("✅ Vector database initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return
    
    print("\n📊 Getting initial collection stats...")
    stats = get_collection_stats()
    print(f"Stats: {json.dumps(stats, indent=2)}")
    
    print("\n🧹 Clearing collection for fresh test...")
    clear_result = clear_collection()
    print(f"Clear result: {json.dumps(clear_result, indent=2)}")
    
    print("\n📥 Adding sample dimension values...")
    sample_data = [
        {
            "value": "Electronics",
            "field_reference": "ecommerce.order_items.product_category",
            "explore_key": "ecommerce:order_items",
            "field_type": "dimension",
            "description": "Product category for retail items"
        },
        {
            "value": "San Francisco",
            "field_reference": "sales.customers.city", 
            "explore_key": "sales:customers",
            "field_type": "dimension",
            "description": "Customer city location"
        },
        {
            "value": "Manager",
            "field_reference": "hr.employees.job_title",
            "explore_key": "hr:employees", 
            "field_type": "dimension",
            "description": "Employee job title classification"
        },
        {
            "value": "Q4 2024",
            "field_reference": "finance.transactions.quarter",
            "explore_key": "finance:transactions",
            "field_type": "dimension",
            "description": "Financial reporting quarter"
        },
        {
            "value": "Premium",
            "field_reference": "products.subscriptions.tier",
            "explore_key": "products:subscriptions",
            "field_type": "dimension", 
            "description": "Subscription tier level"
        }
    ]
    
    add_result = add_dimension_values(sample_data)
    print(f"Add result: {json.dumps(add_result, indent=2)}")
    
    print("\n📊 Getting updated collection stats...")
    stats = get_collection_stats()
    print(f"Updated stats: {json.dumps(stats, indent=2)}")
    
    print("\n🔍 Testing semantic searches...")
    
    # Test various search queries
    test_queries = [
        "electronics products",
        "technology items", 
        "management roles",
        "bay area cities",
        "california locations",
        "fourth quarter",
        "end of year",
        "subscription levels",
        "premium services"
    ]
    
    for query in test_queries:
        print(f"\n🔎 Searching for: '{query}'")
        results = search_dimension_values(query, limit=3, min_similarity=0.2)
        
        if "error" in results:
            print(f"❌ Error: {results['error']}")
        else:
            print(f"Found {results['total_found']} matches:")
            for match in results['matches']:
                print(f"  • {match['value']} → {match['field_reference']} (similarity: {match['similarity']})")
    
    print("\n✅ Test completed successfully!")

if __name__ == "__main__":
    test_vector_server()