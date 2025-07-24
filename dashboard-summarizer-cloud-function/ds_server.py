# MIT License

# Copyright (c) 2023 Looker Data Sciences, Inc.

# Dashboard Summarizer Server for Looker
# This server provides secure token verification and Vertex AI API passthrough
# for dashboard summarization tasks with mandatory Looker user verification.

import os
import time
import json
import base64
import logging
import traceback
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from flask import Flask, request, Response, jsonify
from flask_cors import CORS
from google.auth import default
from google.auth.transport.requests import Request
from google.oauth2 import service_account, id_token
import looker_sdk

logging.basicConfig(level=logging.INFO)

# Initialize environment variables
project = os.environ.get("PROJECT")
location = os.environ.get("REGION", "us-central1")
vertex_model = os.environ.get("VERTEX_MODEL", "gemini-2.0-flash-001")
google_oauth_client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")

def get_response_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
        "Access-Control-Max-Age": "3600",
        "Access-Control-Allow-Credentials": "false"
    }

def verify_google_id_token(bearer_token: str) -> Optional[Dict[str, Any]]:
    """Verify Google ID token using Google's verification service"""
    try:
        logging.info("Verifying Google ID token")
        
        # Remove 'Bearer ' prefix if present
        if bearer_token.lower().startswith('bearer '):
            bearer_token = bearer_token[7:]
        
        # Remove any whitespace
        bearer_token = bearer_token.strip()
        
        # Check if Google OAuth client ID is configured
        if not google_oauth_client_id:
            logging.error("GOOGLE_OAUTH_CLIENT_ID environment variable is not set")
            return None
        
        try:
            # Verify the token using Google's verification service
            # This validates the signature, expiration, and issuer
            idinfo = id_token.verify_oauth2_token(
                bearer_token, 
                Request(), 
                google_oauth_client_id
            )
            
            # Verify the issuer
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                logging.error(f"Invalid token issuer: {idinfo.get('iss')}")
                return None
            
            # Check if token has expired
            current_time = time.time()
            if idinfo.get('exp', 0) < current_time:
                logging.error("Token has expired")
                return None
            
            # Extract user information
            email = idinfo.get('email')
            if not email:
                logging.error("No email found in verified token")
                return None
            
            # Verify email is verified by Google
            if not idinfo.get('email_verified', False):
                logging.error("Email not verified by Google")
                return None
            
            logging.info(f"Successfully verified Google ID token for user: {email}")
            return {
                'email': email,
                'sub': idinfo.get('sub'),
                'iss': idinfo.get('iss'),
                'aud': idinfo.get('aud'),
                'exp': idinfo.get('exp'),
                'iat': idinfo.get('iat'),
                'email_verified': idinfo.get('email_verified'),
                'name': idinfo.get('name'),
                'given_name': idinfo.get('given_name'),
                'family_name': idinfo.get('family_name'),
                'picture': idinfo.get('picture')
            }
                
        except ValueError as ve:
            # Invalid token
            logging.error(f"Invalid Google ID token: {ve}")
            return None
        except Exception as e:
            logging.error(f"Error during token verification: {e}")
            return None
        
    except Exception as e:
        logging.error(f"Error verifying Google ID token: {e}")
        return None

