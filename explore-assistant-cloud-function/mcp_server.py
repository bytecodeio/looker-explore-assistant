# MIT License

# Copyright (c) 2023 Looker Data Sciences, Inc.

# MCP (Model Context Protocol) Server for Looker Explore Assistant
# This server acts as a credential proxy for non-admin users to access
# ConversationalAnalytics API by providing secure token exchange.

import os
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

logging.basicConfig(level=logging.INFO)

# Initialize environment variables
project = os.environ.get("PROJECT")
location = os.environ.get("REGION", "us-central1")
looker_api_client_id = os.environ.get("LOOKER_API_CLIENT_ID")
looker_api_client_secret = os.environ.get("LOOKER_API_CLIENT_SECRET")
looker_base_url = os.environ.get("LOOKER_BASE_URL")
service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")

def get_response_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization"
    }

def validate_oauth_token(bearer_token: str) -> Optional[Dict[str, Any]]:
    """Validate OAuth token using GCP token_info endpoint"""
    try:
        # Remove 'Bearer ' prefix if present
        if bearer_token.startswith('Bearer '):
            bearer_token = bearer_token[7:]
        
        # Call Google's token info endpoint
        token_info_url = f"https://oauth2.googleapis.com/tokeninfo?access_token={bearer_token}"
        response = requests.get(token_info_url)
        print(f"Validating token: {bearer_token}")
        logging.info(f"Validating token: {bearer_token}")
        # Check if the response is successful
        print(f"Response status code: {response.status_code}")
        logging.info(f"Response status code: {response.status_code}")
        print(f"Response text: {response.text}")
        logging.info(f"Response text: {response.text}")

        if not response.ok:
            logging.error(f"Token validation failed: {response.status_code} - {response.text}")
            return None
        
        token_info = response.json()
        
        # Check if token has required scope
        scopes = token_info.get('scope', '').split()
        required_scope = 'https://www.googleapis.com/auth/cloud-platform'
        if required_scope not in scopes:
            logging.error(f"Token missing required scope: {required_scope}")
            return None
        
        # Extract user information
        email = token_info.get('email')
        if not email:
            logging.error("No email found in token info")
            return None
        
        logging.info(f"Token validated for user: {email}")
        return {
            'email': email,
            'user_id': token_info.get('sub'),
            'expires_in': token_info.get('expires_in', 0)
        }
        
    except Exception as e:
        logging.error(f"Error validating OAuth token: {e}")
        return None

def get_service_account_oauth_token() -> Optional[str]:
    """Get Google OAuth token using service account credentials for CA API calls"""
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
        logging.error(f"Error getting service account OAuth token: {e}")
        return None

def get_looker_api_token() -> Optional[str]:
    """Get Looker API admin token for user operations"""
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
        
        return access_token
    except Exception as e:
        logging.error(f"Error getting Looker API token: {e}")
        return None

def find_looker_user_by_email(email: str, admin_token: str) -> Optional[Dict[str, Any]]:
    """Find Looker user by email address"""
    try:
        # Search for user by email
        search_url = f"{looker_base_url}/api/4.0/users/search"
        headers = {'Authorization': f'token {admin_token}'}
        params = {'email': email}
        
        response = requests.get(search_url, headers=headers, params=params)
        if not response.ok:
            logging.error(f"Failed to search for user: {response.status_code} - {response.text}")
            return None
        
        users = response.json()
        if not users:
            logging.error(f"No Looker user found with email: {email}")
            return None
        
        user = users[0]  # Take the first match
        logging.info(f"Found Looker user: {user.get('id')} - {user.get('email')}")
        return user
        
    except Exception as e:
        logging.error(f"Error finding Looker user: {e}")
        return None

def generate_user_looker_token(user_id: int, admin_token: str) -> Optional[str]:
    """Generate a Looker access token for a specific user using login_user"""
    try:
        # Use login_user to switch to the user's context
        login_url = f"{looker_base_url}/api/4.0/login/{user_id}"
        headers = {'Authorization': f'token {admin_token}'}
        
        response = requests.post(login_url, headers=headers)
        if not response.ok:
            logging.error(f"Failed to login as user {user_id}: {response.status_code} - {response.text}")
            return None
        
        login_result = response.json()
        user_token = login_result.get('access_token')
        
        if not user_token:
            logging.error(f"No access token received for user {user_id}")
            return None
        
        logging.info(f"Successfully generated token for user {user_id}")
        return user_token
        
    except Exception as e:
        logging.error(f"Error generating user Looker token: {e}")
        return None

