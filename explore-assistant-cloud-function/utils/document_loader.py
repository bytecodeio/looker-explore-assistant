import os
import logging
from typing import Dict, Optional

class DocumentLoader:
    """Utility class for loading documentation files"""
    
    _document_cache: Dict[str, str] = {}
    _base_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'documents')
    
    @classmethod
    def load_document(cls, filename: str) -> str:
        """
        Load a document from the documents directory
        
        Args:
            filename: The name of the file to load (with extension)
            
        Returns:
            The contents of the file as a string or empty string if file not found
        """
        # Return from cache if available
        if filename in cls._document_cache:
            return cls._document_cache[filename]
            
        try:
            file_path = os.path.join(cls._base_path, filename)
            if not os.path.exists(file_path):
                logging.error(f"Document file not found: {file_path}")
                return ""
                
            with open(file_path, 'r') as f:
                content = f.read()
                
            # Cache the content
            cls._document_cache[filename] = content
            return content
            
        except Exception as e:
            logging.error(f"Error loading document {filename}: {e}")
            return ""
            
    @classmethod
    def get_filter_doc(cls) -> str:
        """Load the filter documentation"""
        return cls.load_document('looker_filter_doc.md')
        
    @classmethod
    def get_intervals_doc(cls) -> str:
        """Load the intervals/timeframes documentation"""
        return cls.load_document('looker_filters_interval_tf.md')
        
    @classmethod
    def get_visualization_doc(cls) -> str:
        """Load the visualization documentation"""
        return cls.load_document('looker_visualization_doc.md')
        
    @classmethod
    def get_pivots_doc(cls) -> str:
        """Load the pivots documentation"""
        return cls.load_document('looker_pivots_url_parameters_doc.md')
