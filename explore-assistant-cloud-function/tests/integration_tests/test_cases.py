"""
Sample test cases and test case builder utilities

Provides pre-built test cases based on real examples and utilities
for creating new test cases with common validation patterns.
"""

import json
import logging
from typing import Dict, Any, List
from copy import deepcopy

from .models import (
    TestCase, TestSuite, TestRequest, AuthConfig, ValidationCriterion,
    TestPriority, ValidationOperator,
    create_field_filter_validation, create_explore_key_validation,
    create_fields_contain_validation, create_debug_info_validation,
    create_success_validation
)
from .template_loader import load_golden_queries_template, TemplateLoadError

logger = logging.getLogger(__name__)


class TestCaseBuilder:
    """Builder for creating test cases with common patterns"""
    
    def __init__(self, test_id: str, name: str):
        self.test_id = test_id
        self.name = name
        self.description = ""
        self.request_data = {}
        self.auth_token = ""
        self.validations = []
        self.priority = TestPriority.MEDIUM
        self.tags = []
        self.expected_debug_interactions = 0
    
    def with_description(self, description: str) -> 'TestCaseBuilder':
        self.description = description
        return self
    
    def with_query(self, query: str) -> 'TestCaseBuilder':
        self.request_data['query'] = query
        return self
    
    def with_explore_key(self, explore_key: str) -> 'TestCaseBuilder':
        self.request_data['explore_key'] = explore_key
        return self
    
    def with_restricted_explores(self, explores: List[str]) -> 'TestCaseBuilder':
        self.request_data['restricted_explore_keys'] = explores
        return self
    
    def with_semantic_models(self, models: Dict[str, Any]) -> 'TestCaseBuilder':
        self.request_data['semantic_models'] = models
        return self
    
    def with_golden_queries(self, queries: Dict[str, Any]) -> 'TestCaseBuilder':
        self.request_data['golden_queries'] = queries
        return self
    
    def with_conversation_context(self, context: str) -> 'TestCaseBuilder':
        self.request_data['conversation_context'] = context
        return self
    
    def with_auth_token(self, token: str) -> 'TestCaseBuilder':
        self.auth_token = token
        return self
    
    def with_priority(self, priority: TestPriority) -> 'TestCaseBuilder':
        self.priority = priority
        return self
    
    def with_tags(self, tags: List[str]) -> 'TestCaseBuilder':
        self.tags = tags
        return self
    
    def with_expected_debug_interactions(self, count: int) -> 'TestCaseBuilder':
        self.expected_debug_interactions = count
        return self
    
    def expect_success(self) -> 'TestCaseBuilder':
        """Expect successful response"""
        self.validations.append(create_success_validation())
        return self
    
    def expect_explore_key(self, explore_key: str) -> 'TestCaseBuilder':
        """Expect specific explore key in response"""
        self.validations.append(create_explore_key_validation(explore_key))
        return self
    
    def expect_field_filter(self, field_name: str, expected_value: Any) -> 'TestCaseBuilder':
        """Expect specific field filter in parameters"""
        self.validations.append(create_field_filter_validation(field_name, expected_value))
        return self
    
    def expect_fields_contain(self, required_fields: List[str]) -> 'TestCaseBuilder':
        """Expect response to contain specific fields"""
        self.validations.append(create_fields_contain_validation(required_fields))
        return self
    
    def expect_debug_info(self) -> 'TestCaseBuilder':
        """Expect debug info in response"""
        self.validations.append(create_debug_info_validation())
        return self
    
    def expect_custom(self, field_path: str, operator: ValidationOperator, 
                     expected_value: Any = None, description: str = "") -> 'TestCaseBuilder':
        """Add custom validation criterion"""
        self.validations.append(ValidationCriterion(
            field_path=field_path,
            operator=operator,
            expected_value=expected_value,
            description=description
        ))
        return self
    
    def build(self) -> TestCase:
        """Build the test case"""
        # Ensure debug mode is enabled
        self.request_data['debug'] = True
        
        # Auto-include golden queries if not already present
        if 'golden_queries' not in self.request_data:
            try:
                golden_queries = load_golden_queries_template()
                self.request_data['golden_queries'] = golden_queries
                logger.debug(f"✅ Auto-included golden queries template in test {self.test_id}")
            except TemplateLoadError as e:
                logger.warning(f"⚠️ Failed to load golden queries template for test {self.test_id}: {e}")
                logger.warning("   Test may fail if golden queries are required by the backend")
        
        return TestCase(
            test_id=self.test_id,
            name=self.name,
            description=self.description,
            request=TestRequest(
                endpoint="/api/v1/query",
                method="POST",
                data=self.request_data,
                timeout=30.0
            ),
            auth_config=AuthConfig(bearer_token=self.auth_token),
            validations=self.validations,
            priority=self.priority,
            tags=self.tags,
            expected_debug_interactions=self.expected_debug_interactions
        )


