#!/bin/bash
# Script to start the Looker Explore Assistant server with proper error checking

# Load environment
source ./local_env.sh

# Explicitly unset FUNCTIONS_FRAMEWORK to ensure Flask mode
unset FUNCTIONS_FRAMEWORK

# Set environment variables for Flask
export FLASK_APP=main.py
export FLASK_ENV=development
export FLASK_DEBUG=1

echo "Starting server in foreground mode..."
echo "Press Ctrl+C to stop"

# Run with unbuffered output and debug mode
python -u main.py
