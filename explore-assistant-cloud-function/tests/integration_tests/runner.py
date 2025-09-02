"""
Test runner for integration testing with authorization support

Executes test suites against the REST API endpoints with comprehensive
request handling, response validation, and result reporting.
"""

import asyncio
import concurrent.futures
import json
import logging
import requests
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, urlencode

from .models import (
    TestCase, TestSuite, TestResult, TestSuiteResult, 
    ValidationResult, AuthConfig
)
from .validator import ValidationEngine

logger = logging.getLogger(__name__)


class TestRunner:
    """
    Executes test suites with comprehensive request handling and validation
    
    Supports both synchronous and parallel test execution with proper
    authorization, debug logging, and detailed result reporting.
    """
    
    def __init__(self, base_url: str = "http://localhost:8080", timeout: float = 30.0):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.validation_engine = ValidationEngine()
        self.session = requests.Session()
        
        # Configure requests session
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'IntegrationTestRunner/1.0'
        })
    
    def run_test_suite(self, test_suite: TestSuite) -> TestSuiteResult:
        """
        Execute a complete test suite
        
        Args:
            test_suite: TestSuite containing test cases to execute
            
        Returns:
            TestSuiteResult with comprehensive execution results
        """
        logger.info(f"🚀 Starting test suite: {test_suite.name}")
        start_time = datetime.utcnow()
        
        # Filter enabled test cases
        enabled_tests = [tc for tc in test_suite.test_cases if tc.enabled]
        logger.info(f"📊 Executing {len(enabled_tests)} enabled test cases")
        
        # Execute tests
        if test_suite.parallel_execution and len(enabled_tests) > 1:
            test_results = self._run_tests_parallel(enabled_tests, test_suite)
        else:
            test_results = self._run_tests_sequential(enabled_tests, test_suite)
        
        end_time = datetime.utcnow()
        total_time_ms = (end_time - start_time).total_seconds() * 1000
        
        # Create comprehensive result
        suite_result = TestSuiteResult(
            suite_id=test_suite.suite_id,
            execution_start_time=start_time.isoformat(),
            execution_end_time=end_time.isoformat(),
            total_execution_time_ms=total_time_ms,
            test_results=test_results
        )
        
        self._log_suite_summary(suite_result)
        return suite_result
    
    def run_single_test(self, test_case: TestCase, auth_config: Optional[AuthConfig] = None, 
                       base_url: Optional[str] = None) -> TestResult:
        """
        Execute a single test case
        
        Args:
            test_case: TestCase to execute
            auth_config: Optional global auth configuration
            base_url: Optional base URL override
            
        Returns:
            TestResult with execution details and validation results
        """
        start_time = time.time()
        logger.info(f"🔍 Running test: {test_case.name}")
        
        # Use test-specific or global auth
        effective_auth = test_case.auth_config
        if auth_config and not effective_auth.bearer_token:
            effective_auth = auth_config
        
        # Execute setup hooks
        self._execute_hooks(test_case.setup_hooks, "setup", test_case.test_id)
        
        try:
            # Make the API request
            response = self._make_request(test_case, effective_auth, base_url)
            
            # Validate the response
            validation_results = self._validate_response(response, test_case.validations)
            
            # Determine overall test success
            test_passed = (
                response.status_code < 400 and 
                all(vr.passed for vr in validation_results)
            )
            
            # Extract debug information if present
            debug_session_id = None
            debug_log_url = None
            
            try:
                response_data = response.json()
                if 'debug_info' in response_data:
                    debug_info = response_data['debug_info']
                    debug_session_id = debug_info.get('session_id')
                    debug_log_url = debug_info.get('debug_log_url')
            except (ValueError, KeyError):
                pass
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            result = TestResult(
                test_case_id=test_case.test_id,
                passed=test_passed,
                execution_time_ms=execution_time_ms,
                response_status=response.status_code,
                response_data=response.json() if response.content else {},
                validation_results=validation_results,
                debug_session_id=debug_session_id,
                debug_log_url=debug_log_url
            )
            
        except Exception as e:
            logger.error(f"❌ Test execution failed for {test_case.test_id}: {e}")
            execution_time_ms = (time.time() - start_time) * 1000
            
            result = TestResult(
                test_case_id=test_case.test_id,
                passed=False,
                execution_time_ms=execution_time_ms,
                response_status=0,
                error_message=str(e)
            )
        
        finally:
            # Execute teardown hooks
            self._execute_hooks(test_case.teardown_hooks, "teardown", test_case.test_id)
        
        self._log_test_result(result, test_case)
        return result
    
    def _run_tests_sequential(self, test_cases: List[TestCase], test_suite: TestSuite) -> List[TestResult]:
        """Run tests sequentially"""
        results = []
        
        for i, test_case in enumerate(test_cases, 1):
            logger.info(f"📝 Progress: {i}/{len(test_cases)} - {test_case.name}")
            
            try:
                result = self.run_single_test(test_case, test_suite.global_auth, test_suite.base_url)
                results.append(result)
                
                # Stop on first failure if configured
                if not result.passed and not test_suite.continue_on_failure:
                    logger.warning("🛑 Stopping test suite execution due to failure")
                    break
                    
            except Exception as e:
                logger.error(f"❌ Failed to execute test {test_case.test_id}: {e}")
                if not test_suite.continue_on_failure:
                    break
        
        return results
    
    def _run_tests_parallel(self, test_cases: List[TestCase], test_suite: TestSuite) -> List[TestResult]:
        """Run tests in parallel using ThreadPoolExecutor"""
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=test_suite.max_workers) as executor:
            # Submit all test cases
            future_to_test = {
                executor.submit(self.run_single_test, tc, test_suite.global_auth, test_suite.base_url): tc
                for tc in test_cases
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_test):
                test_case = future_to_test[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"❌ Parallel test execution failed for {test_case.test_id}: {e}")
                    error_result = TestResult(
                        test_case_id=test_case.test_id,
                        passed=False,
                        execution_time_ms=0,
                        response_status=0,
                        error_message=str(e)
                    )
                    results.append(error_result)
        
        # Sort results by test case order (to maintain consistent reporting)
        test_order = {tc.test_id: i for i, tc in enumerate(test_cases)}
        results.sort(key=lambda r: test_order.get(r.test_case_id, 999))
        
        return results
    
    def _make_request(self, test_case: TestCase, auth_config: AuthConfig, 
                     base_url: Optional[str] = None) -> requests.Response:
        """Make HTTP request for test case"""
        
        # Build URL
        url_base = base_url or self.base_url
        full_url = urljoin(url_base, test_case.request.endpoint.lstrip('/'))
        
        # Add query parameters
        if test_case.request.query_params:
            query_string = urlencode(test_case.request.query_params)
            full_url += f"?{query_string}"
        
        # Prepare headers
        headers = self.session.headers.copy()
        headers.update(test_case.request.headers)
        headers.update(auth_config.get_auth_headers())
        
        # Prepare request data
        request_data = test_case.request.data.copy()
        
        # Add debug flag if not already present
        if 'debug' not in request_data:
            request_data['debug'] = True
        
        logger.debug(f"🌐 {test_case.request.method} {full_url}")
        logger.debug(f"📦 Request data keys: {list(request_data.keys())}")
        
        # Make request
        response = self.session.request(
            method=test_case.request.method,
            url=full_url,
            json=request_data,
            headers=headers,
            timeout=test_case.request.timeout or self.timeout
        )
        
        logger.debug(f"📡 Response status: {response.status_code}")
        return response
    
    def _validate_response(self, response: requests.Response, 
                          validation_criteria: List[ValidationResult]) -> List[ValidationResult]:
        """Validate response against criteria"""
        
        try:
            response_data = response.json() if response.content else {}
        except ValueError:
            response_data = {"_raw_response": response.text}
        
        # Add status code to response data for validation
        response_data["_status_code"] = response.status_code
        response_data["_headers"] = dict(response.headers)
        
        return self.validation_engine.validate_response(response_data, validation_criteria)
    
    def _execute_hooks(self, hooks: List[callable], hook_type: str, test_id: str) -> None:
        """Execute setup or teardown hooks"""
        for hook in hooks:
            try:
                hook()
                logger.debug(f"✅ {hook_type} hook executed for {test_id}")
            except Exception as e:
                logger.error(f"❌ {hook_type} hook failed for {test_id}: {e}")
    
    def _log_test_result(self, result: TestResult, test_case: TestCase) -> None:
        """Log individual test result"""
        status_icon = "✅" if result.passed else "❌"
        logger.info(f"{status_icon} {test_case.name}: {result.response_status} ({result.execution_time_ms:.1f}ms)")
        
        if result.debug_session_id:
            logger.info(f"🐛 Debug log: {result.debug_log_url}")
        
        # Log failed validations
        failed_validations = result.get_failed_validations()
        if failed_validations:
            logger.warning(f"❌ Failed validations for {test_case.test_id}:")
            for vr in failed_validations:
                logger.warning(f"   • {vr.criterion.description}: {vr.error_message}")
    
    def _log_suite_summary(self, result: TestSuiteResult) -> None:
        """Log test suite summary"""
        summary = result.summary
        
        logger.info(f"\n🎯 Test Suite Summary: {result.suite_id}")
        logger.info(f"   Total Tests: {summary['total_tests']}")
        logger.info(f"   ✅ Passed: {summary['passed_tests']}")
        logger.info(f"   ❌ Failed: {summary['failed_tests']}")
        logger.info(f"   📊 Pass Rate: {summary['test_pass_rate']:.1f}%")
        logger.info(f"   ⏱️  Avg Time: {summary['avg_execution_time_ms']:.1f}ms")
        logger.info(f"   🐛 Debug Sessions: {summary['debug_sessions_created']}")
        
        if summary['failed_tests'] > 0:
            logger.warning("\n❌ Failed Tests:")
            for test_result in result.get_failed_tests():
                logger.warning(f"   • {test_result.test_case_id}: {test_result.error_message}")


def create_auth_config(bearer_token: str, additional_headers: Optional[Dict[str, str]] = None) -> AuthConfig:
    """Helper function to create auth configuration"""
    return AuthConfig(
        bearer_token=bearer_token,
        headers=additional_headers or {}
    )


def run_test_file(file_path: str, auth_token: str, base_url: str = "http://localhost:8080") -> TestSuiteResult:
    """
    Convenience function to run tests from a JSON file
    
    Args:
        file_path: Path to JSON file containing test suite
        auth_token: Bearer token for authorization
        base_url: Base URL for API calls
        
    Returns:
        TestSuiteResult with execution results
    """
    with open(file_path, 'r') as f:
        test_data = json.load(f)
    
    # Create test suite from JSON data (simplified)
    # In practice, you'd want a more sophisticated loader
    test_suite = TestSuite(
        suite_id=test_data.get('suite_id', 'file_based_suite'),
        name=test_data.get('name', f'Tests from {file_path}'),
        description=test_data.get('description', ''),
        base_url=base_url,
        global_auth=create_auth_config(auth_token)
    )
    
    runner = TestRunner(base_url=base_url)
    return runner.run_test_suite(test_suite)