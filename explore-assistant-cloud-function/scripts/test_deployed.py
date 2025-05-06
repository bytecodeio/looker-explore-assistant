import os
import json
import requests
import time
import argparse
import logging
import http.client
import socket
import sys

def check_required_env_vars():
    """
    Check if all required environment variables are set
    """
    required_env_vars = [
        "PROJECT",        # GCP Project ID
        "REGION",         # GCP Region (e.g., us-central1)
    ]
    
    optional_env_vars = [
        "MODEL_NAME",     # Model name (default: gemini-2.0-flash-lite)
        "PORT",           # Port for local development (default: 8000)
        "LOOKERSDK_BASE_URL",  # Looker SDK base URL
        "LOOKERSDK_CLIENT_ID", # Looker SDK client ID
        "LOOKERSDK_CLIENT_SECRET", # Looker SDK client secret
        "LOOKERSDK_VERIFY_SSL" # Looker SDK SSL verification (default: false)
    ]
    
    # Check required env vars
    missing_required = [var for var in required_env_vars if not os.environ.get(var)]
    if missing_required:
        print(f"ERROR: Missing required environment variables: {', '.join(missing_required)}")
        print("These variables are required for the cloud function to work properly.")
        return False
    
    # Print current env var configuration
    print("Environment Variables Configuration:")
    print("-----------------------------------")
    for var in required_env_vars:
        value = os.environ.get(var)
        print(f"✅ {var}: {value}")
    
    for var in optional_env_vars:
        value = os.environ.get(var)
        if value:
            print(f"✅ {var}: {value}")
        else:
            print(f"⚠️ {var}: Not set (optional)")
            
    return True

def check_network_connectivity(url, timeout=5):
    """
    Check if the target URL is reachable at a network level
    """
    parsed_url = url.split("://")[1] if "://" in url else url
    host = parsed_url.split("/")[0]
    
    print(f"Checking network connectivity to {host}...")
    try:
        # Try to establish a socket connection
        socket.create_connection((host, 443), timeout=timeout)
        print(f"✅ Network connection to {host} successful")
        return True
    except socket.error as e:
        print(f"❌ Network connection to {host} failed: {e}")
        return False

