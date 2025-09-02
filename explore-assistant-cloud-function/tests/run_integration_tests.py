#!/usr/bin/env python3
"""
Integration test execution script for Looker Explore Assistant

Provides command-line interface for running integration tests against the REST API
with support for different test suites, custom configurations, and result reporting.

Usage:
    python run_integration_tests.py --token "your-bearer-token" --suite comprehensive
    python run_integration_tests.py --token "your-bearer-token" --url "https://api.example.com" --suite quick
    python run_integration_tests.py --config config.json --output results.json
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add the current directory to Python path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from integration_tests import (
    TestRunner, create_comprehensive_test_suite, create_quick_validation_suite,
    save_test_suite_to_file, load_test_suite_from_file, TestSuite, AuthConfig
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False, log_file: str = ''):
    """Configure logging based on command line options"""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        logger.info(f"Logging to file: {log_file}")


def load_config_file(config_path: str) -> dict:
    """Load configuration from JSON file"""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            logger.info(f"Loaded configuration from {config_path}")
            return config
    except Exception as e:
        logger.error(f"Failed to load config file {config_path}: {e}")
        sys.exit(1)


def create_test_suite_from_config(config: dict) -> TestSuite:
    """Create test suite from configuration dictionary"""
    auth_config = None
    if 'auth' in config:
        auth_config = AuthConfig(
            bearer_token=config['auth'].get('bearer_token'),
            headers=config['auth'].get('headers', {})
        )
    
    test_suite = TestSuite(
        suite_id=config.get('suite_id', 'config_based_suite'),
        name=config.get('name', 'Configuration-based Test Suite'),
        description=config.get('description', ''),
        base_url=config.get('base_url', 'https://ea-demo-backend-63299712962.us-central1.run.app'),
        global_auth=auth_config,
        parallel_execution=config.get('parallel_execution', False),
        max_workers=config.get('max_workers', 4),
        continue_on_failure=config.get('continue_on_failure', True)
    )
    
    # TODO: Add logic to create test cases from config
    # For now, this would need to be implemented based on specific requirements
    
    return test_suite


def save_results(results, output_path: str):
    """Save test results to JSON file"""
    try:
        with open(output_path, 'w') as f:
            json.dump(results.to_dict(), f, indent=2)
        logger.info(f"Results saved to: {output_path}")
    except Exception as e:
        logger.error(f"Failed to save results to {output_path}: {e}")


def print_summary(results):
    """Print test results summary to console"""
    summary = results.summary
    
    print("\n" + "="*60)
    print(f"🎯 TEST SUITE RESULTS: {results.suite_id}")
    print("="*60)
    print(f"Execution Time: {results.total_execution_time_ms/1000:.2f}s")
    print(f"Total Tests: {summary['total_tests']}")
    print(f"✅ Passed: {summary['passed_tests']}")
    print(f"❌ Failed: {summary['failed_tests']}")
    print(f"📊 Test Pass Rate: {summary['test_pass_rate']:.1f}%")
    print(f"🐛 Debug Sessions: {summary['debug_sessions_created']}")
    
    if summary['failed_tests'] > 0:
        print("\n❌ FAILED TESTS:")
        failed_tests = results.get_failed_tests()
        for test_result in failed_tests:
            print(f"   • {test_result.test_case_id}")
            if test_result.error_message:
                print(f"     Error: {test_result.error_message}")
            
            failed_validations = test_result.get_failed_validations()
            if failed_validations:
                for validation in failed_validations[:3]:  # Show first 3 failures
                    print(f"     - {validation.criterion.description}")
                    if validation.error_message:
                        print(f"       {validation.error_message}")
                
                if len(failed_validations) > 3:
                    print(f"     ... and {len(failed_validations) - 3} more failures")
            
            if test_result.debug_log_url:
                print(f"     Debug Log: {test_result.debug_log_url}")
    
    print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(
        description="Run integration tests for Looker Explore Assistant API"
    )
    
    # Authentication options
    parser.add_argument(
        '--token', '-t',
        help='Bearer token for API authentication'
    )
    
    # API configuration
    parser.add_argument(
        '--url', '-u',
        default='https://ea-demo-backend-63299712962.us-central1.run.app',
        help='Base URL for API calls (default: https://ea-demo-backend-63299712962.us-central1.run.app)'
    )
    
    # Test suite options
    parser.add_argument(
        '--suite', '-s',
        choices=['comprehensive', 'quick'],
        default='comprehensive',
        help='Test suite to run (default: comprehensive)'
    )
    
    # Configuration file
    parser.add_argument(
        '--config', '-c',
        help='JSON configuration file for advanced test setup'
    )
    
    # Output options
    parser.add_argument(
        '--output', '-o',
        help='File path to save test results as JSON'
    )
    
    parser.add_argument(
        '--log-file',
        help='File path for detailed logging output'
    )
    
    # Execution options
    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Run tests in parallel (faster but harder to debug)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--save-config',
        help='Save the generated test suite configuration to a file'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose, args.log_file)
    
    # Validate required parameters
    if not args.config and not args.token:
        logger.error("Either --token or --config must be provided")
        parser.print_help()
        sys.exit(1)
    
    try:
        # Create test suite
        if args.config:
            logger.info(f"Loading test configuration from {args.config}")
            config = load_config_file(args.config)
            test_suite = create_test_suite_from_config(config)
        else:
            logger.info(f"Creating {args.suite} test suite")
            if args.suite == 'comprehensive':
                test_suite = create_comprehensive_test_suite(args.token, args.url)
            else:  # quick
                test_suite = create_quick_validation_suite(args.token, args.url)
            
            # Override parallel execution if specified
            if args.parallel:
                test_suite.parallel_execution = True
        
        # Save config if requested
        if args.save_config:
            save_test_suite_to_file(test_suite, args.save_config)
            logger.info(f"Test suite configuration saved to {args.save_config}")
        
        # Create and run tests
        logger.info(f"Starting test execution against {test_suite.base_url}")
        runner = TestRunner(base_url=test_suite.base_url)
        results = runner.run_test_suite(test_suite)
        
        # Output results
        print_summary(results)
        
        if args.output:
            save_results(results, args.output)
        
        # Exit with appropriate code
        if results.summary['failed_tests'] > 0:
            logger.warning("Some tests failed")
            sys.exit(1)
        else:
            logger.info("All tests passed!")
            sys.exit(0)
    
    except KeyboardInterrupt:
        logger.warning("Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()