# MIT License

# Copyright (c) 2023 Looker Data Sciences, Inc.

# MCP (Model Context Protocol) Server for Looker Explore Assistant
# This server acts as a credential proxy for non-admin users to access
# ConversationalAnalytics API by providing secure token exchange.

import os
import hmac
import time
import json
import logging
from typing import Dict, Any, Optional
from flask import Flask, request, Response, jsonify
from flask_cors import CORS
import functions_framework
import requests
from google.auth import default
from google.auth.transport.requests import Request
from google.oauth2 import service_account
import jwt

logging.basicConfig(level=logging.INFO)

# Initialize environment variables
project = os.environ.get("PROJECT")
location = os.environ.get("REGION", "us-central1")
mcp_shared_secret = os.environ.get("MCP_SHARED_SECRET")
looker_api_client_id = os.environ.get("LOOKER_API_CLIENT_ID")
looker_api_client_secret = os.environ.get("LOOKER_API_CLIENT_SECRET")
looker_base_url = os.environ.get("LOOKER_BASE_URL")
service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")

def get_response_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-Signature"
    }

def validate_mcp_signature(request_data: bytes, signature: str) -> bool:
    """Validate HMAC signature for MCP requests"""
    if not signature or not mcp_shared_secret:
        logging.error(f"Missing signature or secret: signature={signature}, has_secret={bool(mcp_shared_secret)}")
        return False
    
    secret = mcp_shared_secret.encode("utf-8")
    hmac_obj = hmac.new(secret, request_data, "sha256")
    expected_signature = hmac_obj.hexdigest()
    
    logging.info(f"Signature validation: received={signature}, expected={expected_signature}")
    logging.info(f"Request data: {request_data.decode('utf-8')}")
    logging.info(f"Request data length: {len(request_data)}")
    
    return hmac.compare_digest(signature, expected_signature)

