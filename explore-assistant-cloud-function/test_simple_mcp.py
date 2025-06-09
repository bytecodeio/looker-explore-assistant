#!/usr/bin/env python3
"""
Simple test for MCP token exchange
"""

import json
import hmac
import time
import requests

def test_token_exchange():
    """Test the MCP token exchange endpoint"""
    server_url = "http://localhost:8002"
    shared_secret = "test_mcp_secret_123"
    
    # Create test session info
    session_info = {
        'userId': 'test_user_123',
        'lookerHost': 'https://insightsdev.ossd.co:19999',
        'timestamp': int(time.time() * 1000),
        'extensionId': 'explore-assistant'
    }
    
    request_data = {
        'sessionInfo': session_info
    }
    
    # Generate signature
    message = json.dumps(request_data, separators=(',', ':'))
    message_bytes = message.encode('utf-8')
    secret_bytes = shared_secret.encode('utf-8')
    hmac_obj = hmac.new(secret_bytes, message_bytes, 'sha256')
    signature = hmac_obj.hexdigest()
    
    print(f"🧪 Testing MCP Token Exchange")
    print(f"Server URL: {server_url}/mcp/token-exchange")
    print(f"User ID: {session_info['userId']}")
    print(f"Looker Host: {session_info['lookerHost']}")
    print(f"Generated signature: {signature}")
    print("-" * 60)
    
    # Make request
    url = f"{server_url}/mcp/token-exchange"
    headers = {
        'Content-Type': 'application/json',
        'X-Signature': signature
    }
    
    try:
        json_data = json.dumps(request_data, separators=(',', ':'))
        response = requests.post(url, data=json_data, headers=headers)
        
        print(f"Response Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.headers.get('content-type', '').startswith('application/json'):
            response_data = response.json()
            print(f"Response Data:")
            print(json.dumps(response_data, indent=2))
            
            if response.status_code == 200 and 'tokens' in response_data:
                tokens = response_data['tokens']
                print("\n✅ SUCCESS: Token exchange completed!")
                print(f"   - Google OAuth token length: {len(tokens.get('google_oauth_token', ''))}")
                print(f"   - Looker access token length: {len(tokens.get('looker_access_token', ''))}")
                print(f"   - Expires at: {time.ctime(tokens.get('expires_at', 0))}")
            else:
                print(f"\n❌ FAILED: {response_data.get('error', 'Unknown error')}")
        else:
            print(f"Response Text: {response.text}")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    test_token_exchange()