def handle_token_exchange(oauth_token_info: Dict[str, Any]) -> Dict[str, Any]:
    """Handle token exchange request from extension"""
    try:
        user_email = oauth_token_info['email']
        
        # Get admin Looker API token
        admin_token = get_looker_api_token()
        if not admin_token:
            return {'error': 'Failed to obtain Looker admin token'}, 500
        
        # Find the user in Looker by email
        looker_user = find_looker_user_by_email(user_email, admin_token)
        if not looker_user:
            return {'error': f'User {user_email} not found in Looker'}, 404
        
        # Generate user-specific Looker token
        user_looker_token = generate_user_looker_token(looker_user['id'], admin_token)
        if not user_looker_token:
            return {'error': 'Failed to obtain user Looker token'}, 500
        
        # Get service account OAuth token for ConversationalAnalytics API infrastructure
        service_account_token = get_service_account_oauth_token()
        if not service_account_token:
            return {'error': 'Failed to obtain service account OAuth token'}, 500
        
        # Return tokens with expiry
        # Note: The user_looker_token will be used as the OAuth token for CA API calls
        # This ensures the CA API sees requests as coming from the specific Looker user
        tokens = {
            'google_oauth_token': user_looker_token,  # Use Looker user token for CA API
            'looker_access_token': user_looker_token,  # Also return for direct Looker API calls
            'service_account_token': service_account_token,  # For infrastructure needs
            'expires_at': time.time() + 3600  # 1 hour expiry
        }
        
        logging.info(f"Token exchange successful for user {user_email} (Looker ID: {looker_user['id']})")
        return {'tokens': tokens}, 200
        
    except Exception as e:
        logging.error(f"Error in token exchange: {e}")
        return {'error': 'Internal server error'}, 500

