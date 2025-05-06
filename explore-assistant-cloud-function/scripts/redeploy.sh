#!/bin/bash
# This script is used to build and deploy the Docker image for the Explore Assistant Backend Agent
# It builds the Docker image, pushes it to Google Container Registry, and deploys it to Google Cloud Run
# Ensure you have the Google Cloud SDK installed and authenticated
# Ensure you have Docker installed and running
docker build -t us-central1-docker.pkg.dev/oss-development-323115/explore-assistant-backend-agent/explore-assistant-backend-agent:latest .

docker push us-central1-docker.pkg.dev/oss-development-323115/explore-assistant-backend-agent/explore-assistant-backend-agent:latest

gcloud run deploy explore-assistant-backend-agent \
    --image us-central1-docker.pkg.dev/oss-development-323115/explore-assistant-backend-agent/explore-assistant-backend-agent:latest \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --set-env-vars=FUNCTION_TARGET=cloud_function_entrypoint,PROJECT=oss-development-323115,REGION=us-central1,LOOKERSDK_CLIENT_ID=n7XC5ZZ53X6WMsyNjPCG,LOOKERSDK_CLIENT_SECRET=CGfdX8DsRVGYnvwpSP8zkvyW,LOOKERSDK_BASE_URL=https://insightsdev.ossd.co:19999 \
    --memory=1Gi \
    --timeout=600s 

./test_with_input_file.sh
# This script tests the deployed cloud function using the input_test.json file