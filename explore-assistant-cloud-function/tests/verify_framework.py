#!/usr/bin/env python3
"""
Verification script to test that the integration testing framework works correctly

This script validates the framework components without making actual API calls.
"""

import json
from integration_tests import (
    TestCaseBuilder, TestPriority, ValidationOperator,
    ValidationEngine, ValidationCriterion,
    create_product_sku_test_case, create_comprehensive_test_suite
)


def test_validation_engine():
    """Test the validation engine with sample data"""
    print("🔍 Testing Validation Engine...")
    
    engine = ValidationEngine()
    
    # Sample response data
    sample_response = {
        "success": True,
        "data": {
            "explore_key": "sales_demo_the_look:order_items",
            "parameters": {
                "filters": {
                    "products.sku": "0006AABE0BA47A35C0B0BF6596F85159"
                },
                "fields": ["order_items.order_id", "order_items.sale_price"]
            }
        },
        "debug_info": {
            "session_id": "debug_123",
            "llm_interactions_count": 2
        }
    }
    
    # Test various validations
    validations = [
        ValidationCriterion("success", ValidationOperator.EQUALS, True),
        ValidationCriterion("data.explore_key", ValidationOperator.EQUALS, "sales_demo_the_look:order_items"),
        ValidationCriterion("data.parameters.filters['products.sku']", ValidationOperator.EQUALS, "0006AABE0BA47A35C0B0BF6596F85159"),
        ValidationCriterion("debug_info", ValidationOperator.HAS_KEY, None),
        ValidationCriterion("data.parameters.fields", ValidationOperator.LENGTH_GREATER_THAN, 0)
    ]
    
    results = engine.validate_response(sample_response, validations)
    
    all_passed = all(result.passed for result in results)
    print(f"   Validation Results: {'✅ All Passed' if all_passed else '❌ Some Failed'}")
    
    for result in results:
        status = "✅" if result.passed else "❌"
        print(f"   {status} {result.criterion.description}")
        if not result.passed:
            print(f"      Error: {result.error_message}")
    
    return all_passed


def test_test_case_builder():
    """Test the test case builder"""
    print("\n🔧 Testing Test Case Builder...")
    
    test_case = (TestCaseBuilder("test_builder", "Test Builder Validation")
        .with_description("Test the test case builder functionality")
        .with_query("show me sales data")
        .with_restricted_explores(["test:explore"])
        .with_auth_token("test-token")
        .with_priority(TestPriority.HIGH)
        .with_tags(["builder", "test"])
        .expect_success()
        .expect_explore_key("test:explore")
        .expect_debug_info()
        .build())
    
    print(f"   ✅ Test case created: {test_case.name}")
    print(f"   ✅ Query: {test_case.request.data['query']}")
    print(f"   ✅ Validations: {len(test_case.validations)}")
    print(f"   ✅ Priority: {test_case.priority.value}")
    
    return True


def test_sample_test_cases():
    """Test the pre-built sample test cases"""
    print("\n📝 Testing Sample Test Cases...")
    
    # Test product SKU test case
    sku_test = create_product_sku_test_case("test-token")
    print(f"   ✅ Product SKU test: {sku_test.name}")
    print(f"      Validations: {len(sku_test.validations)}")
    print(f"      Tags: {sku_test.tags}")
    
    # Test comprehensive suite
    suite = create_comprehensive_test_suite("test-token")
    print(f"   ✅ Comprehensive suite: {len(suite.test_cases)} test cases")
    
    # Show test case names
    for test_case in suite.test_cases:
        print(f"      - {test_case.name}")
    
    return True


def test_configuration_export():
    """Test configuration export/import"""
    print("\n📄 Testing Configuration Export...")
    
    suite = create_comprehensive_test_suite("test-token")
    
    # Export to dictionary
    config_dict = suite.to_dict()
    print(f"   ✅ Exported configuration: {len(config_dict)} keys")
    
    # Test JSON serialization
    json_str = json.dumps(config_dict, indent=2)
    print(f"   ✅ JSON serialization: {len(json_str)} characters")
    
    # Test deserialization
    parsed_config = json.loads(json_str)
    print(f"   ✅ JSON deserialization: {len(parsed_config)} keys")
    
    return True


def main():
    """Run all verification tests"""
    print("🚀 Integration Testing Framework Verification")
    print("=" * 50)
    
    tests = [
        ("Validation Engine", test_validation_engine),
        ("Test Case Builder", test_test_case_builder),
        ("Sample Test Cases", test_sample_test_cases),
        ("Configuration Export", test_configuration_export)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result, None))
        except Exception as e:
            results.append((test_name, False, str(e)))
    
    # Summary
    print("\n" + "=" * 50)
    print("🎯 Verification Summary:")
    
    all_passed = True
    for test_name, passed, error in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"   {status} {test_name}")
        if error:
            print(f"      Error: {error}")
        all_passed = all_passed and passed
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All verification tests passed! Framework is ready to use.")
        print("\nNext steps:")
        print("1. Set your bearer token: export BEARER_TOKEN='your-token-here'")
        print("2. Start your backend server: python app.py")
        print("3. Run tests: python run_integration_tests.py --token \"$BEARER_TOKEN\"")
    else:
        print("❌ Some verification tests failed. Please check the errors above.")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)