def call_conversational_analytics_api(user_looker_token: str, request_body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Call Conversational Analytics API with proper authentication
    
    Args:
        user_looker_token: The Looker user token for accessing Looker data
        request_body: The request body for the CA API
    """
    try:
        if not project or not location:
            logging.error("Project or location not configured for CA API")
            return None
        
        # Get service account OAuth token for Google Cloud API calls
        service_account_token = get_service_account_oauth_token()
        if not service_account_token:
            logging.error("Failed to obtain service account OAuth token for CA API")
            return None
        
        # Add Looker credentials to the request body if not already present
        if 'inlineContext' in request_body and 'datasource_references' in request_body['inlineContext']:
            if 'looker' in request_body['inlineContext']['datasource_references']:
                # Add the Looker user token to the credentials section
                if 'credentials' not in request_body['inlineContext']['datasource_references']['looker']:
                    request_body['inlineContext']['datasource_references']['looker']['credentials'] = {
                        'oauth': {
                            'token': {
                                'access_token': user_looker_token
                            }
                        }
                    }
                    logging.info("Added Looker credentials to request body")
        
        # Use the Conversational Analytics API endpoint (not regular Vertex AI)
        ca_api_url = f"https://geminidataanalytics.googleapis.com/v1alpha/projects/{project}/locations/{location}:chat"
        
        headers = {
            'Authorization': f'Bearer {service_account_token}',
            'Content-Type': 'application/json'
        }
        
        logging.info(f"Making CA API request to: {ca_api_url}")
        response = requests.post(ca_api_url, headers=headers, json=request_body)
        
        if not response.ok:
            logging.error(f"CA API call failed: {response.status_code} - {response.text}")
            return None
        
        logging.info("CA API call successful")
        return response.json()
        
    except Exception as e:
        logging.error(f"Error calling Conversational Analytics API: {e}")
        return None

def create_mcp_flask_app():
    """Create Flask app with MCP endpoints"""
    app = Flask(__name__)
    CORS(app)
    
    # Log registered endpoints
    logging.info("Registering MCP endpoints...")
    
    @app.route("/mcp/conversational-analytics", methods=["POST", "OPTIONS"])
    def conversational_analytics():
        if request.method == "OPTIONS":
            return "", 204, get_response_headers()
        
        try:
            # Get Bearer token from Authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return jsonify({'error': 'Missing or invalid Authorization header'}), 401, get_response_headers()
            
            # Validate OAuth token
            oauth_token_info = validate_oauth_token(auth_header)
            if not oauth_token_info:
                return jsonify({'error': 'Invalid OAuth token'}), 401, get_response_headers()
            
            # Get user's Looker token
            user_email = oauth_token_info['email']
            admin_token = get_looker_api_token()
            if not admin_token:
                return jsonify({'error': 'Failed to obtain Looker admin token'}), 500, get_response_headers()
            
            looker_user = find_looker_user_by_email(user_email, admin_token)
            if not looker_user:
                return jsonify({'error': f'User {user_email} not found in Looker'}), 404, get_response_headers()
            
            user_looker_token = generate_user_looker_token(looker_user['id'], admin_token)
            if not user_looker_token:
                return jsonify({'error': 'Failed to obtain user Looker token'}), 500, get_response_headers()
            
            # Get the CA API request body from the request
            request_body = request.get_json()
            if not request_body:
                return jsonify({'error': 'Missing request body'}), 400, get_response_headers()
            
            # Call CA API using the user's Looker token
            ca_response = call_conversational_analytics_api(user_looker_token, request_body)
            if not ca_response:
                return jsonify({'error': 'CA API call failed'}), 500, get_response_headers()
            
            return jsonify(ca_response), 200, get_response_headers()
            
        except Exception as e:
            logging.error(f"Conversational Analytics error: {e}")
            return jsonify({'error': 'Internal server error'}), 500, get_response_headers()
    
    logging.info("Registered endpoint: /mcp/conversational-analytics")
    
    @app.route("/mcp/health", methods=["GET"])
    def health_check():
        """Health check endpoint"""
        return jsonify({
            'status': 'healthy',
            'service': 'mcp-server',
            'timestamp': time.time(),
            'endpoints': ['/mcp/conversational-analytics', '/mcp/health']
        }), 200, get_response_headers()
    
    logging.info("Registered endpoint: /mcp/health")
    
    @app.errorhandler(500)
    def internal_server_error(error):
        return jsonify({'error': 'Internal server error'}), 500, get_response_headers()
    
    # Remove HTTPS redirect for local development - causes issues with SSL
    # @app.before_request  
    # def redirect_to_https():
    #     if not request.is_secure:
    #         return jsonify({'error': 'Please use HTTPS'}), 400
    
    logging.info("MCP Flask app created with endpoints: /mcp/conversational-analytics, /mcp/health")
    return app

@functions_framework.http
def mcp_cloud_function_entrypoint(request):
    """Cloud Function entry point for MCP server"""
    if request.method == "OPTIONS":
        return "", 204, get_response_headers()
    
    path = request.path
    
    if path == "/mcp/conversational-analytics":
        try:
            # Get Bearer token from Authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return jsonify({'error': 'Missing or invalid Authorization header'}), 401, get_response_headers()
            
            # Validate OAuth token
            oauth_token_info = validate_oauth_token(auth_header)
            if not oauth_token_info:
                return jsonify({'error': 'Invalid OAuth token'}), 401, get_response_headers()
            
            # Get user's Looker token
            user_email = oauth_token_info['email']
            admin_token = get_looker_api_token()
            if not admin_token:
                return jsonify({'error': 'Failed to obtain Looker admin token'}), 500, get_response_headers()
            
            looker_user = find_looker_user_by_email(user_email, admin_token)
            if not looker_user:
                return jsonify({'error': f'User {user_email} not found in Looker'}), 404, get_response_headers()
            
            user_looker_token = generate_user_looker_token(looker_user['id'], admin_token)
            if not user_looker_token:
                return jsonify({'error': 'Failed to obtain user Looker token'}), 500, get_response_headers()
            
            # Get the CA API request body from the request
            request_body = request.get_json()
            if not request_body:
                return jsonify({'error': 'Missing request body'}), 400, get_response_headers()
            
            # Call CA API using the user's Looker token
            ca_response = call_conversational_analytics_api(user_looker_token, request_body)
            if not ca_response:
                return jsonify({'error': 'CA API call failed'}), 500, get_response_headers()
            
            return jsonify(ca_response), 200, get_response_headers()
            
        except Exception as e:
            logging.error(f"Conversational Analytics error: {e}")
            return jsonify({'error': 'Internal server error'}), 500, get_response_headers()
    
    elif path == "/mcp/health":
        return jsonify({
            'status': 'healthy',
            'service': 'mcp-server',
            'timestamp': time.time(),
            'endpoints': ['/mcp/conversational-analytics', '/mcp/health']
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
        port = int(os.environ.get("PORT", 8000))  # Changed from 8001 to 8000
        
        logging.info(f"Starting MCP Server on port {port}")
        logging.info("Available endpoints:")
        logging.info("  - POST /mcp/conversational-analytics")
        logging.info("  - GET  /mcp/health")
        
        # Enable HTTPS for local development
        use_https = os.environ.get("USE_HTTPS", "false").lower() == "true"
        
        if use_https:
            # For HTTPS, you'll need SSL certificates
            ssl_cert = os.environ.get("SSL_CERT_PATH", "cert.pem")
            ssl_key = os.environ.get("SSL_KEY_PATH", "key.pem")
            
            if os.path.exists(ssl_cert) and os.path.exists(ssl_key):
                logging.info(f"Starting HTTPS server on port {port}")
                app.run(debug=True, host="0.0.0.0", port=port, ssl_context=(ssl_cert, ssl_key))
            else:
                logging.warning("SSL certificates not found, falling back to HTTP")
                app.run(debug=True, host="0.0.0.0", port=port)
        else:
            # Run without SSL for local development
            app.run(debug=True, host="0.0.0.0", port=port)
        
        print(f"MCP Server running on port {port}")
