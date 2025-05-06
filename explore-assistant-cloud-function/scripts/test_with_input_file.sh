#!/bin/bash

# This script tests the deployed cloud function using the input_test.json file

# Define the URL of your deployed cloud function
CLOUD_FUNCTION_URL="https://explore-assistant-backend-agent-746659087621.us-central1.run.app"

# Run the test with verbose output and using the input file
python ../scripts/test_deployed.py \
  --url "$CLOUD_FUNCTION_URL" \
  --input-file input_test.json \
  --verbose