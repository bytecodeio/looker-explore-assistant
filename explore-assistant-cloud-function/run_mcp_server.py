#!/usr/bin/env python3
"""
Script to run the MCP server with proper environment variable loading
"""

import os
import sys
from dotenv import load_dotenv

def main():
    # Load environment variables from .env file
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    load_dotenv(env_path)
    
    print("🚀 Starting MCP Server with environment configuration...")
    print(f"Project: {os.environ.get('PROJECT', 'Not set')}")
    print(f"Region: {os.environ.get('REGION', 'Not set')}")
    print(f"MCP Shared Secret: {'Set' if os.environ.get('MCP_SHARED_SECRET') else 'Not set'}")
    print(f"Looker Base URL: {os.environ.get('LOOKER_BASE_URL', 'Not set')}")
    print(f"Looker API Client ID: {'Set' if os.environ.get('LOOKER_API_CLIENT_ID') else 'Not set'}")
    print(f"Google Service Account: {'Set' if os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON') else 'Using default credentials'}")
    print("-" * 60)
    
    # Import and run the MCP server
    try:
        from mcp_server import create_mcp_flask_app
        
        app = create_mcp_flask_app()
        port = int(os.environ.get("PORT", 8001))
        
        print(f"🌐 MCP Server starting on http://localhost:{port}")
        print("📋 Available endpoints:")
        print(f"  - Health: http://localhost:{port}/mcp/health")
        print(f"  - Token Exchange: http://localhost:{port}/mcp/token-exchange")
        print("-" * 60)
        
        app.run(debug=True, host="0.0.0.0", port=port)
        
    except ImportError as e:
        print(f"❌ Failed to import MCP server: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to start MCP server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