def create_product_sku_test_case(auth_token: str) -> TestCase:
    """
    Create test case based on the provided sample that should filter by product SKU
    
    This test case represents the scenario where the system found the SKU in vector search
    but failed to include it as a filter in the generated parameters (the "bad response" case).
    """
    
    # Load golden queries template
    try:
        golden_queries = load_golden_queries_template()
        logger.debug("✅ Loaded golden queries template for product SKU test")
    except TemplateLoadError as e:
        logger.warning(f"⚠️ Failed to load golden queries template: {e}")
        golden_queries = {}
    
    # Minimal semantic model for testing (extracted key parts from sample)
    semantic_models = {
        "sales_demo_the_look:order_items": {
            "exploreId": "order_items",
            "modelName": "sales_demo_the_look", 
            "exploreKey": "sales_demo_the_look:order_items",
            "dimensions": [
                {
                    "name": "products.sku",
                    "type": "string",
                    "label": "Products SKU",
                    "description": "Stock keeping unit for products"
                },
                {
                    "name": "order_items.order_id", 
                    "type": "number",
                    "label": "Order Items Order ID",
                    "description": "Uniquely identifies each purchase"
                },
                {
                    "name": "order_items.created_date",
                    "type": "date_date", 
                    "label": "Order Items Item Paid Date",
                    "description": "The timeframe the item was paid for fully"
                }
            ],
            "measures": [
                {
                    "name": "order_items.sale_price",
                    "type": "number",
                    "label": "Order Items Sales Price",
                    "description": "The price the item sold for"
                }
            ]
        }
    }
    
    return (TestCaseBuilder("product_sku_filter_test", "Product SKU Filter Validation")
        .with_description("Test that queries mentioning specific product SKUs result in proper filter generation")
        .with_query("tell me about sales 0006AABE0BA47A35C0B0BF6596F85159")
        .with_restricted_explores(["sales_demo_the_look:order_items"])
        .with_semantic_models(semantic_models)
        .with_golden_queries(golden_queries)  # Explicitly include golden queries
        .with_auth_token(auth_token)
        .with_priority(TestPriority.CRITICAL)
        .with_tags(["product_sku", "vector_search", "filter_validation"])
        .with_expected_debug_interactions(2)  # Explore determination + Parameter generation
        .expect_success()
        .expect_explore_key("sales_demo_the_look:order_items")
        .expect_field_filter("products.sku", "0006AABE0BA47A35C0B0BF6596F85159")
        .expect_debug_info()
        .expect_custom(
            "data.generation_metadata.vector_search_used",
            ValidationOperator.LENGTH_GREATER_THAN,
            0,
            "Should have vector search results for SKU lookup"
        )
        .build())


def create_basic_query_test_case(auth_token: str) -> TestCase:
    """Create a basic query test case without specific product references"""
    
    # Load golden queries template
    try:
        golden_queries = load_golden_queries_template()
        logger.debug("✅ Auto-included golden queries template in test basic_query_test")
    except TemplateLoadError as e:
        logger.warning(f"⚠️ Failed to load golden queries template: {e}")
        golden_queries = {}
    
    # Include semantic models for the explore
    semantic_models = {
        "sales_demo_the_look:order_items": {
            "exploreId": "order_items",
            "modelName": "sales_demo_the_look", 
            "exploreKey": "sales_demo_the_look:order_items",
            "dimensions": [
                {
                    "name": "order_items.created_date",
                    "type": "date_date", 
                    "label": "Order Items Created Date",
                    "description": "The date when the order was created"
                },
                {
                    "name": "order_items.order_id", 
                    "type": "number",
                    "label": "Order Items Order ID",
                    "description": "Uniquely identifies each order"
                },
                {
                    "name": "users.city",
                    "type": "string",
                    "label": "Users City",
                    "description": "User's city"
                }
            ],
            "measures": [
                {
                    "name": "order_items.total_sale_price",
                    "type": "number",
                    "label": "Order Items Total Sale Price",
                    "description": "Total sales revenue"
                },
                {
                    "name": "order_items.count",
                    "type": "count",
                    "label": "Order Items Count",
                    "description": "Count of order items"
                }
            ]
        }
    }
    
    return (TestCaseBuilder("basic_query_test", "Basic Query Processing")
        .with_description("Test basic query processing without specific entity references")
        .with_query("show me sales data for the last month")
        .with_restricted_explores(["sales_demo_the_look:order_items"])
        .with_semantic_models(semantic_models)
        .with_golden_queries(golden_queries)
        .with_auth_token(auth_token)
        .with_priority(TestPriority.HIGH)
        .with_tags(["basic_query", "date_filters"])
        .with_expected_debug_interactions(2)
        .expect_success()
        .expect_explore_key("sales_demo_the_look:order_items")
        .expect_debug_info()
        .expect_custom(
            "data.parameters.fields",
            ValidationOperator.LENGTH_GREATER_THAN,
            0,
            "Should include at least one field"
        )
        .build())


