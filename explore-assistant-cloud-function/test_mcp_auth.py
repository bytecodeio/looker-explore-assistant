#!/usr/bin/env python3
"""
Comprehensive MCP server authentication test
This script tests the MCP server authentication flow step by step
"""

import json
import hmac
import time
import requests
import sys
from datetime import datetime
from typing import Dict, Any

class MCPAuthTester:
    def __init__(self, server_url="http://localhost:8001", shared_secret="test_mcp_secret_123"):
        self.server_url = server_url
        self.shared_secret = shared_secret
        
    def generate_signature(self, data: Dict[str, Any]) -> str:
        """Generate HMAC signature for MCP request"""
        message = json.dumps(data, separators=(',', ':'))
        message_bytes = message.encode('utf-8')
        secret_bytes = self.shared_secret.encode('utf-8')
        hmac_obj = hmac.new(secret_bytes, message_bytes, 'sha256')
        return hmac_obj.hexdigest()
    
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
    
    def test_signature_validation(self) -> bool:
        """Test signature validation without credentials"""
        print("\n🔐 Testing Signature Validation")
        print("-" * 50)
        
        session_info = {
            'userId': 'test_user_123',
            'lookerHost': 'https://test.looker.com',
            'timestamp': int(time.time() * 1000),
            'extensionId': 'explore-assistant'
        }
        
        request_data = {'sessionInfo': session_info}
        
        # Test with correct signature
        print("Testing with CORRECT signature...")
        signature = self.generate_signature(request_data)
        success = self._make_token_request(request_data, signature, expect_auth_success=False)
        
        if not success:
            return False
        
        # Test with incorrect signature
        print("\nTesting with INCORRECT signature...")
        wrong_signature = "wrong_signature_123"
        success = self._make_token_request(request_data, wrong_signature, expect_signature_failure=True)
        
        return success
    
    def test_looker_authentication(self) -> bool:
        """Test Looker authentication with real credentials"""
        print("\n🔑 Testing Looker Authentication")
        print("-" * 50)
        
        session_info = {
            'userId': 'test_user_123',
            'lookerHost': 'https://insightsdev.ossd.co:19999',
            'timestamp': int(time.time() * 1000),
            'extensionId': 'explore-assistant'
        }
        
        request_data = {'sessionInfo': session_info}
        signature = self.generate_signature(request_data)
        
        return self._make_token_request(request_data, signature, expect_auth_success=True)
    
    def _make_token_request(self, request_data: Dict, signature: str, 
                          expect_auth_success=False, expect_signature_failure=False) -> bool:
        """Make a token exchange request and validate response"""
        
        url = f"{self.server_url}/mcp/token-exchange"
        headers = {
            'Content-Type': 'application/json',
            'X-Signature': signature
        }
        
        json_data = json.dumps(request_data, separators=(',', ':'))
        
        print(f"URL: {url}")
        print(f"Request Data: {json_data}")
        print(f"Signature: {signature}")
        
        try:
            response = requests.post(url, data=json_data, headers=headers, timeout=30)
            
            print(f"Status Code: {response.status_code}")
            print(f"Response Time: {response.elapsed.total_seconds():.3f}s")
            
            if response.headers.get('content-type', '').startswith('application/json'):
                response_data = response.json()
                print(f"Response: {json.dumps(response_data, indent=2)}")
                
                if expect_signature_failure:
                    if response.status_code == 403 and 'signature' in response_data.get('error', '').lower():
                        print("✅ Signature validation correctly REJECTED invalid signature")
                        return True
                    else:
                        print("❌ Expected signature failure but got different response")
                        return False
                
                elif expect_auth_success:
                    if response.status_code == 200 and 'tokens' in response_data:
                        tokens = response_data['tokens']
                        print("✅ Token exchange SUCCESSFUL!")
                        print(f"   - Google OAuth token: {'✅ Present' if tokens.get('google_oauth_token') else '❌ Missing'}")
                        print(f"   - Looker access token: {'✅ Present' if tokens.get('looker_access_token') else '❌ Missing'}")
                        
                        # Validate token format
                        google_token = tokens.get('google_oauth_token', '')
                        looker_token = tokens.get('looker_access_token', '')
                        
                        if google_token and len(google_token) > 10:
                            print(f"   - Google token length: {len(google_token)} characters")
                        if looker_token and len(looker_token) > 10:
                            print(f"   - Looker token length: {len(looker_token)} characters")
                        
                        expires_at = tokens.get('expires_at', 0)
                        if expires_at:
                            expiry_time = datetime.fromtimestamp(expires_at)
                            print(f"   - Expires at: {expiry_time}")
                        
                        return True
                    else:
                        error_msg = response_data.get('error', 'Unknown error')
                        print(f"❌ Token exchange FAILED: {error_msg}")
                        
                        # Provide specific guidance based on error
                        if 'Google OAuth token' in error_msg:
                            print("   💡 Check Google Cloud credentials and service account setup")
                        elif 'Looker access token' in error_msg:
                            print("   💡 Check Looker API credentials (client ID/secret)")
                        elif 'session' in error_msg.lower():
                            print("   💡 Check session validation logic")
                        
                        return False
                else:
                    # Just checking that signature validation works, expect some auth error
                    if response.status_code == 403 and 'signature' in response_data.get('error', '').lower():
                        print("❌ Signature validation failed (this means signature is wrong)")
                        return False
                    elif response.status_code in [500, 401]:
                        print("✅ Signature validation PASSED (got auth error as expected)")
                        return True
                    else:
                        print(f"✅ Signature validation PASSED (got status {response.status_code})")
                        return True
            else:
                print(f"Response Text: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            print("❌ Request TIMEOUT (server might be processing)")
            return False
        except requests.exceptions.ConnectionError:
            print("❌ Connection Error: Cannot reach MCP server")
            return False
        except Exception as e:
            print(f"❌ Request ERROR: {e}")
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
        
        # Test Google OAuth token by making a simple API call
        print("Testing Google OAuth token...")
        try:
            headers = {'Authorization': f'Bearer {google_token}'}
            # Test with a simple Google API call (like getting project info)
            response = requests.get('https://cloudresourcemanager.googleapis.com/v1/projects', 
                                  headers=headers, timeout=10)
            
            if response.status_code == 200:
                print("✅ Google OAuth token is VALID")
            elif response.status_code == 401:
                print("❌ Google OAuth token is INVALID (401 Unauthorized)")
            else:
                print(f"⚠️  Google OAuth token test inconclusive (status: {response.status_code})")
                
        except Exception as e:
            print(f"❌ Google OAuth token test failed: {e}")
        
        # Test Looker token
        print("\nTesting Looker access token...")
        try:
            headers = {'Authorization': f'Bearer {looker_token}'}
            looker_url = 'https://insightsdev.ossd.co:19999/api/4.0/user'
            response = requests.get(looker_url, headers=headers, timeout=10, verify=False)
            
            if response.status_code == 200:
                print("✅ Looker access token is VALID")
            elif response.status_code == 401:
                print("❌ Looker access token is INVALID (401 Unauthorized)")
            else:
                print(f"⚠️  Looker access token test inconclusive (status: {response.status_code})")
                
        except Exception as e:
            print(f"❌ Looker access token test failed: {e}")
        
        return True
    
    def run_full_test(self):
        """Run complete authentication test suite"""
        print("🚀 MCP Server Authentication Test Suite")
        print("=" * 60)
        print(f"Server URL: {self.server_url}")
        print(f"Shared Secret: {'*' * len(self.shared_secret)}")
        print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        # Step 1: Health Check
        if not self.test_health_check():
            print("\n❌ CRITICAL: Health check failed. MCP server is not running properly.")
            return False
        
        # Step 2: Signature Validation
        if not self.test_signature_validation():
            print("\n❌ CRITICAL: Signature validation failed.")
            return False
        
        # Step 3: Full Authentication
        if not self.test_looker_authentication():
            print("\n❌ CRITICAL: Looker authentication failed.")
            return False
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED! MCP server authentication is working.")
        print("=" * 60)
        return True

def main():
    if len(sys.argv) > 1:
        server_url = sys.argv[1]
    else:
        server_url = "http://localhost:8001"
    
    if len(sys.argv) > 2:
        shared_secret = sys.argv[2]
    else:
        shared_secret = "test_mcp_secret_123"
    
    tester = MCPAuthTester(server_url, shared_secret)
    success = tester.run_full_test()
    
    if not success:
        print("\n💡 Troubleshooting Tips:")
        print("1. Ensure MCP server is running: python mcp_server.py")
        print("2. Check environment variables are set correctly")
        print("3. Verify Looker API credentials are valid")
        print("4. Check Google Cloud service account credentials")
        print("5. Ensure network connectivity to external APIs")
        
        sys.exit(1)

if __name__ == "__main__":
    main()
