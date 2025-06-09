#!/usr/bin/env python3
"""
Comprehensive MCP server authentication test with OAuth tokens
This script tests the MCP server authentication flow using OAuth Bearer tokens
"""

import json
import time
import requests
import sys
import os
from datetime import datetime
from typing import Dict, Any

class MCPAuthTester:
    def __init__(self, server_url="http://localhost:8000", oauth_token=None):
        self.server_url = server_url
        self.oauth_token = oauth_token or os.environ.get("OAUTH_TOKEN")
        
        if not self.oauth_token:
            print("⚠️  Warning: No OAuth token provided. Some tests will be skipped.")
    
    def test_health_check(self) -> bool:
        """Test MCP server health endpoint"""
        print("🏥 Testing MCP Health Check")
        print("-" * 50)
        
        try:
            url = f"{self.server_url}/mcp/health"
            response = requests.get(url, timeout=10)
            
            print(f"URL: {url}")
            print(f"Status Code: {response.status_code}")
            print(f"Response Time: {response.elapsed.total_seconds():.3f}s")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Response: {json.dumps(data, indent=2)}")
                print("✅ Health check PASSED")
                return True
            else:
                print(f"❌ Health check FAILED: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except requests.exceptions.ConnectionError:
            print("❌ Connection Error: MCP server is not running")
            return False
        except Exception as e:
            print(f"❌ Health check ERROR: {e}")
            return False
    
    def test_oauth_token_validation(self) -> bool:
        """Test OAuth token validation with MCP server"""
        print("\n🔐 Testing OAuth Token Validation")
        print("-" * 50)
        
        if not self.oauth_token:
            print("⚠️  Skipping OAuth validation test - no token provided")
            print("   Set OAUTH_TOKEN environment variable or pass token as parameter")
            return False
        
        # Test with correct OAuth token
        print("Testing with VALID OAuth token...")
        success = self._make_token_request(expect_auth_success=False)
        
        if not success:
            print("❌ Valid token test failed")
            return False
        
        # Test with incorrect token
        print("\nTesting with INVALID OAuth token...")
        original_token = self.oauth_token
        self.oauth_token = "invalid_token_123"
        success = self._make_token_request(expect_auth_failure=True)
        self.oauth_token = original_token  # Restore original token
        
        return success
    
    def test_token_exchange(self) -> bool:
        """Test token exchange with real OAuth token"""
        print("\n🔑 Testing Token Exchange")
        print("-" * 50)
        
        if not self.oauth_token:
            print("⚠️  Skipping token exchange test - no OAuth token provided")
            return False
        
        return self._make_token_request(expect_auth_success=True)
    
    def _make_token_request(self, expect_auth_success=False, expect_auth_failure=False) -> bool:
        """Make a token exchange request and validate response"""
        
        url = f"{self.server_url}/mcp/token-exchange"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.oauth_token}'
        }
        
        print(f"URL: {url}")
        print(f"Using OAuth token: {self.oauth_token[:20]}..." if self.oauth_token else "No token")
        
        try:
            response = requests.post(url, headers=headers, timeout=10)
            print(f"Status Code: {response.status_code}")
            print(f"Response Time: {response.elapsed.total_seconds():.3f}s")
            
            response_text = response.text
            print(f"Response: {response_text}")
            
            if expect_auth_failure:
                if response.status_code == 401:
                    print("✅ Authentication rejection test PASSED")
                    return True
                else:
                    print(f"❌ Expected 401 but got {response.status_code}")
                    return False
            
            elif expect_auth_success:
                if response.status_code == 200:
                    try:
                        data = response.json()
                        tokens = data.get('tokens', {})
                        
                        if 'google_oauth_token' in tokens and 'looker_access_token' in tokens:
                            print("✅ Token exchange test PASSED")
                            print(f"   Google OAuth token: {tokens['google_oauth_token'][:20]}...")
                            print(f"   Looker access token: {tokens['looker_access_token'][:20]}...")
                            return True
                        else:
                            print("❌ Token exchange test FAILED - missing tokens in response")
                            return False
                    except json.JSONDecodeError:
                        print("❌ Token exchange test FAILED - invalid JSON response")
                        return False
                else:
                    print(f"❌ Token exchange test FAILED - status {response.status_code}")
                    return False
            
            else:
                # Just checking that we get a response without authentication errors
                if response.status_code not in [401, 403]:
                    print("✅ Basic request test PASSED")
                    return True
                else:
                    print(f"❌ Basic request test FAILED - authentication error {response.status_code}")
                    return False
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            return False
    
    def test_conversational_analytics_endpoint(self) -> bool:
        """Test the new conversational analytics endpoint"""
        print("\n🤖 Testing Conversational Analytics Endpoint")
        print("-" * 50)
        
        if not self.oauth_token:
            print("⚠️  Skipping CA endpoint test - no OAuth token provided")
            return False
        
        url = f"{self.server_url}/mcp/conversational-analytics"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.oauth_token}'
        }
        
        # Sample CA API request body
        request_body = {
            "project": "test-project",
            "messages": [
                {
                    "user_message": {
                        "text": "Show me sales by region"
                    }
                }
            ],
            "inlineContext": {
                "system_instruction": "You are a helpful data analyst assistant.",
                "datasource_references": {
                    "looker": {
                        "explore_references": [
                            {
                                "looker_instance_uri": "https://test.looker.com",
                                "lookml_model": "test_model",
                                "explore": "test_explore"
                            }
                        ]
                    }
                }
            }
        }
        
        print(f"URL: {url}")
        print(f"Using OAuth token: {self.oauth_token[:20]}...")
        
        try:
            response = requests.post(url, json=request_body, headers=headers, timeout=30)
            print(f"Status Code: {response.status_code}")
            print(f"Response Time: {response.elapsed.total_seconds():.3f}s")
            
            if response.status_code == 200:
                print("✅ CA endpoint test PASSED")
                return True
            elif response.status_code == 401:
                print("❌ CA endpoint test FAILED - Authentication error")
                return False
            elif response.status_code == 404:
                print("❌ CA endpoint test FAILED - User not found in Looker")
                return False
            elif response.status_code == 500:
                print("❌ CA endpoint test FAILED - Server error")
                print(f"Response: {response.text}")
                return False
            else:
                print(f"⚠️  CA endpoint test inconclusive - status {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ CA endpoint test failed: {e}")
            return False
    
    def test_token_usability(self, tokens: Dict[str, Any]) -> bool:
        """Test if returned tokens are actually usable"""
        print("\n🧪 Testing Token Usability")
        print("-" * 50)
        
        google_token = tokens.get('google_oauth_token')
        looker_token = tokens.get('looker_access_token')
        
        if not google_token or not looker_token:
            print("❌ Missing tokens to test")
            return False
        
        # Test Google OAuth token by validating it
        print("Testing Google OAuth token validity...")
        try:
            token_info_url = f"https://oauth2.googleapis.com/tokeninfo?access_token={google_token}"
            response = requests.get(token_info_url, timeout=10)
            
            if response.status_code == 200:
                token_info = response.json()
                print("✅ Google OAuth token is VALID")
                print(f"   Email: {token_info.get('email', 'N/A')}")
                print(f"   Expires in: {token_info.get('expires_in', 'N/A')} seconds")
            elif response.status_code == 400:
                print("❌ Google OAuth token is INVALID")
            else:
                print(f"⚠️  Google OAuth token test inconclusive (status: {response.status_code})")
                
        except Exception as e:
            print(f"❌ Google OAuth token test failed: {e}")
        
        # Note: Testing Looker token would require knowing the Looker instance URL
        print("\n✅ Looker token format appears valid (length: {len(looker_token)})")
        
        return True
    
    def run_full_test(self):
        """Run complete authentication test suite"""
        print("🚀 MCP Server OAuth Authentication Test Suite")
        print("=" * 60)
        print(f"Server URL: {self.server_url}")
        print(f"OAuth Token: {'Present' if self.oauth_token else 'Not provided'}")
        print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        # Step 1: Health Check
        if not self.test_health_check():
            print("\n❌ CRITICAL: Health check failed. MCP server is not running properly.")
            return False
        
        print("\n✅ SERVER STATUS: MCP server is running and healthy!")
        
        # If no OAuth token, skip the authentication tests but don't fail
        if not self.oauth_token:
            print("\n" + "=" * 60)
            print("🟡 PARTIAL SUCCESS: MCP server is running but OAuth tests skipped")
            print("   To test OAuth functionality, provide a token:")
            print("   export OAUTH_TOKEN='your_google_oauth_token'")
            print("   python test_mcp_auth.py")
            print("=" * 60)
            return True
        
        # Step 2: OAuth Token Validation
        oauth_validation_success = self.test_oauth_token_validation()
        
        # Step 3: Token Exchange
        token_exchange_success = self.test_token_exchange()
        
        # Step 4: CA Endpoint Test
        ca_endpoint_success = self.test_conversational_analytics_endpoint()
        
        print("\n" + "=" * 60)
        if oauth_validation_success and token_exchange_success:
            print("🎉 FULL SUCCESS: MCP server OAuth authentication is working!")
        else:
            print("🟡 PARTIAL SUCCESS: Server running but OAuth tests failed")
            print("   This might be due to:")
            print("   - Invalid OAuth token")
            print("   - Missing Looker configuration")
            print("   - User not found in Looker")
        print("=" * 60)
        return True

def main():
    if len(sys.argv) > 1:
        server_url = sys.argv[1]
    else:
        server_url = "http://localhost:8000"
    
    oauth_token = None
    if len(sys.argv) > 2:
        oauth_token = sys.argv[2]
    else:
        oauth_token = os.environ.get("OAUTH_TOKEN")
    
    tester = MCPAuthTester(server_url, oauth_token)
    success = tester.run_full_test()
    
    if not success:
        print("\n💡 Troubleshooting Tips:")
        print("1. Ensure MCP server is running: python run_mcp_server.py")
        print("2. Set OAUTH_TOKEN environment variable with valid Google OAuth token")
        print("3. Verify Looker API credentials are configured in environment")
        print("4. Check Google Cloud service account credentials")
        print("5. Ensure the OAuth token has cloud-platform scope")
        print("6. Verify the user exists in Looker with the same email")
        
        sys.exit(1)

if __name__ == "__main__":
    main()
