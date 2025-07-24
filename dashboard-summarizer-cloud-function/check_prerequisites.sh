#!/bin/bash

# Pre-deployment check script for Dashboard Summarizer
# Run this before deploy_to_cloudrun.sh to verify all prerequisites

set -e

# Configuration (should match deploy_to_cloudrun.sh)
PROJECT_ID="combined-genai-bi"
REGION="us-central1"
SERVICE_NAME="dashboard-summarizer"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Dashboard Summarizer Pre-deployment Check${NC}"
echo "=================================================="

# Check if gcloud is installed and authenticated
echo -e "${YELLOW}1. Checking gcloud installation and authentication...${NC}"
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI is not installed${NC}"
    exit 1
fi

if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo -e "${RED}❌ Not authenticated with gcloud. Run 'gcloud auth login'${NC}"
    exit 1
fi
echo -e "${GREEN}✅ gcloud is installed and authenticated${NC}"

# Check if Docker is available
echo -e "${YELLOW}2. Checking Docker installation...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker is installed${NC}"

# Set and verify project
echo -e "${YELLOW}3. Setting and verifying GCP project...${NC}"
gcloud config set project $PROJECT_ID
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
if [ "$CURRENT_PROJECT" != "$PROJECT_ID" ]; then
    echo -e "${RED}❌ Failed to set project. Current: $CURRENT_PROJECT, Expected: $PROJECT_ID${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Project set correctly: $CURRENT_PROJECT${NC}"

# Check if required APIs are enabled
echo -e "${YELLOW}4. Checking required APIs...${NC}"
REQUIRED_APIS=(
    "cloudbuild.googleapis.com"
    "run.googleapis.com"
    "artifactregistry.googleapis.com"
    "aiplatform.googleapis.com"
)

for api in "${REQUIRED_APIS[@]}"; do
    if gcloud services list --enabled --filter="name:$api" --format="value(name)" | grep -q "$api"; then
        echo -e "${GREEN}✅ $api is enabled${NC}"
    else
        echo -e "${YELLOW}⚠️  $api is not enabled. Enabling now...${NC}"
        gcloud services enable $api
        echo -e "${GREEN}✅ $api enabled${NC}"
    fi
done

# Check if Artifact Registry repository exists or can be created
echo -e "${YELLOW}5. Checking Artifact Registry repository...${NC}"
if gcloud artifacts repositories describe $SERVICE_NAME --location=$REGION &>/dev/null; then
    echo -e "${GREEN}✅ Artifact Registry repository exists${NC}"
else
    echo -e "${YELLOW}⚠️  Creating Artifact Registry repository...${NC}"
    gcloud artifacts repositories create $SERVICE_NAME \
        --repository-format=docker \
        --location=$REGION \
        --description="Docker repository for Dashboard Summarizer Server"
    echo -e "${GREEN}✅ Artifact Registry repository created${NC}"
fi

# Configure Docker authentication
echo -e "${YELLOW}6. Configuring Docker authentication...${NC}"
gcloud auth configure-docker $REGION-docker.pkg.dev --quiet
echo -e "${GREEN}✅ Docker authentication configured${NC}"

# Check if required files exist
echo -e "${YELLOW}7. Checking required files...${NC}"
REQUIRED_FILES=("ds_server.py" "requirements.txt" "Dockerfile")
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅ $file exists${NC}"
    else
        echo -e "${RED}❌ $file is missing${NC}"
        exit 1
    fi
done

# Check if service already exists
echo -e "${YELLOW}8. Checking if service already exists...${NC}"
if gcloud run services describe $SERVICE_NAME --region=$REGION &>/dev/null; then
    echo -e "${YELLOW}⚠️  Service $SERVICE_NAME already exists in region $REGION${NC}"
    echo -e "${YELLOW}   The deployment will update the existing service.${NC}"
else
    echo -e "${GREEN}✅ Service does not exist yet - ready for initial deployment${NC}"
fi

echo ""
echo -e "${GREEN}=================================================="
echo "✅ All prerequisites met! Ready to deploy."
echo "=================================================="
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Run: ./deploy_to_cloudrun.sh"
echo "2. After deployment, run: ./update_env_vars.sh"
echo ""
echo -e "${YELLOW}Current configuration:${NC}"
echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Service Name: $SERVICE_NAME"
echo ""
