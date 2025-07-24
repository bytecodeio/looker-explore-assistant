# Looker Explore Assistant MCP Server - GCP Deployment Guide

This guide provides comprehensive instructions for deploying the Looker Explore Assistant Model Context Protocol (MCP) Server to Google Cloud Platform using Cloud Run.

## Overview

The MCP Server acts as a secure proxy for Looker Explore Assistant, enabling natural language queries to be converted into Looker explore parameters. It leverages Google Vertex AI for language processing and integrates with your Looker instance.

## Architecture

```
User Request → Cloud Run MCP Server → Vertex AI (Gemini) → Looker API → Visualization
```

**Key Components:**
- **Flask Application**: REST API server handling MCP requests
- **Vertex AI Integration**: Gemini 2.0 Flash for natural language processing
- **Looker SDK**: Direct integration with Looker API
- **BigQuery**: Storage for golden query examples and suggested queries

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

### Looker Requirements
- Looker Admin access to create API credentials
- Looker instance with accessible API endpoints

## Quick Start

### 1. Clone and Navigate
```bash
git clone <repository-url>
cd explore-assistant-cloud-function
```

### 2. Configure Project Settings
Edit the `deploy_to_cloudrun.sh` script:
```bash
# Update these variables at the top of the file
PROJECT_ID="your-gcp-project-id"        # Required: Your GCP project ID
REGION="us-central1"                    # Optional: Your preferred region
SERVICE_NAME="looker-explore-assistant-mcp"  # Optional: Service name
```

### 3. Deploy to Cloud Run
```bash
# Make the script executable
chmod +x deploy_to_cloudrun.sh

# Run the deployment
./deploy_to_cloudrun.sh
```

### 4. Configure Environment Variables
After deployment, update with your actual credentials:
```bash
# Make the update script executable
chmod +x update_env_vars.sh

# Run the configuration script
./update_env_vars.sh
```

## Detailed Configuration

### Environment Variables

#### Required Configuration
| Variable | Description | How to Obtain |
|----------|-------------|---------------|
| `MCP_SHARED_SECRET` | Security token for MCP authentication | Generate a secure random string |
| `LOOKER_API_CLIENT_ID` | Looker API client ID | Create in Looker Admin → API |
| `LOOKER_API_CLIENT_SECRET` | Looker API client secret | Create in Looker Admin → API |
| `LOOKERSDK_BASE_URL` | Your Looker instance URL | Format: `https://your-company.looker.com` |

#### Optional Configuration
| Variable | Description | Default |
|----------|-------------|---------|
| `VERTEX_MODEL` | Vertex AI model to use | `gemini-2.0-flash-001` |
| `BQ_PROJECT_ID` | BigQuery project for examples | Same as `PROJECT` |
| `BQ_DATASET_ID` | BigQuery dataset for examples | `explore_assistant` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

### Creating Looker API Credentials

1. **Access Looker Admin Panel**
   - Navigate to Admin → API
   - Click "New API3 Key"

2. **Create API Credentials**
   - User: Select a user with appropriate permissions
   - Copy the Client ID and Client Secret
   - Note: Client Secret is only shown once

3. **Set Required Permissions**
   The API user needs:
   - `see_lookml`
   - `see_logs`
   - `explore`
   - `see_user_dashboards`

## Manual Deployment Steps

If you prefer manual deployment over the automated script:

### 1. Enable Required APIs
```bash
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable aiplatform.googleapis.com
```

### 2. Create Artifact Registry Repository
```bash
gcloud artifacts repositories create looker-explore-assistant-mcp \
    --repository-format=docker \
    --location=us-central1 \
    --description="Looker Explore Assistant MCP Server"
```

### 3. Build and Deploy
```bash
# Build the container
gcloud builds submit --tag us-central1-docker.pkg.dev/PROJECT_ID/looker-explore-assistant-mcp/mcp-server

# Deploy to Cloud Run
gcloud run deploy looker-explore-assistant-mcp \
    --image us-central1-docker.pkg.dev/PROJECT_ID/looker-explore-assistant-mcp/mcp-server \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --port 8080 \
    --memory 1Gi \
    --timeout 3600
```

## Post-Deployment Configuration

### Set Environment Variables
```bash
gcloud run services update looker-explore-assistant-mcp \
    --region us-central1 \
    --set-env-vars "LOOKER_API_CLIENT_ID=your_client_id" \
    --set-env-vars "LOOKER_API_CLIENT_SECRET=your_client_secret" \
    --set-env-vars "LOOKERSDK_BASE_URL=https://your-company.looker.com"
```