def get_looker_sdk():
    """Initialize and return Looker SDK instance using environment variables"""
    try:
        logging.info("Initializing Looker SDK using LOOKERSDK_ environment variables...")
        
        # Check if required environment variables are set
        base_url = os.environ.get('LOOKERSDK_BASE_URL')
        client_id = os.environ.get('LOOKERSDK_CLIENT_ID')
        client_secret = os.environ.get('LOOKERSDK_CLIENT_SECRET')
        
        logging.info(f"LOOKERSDK_BASE_URL: {base_url}")
        logging.info(f"LOOKERSDK_CLIENT_ID: {client_id[:8]}..." if client_id else "LOOKERSDK_CLIENT_ID: None")
        logging.info(f"LOOKERSDK_CLIENT_SECRET: {'***' if client_secret else 'None'}")
        
        if not base_url:
            raise Exception("LOOKERSDK_BASE_URL environment variable is not set")
        if not client_id:
            raise Exception("LOOKERSDK_CLIENT_ID environment variable is not set")
        if not client_secret:
            raise Exception("LOOKERSDK_CLIENT_SECRET environment variable is not set")
        
        # Initialize SDK using environment variables (no config file needed)
        sdk = looker_sdk.init40()
        logging.info("Looker SDK initialized successfully")
        
        # Test the SDK by trying to get current user info
        try:
            user = sdk.me()
            logging.info(f"Looker SDK test successful - logged in as: {user.email}")
        except Exception as test_error:
            logging.warning(f"Looker SDK test failed: {test_error}")
            # Don't fail completely, just log the warning
        
        return sdk
        
    except Exception as e:
        logging.error(f"Error initializing Looker SDK: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return None

def verify_looker_user(email: str) -> Optional[Dict[str, Any]]:
    """Verify that the user exists in Looker (mandatory for access)"""
    try:
        logging.info(f"Verifying Looker user: {email}")
        
        # Initialize Looker SDK
        sdk = get_looker_sdk()
        if not sdk:
            logging.error("Failed to initialize Looker SDK")
            return None
        
        # Search for user by email using SDK
        users = sdk.search_users(email=email)
        
        if not users:
            logging.error(f"No Looker user found with email: {email}")
            return None
        
        # Convert the first user object to dict
        user = users[0]
        user_dict = {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_disabled': user.is_disabled,
            'role_ids': user.role_ids
        }
        
        # Check if user is disabled
        if user_dict.get('is_disabled'):
            logging.error(f"Looker user is disabled: {email}")
            return None
        
        logging.info(f"Verified Looker user: {user_dict['id']} - {user_dict['email']}")
        return user_dict
        
    except Exception as e:
        logging.error(f"Error verifying Looker user: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return None

def call_vertex_ai_api_with_service_account(request_body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Call Vertex AI API using service account credentials"""
    try:
        if not project or not location:
            logging.error("Project or location not configured for Vertex AI API")
            return None
        
        # Get service account credentials
        credentials, _ = default()
        auth_req = Request()
        credentials.refresh(auth_req)
        access_token = credentials.token
        
        # Construct Vertex AI API URL
        vertex_api_url = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/publishers/google/models/{vertex_model}:generateContent"
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Log the request for debugging
        logging.info(f"Calling Vertex AI API with service account: {vertex_api_url}")
        
        response = requests.post(vertex_api_url, headers=headers, json=request_body)
        
        if not response.ok:
            logging.error(f"Vertex AI API call failed: {response.status_code} - {response.text}")
            return None
        
        logging.info("Vertex AI API call successful")
        return response.json()
        
    except Exception as e:
        logging.error(f"Error calling Vertex AI API: {e}")
        return None

def create_ds_flask_app():
    """Create Flask app with dashboard summarizer endpoints"""
    app = Flask(__name__)
    CORS(app)
    
    # Log registered endpoints
    logging.info("Registering Dashboard Summarizer endpoints...")
    
    @app.route("/health", methods=["GET"])
    def health_check():
        """Health check endpoint"""
        return jsonify({
            'status': 'healthy',
            'service': 'dashboard-summarizer',
            'timestamp': time.time(),
            'project': project,
            'location': location,
            'model': vertex_model,
            'endpoints': ['/health (GET)', '/vertex-passthrough (POST)']
        }), 200, get_response_headers()
    
    logging.info("Registered endpoint: /health")
    
    @app.route("/vertex-passthrough", methods=["POST", "OPTIONS"])
    def vertex_passthrough():
        """Vertex AI passthrough endpoint with mandatory token and Looker user verification"""
        logging.info(f"Received {request.method} request to vertex-passthrough endpoint")
        
        # Handle OPTIONS requests first, without authentication
        if request.method == "OPTIONS":
            logging.info("Handling OPTIONS preflight request for vertex-passthrough")
            response = Response()
            response.headers.update(get_response_headers())
            response.status_code = 200
            return response
        
        try:
            logging.info("Processing POST request to vertex-passthrough...")
            
            # Get Bearer token from Authorization header
            auth_header = request.headers.get("Authorization")
            logging.info(f"Authorization header present: {bool(auth_header)}")
            
            # Check for Authorization header
            if not auth_header or not auth_header.lower().startswith("bearer "):
                logging.error("Missing or invalid Authorization header")
                response = jsonify({'error': 'Missing or invalid Authorization header'})
                response.headers.update(get_response_headers())
                response.status_code = 401
                return response
            
            # Verify the Google ID token
            token_info = verify_google_id_token(auth_header)
            if not token_info:
                logging.error("Invalid or expired token")
                response = jsonify({'error': 'Invalid or expired token'})
                response.headers.update(get_response_headers())
                response.status_code = 401
                return response
            
            user_email = token_info.get('email')
            logging.info(f"Token verified for user: {user_email}")
            
            # Mandatory Looker user verification
            looker_user = verify_looker_user(user_email)
            if not looker_user:
                logging.error(f"User not found or disabled in Looker: {user_email}")
                response = jsonify({
                    'error': 'Access denied: User not found or disabled in Looker',
                    'user_email': user_email
                })
                response.headers.update(get_response_headers())
                response.status_code = 403
                return response
            
            logging.info(f"Looker user verified: {looker_user['id']} - {looker_user['email']}")
            
            # Get the request body
            request_data = request.get_json()
            if not request_data:
                logging.error("Missing request body")
                response = jsonify({'error': 'Missing request body'})
                response.headers.update(get_response_headers())
                response.status_code = 400
                return response
            
            logging.info(f"Request data keys: {list(request_data.keys())}")
            
            # Call Vertex AI API with the request data
            vertex_response = call_vertex_ai_api_with_service_account(request_data)
            
            if not vertex_response:
                logging.error("Failed to get response from Vertex AI")
                response = jsonify({'error': 'Failed to process request with Vertex AI'})
                response.headers.update(get_response_headers())
                response.status_code = 500
                return response
            
            # Add user context to response
            vertex_response['user_context'] = {
                'email': user_email,
                'looker_user_id': looker_user['id'],
                'verified_at': time.time()
            }
            
            logging.info("Vertex AI passthrough request completed successfully")
            response = jsonify(vertex_response)
            response.headers.update(get_response_headers())
            response.status_code = 200
            return response
            
        except Exception as e:
            logging.error(f"Vertex AI passthrough error: {e}")
            logging.error(f"Error type: {type(e)}")
            logging.error(f"Traceback: {traceback.format_exc()}")
            
            try:
                response = jsonify({
                    'error': 'Internal server error',
                    'message': str(e),
                    'timestamp': time.time()
                })
                response.headers.update(get_response_headers())
                response.status_code = 500
                return response
            except Exception as json_error:
                logging.error(f"Failed to send JSON error response: {json_error}")
                response = Response("Internal server error", status=500)
                response.headers.update(get_response_headers())
                return response
    
    logging.info("Registered endpoint: /vertex-passthrough (POST)")
    
    @app.route("/cors", methods=["OPTIONS"])
    def cors_preflight():
        """Dedicated CORS preflight endpoint"""
        logging.info("Handling dedicated CORS preflight request")
        response = Response()
        response.headers.update(get_response_headers())
        response.status_code = 200
        return response
    
    @app.errorhandler(500)
    def internal_server_error(error):
        logging.error(f"Internal server error: {error}")
        response = jsonify({
            'error': 'Internal server error',
            'timestamp': time.time()
        })
        response.headers.update(get_response_headers())
        response.status_code = 500
        return response
    
    logging.info("Dashboard Summarizer Flask app created")
    return app

# For running directly as a Flask app (Cloud Run)
if __name__ == "__main__":
    app = create_ds_flask_app()
    port = int(os.environ.get("PORT", 8080))
    logging.info(f"Starting Dashboard Summarizer Flask app on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
