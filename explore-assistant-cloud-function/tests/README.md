# Integration Testing Framework

Comprehensive integration testing framework for the Looker Explore Assistant REST API, providing extensive validation capabilities, debug logging integration, and authorization support.

## Features

- 🔐 **Authorization Support**: API key authentication with X-API-Key header
- 🐛 **Debug Mode Integration**: Automatic debug logging with LLM interaction tracking
- ✅ **Comprehensive Validation**: JSONPath-based field validation with multiple operators
- 🚀 **Parallel Execution**: Support for both sequential and parallel test execution
- 📊 **Detailed Reporting**: Rich test results with debug URLs and execution metrics
- 🔧 **Extensible Framework**: Easy to add new test cases and validation patterns
- 🏆 **Golden Queries Template**: Automatic inclusion of required golden queries from production data

## Quick Start

### 1. Install Dependencies

```bash
cd tests/
pip install -r requirements.txt
```

### 2. Verify Golden Queries Template

The framework automatically includes golden queries (required by the backend) from a template file extracted from production data:

```bash
python3 -c "from integration_tests import validate_template_integrity; print(validate_template_integrity())"
```

### 2. Run Tests

#### Using Command Line

```bash
# Run comprehensive test suite
python run_integration_tests.py --api-key "your-api-key" --suite comprehensive

# Run quick validation suite
python run_integration_tests.py --api-key "your-api-key" --suite quick --parallel

# Custom API URL
python run_integration_tests.py --api-key "your-api-key" --url "https://api.example.com" --suite comprehensive

# Save results to file
python run_integration_tests.py --api-key "your-api-key" --output results.json --verbose

# Use API key from environment variable
export API_SECRET_KEY="your-api-key"
python run_integration_tests.py --api-key "$API_SECRET_KEY" --suite quick
```

#### Using Configuration File

```bash
python run_integration_tests.py --config integration_tests/example_config.json --output results.json
```

#### Programmatic Usage

```python
from tests.integration_tests import TestRunner, create_comprehensive_test_suite

# Create test suite
suite = create_comprehensive_test_suite("your-api-key", "http://localhost:8080")

# Run tests
runner = TestRunner()
results = runner.run_test_suite(suite)

# Check results
print(f"Pass rate: {results.summary['test_pass_rate']:.1f}%")
for failed_test in results.get_failed_tests():
    print(f"Failed: {failed_test.test_case_id}")
    if failed_test.debug_log_url:
        print(f"Debug log: {failed_test.debug_log_url}")
```

## Test Cases

### Built-in Test Cases

#### 1. Product SKU Filter Validation (`product_sku_filter_test`)
- **Purpose**: Tests that queries mentioning specific product SKUs result in proper filter generation
- **Example**: `"tell me about sales 0006AABE0BA47A35C0B0BF6596F85159"`
- **Validates**: 
  - Correct explore selection
  - Proper SKU filter generation (`products.sku = "0006AABE0BA47A35C0B0BF6596F85159"`)
  - Vector search utilization
  - Debug logging presence

#### 2. Basic Query Processing (`basic_query_test`)
- **Purpose**: Tests basic query processing without specific entity references
- **Example**: `"show me sales data for the last month"`
- **Validates**:
  - Successful query processing
  - Field selection
  - Basic parameter generation

#### 3. Debug Mode Functionality (`debug_mode_validation`)
- **Purpose**: Validates debug mode provides comprehensive logging
- **Validates**:
  - Debug info presence
  - LLM interaction logging
  - Processing step tracking
  - Debug log URL generation

#### 4. Error Handling (`invalid_explore_test`)
- **Purpose**: Tests error handling for irrelevant queries
- **Example**: `"tell me about quantum mechanics"`
- **Validates**:
  - Proper error responses
  - Debug information in error cases

## Creating Custom Test Cases

### Using TestCaseBuilder

```python
from tests.integration_tests import TestCaseBuilder, TestPriority, ValidationOperator

test_case = (TestCaseBuilder("my_test", "My Custom Test")
    .with_description("Test custom functionality")
    .with_query("my custom query")
    .with_api_key("your-api-key")
    .with_priority(TestPriority.HIGH)
    .with_tags(["custom", "validation"])
    .expect_success()
    .expect_explore_key("my_model:my_explore")
    .expect_field_filter("my_field", "expected_value")
    .expect_debug_info()
    .expect_custom(
        "data.parameters.fields",
        ValidationOperator.LENGTH_GREATER_THAN,
        0,
        "Should include fields"
    )
    .build())
```

### Validation Criteria

The framework supports comprehensive validation with multiple operators:

```python
# Basic comparisons
ValidationOperator.EQUALS
ValidationOperator.NOT_EQUALS
ValidationOperator.GREATER_THAN
ValidationOperator.LESS_THAN

# Container operations
ValidationOperator.CONTAINS
ValidationOperator.NOT_CONTAINS
ValidationOperator.IN_LIST
ValidationOperator.NOT_IN_LIST

# Structure validation
ValidationOperator.HAS_KEY
ValidationOperator.NOT_HAS_KEY
ValidationOperator.LENGTH_EQUALS
ValidationOperator.LENGTH_GREATER_THAN

# Pattern matching
ValidationOperator.REGEX_MATCH

# State checks
ValidationOperator.IS_EMPTY
ValidationOperator.IS_NOT_EMPTY

# Custom validation
ValidationOperator.CUSTOM  # With custom_validator function
```

### JSONPath Field Selection

Use JSONPath expressions to validate nested response data:

