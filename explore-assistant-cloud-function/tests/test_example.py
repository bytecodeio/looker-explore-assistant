#!/usr/bin/env python3
"""
Example usage of the integration testing framework

This demonstrates how to use the framework to test the backend endpoint
with the specific product SKU case you mentioned.
"""

from integration_tests import (
    TestRunner, TestCaseBuilder, create_product_sku_test_case,
    create_comprehensive_test_suite, ValidationOperator
)


def main():
    # Your bearer token (replace with actual token)
    AUTH_TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6IjE0OTljMTU0Y2NjOGEyNWUyNGQ4ZGU4YjFhOWY4NDVhZWZiNmYzY2EiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL2FjY291bnRzLmdvb2dsZS5jb20iLCJhenAiOiIzMjU1NTk0MDU1OS5hcHBzLmdvb2dsZXVzZXJjb250ZW50LmNvbSIsImF1ZCI6IjMyNTU1OTQwNTU5LmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29tIiwic3ViIjoiMTEzMzU1MjQ0NTIyNzM5MTM0NTY3IiwiaGQiOiJieXRlY29kZS5pbyIsImVtYWlsIjoiY29saW4ucm95LmVocmlAYnl0ZWNvZGUuaW8iLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiYXRfaGFzaCI6ImpBckZTb3Q2NE5CY3o1d20tcHBMTlEiLCJpYXQiOjE3NTY0OTY3NTIsImV4cCI6MTc1NjUwMDM1Mn0.G6QFbFS1hbmeYqoEky21yQCry3vSzm9Ni_1bWOMOeqxl5kiF2lTWmWVFko66_zZG1lsaILVX03d8XgR-vrrqB81KTGV5LuevZ4O76cEe_jIacu9_87wawrJ1iAmy5-ccqYEr2GkWM_3yxTyJW-txV5DUQ4vaCzo0qdipiuGBSAcfXhLnLMN4usDw0S7vYd4MZcNAHb38BuHQpPtoVHZT45qNv-6-XJe-dExgrJCC6Ug50HADCDMJtpPLg16Jjp-QIkjIGh7RPCl4cZ48MsXAtiS4xYll0BVQs9fMF2ePlZ0YHpqB_gjeVkr7y_VxYb-xLyAJKPMm-28xJaQFyhAWaQ"
    BASE_URL = "https://ea-demo-backend-63299712962.us-central1.run.app"
    
    print("🚀 Integration Testing Framework Example")
    print("="*50)
    
    # Example 1: Single test case execution
    print("\n📝 Example 1: Single Product SKU Test")
    
    # Create the specific test case that should catch the bug you mentioned
    sku_test = create_product_sku_test_case(AUTH_TOKEN)
    
    # Run the single test
    runner = TestRunner(BASE_URL)
    result = runner.run_single_test(sku_test)
    
    print(f"Test Result: {'✅ PASSED' if result.passed else '❌ FAILED'}")
    print(f"Response Status: {result.response_status}")
    print(f"Execution Time: {result.execution_time_ms:.1f}ms")
    
    if result.debug_session_id:
        print(f"🐛 Debug Log Available: {result.debug_log_url}")
    
    # Show validation details
    print("\nValidation Results:")
    for validation in result.validation_results:
        status = "✅" if validation.passed else "❌"
        print(f"  {status} {validation.criterion.description}")
        if not validation.passed:
            print(f"      Error: {validation.error_message}")
            print(f"      Expected: {validation.criterion.expected_value}")
            print(f"      Actual: {validation.actual_value}")
    
    # Example 2: Custom test case
    print("\n📝 Example 2: Custom Test Case")
    
    # Build a custom test case
    custom_test = (TestCaseBuilder("custom_filter_test", "Custom Filter Validation")
        .with_description("Test that specific queries generate expected filters")
        .with_query("show me orders for product ABC123")
        .with_restricted_explores(["sales_demo_the_look:order_items"])
        .with_auth_token(AUTH_TOKEN)
        .expect_success()
        .expect_debug_info()
        .expect_custom(
            "data.parameters.filters",
            ValidationOperator.HAS_KEY,
            None,  # Just check that filters exist
            "Response should include filters"
        )
        .expect_custom(
            "data.parameters.fields",
            ValidationOperator.LENGTH_GREATER_THAN,
            0,
            "Should include at least one field"
        )
        .build())
    
    # Run the custom test
    custom_result = runner.run_single_test(custom_test)
    print(f"Custom Test Result: {'✅ PASSED' if custom_result.passed else '❌ FAILED'}")
    
    # Example 3: Full test suite
    print("\n📝 Example 3: Comprehensive Test Suite")
    
    # Create and run a full test suite
    test_suite = create_comprehensive_test_suite(AUTH_TOKEN, BASE_URL)
    print(f"Running {len(test_suite.test_cases)} test cases...")
    
    suite_results = runner.run_test_suite(test_suite)
    
    # Print summary
    summary = suite_results.summary
    print(f"\n🎯 Test Suite Results:")
    print(f"   Total Tests: {summary['total_tests']}")
    print(f"   ✅ Passed: {summary['passed_tests']}")
    print(f"   ❌ Failed: {summary['failed_tests']}")
    print(f"   📊 Pass Rate: {summary['test_pass_rate']:.1f}%")
    print(f"   ⏱️  Total Time: {suite_results.total_execution_time_ms/1000:.2f}s")
    print(f"   🐛 Debug Sessions: {summary['debug_sessions_created']}")
    
    # Show failed tests
    failed_tests = suite_results.get_failed_tests()
    if failed_tests:
        print(f"\n❌ Failed Tests:")
        for failed_test in failed_tests:
            print(f"   • {failed_test.test_case_id}")
            if failed_test.debug_log_url:
                print(f"     Debug Log: {failed_test.debug_log_url}")


if __name__ == "__main__":
    main()