import re
import logging
from typing import Dict, List, Tuple
from langchain_community.llms import VertexAI

class QueryAnalyzer:
    """Utility class for analyzing user queries"""
    
    @staticmethod
    def needs_visualization(query: str) -> bool:
        """
        Determine if the query needs visualization documentation
        
        Args:
            query: The user's query
            
        Returns:
            True if visualization docs should be included
        """
        # Simple rule-based check for visualization keywords
        viz_keywords = [
            'chart', 'graph', 'plot', 'visualize', 'visualization', 'display',
            'bar chart', 'line chart', 'pie chart', 'scatter plot', 'map',
            'dashboard', 'table', 'heatmap', 'treemap'
        ]
        
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in viz_keywords)
    
    @staticmethod
    def needs_pivots(query: str, dimensions: List[Dict]) -> Tuple[bool, str]:
        """
        Determine if the query needs pivot documentation and suggest pivot field
        
        Args:
            query: The user's query
            dimensions: List of dimension fields
            
        Returns:
            Tuple of (needs_pivots: bool, suggested_pivot_field: str)
        """
        # Check for pivot keywords
        pivot_keywords = [
            'pivot', 'by', 'grouped by', 'split by', 'compare across',
            'compare by', 'matrix', 'crosstab', 'cross-tabulation'
        ]
        
        # Check if there are dimension comparison words in the query
        query_lower = query.lower()
        has_pivot_terms = any(keyword in query_lower for keyword in pivot_keywords)
        
        # Count potential dimensions in the query that might need comparison
        dimension_count = 0
        suggested_pivot = ""
        
        # Find dimensions mentioned in the query
        mentioned_dimensions = []
        for dim in dimensions:
            name = dim.get('name', '')
            label = dim.get('label', '')
            
            # Extract the view name and field name
            if '.' in name:
                field_name = name.split('.')[1]
            else:
                field_name = name
                
            # Check if field name or label is in the query
            if field_name.lower() in query_lower or (label and label.lower() in query_lower):
                mentioned_dimensions.append(dim)
                
        dimension_count = len(mentioned_dimensions)
        
        # If 2+ dimensions are mentioned or pivot terms exist, we likely need pivots
        if dimension_count >= 2 or has_pivot_terms:
            # Find the dimension with lowest cardinality (best for pivoting)
            # This is a heuristic - time dimensions are often good pivots
            time_dimension = next((d for d in mentioned_dimensions if 'time' in d.get('type', '').lower() 
                                   or 'date' in d.get('type', '').lower()), None)
                                   
            if time_dimension:
                suggested_pivot = time_dimension.get('name', '')
            elif mentioned_dimensions:
                # Just pick the first mentioned dimension as pivot
                suggested_pivot = mentioned_dimensions[0].get('name', '')
                
            return True, suggested_pivot
            
        return False, ""
        
    @staticmethod
    async def analyze_with_llm(llm, query: str, dimensions: List[Dict]) -> Dict:
        """
        Use LLM to analyze the query requirements
        
        Args:
            llm: LLM instance
            query: The user's query
            dimensions: List of dimension fields
            
        Returns:
            Dict with analysis results
        """
        dimension_names = [d.get('name', '') for d in dimensions]
        dimension_list = "\n".join([f"- {name}" for name in dimension_names])
        
        prompt = f"""
        Analyze the following user query about Looker data and determine:
        
        1. Does it need visualization capabilities? (yes/no)
        2. Does it need pivot functionality? (yes/no)
        3. If pivot is needed, which dimension would be best to pivot on?
        
        User query: "{query}"
        
        Available dimensions:
        {dimension_list}
        
        Return your analysis as a JSON object with these fields:
        {{
            "needs_visualization": true/false,
            "needs_pivots": true/false,
            "pivot_field": "dimension name or empty string"
        }}
        """
        
        try:
            response = llm.invoke(prompt)
            import json
            return json.loads(response)
        except Exception as e:
            logging.error(f"Error analyzing query with LLM: {e}")
            # Fall back to rule-based analysis
            needs_viz = QueryAnalyzer.needs_visualization(query)
            needs_pivots, pivot_field = QueryAnalyzer.needs_pivots(query, dimensions)
            return {
                "needs_visualization": needs_viz,
                "needs_pivots": needs_pivots,
                "pivot_field": pivot_field
            }
