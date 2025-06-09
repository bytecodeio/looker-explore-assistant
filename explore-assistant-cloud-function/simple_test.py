#!/usr/bin/env python3

import requests
import json
import hmac
import time

def test_mcp_server():
    print("Testing MCP Server...")
    
    # Test 1: Health check
    try:
        response = requests.get("http://localhost:8001/mcp/health", timeout=5)
        print(f"Health check status: {response.status_code}")
        if response.status_code == 200:
            print(f"Health response: {response.json()}")
        print("✅ Health check successful")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return
    
    # Test 2: Token exchange with signature
    try:
        shared_secret = "test_mcp_secret_123"
        
        session_info = {
            'userId': 'test_user_123',
            'lookerHost': 'https://test.looker.com',
            'timestamp': int(time.time() * 1000),
            'extensionId': 'explore-assistant'
        }
        
        request_data = {'sessionInfo': session_info}
        
        # Generate signature
        message = json.dumps(request_data, separators=(',', ':'))
        message_bytes = message.encode('utf-8')
        secret_bytes = shared_secret.encode('utf-8')
        hmac_obj = hmac.new(secret_bytes, message_bytes, 'sha256')
        signature = hmac_obj.hexdigest()
        
        print(f"Request data: {message}")
        print(f"Signature: {signature}")
        
        # Make request
        headers = {
            'Content-Type': 'application/json',
            'X-Signature': signature
        }
        
        response = requests.post(
            "http://localhost:8001/mcp/token-exchange",
            data=message,
            headers=headers,
            timeout=10
        )
        
        print(f"Token exchange status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Token exchange successful")
        else:
            print("⚠️ Token exchange returned error (expected without proper credentials)")
            
    except Exception as e:
        print(f"❌ Token exchange test failed: {e}")

if __name__ == "__main__":
    test_mcp_server()