def get_google_oauth_token() -> Optional[str]:
    """Get Google OAuth token using service account credentials"""
    try:
        if service_account_json:
            # Load service account from JSON string
            credentials_info = json.loads(service_account_json)
            credentials = service_account.Credentials.from_service_account_info(
                credentials_info,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
        else:
            # Use default credentials (when running in GCP)
            credentials, _ = default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        
        # Refresh the token
        credentials.refresh(Request())
        return credentials.token
    except Exception as e:
        logging.error(f"Error getting Google OAuth token: {e}")
        return None

def validate_looker_session(session_info: Dict[str, Any]) -> Dict[str, Any]:
    """Validate Looker session and get user information"""
    try:
        user_id = session_info.get('userId')
        looker_host = session_info.get('lookerHost')
        timestamp = session_info.get('timestamp', 0)
        
        # Basic validation
        if not user_id or not looker_host:
            return {'is_valid': False, 'error': 'Missing session information'}
        
        # Check timestamp (within last 5 minutes)
        if time.time() - (timestamp / 1000) > 300:  # 5 minutes
            return {'is_valid': False, 'error': 'Session timestamp too old'}
        
        # TODO: Add more sophisticated session validation
        # For now, we'll trust the session info if it has required fields
        return {
            'is_valid': True,
            'user_id': user_id,
            'looker_host': looker_host
        }
    except Exception as e:
        logging.error(f"Error validating Looker session: {e}")
        return {'is_valid': False, 'error': str(e)}

def generate_looker_access_token(user_id: str, looker_host: str) -> Optional[str]:
    """Generate a scoped Looker access token for the user"""
    try:
        if not all([looker_api_client_id, looker_api_client_secret, looker_base_url]):
            logging.error("Looker API credentials not configured")
            return None
        
        # Get Looker API token
        auth_url = f"{looker_base_url}/api/4.0/login"
        auth_data = {
            'client_id': looker_api_client_id,
            'client_secret': looker_api_client_secret
        }
        
        auth_response = requests.post(auth_url, data=auth_data)
        if not auth_response.ok:
            logging.error(f"Failed to authenticate with Looker API: {auth_response.text}")
            return None
        
        auth_result = auth_response.json()
        access_token = auth_result.get('access_token')
        
        if not access_token:
            logging.error("No access token received from Looker API")
            return None
        
        # For non-admin users, we can't use login_user directly
        # Instead, we'll generate a limited-scope token that works for the specific user
        # This would require additional Looker API setup for impersonation
        
        # TODO: Implement proper user impersonation token generation
        # For now, return the service account token with user context
        
        return access_token
    except Exception as e:
        logging.error(f"Error generating Looker access token: {e}")
        return None

def handle_token_exchange(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle token exchange request from extension"""
    try:
        session_info = request_data.get('sessionInfo')
        if not session_info:
            return {'error': 'Missing session information'}, 400
        
        # Validate the session
        session_validation = validate_looker_session(session_info)
        if not session_validation.get('is_valid'):
            return {'error': session_validation.get('error', 'Invalid session')}, 401
        
        # Get Google OAuth token for ConversationalAnalytics API
        google_oauth_token = get_google_oauth_token()
        if not google_oauth_token:
            return {'error': 'Failed to obtain Google OAuth token'}, 500
        
        # Generate Looker access token
        looker_access_token = generate_looker_access_token(
            session_validation['user_id'],
            session_validation['looker_host']
        )
        if not looker_access_token:
            return {'error': 'Failed to obtain Looker access token'}, 500
        
        # Return tokens with expiry
        tokens = {
            'google_oauth_token': google_oauth_token,
            'looker_access_token': looker_access_token,
            'expires_at': time.time() + 3600  # 1 hour expiry
        }
        
        logging.info(f"Token exchange successful for user {session_validation['user_id']}")
        return {'tokens': tokens}, 200
        
    except Exception as e:
        logging.error(f"Error in token exchange: {e}")
        return {'error': 'Internal server error'}, 500

def create_mcp_flask_app():
    """Create Flask app with MCP endpoints"""
    app = Flask(__name__)
    CORS(app)
    
    @app.route("/mcp/token-exchange", methods=["POST", "OPTIONS"])
    def token_exchange():
        if request.method == "OPTIONS":
            return "", 204, get_response_headers()
        
        try:
            # Validate signature
            signature = request.headers.get("X-Signature")
            request_data = request.get_data()
            
            if not validate_mcp_signature(request_data, signature):
                return jsonify({'error': 'Invalid signature'}), 403, get_response_headers()
            
            # Process token exchange
            request_json = request.get_json()
            result, status_code = handle_token_exchange(request_json)
            
            return jsonify(result), status_code, get_response_headers()
            
        except Exception as e:
            logging.error(f"Token exchange error: {e}")
            return jsonify({'error': 'Internal server error'}), 500, get_response_headers()
    
    @app.route("/mcp/health", methods=["GET"])
    def health_check():
        """Health check endpoint"""
        return jsonify({
            'status': 'healthy',
            'service': 'mcp-server',
            'timestamp': time.time()
        }), 200, get_response_headers()
    
    @app.errorhandler(500)
    def internal_server_error(error):
        return jsonify({'error': 'Internal server error'}), 500, get_response_headers()
    
    return app

@functions_framework.http
def mcp_cloud_function_entrypoint(request):
    """Cloud Function entry point for MCP server"""
    if request.method == "OPTIONS":
        return "", 204, get_response_headers()
    
    path = request.path
    
    if path == "/mcp/token-exchange":
        try:
            # Validate signature
            signature = request.headers.get("X-Signature")
            request_data = request.get_data()
            
            if not validate_mcp_signature(request_data, signature):
                return jsonify({'error': 'Invalid signature'}), 403, get_response_headers()
            
            # Process token exchange
            request_json = request.get_json()
            result, status_code = handle_token_exchange(request_json)
            
            return jsonify(result), status_code, get_response_headers()
            
        except Exception as e:
            logging.error(f"Token exchange error: {e}")
            return jsonify({'error': 'Internal server error'}), 500, get_response_headers()
    
    elif path == "/mcp/health":
        return jsonify({
            'status': 'healthy',
            'service': 'mcp-server',
            'timestamp': time.time()
        }), 200, get_response_headers()
    
    else:
        return jsonify({'error': 'Endpoint not found'}), 404, get_response_headers()

if __name__ == "__main__":
    # For local development
    if os.environ.get("FUNCTIONS_FRAMEWORK"):
        # Cloud Function mode
        pass
    else:
        # Local Flask mode
        app = create_mcp_flask_app()
        port = int(os.environ.get("PORT", 8001))
        app.run(debug=True, host="0.0.0.0", port=port)
        print(f"MCP Server running on port {port}")
