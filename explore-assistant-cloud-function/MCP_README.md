# MCP Server for Looker Explore Assistant

## Overview

The Model Context Protocol (MCP) Server provides secure credential proxying for non-admin Looker users who need to access the ConversationalAnalytics API. This server acts as an intermediary that:

1. Validates Looker extension session context
2. Generates appropriate service account tokens for Google Cloud APIs
3. Provides scoped Looker access tokens for data access
4. Ensures secure token exchange without exposing admin credentials

## Problem Solved

Non-admin Looker users cannot:
- Use the `login_user()` API method (admin-only)
- Create API keys or access tokens directly
- Access ConversationalAnalytics API with their session credentials

The MCP server solves this by providing a secure proxy that uses service account credentials to generate the necessary tokens while maintaining user context and security.

## Architecture

```
Extension (Non-Admin User)
    ↓ Session Context + HMAC Signature
MCP Server (Service Account)
    ↓ Validates Session + Generates Tokens
ConversationalAnalytics API
    ↓ Returns Results
Extension (Display to User)
```

## API Endpoints

### POST /mcp/token-exchange

Exchanges Looker session context for Google OAuth and Looker access tokens.

**Request:**
```json
{
  "sessionInfo": {
    "userId": "user123",
    "lookerHost": "https://company.looker.com",
    "timestamp": 1640995200000,
    "extensionId": "explore-assistant"
  }
}
```

**Headers:**
- `Content-Type: application/json`
- `X-Signature: <HMAC-SHA256 signature>`

**Response (Success):**
```json
{
  "tokens": {
    "google_oauth_token": "ya29.a0...",
    "looker_access_token": "abc123...",
    "expires_at": 1640998800
  }
}
```

**Response (Error):**
```json
{
  "error": "Invalid session"
}
```

### GET /mcp/health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "mcp-server",
  "timestamp": 1640995200.0
}
```

## Security

### HMAC Signature Validation
All requests must include an `X-Signature` header containing an HMAC-SHA256 signature of the request body using the shared secret.

### Session Validation
- Validates user ID and Looker host
- Checks timestamp (max 5 minutes old)
- Verifies extension context

### Token Scoping
- Google OAuth tokens have minimal required scopes
- Looker access tokens are user-scoped where possible
- Tokens expire after 1 hour

## Environment Variables

### Required
- `PROJECT`: GCP Project ID
- `MCP_SHARED_SECRET`: Shared secret for HMAC validation
- `GOOGLE_SERVICE_ACCOUNT_JSON`: Service account credentials (JSON string)
- `LOOKER_API_CLIENT_ID`: Looker API client ID
- `LOOKER_API_CLIENT_SECRET`: Looker API client secret
- `LOOKER_BASE_URL`: Base URL for Looker instance

### Optional
- `REGION`: GCP region (default: us-central1)
- `PORT`: Local development port (default: 8001)

## Deployment

### Local Development
```bash
# Install dependencies
pip install -r mcp_requirements.txt

# Set environment variables
export PROJECT="your-gcp-project"
export MCP_SHARED_SECRET="your-secret-key"
export GOOGLE_SERVICE_ACCOUNT_JSON='{"type": "service_account", ...}'
export LOOKER_API_CLIENT_ID="your-looker-client-id"
export LOOKER_API_CLIENT_SECRET="your-looker-client-secret"
export LOOKER_BASE_URL="https://your-company.looker.com"

# Run server
python mcp_server.py
```

### Google Cloud Function
```bash
# Deploy as Cloud Function
gcloud functions deploy mcp-server \
  --runtime python39 \
  --trigger-http \
  --entry-point mcp_cloud_function_entrypoint \
  --source . \
  --set-env-vars PROJECT=your-gcp-project \
  --set-secrets MCP_SHARED_SECRET=mcp-secret:latest \
  --set-secrets GOOGLE_SERVICE_ACCOUNT_JSON=service-account-json:latest \
  --set-secrets LOOKER_API_CLIENT_ID=looker-client-id:latest \
  --set-secrets LOOKER_API_CLIENT_SECRET=looker-client-secret:latest \
  --set-env-vars LOOKER_BASE_URL=https://your-company.looker.com
```

## Testing

Run the test suite:
```bash
python test_mcp.py
```

The test suite will:
1. Test the health check endpoint
2. Test token exchange with sample session data
3. Validate response formats and error handling

## Integration with Extension

The extension's `useConversationalAnalytics` hook automatically detects MCP server configuration and falls back to direct Looker SDK calls if unavailable:

```typescript
// Extension settings
mcp_server_url: "https://your-mcp-server.com"
mcp_shared_secret: "your-shared-secret"
```

## Limitations and Future Improvements

### Current Limitations
- Basic session validation (timestamp and required fields only)
- Limited user impersonation capabilities
- No replay attack protection (nonces)

### Planned Improvements
1. **Enhanced Session Validation**: JWT-based session tokens
2. **Nonce Support**: Prevent replay attacks
3. **User Impersonation**: Proper user-scoped token generation
4. **Rate Limiting**: Protect against abuse
5. **Audit Logging**: Track token usage and access patterns
6. **Token Caching**: Reduce API calls for repeated requests

## Troubleshooting

### Common Issues

**"Invalid signature" error:**
- Verify MCP_SHARED_SECRET matches between extension and server
- Check request body encoding (JSON without formatting)

**"Failed to obtain Google OAuth token":**
- Verify service account has cloud-platform scope
- Check GOOGLE_SERVICE_ACCOUNT_JSON format

**"Failed to obtain Looker access token":**
- Verify Looker API credentials
- Check LOOKER_BASE_URL format
- Ensure service account has necessary Looker permissions

**"Invalid session" error:**
- Check session timestamp (must be within 5 minutes)
- Verify userId and lookerHost are provided
- Ensure extension context is valid

## Security Considerations

1. **Shared Secret Management**: Use GCP Secret Manager for production
2. **Network Security**: Deploy behind load balancer with TLS
3. **Access Control**: Restrict function invocation to authorized sources
4. **Monitoring**: Enable Cloud Logging and monitoring
5. **Token Lifecycle**: Implement proper token expiration and refresh

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review Cloud Function logs
3. Test with the provided test suite
4. Verify environment variables and secrets