def create_invalid_explore_test_case(auth_token: str) -> TestCase:
    """Create test case with invalid explore to test error handling"""
    
    # Load golden queries template even for invalid tests for consistency
    try:
        golden_queries = load_golden_queries_template()
        logger.debug("✅ Auto-included golden queries template in test invalid_explore_test")
    except TemplateLoadError as e:
        logger.warning(f"⚠️ Failed to load golden queries template: {e}")
        golden_queries = {}
    
    return (TestCaseBuilder("invalid_explore_test", "Invalid Explore Handling")
        .with_description("Test error handling when no valid explore can be determined")
        .with_query("tell me about quantum mechanics")
        .with_restricted_explores(["sales_demo_the_look:order_items"])
        .with_golden_queries(golden_queries)
        .with_auth_token(auth_token)
        .with_priority(TestPriority.MEDIUM)
        .with_tags(["error_handling", "edge_case"])
        .with_expected_debug_interactions(1)  # May fail at explore determination
        .expect_custom(
            "success",
            ValidationOperator.EQUALS,
            False,
            "Should fail for irrelevant queries"
        )
        # .expect_debug_info()  # Debug info not returned for 400 responses
        .build())


def create_debug_mode_test_case(auth_token: str) -> TestCase:
    """Create test case specifically to validate debug mode functionality"""
    
    # Load golden queries template
    try:
        golden_queries = load_golden_queries_template()
        logger.debug("✅ Auto-included golden queries template in test debug_mode_validation")
    except TemplateLoadError as e:
        logger.warning(f"⚠️ Failed to load golden queries template: {e}")
        golden_queries = {}
    
    # Include semantic models for the explore
    semantic_models = {
        "sales_demo_the_look:order_items": {
            "exploreId": "order_items",
            "modelName": "sales_demo_the_look", 
            "exploreKey": "sales_demo_the_look:order_items",
            "dimensions": [
                {
                    "name": "order_items.order_id", 
                    "type": "number",
                    "label": "Order Items Order ID",
                    "description": "Uniquely identifies each order"
                },
                {
                    "name": "order_items.status",
                    "type": "string",
                    "label": "Order Items Status",
                    "description": "The current status of the order"
                },
                {
                    "name": "order_items.created_date",
                    "type": "date_date", 
                    "label": "Order Items Created Date",
                    "description": "The date when the order was created"
                }
            ],
            "measures": [
                {
                    "name": "order_items.count",
                    "type": "count",
                    "label": "Order Items Count",
                    "description": "Count of order items"
                },
                {
                    "name": "order_items.total_sale_price",
                    "type": "number",
                    "label": "Order Items Total Sale Price",
                    "description": "Total sales revenue"
                }
            ]
        }
    }
    
    return (TestCaseBuilder("debug_mode_validation", "Debug Mode Functionality")
        .with_description("Validate that debug mode provides comprehensive logging and debug URLs")
        .with_query("show me order information")
        .with_restricted_explores(["sales_demo_the_look:order_items"])
        .with_semantic_models(semantic_models)
        .with_golden_queries(golden_queries)
        .with_auth_token(auth_token)
        .with_priority(TestPriority.HIGH)
        .with_tags(["debug_mode", "logging"])
        .with_expected_debug_interactions(2)
        .expect_success()
        .expect_debug_info()
        .expect_custom(
            "debug_info.debug_log_url",
            ValidationOperator.CONTAINS,
            "/api/v1/debug/logs/",
            "Should provide debug log URL"
        )
        # .expect_custom(
        #     "debug_info.llm_interactions_count",
        #     ValidationOperator.GREATER_THAN,
        #     0,
        #     "Should log LLM interactions"
        # )
        # .expect_custom(
        #     "debug_info.processing_steps_count",
        #     ValidationOperator.GREATER_THAN,
        #     0,
        #     "Should log processing steps"
        # )
        .build())


