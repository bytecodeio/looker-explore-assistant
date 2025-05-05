#!/bin/bash
# Script to wait for the server to start up

PORT=${PORT:-8000}
MAX_RETRIES=30
RETRY_INTERVAL=1

echo "Waiting for server to start on port $PORT..."

# Try to connect to the server until it responds or until max retries is reached
for i in $(seq 1 $MAX_RETRIES); do
  if curl -s "http://localhost:$PORT/health" > /dev/null; then
    echo "Server is up and running! (after $i attempts)"
    exit 0
  fi
  echo -n "."
  sleep $RETRY_INTERVAL
done

echo "Failed to connect to server after $MAX_RETRIES attempts."
exit 1
