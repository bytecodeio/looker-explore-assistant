#!/bin/bash

# Start Looker Explore Assistant with Vector Search Integration
# This script starts both the vector MCP server and the main application

echo "🚀 Starting Looker Explore Assistant with Vector Search Integration"

# Function to check if a port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null ; then
        echo "✅ Port $1 is in use"
        return 0
    else
        echo "❌ Port $1 is not in use"
        return 1
    fi
}

# Start vector MCP server in background
echo "📡 Starting Vector MCP Server on port 8000..."
cd ../explore-assistant-vector-mcp
uv run python server.py &
VECTOR_PID=$!
cd ../explore-assistant-cloud-function

# Wait for vector server to start
echo "⏳ Waiting for vector MCP server to initialize..."
sleep 5

# Check if vector server is running
if check_port 8000; then
    echo "✅ Vector MCP server is running (PID: $VECTOR_PID)"
else
    echo "❌ Vector MCP server failed to start"
    exit 1
fi

# Set environment variable for vector server URL
export VECTOR_MCP_URL="http://localhost:8000"

# Start main application
echo "🌟 Starting main Looker Explore Assistant..."
echo "📍 Using vector MCP server at: $VECTOR_MCP_URL"

# Check if we're in development or production mode
if [ "$1" = "local" ]; then
    echo "🔧 Starting in local development mode..."
    python3 run_local.sh
else
    echo "🚀 Starting in production mode..."
    functions-framework --target=vertex_ai_proxy --port=8001
fi

# Cleanup function
cleanup() {
    echo "🧹 Cleaning up..."
    kill $VECTOR_PID 2>/dev/null
    echo "✅ Vector MCP server stopped"
    exit 0
}

# Set trap to cleanup on exit
trap cleanup SIGINT SIGTERM

# Keep script running
wait