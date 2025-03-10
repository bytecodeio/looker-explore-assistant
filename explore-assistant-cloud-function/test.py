import os
import hmac
import json
import requests
import time

def create_signature(data, auth_token):
    """
    Create HMAC signature for request authentication
    """
    secret = auth_token.encode('utf-8')
    message = json.dumps(data).encode('utf-8')
    signature = hmac.new(secret, message, 'sha256').hexdigest()
    return signature

def send_request(url, data):
    """
    Send a POST request to the given URL with the provided data.
    """
    auth_token = os.environ.get('AI_CF_AUTH_TOKEN')
    if not auth_token:
        raise ValueError("AI_CF_AUTH_TOKEN environment variable not set")

    headers = {
        'Content-Type': 'application/json',
        'X-Signature': create_signature(data, auth_token)
    }
    
    # Add retry logic
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise
            print(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            retry_delay *= 2

def main():
    # Give the server a moment to start up if needed
    time.sleep(1)
    
    # URL of the endpoint
    url = 'http://localhost:8000'

    # Request payload
    data = {
        "contents": "how are you doing?",
        "parameters": {"max_output_tokens": 1000}
    }

    # Send the request
    response = send_request(url, data)
    print("Response from server:", response)

if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {str(e)}")
        exit(1)
