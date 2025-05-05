#!/usr/bin/env python3
import requests
import json
import argparse
import logging
import sys
from typing import Dict, Any, Optional
import time
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_server_status(url: str) -> bool:
    """
    Check if the server is running
    
    Args:
        url: Base URL of the server
        
    Returns:
        True if the server is running
    """
    try:
        # Try to access the health endpoint or the root
        health_url = url.rstrip('/') + '/health'
        response = requests.get(health_url, timeout=2)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        try:
            # Try the base URL as a fallback
            requests.options(url, timeout=2)
            return True
        except requests.exceptions.RequestException:
            return False

def load_json_file(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Load data from a JSON file
    
    Args:
        filepath: Path to the JSON file
        
    Returns:
        Dictionary with the loaded data or None if the file doesn't exist
    """
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            return data
    except FileNotFoundError:
        logger.error(f"File not found: {filepath}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON file {filepath}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error loading file {filepath}: {e}")
        return None

def send_request(url: str, payload: Dict[str, Any], verbose: bool = False) -> None:
    """
    Send a request to the server and print the response
    
    Args:
        url: The URL of the server
        payload: The payload to send
        verbose: Whether to print verbose output
    """
    headers = {
        'Content-Type': 'application/json'
    }
    
    logger.info(f"Sending request to {url}")
    if verbose:
        logger.debug(f"Headers: {headers}")
        logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        start_time = time.time()
        response = requests.post(url, headers=headers, json=payload)
        elapsed_time = time.time() - start_time
        
        # Print response headers for debugging
        if verbose:
            logger.debug(f"Response headers: {response.headers}")
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Request took {elapsed_time:.2f} seconds")
        
        # Print response content
        logger.info("Response content:")
        if response.status_code == 200:
            print(response.text)
        else:
            logger.error(f"Error response: {response.text}")
        
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error: Could not connect to {url}")
        logger.error("Is the server running?")
    except Exception as e:
        logger.error(f"Error sending request: {e}")

def main():
    parser = argparse.ArgumentParser(description='Test the Looker Explore Assistant locally')
    parser.add_argument('--url', type=str, default='http://localhost:8000/', 
                        help='URL of the server')
    parser.add_argument('--query', type=str, 
                        default='Show me the top 10 sales by region',
                        help='Query to send to the server')
    parser.add_argument('--input-file', type=str, 
                        help='JSON file containing the input payload')
    parser.add_argument('--standard-fields-file', type=str, 
                        help='JSON file containing standard fields')
    parser.add_argument('--model-name', type=str, 
                        help='Override the model name to use')
    parser.add_argument('--verbose', action='store_true',
                        help='Enable verbose logging')
    parser.add_argument('--output', type=str, 
                        help='Save response to this file')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        # Also set root logger to DEBUG
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Check if the server is running
    if not check_server_status(args.url):
        logger.error(f"Server at {args.url} is not running or not reachable")
        sys.exit(1)
    
    # Initialize payload
    if args.input_file:
        # Load payload from file
        data = load_json_file(args.input_file)
        if not data:
            sys.exit(1)
        payload = data
        
        # If "prompt" is present but not "contents", convert it
        if "prompt" in payload and "contents" not in payload:
            payload["contents"] = payload["prompt"]
        
        # Check if we have either contents or prompt
        if "contents" not in payload and "prompt" not in payload:
            logger.error("Neither 'contents' nor 'prompt' found in input file")
            sys.exit(1)
            
    else:
        # Build payload from command line arguments
        payload = {
            "contents": args.query
        }
        
        # Add standard fields if provided
        if args.standard_fields_file:
            fields_data = load_json_file(args.standard_fields_file)
            if fields_data and "standard_fields" in fields_data:
                payload["standard_fields"] = fields_data["standard_fields"]
                logger.info(f"Loaded standard fields from {args.standard_fields_file}")
    
    # Override model name if specified
    if args.model_name:
        if "parameters" not in payload:
            payload["parameters"] = {}
        payload["parameters"]["model_name"] = args.model_name
        logger.info(f"Using model name: {args.model_name}")
    
    # Send the request
    send_request(args.url, payload, args.verbose)
    
    # Save response to file if specified
    if args.output:
        pass  # Implement saving response to file if needed

if __name__ == "__main__":
    main()
