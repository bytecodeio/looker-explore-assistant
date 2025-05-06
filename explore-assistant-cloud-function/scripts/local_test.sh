#!/bin/bash
# Script to test the Looker Explore Assistant locally

# Set default values
LOCAL_URL="http://localhost:8000/"
QUERY="Who was in the office last week and what was utilization like?"
STANDARD_FIELDS_FILE="input_test.json"
VERBOSE=""
TIMEOUT=120

# Display usage information
function show_usage {
  echo "Usage: $0 [options]"
  echo "Options:"
  echo "  --url URL                   URL of the local server (default: http://localhost:8000/)"
  echo "  --query QUERY               Query to send to the server"
  echo "  --standard-fields-file FILE JSON file containing standard fields (default: input_test.json)"
  echo "  --verbose                   Enable verbose logging"
  echo "  --timeout SECONDS           Request timeout in seconds (default: 120)"
  echo "  --help                      Show this help message"
}

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
  case $1 in
    --url) LOCAL_URL="$2"; shift ;;
    --query) QUERY="$2"; shift ;;
    --standard-fields-file) STANDARD_FIELDS_FILE="$2"; shift ;;
    --verbose) VERBOSE="--verbose" ;;
    --timeout) TIMEOUT="$2"; shift ;;
    --help) show_usage; exit 0 ;;
    *) echo "Unknown parameter: $1"; show_usage; exit 1 ;;
  esac
  shift
done

echo "Testing Looker Explore Assistant locally..."
echo "URL: $LOCAL_URL"
echo "Query: $QUERY"
echo "Standard Fields File: $STANDARD_FIELDS_FILE"
echo "Timeout: ${TIMEOUT}s"

# Run the test
python test_local.py --url "$LOCAL_URL" --query "$QUERY" \
  --standard-fields-file "$STANDARD_FIELDS_FILE" --timeout "$TIMEOUT" $VERBOSE