```python
# Simple paths
"data.explore_key"
"data.parameters.filters.field_name"

# Complex paths
"data.generation_metadata.vector_search_used[*].function"
"debug_info.llm_interactions_count"
```

## Response Structure

The testing framework validates responses with debug mode enabled:

```json
{
  "success": true,
  "data": {
    "explore_key": "sales_demo_the_look:order_items",
    "parameters": {
      "model": "sales_demo_the_look",
      "view": "order_items",
      "fields": ["order_items.order_id", "order_items.sale_price"],
      "filters": {
        "products.sku": "0006AABE0BA47A35C0B0BF6596F85159"
      },
      "sorts": ["order_items.created_date desc"],
      "limit": 500
    },
    "generation_metadata": {
      "model_used": "gemini-2.0-flash-001",
      "vector_search_used": [...],
      "vector_search_summary": {...},
      "generation_method": "vector_search_enhanced"
    }
  },
  "debug_info": {
    "session_id": "debug_abc123def456",
    "debug_log_url": "/api/v1/debug/logs/debug_abc123def456",
    "llm_interactions_count": 2,
    "processing_steps_count": 6,
    "verbose_details": {...}
  },
  "processing_time_ms": 1250.3,
  "timestamp": "2025-08-29T19:15:44.903787"
}
```

## Debug Integration

The framework automatically enables debug mode and captures:

- **LLM Interactions**: Full request/response data for all AI calls
- **Processing Steps**: Detailed pipeline execution tracking  
- **Performance Metrics**: Timing information for each step
- **Debug URLs**: Links to detailed debug logs for failed tests

Example debug log access:
```python
for test_result in results.test_results:
    if test_result.debug_session_id:
        print(f"Debug log: {test_result.debug_log_url}")
        # Access via: GET /api/v1/debug/logs/{debug_session_id}
```

## Configuration File Format

Create custom test configurations with JSON:

```json
{
  "suite_id": "custom_suite",
  "name": "Custom Test Suite",
  "base_url": "http://localhost:8080",
  "parallel_execution": false,
  "continue_on_failure": true,

  "auth": {
    "api_key": "your-api-key",
    "headers": {"User-Agent": "TestSuite/1.0"}
  },
  
  "test_cases": [
    {
      "test_id": "my_test",
      "name": "My Test Case",
      "request": {
        "endpoint": "/api/v1/query",
        "method": "POST",
        "data": {
          "query": "test query",
          "debug": true
        }
      },
      "validations": [
        {
          "field_path": "success",
          "operator": "equals",
          "expected_value": true,
          "description": "Should be successful"
        }
      ]
    }
  ]
}
```

## Command Line Options

```bash
python run_integration_tests.py [OPTIONS]

Options:
  -k, --api-key TEXT     API key for authentication
  -u, --url TEXT         API base URL (default: http://localhost:8080)
  -s, --suite CHOICE     Test suite: comprehensive|quick (default: comprehensive)
  -c, --config PATH      JSON configuration file
  -o, --output PATH      Save results as JSON
  --log-file PATH        Save detailed logs to file
  --parallel             Run tests in parallel
  -v, --verbose          Enable verbose logging
  --save-config PATH     Save test suite config to file
```

## Result Analysis

Test results include comprehensive metrics:

```python
# Suite-level results
results.summary = {
    "total_tests": 4,
    "passed_tests": 3, 
    "failed_tests": 1,
    "test_pass_rate": 75.0,
    "total_validations": 15,
    "passed_validations": 12,
    "failed_validations": 3,
    "validation_pass_rate": 80.0,
    "avg_execution_time_ms": 1250.3,
    "debug_sessions_created": 4
}

# Individual test results
for test_result in results.test_results:
    print(f"Test: {test_result.test_case_id}")
    print(f"Passed: {test_result.passed}")
    print(f"Response Status: {test_result.response_status}")
    print(f"Execution Time: {test_result.execution_time_ms}ms")
    
    # Failed validations
    for failed_validation in test_result.get_failed_validations():
        print(f"  ❌ {failed_validation.criterion.description}")
        print(f"     {failed_validation.error_message}")
```

## Example: Product SKU Bug Detection

The framework can detect the specific bug mentioned in your example:

```python
# Test case that should pass but currently fails
test_case = create_product_sku_test_case("your-api-key")

# This validation will fail if the bug exists
validation = create_field_filter_validation(
    "products.sku", 
    "0006AABE0BA47A35C0B0BF6596F85159"
)

# The system finds the SKU in vector search but fails to add it as a filter
# Debug logs will show the vector search found the SKU but parameter 
# generation didn't include it in the filters
```

## Extending the Framework

### Custom Validators

```python
def custom_field_count_validator(actual_fields):
    """Custom validator for field count logic"""
    return len(actual_fields) >= 3 and 'order_id' in actual_fields

criterion = ValidationCriterion(
    field_path="data.parameters.fields",
    operator=ValidationOperator.CUSTOM,
    custom_validator=custom_field_count_validator,
    description="Should have at least 3 fields including order_id"
)
```

### Custom Test Suites

```python
def create_my_test_suite(api_key: str) -> TestSuite:
    suite = TestSuite(
        suite_id="my_custom_suite",
        name="My Custom Test Suite",
        base_url="http://localhost:8080",
        global_auth=AuthConfig(api_key=api_key)
    )

    # Add your custom test cases
    suite.add_test_case(my_custom_test_case())
    return suite
```

This framework provides everything needed to comprehensively test the REST API endpoints with authorization, debug logging, and detailed validation of complex response structures.