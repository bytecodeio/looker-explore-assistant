#!/bin/bash
# Script to start the server and run a test query

# Make sure local_env.sh exists
if [ ! -f ./local_env.sh ]; then
    echo "Error: local_env.sh file not found. Please create it from local_env.sh.template."
    exit 1
fi

# Start the server in the background
echo "Starting server in the background..."
./run_local.sh &
SERVER_PID=$!

# Wait for the server to start up
echo "Waiting for server to start up..."
sleep 5

# Run test with input_test.json
echo "Running test with input_test.json..."
./local_test.sh --query "Show me who was in the office yesterday" --verbose

# Ask user if they want to keep the server running
read -p "Keep the server running? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Stopping server..."
    kill $SERVER_PID
    wait $SERVER_PID 2>/dev/null
    echo "Server stopped."
else
    echo "Server is still running with PID $SERVER_PID"
    echo "You can stop it later using: kill $SERVER_PID"
fi
