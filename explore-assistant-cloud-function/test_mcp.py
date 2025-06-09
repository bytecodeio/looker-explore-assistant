#!/usr/bin/env python3
"""
Test script for the MCP server token exchange functionality
"""

import json
import hmac
import time
import requests
from typing import Dict, Any

def generate_mcp_signature(secret: str, data: Dict[str, Any]) -> str:
    """Generate HMAC signature for MCP request"""
    # Convert to JSON bytes the same way the server expects
    message = json.dumps(data, separators=(',', ':'))
    message_bytes = message.encode('utf-8')
    secret_bytes = secret.encode('utf-8')
    
    hmac_obj = hmac.new(secret_bytes, message_bytes, 'sha256')
    return hmac_obj.hexdigest()

def test_token_exchange(server_url: str, shared_secret: str):
    """Test the MCP token exchange endpoint"""
    
    # Create test session info
    session_info = {
        'userId': 'test_user_123',
        'lookerHost': 'https://test.looker.com',
        'timestamp': int(time.time() * 1000),  # Current timestamp in milliseconds
        'extensionId': 'explore-assistant'
    }
    
    request_data = {
        'sessionInfo': session_info
    }
    
    # Generate signature
    signature = generate_mcp_signature(shared_secret, request_data)
    
    # Debug: print the exact JSON being signed
    test_json = json.dumps(request_data, separators=(',', ':'))
    print(f"JSON being signed: {test_json}")
    print(f"Generated signature: {signature}")
    
    # Make request
    url = f"{server_url}/mcp/token-exchange"
    headers = {
        'Content-Type': 'application/json',
        'X-Signature': signature
    }
    
    print(f"Testing MCP token exchange at: {url}")
    print(f"Session info: {json.dumps(session_info, indent=2)}")
    
    try:
        # Send the request with custom JSON to match signature
        json_data = json.dumps(request_data, separators=(',', ':'))
        response = requests.post(url, data=json_data, headers=headers)
        
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        
        if response.headers.get('content-type', '').startswith('application/json'):
            response_data = response.json()
            print(f"Response data: {json.dumps(response_data, indent=2)}")
            
            if response.status_code == 200 and 'tokens' in response_data:
                tokens = response_data['tokens']
                print("\n✅ Token exchange successful!")
                print(f"Google OAuth token length: {len(tokens.get('google_oauth_token', ''))}")
                print(f"Looker access token length: {len(tokens.get('looker_access_token', ''))}")
                print(f"Expires at: {time.ctime(tokens.get('expires_at', 0))}")
            else:
                print(f"\n❌ Token exchange failed: {response_data.get('error', 'Unknown error')}")
        else:
            print(f"Response text: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def test_health_check(server_url: str):
    """Test the MCP health check endpoint"""
    url = f"{server_url}/mcp/health"
    
    print(f"\nTesting MCP health check at: {url}")
    
    try:
        response = requests.get(url)
        print(f"Response status: {response.status_code}")
        
        if response.headers.get('content-type', '').startswith('application/json'):
            response_data = response.json()
            print(f"Response data: {json.dumps(response_data, indent=2)}")
            
            if response.status_code == 200:
                print("✅ Health check successful!")
            else:
                print("❌ Health check failed!")
        else:
            print(f"Response text: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def main():
    # Configuration
    server_url = "http://localhost:8002"  # Default local development URL
    shared_secret = "test_mcp_secret_123"  # Default test secret
    
    print("🧪 MCP Server Test Suite")
    print("=" * 50)
    
    # Test health check first
    test_health_check(server_url)
    
    # Test token exchange
    test_token_exchange(server_url, shared_secret)
    
    print("\n" + "=" * 50)
    print("🏁 Test suite completed")

if __name__ == "__main__":
    main()
