"""
Data models for integration testing framework

Defines the structure of test cases, validation criteria, and test results
for comprehensive endpoint testing with authorization.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union, Callable
from enum import Enum
import json


class ValidationOperator(Enum):
    """Operators for validation criteria"""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    HAS_KEY = "has_key"
    NOT_HAS_KEY = "not_has_key"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    LENGTH_EQUALS = "length_equals"
    LENGTH_GREATER_THAN = "length_greater_than"
    LENGTH_LESS_THAN = "length_less_than"
    REGEX_MATCH = "regex_match"
    IN_LIST = "in_list"
    NOT_IN_LIST = "not_in_list"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"
    CUSTOM = "custom"


class TestPriority(Enum):
    """Test priority levels"""
    CRITICAL = "critical"
    HIGH = "high" 
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ValidationCriterion:
    """A single validation criterion for testing responses"""
    field_path: str  # JSONPath-style path like "data.parameters.filters"
    operator: ValidationOperator
    expected_value: Any = None
    description: str = ""
    custom_validator: Optional[Callable[[Any], bool]] = None
    
    def __post_init__(self):
        if self.operator == ValidationOperator.CUSTOM and not self.custom_validator:
            raise ValueError("Custom validator function required when using CUSTOM operator")
        if not self.description:
            self.description = f"{self.field_path} {self.operator.value} {self.expected_value}"


@dataclass 
class AuthConfig:
    """Authentication configuration for test requests"""
    bearer_token: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get headers with authorization"""
        auth_headers = self.headers.copy()
        if self.bearer_token:
            auth_headers["Authorization"] = f"Bearer {self.bearer_token}"
        return auth_headers


@dataclass
class TestRequest:
    """Test request configuration"""
    endpoint: str = "/api/v1/query"
    method: str = "POST"
    data: Dict[str, Any] = field(default_factory=dict)
    query_params: Dict[str, str] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "endpoint": self.endpoint,
            "method": self.method,
            "data": self.data,
            "query_params": self.query_params,
            "headers": self.headers,
            "timeout": self.timeout
        }


@dataclass
class ValidationResult:
    """Result of a single validation criterion"""
    criterion: ValidationCriterion
    passed: bool
    actual_value: Any = None
    error_message: str = ""
    execution_time_ms: float = 0.0


@dataclass
class TestResult:
    """Result of a complete test case execution"""
    test_case_id: str
    passed: bool
    execution_time_ms: float
    response_status: int
    response_data: Dict[str, Any] = field(default_factory=dict)
    validation_results: List[ValidationResult] = field(default_factory=list)
    error_message: str = ""
    debug_session_id: Optional[str] = None
    debug_log_url: Optional[str] = None
    
    def get_failed_validations(self) -> List[ValidationResult]:
        """Get list of failed validation results"""
        return [vr for vr in self.validation_results if not vr.passed]
    
    def get_success_rate(self) -> float:
        """Get percentage of validations that passed"""
        if not self.validation_results:
            return 100.0
        passed_count = sum(1 for vr in self.validation_results if vr.passed)
        return (passed_count / len(self.validation_results)) * 100


@dataclass
class TestCase:
    """Complete test case definition"""
    test_id: str
    name: str
    description: str
    request: TestRequest
    auth_config: AuthConfig
    validations: List[ValidationCriterion] = field(default_factory=list)
    priority: TestPriority = TestPriority.MEDIUM
    enabled: bool = True
    tags: List[str] = field(default_factory=list)
    setup_hooks: List[Callable] = field(default_factory=list)
    teardown_hooks: List[Callable] = field(default_factory=list)
    expected_debug_interactions: int = 0  # Expected number of LLM interactions
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "test_id": self.test_id,
            "name": self.name,
            "description": self.description,
            "request": self.request.to_dict(),
            "auth_config": {
                "bearer_token": self.auth_config.bearer_token,
                "headers": self.auth_config.headers
            },
            "validations": [
                {
                    "field_path": v.field_path,
                    "operator": v.operator.value,
                    "expected_value": v.expected_value,
                    "description": v.description
                }
                for v in self.validations
            ],
            "priority": self.priority.value,
            "enabled": self.enabled,
            "tags": self.tags,
            "expected_debug_interactions": self.expected_debug_interactions
        }