def send_request(url, data, verbose=False):
    """
    Send a POST request to the given URL with the provided data.
    """
    headers = {
        'Content-Type': 'application/json'
    }
    
    # Add retry logic
    max_retries = 3
    retry_delay = 1
    
    if verbose:
        print(f"Sending request to {url}")
        print(f"Request data: {json.dumps(data, indent=2)}")
        print(f"Request headers: {headers}")
    
    for attempt in range(max_retries):
        try:
            start_time = time.time()
            # First try to connect to check if the server is reachable
            if verbose:
                print(f"Checking if {url} is reachable...")
            connection_test = requests.head(url, timeout=5)
            if verbose:
                print(f"HEAD request status code: {connection_test.status_code}")
                print(f"HEAD response headers: {dict(connection_test.headers)}")
            
            # Now send the actual POST request
            if verbose:
                print(f"Sending POST request to {url}...")
            response = requests.post(url, headers=headers, json=data, timeout=30)
            elapsed_time = time.time() - start_time
            
            if verbose:
                print(f"Received response in {elapsed_time:.2f} seconds")
                print(f"Status code: {response.status_code}")
                print(f"Response headers: {dict(response.headers)}")
                print(f"Response content: {response.text[:500]}..." if len(response.text) > 500 else f"Response content: {response.text}")
            
            response.raise_for_status()
            return response.text
        except requests.exceptions.ConnectionError as e:
            print(f"Connection error: {str(e)}")
            print(f"The server at {url} is not reachable. Please check if the server is running and the URL is correct.")
            if verbose:
                print(f"Error details: {repr(e)}")
            if attempt == max_retries - 1:
                raise
            print(f"Attempt {attempt + 1} failed. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            retry_delay *= 2
        except requests.exceptions.RequestException as e:
            print(f"Request error: {str(e)}")
            if verbose:
                print(f"Error details: {repr(e)}")
                print(f"Error type: {type(e)}")
            if attempt == max_retries - 1:
                raise
            print(f"Attempt {attempt + 1} failed. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            retry_delay *= 2

def check_url_status(url, verbose=False):
    """
    Check if a URL is reachable and print its status
    """
    try:
        if verbose:
            print(f"Checking URL status: {url}")
        response = requests.get(url, timeout=5)
        print(f"URL status: {url} - Status code: {response.status_code}")
        if verbose:
            print(f"Response headers: {dict(response.headers)}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"URL {url} is not reachable: {str(e)}")
        return False

def check_curl_request(url, verbose=False):
    """
    Use curl command to check connectivity (as a fallback)
    """
    import subprocess
    
    print(f"Trying curl to check endpoint: {url}")
    try:
        cmd = ["curl", "-v", "-X", "HEAD", url]
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(f"Curl exit code: {result.returncode}")
        if verbose:
            print("Curl output:")
            print(result.stderr)
            print(result.stdout)
        return result.returncode == 0
    except Exception as e:
        print(f"Curl check failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Test the deployed Looker Explore Assistant Cloud Function")
    parser.add_argument("--url", default="https://explore-assistant-backend-agent-746659087621.us-central1.run.app",
                       help="URL of the deployed cloud function")
    parser.add_argument("--query", default="What was the revenue yesterday?",
                       help="Natural language query to test")
    parser.add_argument("--max-tokens", type=int, default=1000,
                       help="Maximum number of output tokens")
    parser.add_argument("--debug", "-d", action="store_true",
                       help="Enable debug mode (more verbose than verbose)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose output")
    parser.add_argument("--check-only", action="store_true",
                       help="Only check if the URL is reachable, don't send a request")
    parser.add_argument("--path", default="",
                       help="Additional path to append to the URL (e.g. '/api')")
    parser.add_argument("--check-env", action="store_true",
                       help="Check required environment variables")
    parser.add_argument("--curl-check", action="store_true",
                       help="Use curl to check connectivity as a fallback")
    parser.add_argument("--input-file", 
                       help="Path to a JSON file containing the request body")
    
    args = parser.parse_args()
    
    # Banner
    print("\n" + "="*60)
    print(" LOOKER EXPLORE ASSISTANT - CLOUD FUNCTION TEST TOOL")
    print("="*60)
    
    # Check environment variables if requested
    if args.check_env:
        if not check_required_env_vars():
            return
    
    # Enable debug logging if requested
    if args.debug:
        import http.client as http_client
        http_client.HTTPConnection.debuglevel = 1
        logging_level = logging.DEBUG
        args.verbose = True  # Debug implies verbose
    else:
        logging_level = logging.INFO if args.verbose else logging.WARNING
    
    # Setup logging
    logging.basicConfig(level=logging_level)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging_level)
    requests_log.propagate = True
    
    # Construct the full URL
    full_url = args.url.rstrip('/') + '/' + args.path.lstrip('/')
    if args.path and not full_url.endswith('/'):
        full_url = full_url.rstrip('/')
    
    print(f"Target URL: {full_url}")
    
    # Check network connectivity
    check_network_connectivity(full_url)
    
    # Just check if the URL is reachable if requested
    if args.check_only:
        check_url_status(full_url, args.verbose)
        return
    
    # Request payload
    if args.input_file:
        try:
            with open(args.input_file, 'r') as file:
                input_data = json.load(file)
                
                # Handle different input file formats
                if "prompt" in input_data:
                    # Format from input_test.json
                    data = {
                        "contents": input_data["prompt"],
                        "parameters": {"max_output_tokens": args.max_tokens}
                    }
                    
                    # Add standard_fields if present
                    if "standard_fields" in input_data:
                        data["standard_fields"] = input_data["standard_fields"]
                        
                elif "contents" in input_data:
                    # Already in the right format
                    data = input_data
                    if "parameters" not in data:
                        data["parameters"] = {"max_output_tokens": args.max_tokens}
                else:
                    # Use the whole file as the payload
                    data = input_data
                    
                if args.verbose:
                    print(f"Loaded request data from {args.input_file}")
        except Exception as e:
            print(f"Error loading input file: {e}")
            return
    else:
        # Use command line parameters
        data = {
            "contents": args.query,
            "parameters": {"max_output_tokens": args.max_tokens}
        }

    try:
        # First check if the URL is reachable
        url_status = check_url_status(full_url, args.verbose)
        
        if not url_status and args.curl_check:
            # Try curl as a fallback
            check_curl_request(full_url, args.verbose)
        
        if not url_status:
            print("Warning: The URL does not seem to be reachable, but trying the request anyway...")
        
        # Send the request
        print(f"Testing cloud function at: {full_url}")
        if args.input_file:
            print(f"Using input file: {args.input_file}")
        else:
            print(f"Query: \"{args.query}\"")
        print(f"Max tokens: {args.max_tokens}")
        print("Sending request...")
        
        # Print the request data
        if args.verbose or args.debug:
            print("\n" + "="*60)
            print(" REQUEST DATA")
            print("="*60)
            print(json.dumps(data, indent=2))
        
        response = send_request(full_url, data, args.verbose)
        
        print("\n" + "="*60)
        print(" RESPONSE")
        print("="*60)
        print(response)
        
        # Try to parse as JSON to check if it's a structured response
        try:
            json_response = json.loads(response)
            if args.verbose or args.debug:
                print("\n" + "="*60)
                print(" PARSED JSON RESPONSE")
                print("="*60)
                print(json.dumps(json_response, indent=2))
        except json.JSONDecodeError:
            # Not JSON, which is fine
            if args.verbose or args.debug:
                print("\nResponse is not JSON. Content appears to be plain text.")
            
            
    except requests.exceptions.RequestException as e:
        print("\n" + "="*60)
        print(" ERROR")
        print("="*60)
        print(f"Error making request: {str(e)}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()