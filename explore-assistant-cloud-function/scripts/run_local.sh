#!/bin/bash
# Script to run the Looker Explore Assistant locally

# Set default Python path
PYTHON_CMD=${PYTHON_CMD:-python}

# Check if local_env.sh exists
if [ ! -f ./local_env.sh ]; then
    echo "Error: local_env.sh file not found. Please create it using local_env.sh.template."
    exit 1
fi

# Load environment variables
source ./local_env.sh

# Print environment info
echo "===== Starting Looker Explore Assistant locally ====="
echo "Using PROJECT: $PROJECT"
echo "Using REGION: $REGION" 
echo "Using MODEL_NAME: $MODEL_NAME"
echo "Using LOOKERSDK_BASE_URL: $LOOKERSDK_BASE_URL"
echo "Using PORT: ${PORT:-8000}"
echo "======================================================"

# Check if Looker SDK environment variables are set
if [ -z "$LOOKERSDK_BASE_URL" ] || [ -z "$LOOKERSDK_CLIENT_ID" ] || [ -z "$LOOKERSDK_CLIENT_SECRET" ]; then
    echo "Warning: One or more Looker SDK environment variables are not set."
    echo "The application may not be able to connect to Looker."
    echo "Please check your LOOKERSDK_BASE_URL, LOOKERSDK_CLIENT_ID, and LOOKERSDK_CLIENT_SECRET variables."
fi

# Check if required environment variables are set
if [ -z "$PROJECT" ]; then
    echo "Warning: PROJECT environment variable not set. Set this in local_env.sh"
fi

if [ -z "$REGION" ]; then
    echo "Warning: REGION environment variable not set. Set this in local_env.sh"
fi

if [ -z "$LOOKERSDK_BASE_URL" ]; then
    echo "Warning: LOOKERSDK_BASE_URL environment variable not set. Set this in local_env.sh"
fi

# Check if port is already in use
PORT=${PORT:-8000}
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null; then
    echo "Warning: Port $PORT is already in use. The server may already be running."
    echo "Use 'lsof -i :$PORT' to see which process is using it."
    echo "You can kill the existing process with: kill \$(lsof -t -i:$PORT)"
    read -p "Do you want to try to start the server anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if we have Google Cloud authentication
echo "Checking Google Cloud authentication..."
gcloud config list account --format "value(core.account)" 2>/dev/null || {
    echo "Warning: Not logged in to Google Cloud. Authenticate with: gcloud auth login"
}

# Make sure we're not in FUNCTIONS_FRAMEWORK mode - explicitly unset it
unset FUNCTIONS_FRAMEWORK

# Set Flask environment variables
export FLASK_ENV=development
export FLASK_APP=main.py
export FLASK_DEBUG=1

# Run the Flask app
echo "Starting Flask server on port ${PORT}"
echo "To test the server is running: curl http://localhost:${PORT}/health"
echo "To stop the server, press Ctrl+C"

# Start the server in the foreground
$PYTHON_CMD -u main.py

# Add trap to catch ctrl+c and clean up
trap 'echo "Server stopped."; exit 0' INT