@dataclass
class TestSuite:
    """Collection of test cases with execution configuration"""
    suite_id: str
    name: str
    description: str
    test_cases: List[TestCase] = field(default_factory=list)
    base_url: str = "http://localhost:8080"
    global_auth: Optional[AuthConfig] = None
    parallel_execution: bool = False
    max_workers: int = 4
    continue_on_failure: bool = True
    
    def add_test_case(self, test_case: TestCase) -> None:
        """Add a test case to the suite"""
        self.test_cases.append(test_case)
    
    def get_test_case(self, test_id: str) -> Optional[TestCase]:
        """Get a test case by ID"""
        for test_case in self.test_cases:
            if test_case.test_id == test_id:
                return test_case
        return None
    
    def filter_by_tags(self, tags: List[str]) -> List[TestCase]:
        """Filter test cases by tags"""
        return [tc for tc in self.test_cases if any(tag in tc.tags for tag in tags)]
    
    def filter_by_priority(self, min_priority: TestPriority) -> List[TestCase]:
        """Filter test cases by minimum priority"""
        priority_order = {
            TestPriority.LOW: 0,
            TestPriority.MEDIUM: 1,
            TestPriority.HIGH: 2,
            TestPriority.CRITICAL: 3
        }
        min_level = priority_order[min_priority]
        return [tc for tc in self.test_cases if priority_order[tc.priority] >= min_level]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "suite_id": self.suite_id,
            "name": self.name,
            "description": self.description,
            "test_cases": [tc.to_dict() for tc in self.test_cases],
            "base_url": self.base_url,
            "global_auth": self.global_auth.get_auth_headers() if self.global_auth else None,
            "parallel_execution": self.parallel_execution,
            "max_workers": self.max_workers,
            "continue_on_failure": self.continue_on_failure
        }


@dataclass
class TestSuiteResult:
    """Results from executing a complete test suite"""
    suite_id: str
    execution_start_time: str
    execution_end_time: str
    total_execution_time_ms: float
    test_results: List[TestResult] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate summary statistics"""
        if self.test_results:
            total_tests = len(self.test_results)
            passed_tests = sum(1 for tr in self.test_results if tr.passed)
            failed_tests = total_tests - passed_tests
            
            total_validations = sum(len(tr.validation_results) for tr in self.test_results)
            passed_validations = sum(
                len([vr for vr in tr.validation_results if vr.passed])
                for tr in self.test_results
            )
            failed_validations = total_validations - passed_validations
            
            self.summary = {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "test_pass_rate": (passed_tests / total_tests) * 100 if total_tests > 0 else 0,
                "total_validations": total_validations,
                "passed_validations": passed_validations,
                "failed_validations": failed_validations,
                "validation_pass_rate": (passed_validations / total_validations) * 100 if total_validations > 0 else 0,
                "avg_execution_time_ms": sum(tr.execution_time_ms for tr in self.test_results) / total_tests if total_tests > 0 else 0,
                "debug_sessions_created": sum(1 for tr in self.test_results if tr.debug_session_id)
            }
    
    def get_failed_tests(self) -> List[TestResult]:
        """Get list of failed test results"""
        return [tr for tr in self.test_results if not tr.passed]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "suite_id": self.suite_id,
            "execution_start_time": self.execution_start_time,
            "execution_end_time": self.execution_end_time,
            "total_execution_time_ms": self.total_execution_time_ms,
            "summary": self.summary,
            "test_results": [
                {
                    "test_case_id": tr.test_case_id,
                    "passed": tr.passed,
                    "execution_time_ms": tr.execution_time_ms,
                    "response_status": tr.response_status,
                    "validation_results": [
                        {
                            "description": vr.criterion.description,
                            "passed": vr.passed,
                            "actual_value": vr.actual_value,
                            "error_message": vr.error_message
                        }
                        for vr in tr.validation_results
                    ],
                    "error_message": tr.error_message,
                    "debug_session_id": tr.debug_session_id,
                    "debug_log_url": tr.debug_log_url
                }
                for tr in self.test_results
            ]
        }


# Helper functions for common validation patterns

def create_field_filter_validation(field_name: str, expected_value: Any) -> ValidationCriterion:
    """Create validation for checking if a field filter has the expected value"""
    return ValidationCriterion(
        field_path=f"data.parameters.filters['{field_name}']",
        operator=ValidationOperator.EQUALS,
        expected_value=expected_value,
        description=f"Filter {field_name} should equal {expected_value}"
    )


def create_explore_key_validation(expected_explore: str) -> ValidationCriterion:
    """Create validation for checking the explore_key"""
    return ValidationCriterion(
        field_path="data.explore_key",
        operator=ValidationOperator.EQUALS,
        expected_value=expected_explore,
        description=f"Explore key should be {expected_explore}"
    )


def create_fields_contain_validation(expected_fields: List[str]) -> ValidationCriterion:
    """Create validation for checking if response contains specific fields"""
    def custom_validator(actual_fields: List[str]) -> bool:
        return all(field in actual_fields for field in expected_fields)
    
    return ValidationCriterion(
        field_path="data.parameters.fields",
        operator=ValidationOperator.CUSTOM,
        expected_value=expected_fields,
        custom_validator=custom_validator,
        description=f"Response should contain all fields: {expected_fields}"
    )


def create_debug_info_validation() -> ValidationCriterion:
    """Create validation for checking debug info presence"""
    return ValidationCriterion(
        field_path="debug_info",
        operator=ValidationOperator.HAS_KEY,
        description="Response should include debug_info when debug=True"
    )


def create_success_validation() -> ValidationCriterion:
    """Create validation for checking successful response"""
    return ValidationCriterion(
        field_path="success",
        operator=ValidationOperator.EQUALS,
        expected_value=True,
        description="Response should indicate success"
    )