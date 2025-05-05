import logging
import re
import datetime
from typing import Dict, List, Any, Set, Optional, Tuple, Union

class ExploreFieldValidator:
    """Utility class for validating and working with Looker explore fields"""
    
    # Common filter values
    NULL_VALUES = ["NULL", "null", "EMPTY", "empty"]
    NOT_NULL_VALUES = ["NOT NULL", "not null", "-NULL", "-null", "-EMPTY", "-empty"]
    
    # Date related constants
    DATE_INTERVALS = [
        "second", "minute", "hour", "day", "week", "month", "quarter", "year"
    ]
    
    # Boolean related constants
    BOOLEAN_TRUE_VALUES = ["yes", "Yes", "TRUE", "true", "1"]
    BOOLEAN_FALSE_VALUES = ["no", "No", "FALSE", "false", "0"]
    
    @staticmethod
    def validate_filter_expression(field_type: str, filter_expression: str) -> bool:
        """
        Validate if a filter expression is appropriate for a field type
        
        Args:
            field_type: The Looker field type
            filter_expression: The filter expression to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not field_type or not filter_expression:
            return False
            
        # Normalize field type to lowercase
        field_type = field_type.lower()
        
        # Handle null values for any field type
        if filter_expression in ExploreFieldValidator.NULL_VALUES + ExploreFieldValidator.NOT_NULL_VALUES:
            return True
            
        # Choose validation method based on field type
        if field_type in ('date', 'date_time', 'datetime', 'timestamp', 'time'):
            return ExploreFieldValidator.validate_date_filter(filter_expression)
        elif field_type in ('string', 'varchar', 'text', 'char'):
            return ExploreFieldValidator.validate_string_filter(filter_expression)
        elif field_type in ('number', 'int', 'integer', 'decimal', 'float', 'double', 'money', 'currency'):
            return ExploreFieldValidator.validate_number_filter(filter_expression)
        elif field_type in ('boolean', 'bool', 'yesno'):
            return ExploreFieldValidator.validate_boolean_filter(filter_expression)
            
        # Default to accepting if no specific rule
        return True
        
    @staticmethod
    def validate_date_filter(filter_expression: str) -> bool:
        """
        Validate date filter expressions based on Looker documentation
        
        Args:
            filter_expression: Date filter expression to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Common date patterns
        date_patterns = [
            # Date format patterns (YYYY-MM-DD, YYYY/MM/DD)
            r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',
            
            # Date with time format
            r'\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{1,2}(:\d{1,2})?',
            
            # Year, Month, or Fiscal Year formats
            r'\d{4}', r'FY\d{4}', r'\d{4}[-/]\d{1,2}', r'FY\d{4}-Q[1-4]',
            
            # Common date keywords
            r'today|yesterday|tomorrow',
            
            # Day of week
            r'monday|tuesday|wednesday|thursday|friday|saturday|sunday',
            
            # Relative date patterns
            r'(this|next|last)\s+(day|week|month|quarter|year)',
            
            # Numeric intervals
            r'\d+\s+(second|minute|hour|day|week|month|quarter|year)s?(\s+ago)?(\s+for\s+\d+\s+(second|minute|hour|day|week|month|quarter|year)s?)?',
            
            # Before/after date patterns
            r'(before|after)\s+(\d+\s+(second|minute|hour|day|week|month|quarter|year)s?\s+ago|\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            
            # Date ranges
            r'\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+to\s+\d{4}[-/]\d{1,2}[-/]\d{1,2}',
            
            # Future dates
            r'\d+\s+(second|minute|hour|day|week|month|quarter|year)s?\s+from\s+now'
        ]
        
        # Check for multiple date expressions (comma-separated for OR logic)
        if ',' in filter_expression:
            parts = [part.strip() for part in filter_expression.split(',')]
            return all(ExploreFieldValidator.validate_date_filter(part) for part in parts)
        
        # Check against patterns
        for pattern in date_patterns:
            if re.match(f'^{pattern}$', filter_expression, re.IGNORECASE):
                return True
                
        # Check for negated date expressions
        if filter_expression.startswith('-') and ExploreFieldValidator.validate_date_filter(filter_expression[1:]):
            return True
                
        return False
        
    @staticmethod
    def validate_string_filter(filter_expression: str) -> bool:
        """
        Validate string filter expressions based on Looker documentation
        
        Args:
            filter_expression: String filter expression to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Most string filters are valid, but check for certain patterns
        string_patterns = [
            # Basic equality
            r'[^,%_]+',
            
            # Contains, starts with, ends with
            r'%[^,%]+%', r'[^,%]+%', r'%[^,%]+',
            
            # Multiple values (OR)
            r'[^,%]+,[^,%]+',
            
            # Negation
            r'-[^,%]+', r'-[^,%]+%', r'-%[^,%]+', r'-%[^,%]+%',
            
            # Wildcard with underscore
            r'[^,%]*_[^,%]*'
        ]
        
        # Check for null values
        if filter_expression in ExploreFieldValidator.NULL_VALUES + ExploreFieldValidator.NOT_NULL_VALUES:
            return True
            
        # Check for comma-separated values (OR logic)
        if ',' in filter_expression and not filter_expression.startswith('-'):
            parts = [part.strip() for part in filter_expression.split(',')]
            return all(ExploreFieldValidator.validate_string_filter(part) for part in parts)
        
        # Check against patterns
        for pattern in string_patterns:
            if re.match(f'^{pattern}$', filter_expression):
                return True
                
        # By default, accept most string filters
        return len(filter_expression) > 0
        
    @staticmethod
    def validate_number_filter(filter_expression: str) -> bool:
        """
        Validate number filter expressions based on Looker documentation
        
        Args:
            filter_expression: Number filter expression to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Common number patterns
        number_patterns = [
            # Simple number
            r'-?\d+(\.\d*)?',
            
            # Comparison operators
            r'[<>]=?\s*-?\d+(\.\d*)?',
            r'!=\s*-?\d+(\.\d*)?',
            r'<>\s*-?\d+(\.\d*)?',
            
            # Ranges
            r'-?\d+(\.\d*)?\s+to\s+-?\d+(\.\d*)?',
            r'to\s+-?\d+(\.\d*)?',
            r'-?\d+(\.\d*)?\s+to',
            
            # Interval notation
            r'\(\s*-?\d+(\.\d*)?\s*,\s*-?\d+(\.\d*)?\s*\)',
            r'\[\s*-?\d+(\.\d*)?\s*,\s*-?\d+(\.\d*)?\s*\]',
            r'\(\s*-?\d+(\.\d*)?\s*,\s*-?\d+(\.\d*)?\s*\]',
            r'\[\s*-?\d+(\.\d*)?\s*,\s*-?\d+(\.\d*)?\s*\)',
            r'\(\s*-?\d+(\.\d*)?\s*,\s*\)',
            r'\(\s*,\s*-?\d+(\.\d*)?\s*\]',
            
            # AND/OR logic
            r'[<>]=?\s*-?\d+(\.\d*)?\s+(AND|OR)\s+[<>]=?\s*-?\d+(\.\d*)?',
            
            # NOT notation
            r'NOT\s+(-?\d+(\.\d*)?|[<>]=?\s*-?\d+(\.\d*)?)'
        ]
        
        # Check for comma-separated values (OR logic)
        if ',' in filter_expression:
            # Handle complex cases with 'NOT'
            if filter_expression.upper().startswith('NOT '):
                # Special case for NOT syntax
                return True  # Complex NOT handling requires SQL context
                
            # Normal comma-separated values
            parts = [part.strip() for part in filter_expression.split(',')]
            return all(ExploreFieldValidator.validate_number_filter(part) for part in parts)
        
        # Check for null values
        if filter_expression in ExploreFieldValidator.NULL_VALUES + ExploreFieldValidator.NOT_NULL_VALUES:
            return True
            
        # Check against patterns
        for pattern in number_patterns:
            if re.match(f'^{pattern}$', filter_expression, re.IGNORECASE):
                return True
                
        return False
        
    @staticmethod
    def validate_boolean_filter(filter_expression: str) -> bool:
        """
        Validate boolean filter expressions based on Looker documentation
        
        Args:
            filter_expression: Boolean filter expression to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Check if the filter expression is a valid boolean value
        return (filter_expression.strip() in 
                ExploreFieldValidator.BOOLEAN_TRUE_VALUES + 
                ExploreFieldValidator.BOOLEAN_FALSE_VALUES + 
                ExploreFieldValidator.NULL_VALUES + 
                ExploreFieldValidator.NOT_NULL_VALUES)
    
    @staticmethod
    def get_field_names_by_type(semantic_model: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        """
        Extract dimension and measure names from a semantic model
        
        Args:
            semantic_model: The semantic model dictionary
            
        Returns:
            Tuple of (dimension_names, measure_names)
        """
        dimensions = semantic_model.get("dimensions", [])
        measures = semantic_model.get("measures", [])
        
        dimension_names = [dim.get("name") for dim in dimensions if dim.get("name")]
        measure_names = [meas.get("name") for meas in measures if meas.get("name")]
        
        return dimension_names, measure_names
    
    @staticmethod
    def find_matching_field(field_name: str, semantic_model: Dict, field_mapping: Optional[Dict] = None) -> str:
        """
        Find a matching field in the semantic model, with optional alias mapping
        
        Args:
            field_name: The field name to look for
            semantic_model: The semantic model containing dimensions and measures
            field_mapping: Optional dictionary mapping user terms to standard field names
            
        Returns:
            The actual field name in the semantic model, or empty string if not found
        """
        if not field_mapping:
            field_mapping = {}
            
        field_name_lower = field_name.lower()
        
        # Check if this field name appears in our mapping
        mapped_name = None
        for alias, std_field in field_mapping.items():
            if alias.lower() in field_name_lower:
                mapped_name = std_field
                break
        
        # Search in dimensions
        for dimension in semantic_model.get('dimensions', []):
            dim_name = dimension.get('name', '').lower()
            dim_label = dimension.get('label', '').lower()
            
            # Direct match
            if field_name_lower == dim_name or field_name_lower == dim_label:
                return dimension.get('name', '')
                
            # Match through alias/mapping
            if mapped_name and (mapped_name.lower() in dim_name or mapped_name.lower() in dim_label):
                return dimension.get('name', '')
        
        # Search in measures
        for measure in semantic_model.get('measures', []):
            measure_name = measure.get('name', '').lower()
            measure_label = measure.get('label', '').lower()
            
            # Direct match
            if field_name_lower == measure_name or field_name_lower == measure_label:
                return measure.get('name', '')
                
            # Match through alias/mapping
            if mapped_name and (mapped_name.lower() in measure_name or mapped_name.lower() in measure_label):
                return measure.get('name', '')
        
        return ""
    
    @staticmethod
    def get_field_type(field_name: str, semantic_model: Dict[str, Any]) -> str:
        """
        Get the type of a field from the semantic model
        
        Args:
            field_name: Name of the field
            semantic_model: Semantic model containing fields
            
        Returns:
            Field type string or empty string if not found
        """
        # Check dimensions
        for dimension in semantic_model.get('dimensions', []):
            if dimension.get('name') == field_name:
                return dimension.get('type', '')
                
        # Check measures
        for measure in semantic_model.get('measures', []):
            if measure.get('name') == field_name:
                return measure.get('type', '')
                
        return ""
    
    @staticmethod
    def validate_filters_with_feedback(filters: Dict[str, Any], semantic_model: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """
        Validate filters and provide detailed feedback on invalid filters
        
        Args:
            filters: Dictionary of filters to validate {field_name: filter_expression}
            semantic_model: Semantic model containing field information
            
        Returns:
            Tuple of (valid_filters, invalid_filters_with_reasons)
            where valid_filters is {field_name: filter_expression} for valid filters
            and invalid_filters_with_reasons is {field_name: reason} for invalid filters
        """
        valid_filters = {}
        invalid_filters = {}
        
        # Get dimensions and measures
        dimensions = semantic_model.get("dimensions", [])
        measures = semantic_model.get("measures", [])
        
        # Extract valid field names
        dimension_names = [dim.get("name") for dim in dimensions if dim.get("name")]
        measure_names = [meas.get("name") for meas in measures if meas.get("name")]
        valid_fields = set(dimension_names + measure_names)
        
        for field, value in filters.items():
            # Check if field exists
            if field not in valid_fields:
                invalid_filters[field] = f"Field '{field}' does not exist in the semantic model"
                continue
            
            # Get field type
            field_type = ExploreFieldValidator.get_field_type(field, semantic_model)
            
            if isinstance(value, list):
                # Handle multiple filter values
                invalid_values = []
                valid_values = []
                
                for v in value:
                    if ExploreFieldValidator.validate_filter_expression(field_type, v):
                        valid_values.append(v)
                    else:
                        invalid_values.append(v)
                
                if invalid_values:
                    invalid_filters[field] = f"Invalid filter expression(s) for {field_type} field: {', '.join(invalid_values)}"
                
                if valid_values:
                    valid_filters[field] = valid_values
            else:
                # Handle single filter value
                if ExploreFieldValidator.validate_filter_expression(field_type, value):
                    valid_filters[field] = value
                else:
                    invalid_filters[field] = f"Invalid filter expression '{value}' for {field_type} field"
        
        return valid_filters, invalid_filters

    @staticmethod
    def validate_explore_params(params: Dict[str, Any], semantic_model: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate explore parameters against a semantic model
        
        Args:
            params: The explore parameters to validate
            semantic_model: The semantic model containing valid fields
            
        Returns:
            Validated and cleaned explore parameters
        """
        # Extract model name and explore ID
        model_name = semantic_model.get("modelName", params.get("model", ""))
        explore_id = semantic_model.get("exploreId", params.get("view", ""))
        
        # Get valid field names
        dimension_names, measure_names = ExploreFieldValidator.get_field_names_by_type(semantic_model)
        valid_fields = set(dimension_names + measure_names)
        
        # Create a clean params object with required fields
        clean_params = {
            "model": model_name,
            "view": explore_id,
            "fields": [],
            "sorts": [],
            "filters": {},
            "limit": params.get("limit", "500")
        }
        
        # Validate fields
        if isinstance(params.get("fields"), list):
            clean_params["fields"] = [f for f in params["fields"] if f in valid_fields]
            
            # Add default fields if none valid
            if not clean_params["fields"]:
                if dimension_names:
                    clean_params["fields"].append(dimension_names[0])
                if measure_names:
                    clean_params["fields"].append(measure_names[0])
        
        # Validate sorts
        if isinstance(params.get("sorts"), list):
            valid_sorts = []
            for sort in params["sorts"]:
                sort_field = sort.split()[0] if ' ' in sort else sort
                if sort_field in valid_fields:
                    valid_sorts.append(sort)
            clean_params["sorts"] = valid_sorts
        
        # Validate filters
        if isinstance(params.get("filters"), dict):
            valid_filters = {}
            for field, value in params["filters"].items():
                if field in valid_fields:
                    # Get the field type to validate the filter expression
                    field_type = ExploreFieldValidator.get_field_type(field, semantic_model)
                    
                    # Validate filter value based on field type
                    if isinstance(value, list):
                        # Multiple filter values
                        valid_values = [v for v in value if ExploreFieldValidator.validate_filter_expression(field_type, v)]
                        if valid_values:
                            valid_filters[field] = valid_values
                    else:
                        # Single filter value
                        if ExploreFieldValidator.validate_filter_expression(field_type, value):
                            valid_filters[field] = value
                            
            clean_params["filters"] = valid_filters
        
        # Copy any other fields that might be needed
        for key in ["pivots", "vis_config", "filter_expression"]:
            if key in params:
                clean_params[key] = params[key]
        
        return clean_params
