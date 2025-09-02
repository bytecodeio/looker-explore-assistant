# Integration Testing Framework - Usage Examples

## Quick Start Commands

### 1. Verify Framework Installation
```bash
cd tests/
python3 verify_framework.py
```

### 2. Basic Test Execution

```bash
# Get your bearer token (using gcloud)
export BEARER_TOKEN=$(gcloud auth print-identity-token)

# Run comprehensive test suite
python3 run_integration_tests.py --token "$BEARER_TOKEN" --suite comprehensive --verbose

# Run quick validation suite  
python3 run_integration_tests.py --token "$BEARER_TOKEN" --suite quick --parallel

# Test against custom URL
python3 run_integration_tests.py --token "$BEARER_TOKEN" --url "https://your-api.example.com" --suite comprehensive

# Save results to file
python3 run_integration_tests.py --token "$BEARER_TOKEN" --output results.json --verbose
```

### 3. Configuration File Usage

```bash
# Create custom config (edit integration_tests/example_config.json)
cp integration_tests/example_config.json my_config.json
# Edit my_config.json with your settings

# Run with config file
python3 run_integration_tests.py --config my_config.json --output results.json
```

## Expected Output

### Successful Test Run
```
🚀 Starting test suite: Comprehensive Integration Test Suite
📊 Executing 4 enabled test cases
🔍 Running test: Product SKU Filter Validation
✅ Product SKU Filter Validation: 200 (1250.3ms)
🐛 Debug log: /api/v1/debug/logs/debug_abc123def456
🔍 Running test: Basic Query Processing
✅ Basic Query Processing: 200 (980.2ms)
🔍 Running test: Debug Mode Functionality
✅ Debug Mode Functionality: 200 (1100.5ms)
🔍 Running test: Invalid Explore Handling
✅ Invalid Explore Handling: 400 (750.1ms)

🎯 Test Suite Results: comprehensive_integration_tests
   Total Tests: 4
   ✅ Passed: 4
   ❌ Failed: 0
   📊 Pass Rate: 100.0%
   ⏱️  Avg Time: 1020.3ms
   🐛 Debug Sessions: 4
```

### Failed Test (Product SKU Bug Detection)
```
❌ Product SKU Filter Validation: 200 (1250.3ms)
🐛 Debug log: /api/v1/debug/logs/debug_abc123def456
❌ Failed validations for product_sku_filter_test:
   • Filter products.sku should equal 0006AABE0BA47A35C0B0BF6596F85159: Expected 0006AABE0BA47A35C0B0BF6596F85159, got None
```

## Test Case Breakdown

### 1. Product SKU Filter Test (`product_sku_filter_test`)
**Purpose**: Detects the specific bug you mentioned where vector search finds a SKU but the filter isn't generated.

**Query**: `"tell me about sales 0006AABE0BA47A35C0B0BF6596F85159"`

**Validations**:
- ✅ Response is successful
- ✅ Correct explore key selected
- ❌ **Filter `products.sku = "0006AABE0BA47A35C0B0BF6596F85159"` is present** (this will fail if bug exists)
- ✅ Debug info is included
- ✅ Vector search was used

**Expected Failure**: If the bug exists, this test will pass all validations except the filter validation, clearly identifying the issue.

### 2. Basic Query Test (`basic_query_test`)
Tests general query processing without specific entity references.

### 3. Debug Mode Test (`debug_mode_validation`) 
Validates that debug mode logging works correctly.

### 4. Error Handling Test (`invalid_explore_test`)
Tests proper error responses for irrelevant queries.

## Programmatic Usage

```python
from integration_tests import TestRunner, create_product_sku_test_case

# Create specific test for your bug
test_case = create_product_sku_test_case("your-bearer-token")

# Run test
runner = TestRunner("http://localhost:8080")
result = runner.run_single_test(test_case)

# Check results
if not result.passed:
    print("❌ Product SKU bug detected!")
    print(f"Debug log: {result.debug_log_url}")
    
    # Show specific failures
    for validation in result.get_failed_validations():
        if "products.sku" in validation.criterion.description:
            print(f"   • Missing filter: {validation.error_message}")
            print(f"   • Expected: {validation.criterion.expected_value}")
            print(f"   • Actual: {validation.actual_value}")
```

## Debug Log Analysis

When tests fail, you get debug log URLs like:
`/api/v1/debug/logs/debug_abc123def456`

Access these to see:
- **LLM Interactions**: Full request/response data for AI calls
- **Processing Steps**: Step-by-step pipeline execution
- **Vector Search Results**: What the system found vs. what it used
- **Parameter Generation**: How the AI converted context to parameters

## Custom Test Cases

```python
from integration_tests import TestCaseBuilder, ValidationOperator

# Create custom test for your specific scenario
custom_test = (TestCaseBuilder("my_bug_test", "My Bug Detection")
    .with_query("your problematic query here")
    .with_restricted_explores(["your:explore"])
    .with_auth_token("your-token")
    .expect_success()
    .expect_field_filter("your.field", "expected_value")
    .expect_custom(
        "data.generation_metadata.vector_search_used",
        ValidationOperator.LENGTH_GREATER_THAN, 
        0,
        "Should use vector search"
    )
    .build())
```

## Troubleshooting

### Import Errors
```bash
# Install dependencies
cd tests/
pip install -r requirements.txt
```

### Authentication Issues
```bash
# Check token is valid
curl -H "Authorization: Bearer $BEARER_TOKEN" http://localhost:8080/api/v1/health
```

### Backend Not Running
```bash
# Start backend (from project root)
python app.py
# or
gunicorn --bind 0.0.0.0:8080 restful_backend:app
```

### Test Failures
- Check the debug log URLs provided in test results
- Use `--verbose` flag for detailed logging
- Verify your bearer token has proper permissions
- Ensure backend is running and accessible

## Extending the Framework

### Add New Validation Operators
Edit `integration_tests/validator.py` to add new validation logic.

### Add New Test Cases  
Edit `integration_tests/test_cases.py` to add domain-specific tests.

### Custom Test Suites
Create your own test suite functions for specific testing scenarios.

This framework gives you comprehensive testing capabilities with detailed debugging information to identify and fix issues in your REST API endpoints.