def create_bfoc_sku_test_case(auth_token: str) -> TestCase:
    """Create test case for BF0C SKU monthly sales analysis"""
    
    # Load golden queries template
    try:
        golden_queries = load_golden_queries_template()
        logger.debug("✅ Loaded golden queries template for BF0C SKU test")
    except TemplateLoadError as e:
        logger.warning(f"⚠️ Failed to load golden queries template: {e}")
        golden_queries = {}
    
    # Semantic models for the explore
    semantic_models = {
        "sales_demo_the_look:order_items": {
            "exploreId": "order_items",
            "modelName": "sales_demo_the_look", 
            "exploreKey": "sales_demo_the_look:order_items",
            "dimensions": [
                {
                    "name": "order_items.created_month",
                    "type": "date_month", 
                    "label": "Order Items Created Month",
                    "description": "The month when the order was created"
                },
                {
                    "name": "products.sku",
                    "type": "string",
                    "label": "Products SKU",
                    "description": "Stock keeping unit for products"
                },
                {
                    "name": "order_items.order_id", 
                    "type": "number",
                    "label": "Order Items Order ID",
                    "description": "Uniquely identifies each order"
                }
            ],
            "measures": [
                {
                    "name": "order_items.total_sale_price",
                    "type": "number",
                    "label": "Order Items Total Sale Price",
                    "description": "Total sales revenue"
                },
                {
                    "name": "order_items.count",
                    "type": "count",
                    "label": "Order Items Count", 
                    "description": "Count of order items"
                }
            ]
        }
    }
    
    return (TestCaseBuilder("bfoc_sku_monthly_sales", "BF0C SKU Monthly Sales Analysis")
        .with_description("Test monthly sales trend analysis for specific product SKU BF0C0D36A5A3F240CCBC590FCA184A7F")
        .with_query("show me monthly sales for product BF0C0D36A5A3F240CCBC590FCA184A7F")
        .with_restricted_explores(["sales_demo_the_look:order_items"])
        .with_semantic_models(semantic_models)
        .with_golden_queries(golden_queries)
        .with_auth_token(auth_token)
        .with_priority(TestPriority.HIGH)
        .with_tags(["product_sku", "monthly_analysis", "time_series"])
        .with_expected_debug_interactions(2)
        .expect_success()
        .expect_explore_key("sales_demo_the_look:order_items")
        .expect_field_filter("products.sku", "BF0C0D36A5A3F240CCBC590FCA184A7F")
        .expect_fields_contain(["order_items.created_month", "order_items.total_sale_price"])
        .expect_debug_info()
        .expect_custom(
            "data.generation_metadata.vector_search_used",
            ValidationOperator.LENGTH_GREATER_THAN,
            0,
            "Should have vector search results for BF0C SKU lookup"
        )
        .build())


def create_comprehensive_test_suite(auth_token: str, base_url: str = "https://ea-demo-backend-63299712962.us-central1.run.app") -> TestSuite:
    """Create a comprehensive test suite with all sample test cases"""
    
    test_suite = TestSuite(
        suite_id="comprehensive_integration_tests",
        name="Comprehensive Integration Test Suite",
        description="Full integration test suite covering query processing, validation, and debug functionality",
        base_url=base_url,
        global_auth=AuthConfig(bearer_token=auth_token),
        parallel_execution=False,  # Start with sequential for easier debugging
        continue_on_failure=True
    )
    
    # Add all test cases
    test_suite.add_test_case(create_product_sku_test_case(auth_token))
    test_suite.add_test_case(create_basic_query_test_case(auth_token))
    test_suite.add_test_case(create_bfoc_sku_test_case(auth_token))
    test_suite.add_test_case(create_debug_mode_test_case(auth_token))
    test_suite.add_test_case(create_invalid_explore_test_case(auth_token))
    
    return test_suite


def create_quick_validation_suite(auth_token: str, base_url: str = "https://ea-demo-backend-63299712962.us-central1.run.app") -> TestSuite:
    """Create a quick test suite with just critical test cases"""
    
    test_suite = TestSuite(
        suite_id="quick_validation_tests",
        name="Quick Validation Test Suite", 
        description="Fast test suite with critical functionality tests",
        base_url=base_url,
        global_auth=AuthConfig(bearer_token=auth_token),
        parallel_execution=True,
        max_workers=2,
        continue_on_failure=True
    )
    
    # Add only critical test cases
    test_suite.add_test_case(create_product_sku_test_case(auth_token))
    test_suite.add_test_case(create_debug_mode_test_case(auth_token))
    
    return test_suite


def save_test_suite_to_file(test_suite: TestSuite, file_path: str) -> None:
    """Save test suite configuration to JSON file"""
    with open(file_path, 'w') as f:
        json.dump(test_suite.to_dict(), f, indent=2)


def load_test_suite_from_file(file_path: str) -> Dict[str, Any]:
    """Load test suite configuration from JSON file"""
    with open(file_path, 'r') as f:
        return json.load(f)