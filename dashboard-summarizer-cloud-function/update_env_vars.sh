#!/bin/bash

# Script to update environment variables for the Dashboard Summarizer Cloud Run service
# Use this script after initial deployment to set your actual configuration values

set -e  # Exit on any error

# Configuration variables - Modify these to match your deployment
PROJECT_ID="combined-genai-bi"  # Replace with your GCP project ID
REGION="us-central1"  # Replace with your region (should match deployment)
SERVICE_NAME="dashboard-summarizer"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Updating environment variables for Cloud Run service: $SERVICE_NAME${NC}"

# Validate project ID is set
if [ "$PROJECT_ID" = "YOUR_PROJECT_ID" ]; then
    echo -e "${RED}Error: Please set your PROJECT_ID in the script before running.${NC}"
    exit 1
fi

# Function to update environment variable
update_env_var() {
    local var_name=$1
    local var_value=$2
    local description=$3
    
    if [ -z "$var_value" ] || [ "$var_value" = "PLACEHOLDER_"* ]; then
        echo -e "${YELLOW}Skipping $var_name - no value provided${NC}"
        return
    fi
    
    echo -e "${YELLOW}Updating $var_name ($description)...${NC}"
    gcloud run services update $SERVICE_NAME \
        --region=$REGION \
        --set-env-vars "$var_name=$var_value" \
        --quiet
}

# Prompt for each environment variable
echo ""
echo -e "${YELLOW}Please provide the following environment variable values:${NC}"
echo "Press Enter to skip any variable you don't want to update."
echo ""

# Google OAuth Client ID
echo -e "${YELLOW}Enter your Google OAuth Client ID:${NC}"
echo "Get this from Google Cloud Console → APIs & Services → Credentials"
echo "Format: 123456789-abc.apps.googleusercontent.com"
read -p "GOOGLE_OAUTH_CLIENT_ID: " google_oauth_client_id

# Looker Base URL
echo ""
echo -e "${YELLOW}Enter your Looker instance URL:${NC}"
echo "Format: https://your-company.looker.com"
read -p "LOOKERSDK_BASE_URL: " looker_base_url

# Looker Client ID
echo ""
echo -e "${YELLOW}Enter your Looker API Client ID:${NC}"
echo "Get this from Looker Admin → API"
read -p "LOOKERSDK_CLIENT_ID: " looker_client_id

# Looker Client Secret
echo ""
echo -e "${YELLOW}Enter your Looker API Client Secret:${NC}"
echo "Get this from Looker Admin → API (shown only once during creation)"
read -s -p "LOOKERSDK_CLIENT_SECRET: " looker_client_secret
echo ""

# Update environment variables
echo ""
echo -e "${GREEN}Updating Cloud Run service environment variables...${NC}"

update_env_var "GOOGLE_OAUTH_CLIENT_ID" "$google_oauth_client_id" "Google OAuth Client ID"
update_env_var "LOOKERSDK_BASE_URL" "$looker_base_url" "Looker Base URL"
update_env_var "LOOKERSDK_CLIENT_ID" "$looker_client_id" "Looker Client ID"
update_env_var "LOOKERSDK_CLIENT_SECRET" "$looker_client_secret" "Looker Client Secret"

# Get service URL for testing
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)' 2>/dev/null || echo "Unable to get service URL")

echo ""
echo -e "${GREEN}Environment variables updated successfully!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Test the health endpoint:"
echo "   curl $SERVICE_URL/health"
echo ""
echo "2. Test authentication with a valid Google ID token:"
echo "   curl -X POST $SERVICE_URL/vertex-passthrough \\"
echo "     -H \"Authorization: Bearer YOUR_GOOGLE_ID_TOKEN\" \\"
echo "     -H \"Content-Type: application/json\" \\"
echo "     -d '{\"contents\":[{\"role\":\"user\",\"parts\":[{\"text\":\"test\"}]}]}'"
echo ""
echo -e "${YELLOW}Security reminders:${NC}"
echo "- Ensure your Google OAuth client is properly configured"
echo "- Verify that authorized JavaScript origins include your frontend domain"
echo "- Test with a user that exists in your Looker instance"
echo ""

# Optional: Test the health endpoint
if [ "$SERVICE_URL" != "Unable to get service URL" ]; then
    echo -e "${YELLOW}Testing health endpoint...${NC}"
    if curl -f "$SERVICE_URL/health" > /dev/null 2>&1; then
        echo -e "${GREEN}Health check passed!${NC}"
    else
        echo -e "${YELLOW}Health check failed or service is still updating.${NC}"
        echo "Wait a moment and try: curl $SERVICE_URL/health"
    fi
fi

echo -e "${GREEN}Configuration complete!${NC}"
