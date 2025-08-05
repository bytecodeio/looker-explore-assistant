#!/usr/bin/env python3
"""
Looker Explore Assistant Vector MCP Server

This MCP server provides semantic search capabilities for Looker dimension values,
mapping string values to their corresponding field references (model.explore.view.field).

Features:
- Semantic search of dimension values using vector embeddings
- Fast lookup of field references for natural language queries
- Privacy-safe: only stores dimension values and field paths, no row-level data
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("Looker Vector Search")

# Global variables for vector database and model
vector_db_client = None
collection = None
embedding_model = None

def initialize_vector_db():
    """Initialize ChromaDB and sentence transformer model"""
    global vector_db_client, collection, embedding_model
    
    try:
        # Initialize ChromaDB client
        vector_db_client = chromadb.PersistentClient(
            path="./vector_db",
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection for dimension values
        collection = vector_db_client.get_or_create_collection(
            name="looker_dimension_values",
            metadata={"description": "Looker dimension values mapped to field references"}
        )
        
        # Initialize sentence transformer model
        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        logger.info("Vector database initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize vector database: {e}")
        raise

@mcp.tool()
def search_dimension_values(
    query: str, 
    limit: int = 10,
    min_similarity: float = 0.3
) -> List[Dict[str, Any]]:
    """
    Search for dimension values that match the query semantically.
    
    Args:
        query: Natural language search term (e.g., "electronics", "manager roles")
        limit: Maximum number of results to return
        min_similarity: Minimum similarity score (0.0 to 1.0)
    
    Returns:
        List of matches with field references and similarity scores
    """
    if not collection or not embedding_model:
        return {"error": "Vector database not initialized. Please run initialize_data first."}
    
    try:
        # Generate embedding for the query
        query_embedding = embedding_model.encode([query]).tolist()[0]
        
        # Search the collection
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            include=['documents', 'metadatas', 'distances']
        )
        
        matches = []
        if results['documents'] and results['documents'][0]:
            for i, (doc, metadata, distance) in enumerate(zip(
                results['documents'][0],
                results['metadatas'][0], 
                results['distances'][0]
            )):
                # Convert distance to similarity score (ChromaDB uses cosine distance)
                similarity = 1 - distance
                
                if similarity >= min_similarity:
                    matches.append({
                        "value": doc,
                        "field_reference": metadata.get('field_reference', ''),
                        "explore_key": metadata.get('explore_key', ''),
                        "field_type": metadata.get('field_type', ''),
                        "similarity": round(similarity, 3),
                        "description": metadata.get('description', '')
                    })
        
        return {
            "query": query,
            "matches": matches,
            "total_found": len(matches)
        }
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return {"error": f"Search failed: {str(e)}"}

@mcp.tool()
def add_dimension_values(dimension_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Add dimension values to the vector database.
    
    Args:
        dimension_data: List of dimension value records with structure:
        [
            {
                "value": "Electronics",
                "field_reference": "ecommerce.order_items.product_category", 
                "explore_key": "ecommerce:order_items",
                "field_type": "dimension",
                "description": "Product category classification"
            }
        ]
    
    Returns:
        Status of the add operation
    """
    if not collection or not embedding_model:
        return {"error": "Vector database not initialized"}
    
    try:
        values = []
        metadatas = []
        embeddings = []
        ids = []
        
        for i, item in enumerate(dimension_data):
            value = item.get('value', '')
            if not value:
                continue
                
            values.append(value)
            metadatas.append({
                'field_reference': item.get('field_reference', ''),
                'explore_key': item.get('explore_key', ''),
                'field_type': item.get('field_type', 'dimension'),
                'description': item.get('description', '')
            })
            
            # Generate embedding
            embedding = embedding_model.encode([value]).tolist()[0]
            embeddings.append(embedding)
            
            # Create unique ID
            ids.append(f"{item.get('explore_key', 'unknown')}_{item.get('field_reference', 'unknown')}_{i}")
        
        if values:
            # Add to collection
            collection.add(
                documents=values,
                metadatas=metadatas,
                embeddings=embeddings,
                ids=ids
            )
            
            return {
                "status": "success",
                "added_count": len(values),
                "message": f"Successfully added {len(values)} dimension values"
            }
        else:
            return {"error": "No valid dimension values provided"}
            
    except Exception as e:
        logger.error(f"Failed to add dimension values: {e}")
        return {"error": f"Failed to add dimension values: {str(e)}"}

@mcp.tool()
def get_collection_stats() -> Dict[str, Any]:
    """Get statistics about the vector database collection"""
    if not collection:
        return {"error": "Vector database not initialized"}
    
    try:
        count = collection.count()
        return {
            "total_values": count,
            "collection_name": "looker_dimension_values",
            "status": "ready" if count > 0 else "empty"
        }
    except Exception as e:
        logger.error(f"Failed to get collection stats: {e}")
        return {"error": f"Failed to get collection stats: {str(e)}"}

@mcp.tool()
def clear_collection() -> Dict[str, Any]:
    """Clear all data from the vector database collection (use with caution!)"""
    if not collection:
        return {"error": "Vector database not initialized"}
    
    try:
        # Get all IDs and delete them
        all_data = collection.get()
        if all_data['ids']:
            collection.delete(ids=all_data['ids'])
            return {
                "status": "success", 
                "message": f"Cleared {len(all_data['ids'])} items from collection"
            }
        else:
            return {"status": "success", "message": "Collection was already empty"}
            
    except Exception as e:
        logger.error(f"Failed to clear collection: {e}")
        return {"error": f"Failed to clear collection: {str(e)}"}

# Resource for sample dimension data format
@mcp.resource("sample://dimension_data_format")
def get_sample_dimension_data_format() -> str:
    """Returns the expected format for dimension data"""
    sample = {
        "sample_dimension_data": [
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
            }
        ]
    }
    return json.dumps(sample, indent=2)

if __name__ == "__main__":
    # Initialize vector database on startup
    try:
        initialize_vector_db()
        logger.info("Starting Looker Vector Search MCP Server...")
        mcp.run()
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise