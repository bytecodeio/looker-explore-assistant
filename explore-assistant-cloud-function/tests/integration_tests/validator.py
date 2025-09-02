"""
Response validation engine for integration testing

Provides comprehensive validation capabilities for API responses,
supporting various comparison operators and custom validation functions.
"""

import re
import time
from typing import Any, Dict, List, Union
from jsonpath_ng import parse as jsonpath_parse
from jsonpath_ng.ext import parse as jsonpath_ext_parse
import logging

from .models import (
    ValidationCriterion, ValidationResult, ValidationOperator
)

logger = logging.getLogger(__name__)


class ValidationEngine:
    """
    Engine for validating API responses against defined criteria
    
    Supports JSONPath-based field selection and multiple validation operators
    including custom validation functions.
    """
    
    def __init__(self):
        self.operator_handlers = {
            ValidationOperator.EQUALS: self._validate_equals,
            ValidationOperator.NOT_EQUALS: self._validate_not_equals,
            ValidationOperator.CONTAINS: self._validate_contains,
            ValidationOperator.NOT_CONTAINS: self._validate_not_contains,
            ValidationOperator.HAS_KEY: self._validate_has_key,
            ValidationOperator.NOT_HAS_KEY: self._validate_not_has_key,
            ValidationOperator.GREATER_THAN: self._validate_greater_than,
            ValidationOperator.LESS_THAN: self._validate_less_than,
            ValidationOperator.LENGTH_EQUALS: self._validate_length_equals,
            ValidationOperator.LENGTH_GREATER_THAN: self._validate_length_greater_than,
            ValidationOperator.LENGTH_LESS_THAN: self._validate_length_less_than,
            ValidationOperator.REGEX_MATCH: self._validate_regex_match,
            ValidationOperator.IN_LIST: self._validate_in_list,
            ValidationOperator.NOT_IN_LIST: self._validate_not_in_list,
            ValidationOperator.IS_EMPTY: self._validate_is_empty,
            ValidationOperator.IS_NOT_EMPTY: self._validate_is_not_empty,
            ValidationOperator.CUSTOM: self._validate_custom,
        }
    
    def validate_response(self, response_data: Dict[str, Any], 
                         validation_criteria: List[ValidationCriterion]) -> List[ValidationResult]:
        """
        Validate response against multiple criteria
        
        Args:
            response_data: The API response data to validate
            validation_criteria: List of validation criteria to check
            
        Returns:
            List of ValidationResult objects with validation outcomes
        """
        results = []
        
        for criterion in validation_criteria:
            start_time = time.time()
            try:
                result = self._validate_single_criterion(response_data, criterion)
            except Exception as e:
                logger.error(f"Validation error for {criterion.field_path}: {e}")
                result = ValidationResult(
                    criterion=criterion,
                    passed=False,
                    error_message=f"Validation exception: {str(e)}"
                )
            
            result.execution_time_ms = (time.time() - start_time) * 1000
            results.append(result)
        
        return results
    
    def _validate_single_criterion(self, response_data: Dict[str, Any], 
                                  criterion: ValidationCriterion) -> ValidationResult:
        """Validate a single criterion against response data"""
        
        # Extract the actual value using JSONPath
        actual_value = self._extract_value(response_data, criterion.field_path)
        
        # Get the appropriate validation handler
        handler = self.operator_handlers.get(criterion.operator)
        if not handler:
            return ValidationResult(
                criterion=criterion,
                passed=False,
                actual_value=actual_value,
                error_message=f"Unsupported validation operator: {criterion.operator}"
            )
        
        # Perform validation
        try:
            passed, error_message = handler(actual_value, criterion.expected_value, criterion)
            return ValidationResult(
                criterion=criterion,
                passed=passed,
                actual_value=actual_value,
                error_message=error_message
            )
        except Exception as e:
            return ValidationResult(
                criterion=criterion,
                passed=False,
                actual_value=actual_value,
                error_message=f"Validation handler error: {str(e)}"
            )
    
    def _extract_value(self, data: Dict[str, Any], field_path: str) -> Any:
        """
        Extract value from nested data using JSONPath
        
        Args:
            data: Dictionary to search in
            field_path: JSONPath expression (e.g., "data.parameters.filters.field_name")
            
        Returns:
            The extracted value or None if path not found
        """
        try:
            # Handle simple dot notation
            if not any(char in field_path for char in ['[', ']', '*', '?', '@']):
                # Simple dot notation - traverse manually for better error messages
                current = data
                path_parts = field_path.split('.')
                
                for i, part in enumerate(path_parts):
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        # Return None for missing paths
                        return None
                
                return current
            
            # Use JSONPath for complex expressions
            jsonpath_expr = jsonpath_ext_parse(f'$.{field_path}')
            matches = [match.value for match in jsonpath_expr.find(data)]
            
            if not matches:
                return None
            elif len(matches) == 1:
                return matches[0]
            else:
                return matches
                
        except Exception as e:
            logger.warning(f"JSONPath extraction failed for '{field_path}': {e}")
            return None
    
    # Validation operator implementations
    
    def _validate_equals(self, actual: Any, expected: Any, criterion: ValidationCriterion) -> tuple[bool, str]:
        """Validate that actual equals expected"""
        if actual == expected:
            return True, ""
        return False, f"Expected {expected}, got {actual}"
    
    def _validate_not_equals(self, actual: Any, expected: Any, criterion: ValidationCriterion) -> tuple[bool, str]:
        """Validate that actual does not equal expected"""
        if actual != expected:
            return True, ""
        return False, f"Expected not {expected}, but got {actual}"
    
    def _validate_contains(self, actual: Any, expected: Any, criterion: ValidationCriterion) -> tuple[bool, str]:
        """Validate that actual contains expected"""
        try:
            if hasattr(actual, '__contains__') and expected in actual:
                return True, ""
            return False, f"Expected {actual} to contain {expected}"
        except TypeError:
            return False, f"Cannot check if {type(actual)} contains {expected}"
    
    def _validate_not_contains(self, actual: Any, expected: Any, criterion: ValidationCriterion) -> tuple[bool, str]:
        """Validate that actual does not contain expected"""
        try:
            if hasattr(actual, '__contains__') and expected not in actual:
                return True, ""
            return False, f"Expected {actual} to not contain {expected}"
        except TypeError:
            return False, f"Cannot check if {type(actual)} contains {expected}"
    
    def _validate_has_key(self, actual: Any, expected: Any, criterion: ValidationCriterion) -> tuple[bool, str]:
        """Validate that actual (dict) has the expected key"""
        if isinstance(actual, dict):
            if expected and expected in actual:
                return True, ""
            elif not expected:
                # If expected is None, just check that actual is a non-empty dict
                return len(actual) > 0, f"Expected non-empty dict, got {actual}"
            return False, f"Key '{expected}' not found in {list(actual.keys())}"
        
        # For the special case where we just want to check if the field path exists
        if expected is None and actual is not None:
            return True, ""
        
        return False, f"Expected dict with key '{expected}', got {type(actual)}"
    
    def _validate_not_has_key(self, actual: Any, expected: Any, criterion: ValidationCriterion) -> tuple[bool, str]:
        """Validate that actual (dict) does not have the expected key"""
        if isinstance(actual, dict):
            if expected not in actual:
                return True, ""
            return False, f"Key '{expected}' found in dict when it should not be"
        return True, ""  # Non-dicts don't have keys
    
    def _validate_greater_than(self, actual: Any, expected: Any, criterion: ValidationCriterion) -> tuple[bool, str]:
        """Validate that actual is greater than expected"""
        try:
            if actual > expected:
                return True, ""
            return False, f"Expected {actual} > {expected}"
        except TypeError:
            return False, f"Cannot compare {type(actual)} with {type(expected)}"
    
    def _validate_less_than(self, actual: Any, expected: Any, criterion: ValidationCriterion) -> tuple[bool, str]:
        """Validate that actual is less than expected"""
        try:
            if actual < expected:
                return True, ""
            return False, f"Expected {actual} < {expected}"
        except TypeError:
            return False, f"Cannot compare {type(actual)} with {type(expected)}"
    
    def _validate_length_equals(self, actual: Any, expected: Any, criterion: ValidationCriterion) -> tuple[bool, str]:
        """Validate that length of actual equals expected"""
        try:
            actual_length = len(actual) if actual is not None else 0
            if actual_length == expected:
                return True, ""
            return False, f"Expected length {expected}, got {actual_length}"
        except TypeError:
            return False, f"Cannot get length of {type(actual)}"
    
    def _validate_length_greater_than(self, actual: Any, expected: Any, criterion: ValidationCriterion) -> tuple[bool, str]:
        """Validate that length of actual is greater than expected"""
        try:
            actual_length = len(actual) if actual is not None else 0
            if actual_length > expected:
                return True, ""
            return False, f"Expected length > {expected}, got {actual_length}"
        except TypeError:
            return False, f"Cannot get length of {type(actual)}"
    
    def _validate_length_less_than(self, actual: Any, expected: Any, criterion: ValidationCriterion) -> tuple[bool, str]:
        """Validate that length of actual is less than expected"""
        try:
            actual_length = len(actual) if actual is not None else 0
            if actual_length < expected:
                return True, ""
            return False, f"Expected length < {expected}, got {actual_length}"
        except TypeError:
            return False, f"Cannot get length of {type(actual)}"
    
    def _validate_regex_match(self, actual: Any, expected: Any, criterion: ValidationCriterion) -> tuple[bool, str]:
        """Validate that actual matches the expected regex pattern"""
        if not isinstance(expected, str):
            return False, "Regex pattern must be a string"
        
        try:
            actual_str = str(actual) if actual is not None else ""
            if re.search(expected, actual_str):
                return True, ""
            return False, f"'{actual_str}' does not match pattern '{expected}'"
        except re.error as e:
            return False, f"Invalid regex pattern '{expected}': {e}"
    
    def _validate_in_list(self, actual: Any, expected: Any, criterion: ValidationCriterion) -> tuple[bool, str]:
        """Validate that actual is in expected list"""
        if not isinstance(expected, (list, tuple, set)):
            return False, "Expected value must be a list/tuple/set for 'in_list' validation"
        
        if actual in expected:
            return True, ""
        return False, f"Expected {actual} to be in {expected}"
    
    def _validate_not_in_list(self, actual: Any, expected: Any, criterion: ValidationCriterion) -> tuple[bool, str]:
        """Validate that actual is not in expected list"""
        if not isinstance(expected, (list, tuple, set)):
            return False, "Expected value must be a list/tuple/set for 'not_in_list' validation"
        
        if actual not in expected:
            return True, ""
        return False, f"Expected {actual} to not be in {expected}"
    
    def _validate_is_empty(self, actual: Any, expected: Any, criterion: ValidationCriterion) -> tuple[bool, str]:
        """Validate that actual is empty"""
        if actual is None or actual == "" or (hasattr(actual, '__len__') and len(actual) == 0):
            return True, ""
        return False, f"Expected empty value, got {actual}"
    
    def _validate_is_not_empty(self, actual: Any, expected: Any, criterion: ValidationCriterion) -> tuple[bool, str]:
        """Validate that actual is not empty"""
        if actual is not None and actual != "" and (not hasattr(actual, '__len__') or len(actual) > 0):
            return True, ""
        return False, f"Expected non-empty value, got {actual}"
    
    def _validate_custom(self, actual: Any, expected: Any, criterion: ValidationCriterion) -> tuple[bool, str]:
        """Validate using custom validation function"""
        if not criterion.custom_validator:
            return False, "No custom validator function provided"
        
        try:
            result = criterion.custom_validator(actual)
            if result:
                return True, ""
            return False, f"Custom validation failed for value: {actual}"
        except Exception as e:
            return False, f"Custom validation error: {str(e)}"


# Utility functions for common validation patterns

def create_response_structure_validator(required_keys: List[str]) -> ValidationCriterion:
    """Create a custom validator that checks if response has required structure"""
    def validator(response_data: Dict[str, Any]) -> bool:
        try:
            for key_path in required_keys:
                current = response_data
                for key in key_path.split('.'):
                    if not isinstance(current, dict) or key not in current:
                        return False
                    current = current[key]
            return True
        except Exception:
            return False
    
    return ValidationCriterion(
        field_path="",  # We're validating the whole response
        operator=ValidationOperator.CUSTOM,
        custom_validator=validator,
        description=f"Response should have required structure: {required_keys}"
    )


def create_field_type_validator(field_path: str, expected_type: type) -> ValidationCriterion:
    """Create a validator that checks field type"""
    def validator(actual_value: Any) -> bool:
        return isinstance(actual_value, expected_type)
    
    return ValidationCriterion(
        field_path=field_path,
        operator=ValidationOperator.CUSTOM,
        custom_validator=validator,
        description=f"Field {field_path} should be of type {expected_type.__name__}"
    )