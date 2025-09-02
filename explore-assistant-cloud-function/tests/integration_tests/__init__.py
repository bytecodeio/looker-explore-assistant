"""
Integration testing framework for Looker Explore Assistant REST API

This framework provides comprehensive testing capabilities for API endpoints
with support for authorization, debug logging, and detailed validation.

Key Features:
- Extensible test case definition with validation criteria
- Authorization support with Bearer tokens
- Debug mode integration for LLM interaction logging
- Parallel and sequential test execution
- Comprehensive result reporting with debug URLs

Usage:
    from tests.integration_tests import TestRunner, create_comprehensive_test_suite
    
    # Create test suite
    suite = create_comprehensive_test_suite("your-bearer-token")
    
    # Run tests
    runner = TestRunner("http://localhost:8080")
    results = runner.run_test_suite(suite)
    
    # Check results
    print(f"Tests passed: {results.summary['test_pass_rate']:.1f}%")
"""

from .models import (
    TestCase, TestSuite, TestRequest, AuthConfig, ValidationCriterion,
    TestResult, TestSuiteResult, ValidationResult, TestPriority, ValidationOperator,
    create_field_filter_validation, create_explore_key_validation,
    create_fields_contain_validation, create_debug_info_validation,
    create_success_validation
)

from .validator import ValidationEngine, create_response_structure_validator, create_field_type_validator

from .runner import TestRunner, create_auth_config, run_test_file

from .test_cases import (
    TestCaseBuilder, create_product_sku_test_case, create_basic_query_test_case,
    create_debug_mode_test_case, create_invalid_explore_test_case,
    create_comprehensive_test_suite, create_quick_validation_suite,
    save_test_suite_to_file, load_test_suite_from_file
)

from .template_loader import (
    load_golden_queries_template, TemplateLoadError,
    get_template_statistics, validate_template_integrity,
    clear_template_cache
)

__version__ = "1.0.0"
__all__ = [
    # Models
    "TestCase", "TestSuite", "TestRequest", "AuthConfig", "ValidationCriterion",
    "TestResult", "TestSuiteResult", "ValidationResult", "TestPriority", "ValidationOperator",
    
    # Model helpers
    "create_field_filter_validation", "create_explore_key_validation",
    "create_fields_contain_validation", "create_debug_info_validation",
    "create_success_validation",
    
    # Validator
    "ValidationEngine", "create_response_structure_validator", "create_field_type_validator",
    
    # Runner
    "TestRunner", "create_auth_config", "run_test_file",
    
    # Test cases
    "TestCaseBuilder", "create_product_sku_test_case", "create_basic_query_test_case",
    "create_debug_mode_test_case", "create_invalid_explore_test_case",
    "create_comprehensive_test_suite", "create_quick_validation_suite",
    "save_test_suite_to_file", "load_test_suite_from_file",
    
    # Template loader
    "load_golden_queries_template", "TemplateLoadError",
    "get_template_statistics", "validate_template_integrity",
    "clear_template_cache"
]