### Test the Deployment
```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe looker-explore-assistant-mcp --region us-central1 --format='value(status.url)')

# Test health endpoint
curl $SERVICE_URL/health

# Expected response: {"status": "healthy", "timestamp": "..."}
```

## BigQuery Setup (Optional)

For enhanced functionality with golden query examples:

### 1. Create Dataset
```bash
bq mk --dataset $PROJECT_ID:explore_assistant
```

### 2. Create Required Tables
The MCP server will automatically create these tables on first run:
- `bronze_queries`: Raw query history
- `silver_queries`: Curated query examples

## Security Considerations

### Production Security

#### Remove Public Access
```bash
gcloud run services remove-iam-policy-binding looker-explore-assistant-mcp \
    --region us-central1 \
    --member "allUsers" \
    --role "roles/run.invoker"
```

#### Add Specific Access
```bash
gcloud run services add-iam-policy-binding looker-explore-assistant-mcp \
    --region us-central1 \
    --member "user:admin@your-company.com" \
    --role "roles/run.invoker"
```

### Use Secret Manager
For production deployments, store sensitive values in Secret Manager:

```bash
# Create secrets
echo "your-client-secret" | gcloud secrets create looker-client-secret --data-file=-

# Update service to use secrets
gcloud run services update looker-explore-assistant-mcp \
    --region us-central1 \
    --update-secrets LOOKER_API_CLIENT_SECRET=looker-client-secret:latest
```

## Monitoring and Troubleshooting

### View Logs
```bash
# Real-time logs
gcloud run logs tail looker-explore-assistant-mcp --region us-central1

# Recent logs
gcloud run logs read looker-explore-assistant-mcp --region us-central1 --limit 100
```

### Common Issues

#### **Service won't start**
- Check logs for error messages
- Verify all required environment variables are set
- Ensure Looker credentials are correct

#### **Vertex AI errors**
- Verify project has Vertex AI API enabled
- Check service account has `aiplatform.user` role
- Confirm `PROJECT` and `REGION` environment variables

#### **Looker connection failures**
- Test Looker credentials manually
- Verify `LOOKERSDK_BASE_URL` format (include https://)
- Check Looker instance accessibility from Cloud Run

### Performance Tuning

#### Adjust Resources
```bash
gcloud run services update looker-explore-assistant-mcp \
    --region us-central1 \
    --memory 2Gi \
    --cpu 2 \
    --concurrency 80
```

#### Configure Scaling
```bash
gcloud run services update looker-explore-assistant-mcp \
    --region us-central1 \
    --min-instances 1 \
    --max-instances 10
```

## Cost Optimization

### Development Environment
- Use `--min-instances 0` to save costs
- Lower memory/CPU allocation
- Enable request timeout for unused instances

### Production Environment
- Set `--min-instances 1` for better response times
- Monitor usage with Cloud Monitoring
- Use committed use discounts for consistent workloads

## API Endpoints

Once deployed, the service provides these endpoints:

- `GET /health` - Health check
- `POST /` - Main MCP processing endpoint
- `POST /vertex-passthrough` - Direct Vertex AI proxy
- `OPTIONS /*` - CORS preflight handling

## Integration with Looker Extension

After deployment, update your Looker extension configuration:

1. **Update Frontend Configuration**
   ```typescript
   // In your Looker extension
   const MCP_SERVER_URL = "https://your-service-url.run.app";
   ```

2. **Configure CORS** (if needed)
   The service is configured to allow all origins. For production, consider restricting to your Looker domain.

## Support and Troubleshooting

### Debug Mode
Enable debug logging by setting:
```bash
gcloud run services update looker-explore-assistant-mcp \
    --region us-central1 \
    --set-env-vars "LOG_LEVEL=DEBUG"
```

### Health Checks
The service includes comprehensive health checks that verify:
- Flask application status
- Vertex AI connectivity
- Looker API accessibility
- BigQuery connectivity (if configured)

### Getting Help
1. Check the service logs first
2. Verify all environment variables are correctly set
3. Test individual components (Looker API, Vertex AI) separately
4. Review the Looker extension logs for client-side issues

---

For questions or issues specific to the Looker Explore Assistant, refer to the main project documentation or create an issue in the project repository.
