# Dashboard Summarizer Server - Google Cloud Deployment

This server provides secure Vertex AI API passthrough for dashboard summarization with mandatory Google OAuth and Looker user verification.

## Features

- **Proper Google ID Token Verification**: Uses Google's `id_token.verify_oauth2_token` for secure authentication
- **Mandatory Looker User Verification**: Ensures only valid Looker users can access the service
- **Vertex AI Passthrough**: Secure proxy to Vertex AI API using service account credentials
- **No BigQuery Dependencies**: Simplified architecture focused on summarization tasks

## Prerequisites

### Required Tools
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) (gcloud)
- [Docker](https://docs.docker.com/get-docker/)
- A Google Cloud Project with billing enabled

### Required Permissions
Your Google Cloud account needs the following IAM roles:
- `Cloud Run Admin`
- `Cloud Build Editor`
- `Artifact Registry Admin`
- `Service Account User`
- `Vertex AI User`

## Setup Instructions

### 1. Create Google OAuth Client ID

To enable proper token verification, you need to create a Google OAuth client ID:

1. **Go to Google Cloud Console**
   - Navigate to [Google Cloud Console](https://console.cloud.google.com/)
   - Select your project

2. **Enable APIs**
   ```bash
   gcloud services enable iamcredentials.googleapis.com
   gcloud services enable oauth2.googleapis.com
   ```

3. **Configure OAuth Consent Screen**
   - Go to APIs & Services → OAuth consent screen
   - Choose "External" user type
   - Fill in required fields:
     - App name: "Dashboard Summarizer"
     - User support email: Your email
     - Developer contact: Your email
   - Add scopes: `email`, `profile`, `openid`
   - Add test users (if needed)

4. **Create OAuth Client ID**
   - Go to APIs & Services → Credentials
   - Click "Create Credentials" → "OAuth client ID"
   - Application type: "Web application"
   - Name: "Dashboard Summarizer Client"
   - Authorized JavaScript origins: Add your frontend domain(s)
   - Copy the Client ID (you'll need this for deployment)

### 2. Set Up Looker API Credentials

1. **Access Looker Admin Panel**
   - Navigate to Admin → API
   - Click "New API3 Key"

2. **Create API Credentials**
   - User: Select a user with appropriate permissions
   - Copy the Client ID and Client Secret

3. **Required Permissions**
   The API user needs:
   - `see_users` (to verify user existence)
   - Basic user lookup permissions

### 3. Deploy the Service

1. **Clone and Navigate**
   ```bash
   cd dashboard-summarizer-cloud-function
   ```

2. **Configure Deployment**
   Edit `deploy_to_cloudrun.sh`:
   ```bash
   PROJECT_ID="your-gcp-project-id"
   REGION="us-central1"
   ```

3. **Run Deployment**
   ```bash
   chmod +x deploy_to_cloudrun.sh
   ./deploy_to_cloudrun.sh
   ```

4. **Update Environment Variables**
   After deployment, update with your actual credentials:
   ```bash
   gcloud run services update dashboard-summarizer \
       --region us-central1 \
       --set-env-vars "GOOGLE_OAUTH_CLIENT_ID=your-oauth-client-id" \
       --set-env-vars "LOOKERSDK_BASE_URL=https://your-company.looker.com" \
       --set-env-vars "LOOKERSDK_CLIENT_ID=your-looker-client-id" \
       --set-env-vars "LOOKERSDK_CLIENT_SECRET=your-looker-client-secret"
   ```

## Environment Variables

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| `PROJECT` | GCP Project ID | Yes | `my-project-123` |
| `REGION` | GCP Region | Yes | `us-central1` |
| `VERTEX_MODEL` | Vertex AI model | No | `gemini-2.0-flash-001` |
| `GOOGLE_OAUTH_CLIENT_ID` | Google OAuth client ID | Yes | `123456789-abc.apps.googleusercontent.com` |
| `LOOKERSDK_BASE_URL` | Looker instance URL | Yes | `https://company.looker.com` |
| `LOOKERSDK_CLIENT_ID` | Looker API client ID | Yes | `abc123def456` |
| `LOOKERSDK_CLIENT_SECRET` | Looker API client secret | Yes | `xyz789uvw012` |

## API Endpoints

### Health Check
```
GET /health
```
Returns service status and configuration.

### Vertex AI Passthrough
```
POST /vertex-passthrough
Authorization: Bearer <google-id-token>
Content-Type: application/json

{
  "contents": [...],
  "generationConfig": {...}
}
```

**Authentication Flow:**
1. Validates Google ID token signature and expiration
2. Extracts user email from verified token
3. Verifies user exists and is active in Looker
4. Proxies request to Vertex AI using service account
5. Returns response with user context

## Security Features

### Google ID Token Verification
- Uses Google's official `id_token.verify_oauth2_token()` method
- Validates token signature against Google's public keys
- Checks token expiration and issuer
- Ensures email is verified by Google

### Looker User Verification
- Mandatory check that user exists in Looker
- Verifies user is not disabled
- Fails request if user not found in Looker

### Service Account Security
- Uses Google Cloud service account for Vertex AI access
- No user credentials passed to Vertex AI
- Secure token exchange pattern

## Testing

### Test Health Endpoint
```bash
SERVICE_URL=$(gcloud run services describe dashboard-summarizer --region us-central1 --format='value(status.url)')
curl $SERVICE_URL/health
```

### Test Authentication
```bash
# Get a Google ID token (from your frontend application)
curl -X POST $SERVICE_URL/vertex-passthrough \
  -H "Authorization: Bearer YOUR_GOOGLE_ID_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [
      {
        "role": "user",
        "parts": [{"text": "Hello, test message"}]
      }
    ]
  }'
```

## Troubleshooting

### Common Issues

1. **"Invalid token" errors**
   - Verify `GOOGLE_OAUTH_CLIENT_ID` is correctly set
   - Ensure the token was issued for your client ID
   - Check token hasn't expired

2. **"User not found in Looker" errors**
   - Verify Looker SDK configuration
   - Check user exists in Looker with the same email
   - Ensure user is not disabled

3. **"Project or location not configured" errors**
   - Verify `PROJECT` and `REGION` environment variables
   - Ensure Vertex AI API is enabled

### Debug Mode
Enable debug logging:
```bash
gcloud run services update dashboard-summarizer \
    --region us-central1 \
    --set-env-vars "LOG_LEVEL=DEBUG"
```

### View Logs
```bash
gcloud run logs tail dashboard-summarizer --region us-central1
```

## Production Considerations

1. **Remove Public Access**
   ```bash
   gcloud run services remove-iam-policy-binding dashboard-summarizer \
       --region us-central1 \
       --member "allUsers" \
       --role "roles/run.invoker"
   ```

2. **Use Secret Manager**
   ```bash
   # Store sensitive values in Secret Manager
   echo "your-secret" | gcloud secrets create looker-client-secret --data-file=-
   
   # Update service to use secrets
   gcloud run services update dashboard-summarizer \
       --region us-central1 \
       --update-secrets LOOKERSDK_CLIENT_SECRET=looker-client-secret:latest
   ```

3. **Configure Resource Limits**
   ```bash
   gcloud run services update dashboard-summarizer \
       --region us-central1 \
       --memory 1Gi \
       --cpu 1 \
       --min-instances 0 \
       --max-instances 10
   ```

## Cost Optimization

- Uses `--min-instances 0` by default to minimize costs
- Scales to zero when not in use
- Monitor usage with Cloud Monitoring
- Consider committed use discounts for production workloads
