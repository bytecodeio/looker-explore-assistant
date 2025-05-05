#!/bin/bash
# Quick script to test if the server is running

PORT=${PORT:-8000}
URL="http://localhost:$PORT/health"

echo "Testing connection to server at $URL..."
response=$(curl -s -o /dev/null -w "%{http_code}" $URL)

if [ $response -eq 200 ]; then
  echo "✓ Server is running properly (HTTP 200)"
  exit 0
else
  echo "✗ Server is not responding correctly (HTTP $response)"
  echo "Make sure the server is started with ./run_local.sh"
  exit 1
fi
