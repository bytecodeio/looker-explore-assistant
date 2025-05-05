# MIT License

# Copyright (c) 2023 Looker Data Sciences, Inc.

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import hmac
from flask import Flask, request, Response
from flask_cors import CORS
import functions_framework
import vertexai
from vertexai.preview.generative_models import GenerativeModel, GenerationConfig
from langchain_community.llms import VertexAI
import logging
import json
from google.cloud import bigquery

# Setup SSL verification based on environment variable
verify_ssl = os.environ.get('LOOKERSDK_VERIFY_SSL', 'true').lower()
verify_ssl = verify_ssl == 'true' or verify_ssl == '1'

if not verify_ssl:
    # Suppress certificate warnings if verification is disabled
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    logging.info("SSL certificate verification disabled globally")

# Set up detailed debug logging
logging.basicConfig(level=logging.DEBUG)

# Log environment variables on startup
logging.info("Starting application with the following environment variables:")
logging.info(f"PROJECT: {os.environ.get('PROJECT', 'Not Set')}")
logging.info(f"REGION: {os.environ.get('REGION', 'Not Set')}")
logging.info(f"MODEL_NAME: {os.environ.get('MODEL_NAME', 'gemini-2.0-flash-lite')}")
logging.info(f"DATASET: {os.environ.get('DATASET', 'bytecode')}")
logging.info(f"PORT: {os.environ.get('PORT', '8000')}")
logging.info(f"LOOKERSDK_BASE_URL: {os.environ.get('LOOKERSDK_BASE_URL', 'Not Set')}")
logging.info(f"LOOKERSDK_CLIENT_ID: {os.environ.get('LOOKERSDK_CLIENT_ID', 'Not Set')}")
logging.info(f"LOOKERSDK_CLIENT_SECRET is set: {'Yes' if os.environ.get('LOOKERSDK_CLIENT_SECRET') else 'No'}")
logging.info(f"LOOKERSDK_VERIFY_SSL: {verify_ssl}")

# Initialize the Vertex AI
project = os.environ.get("PROJECT")
location = os.environ.get("REGION")
model_name = os.environ.get("MODEL_NAME", "gemini-2.0-flash-lite")
dataset_id = os.environ.get("DATASET", "bytecode")

# Initialize Vertex AI properly
vertexai.init(project=project, location=location)

# Initialize BigQuery client
bq_client = bigquery.Client(project=project)

# Function to check if a table exists in BigQuery
def check_table_exists(project_id, dataset_id, table_id):
    """Check if a table exists in BigQuery"""
    try:
        table_ref = f"{project_id}.{dataset_id}.{table_id}"
        bq_client.get_table(table_ref)
        logging.info(f"Table {table_ref} exists")
        return True
    except Exception as e:
        logging.info(f"Table {table_ref} does not exist: {e}")
        return False

def get_response_headers(request):
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }
    return headers

def generate_looker_query(contents, parameters=None, model_name="gemini-2.0-flash-lite", standard_fields=None):
    """Generate Looker query with debug logging of workflow steps"""
    logging.debug(f"WORKFLOW STEP 1: Starting generate_looker_query with contents: {contents[:100]}...")
    logging.debug(f"WORKFLOW STEP 1: standard_fields: {standard_fields}")

    # Define default parameters
    default_parameters = {
        "temperature": 0.2,
        "max_output_tokens": 500,
        "top_p": 0.8,
        "top_k": 40
    }

    # Ensure explores table exists and has data
    try:
        from utils.bigquery_utils import ensure_table_exists, populate_explores_from_looker
        from utils.looker_sdk_utils import init_looker_sdk

        # Check and create explores table if needed
        project_id = os.environ.get("PROJECT")
        dataset_id = os.environ.get("DATASET", "bytecode")
        table_id = "explores"
        
        client = bigquery.Client(project=project_id)
        sdk = init_looker_sdk()
        
        # Ensure dataset and table exist
        ensure_table_exists(client, project_id, dataset_id, table_id, "explores")
        
        # Check if table has data
        query = f"SELECT COUNT(*) as count FROM `{project_id}.{dataset_id}.{table_id}`"
        try:
            query_job = client.query(query)
            result = query_job.result()
            count = [row['count'] for row in result][0]
            if count == 0:
                logging.info("Explores table exists but is empty, populating from Looker")
                populate_explores_from_looker(client, project_id, dataset_id, sdk)
        except Exception as e:
            logging.error(f"Error checking or populating explores table: {e}")
    except Exception as e:
        logging.error(f"Error ensuring explores table exists: {e}")

    # Override default parameters with any provided in the request
    if parameters:
        default_parameters.update(parameters)
        logging.debug(f"WORKFLOW STEP 2: Using custom parameters: {default_parameters}")
    else:
        logging.debug("WORKFLOW STEP 2: Using default parameters")

    # Import workflow here to avoid circular imports
    try:
        from workflow import LookerExploreWorkflow
        from utils.model_manager import ModelManager
        logging.debug("WORKFLOW STEP 3: Successfully imported workflow modules")
        
        # Initialize ModelManager with model_name from environment or parameter
        model_manager = ModelManager(model_name=model_name or os.environ.get("MODEL_NAME", "gemini-2.0-flash-lite"))
        logging.debug(f"WORKFLOW STEP 4: Initialized ModelManager with model: {model_name}")
        
        # Create workflow instance - it will use environment variables for Looker connection
        workflow = LookerExploreWorkflow(model_manager=model_manager)
        logging.debug("WORKFLOW STEP 5: Created LookerExploreWorkflow instance")
        logging.debug(f"WORKFLOW STEP 5: Using Looker URL: {workflow.looker_instance_url}")
        
        # Prepare input for the workflow
        workflow_input = {
            "query": contents,
            "request_visualization": False,
        }
        
        # Add standard_fields to the workflow input if present
        if standard_fields:
            workflow_input["standard_fields"] = standard_fields
            logging.debug(f"WORKFLOW STEP 6: Added standard_fields to workflow input")
        
        logging.debug(f"WORKFLOW STEP 7: Calling workflow with input: {json.dumps(workflow_input)[:200]}...")
        
        # Call the workflow
        result = workflow.invoke(workflow_input)
        logging.debug(f"WORKFLOW STEP 8: Workflow execution completed with result keys: {list(result.keys())}")
        
        # Return the response text
        return result.get("response", "No response generated")
        
    except Exception as e:
        logging.error(f"WORKFLOW ERROR: Error in workflow execution: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return f"An error occurred while processing your request: {str(e)}"

    # This is the fallback if workflow isn't used
    try:
        logging.debug("FALLBACK STEP 1: Using direct Gemini model since workflow failed")
        # instantiate gemini model for prediction
        model = GenerativeModel(model_name)

        # make prediction to generate Looker Explore URL
        response = model.generate_content(
            contents=contents,
            generation_config=GenerationConfig(
                temperature=default_parameters["temperature"],
                top_p=default_parameters["top_p"],
                top_k=default_parameters["top_k"],
                max_output_tokens=default_parameters["max_output_tokens"],
                candidate_count=1
            )
        )
        logging.debug("FALLBACK STEP 2: Generated response from Gemini model")

        # grab token character count metadata and log
        metadata = response.__dict__['_raw_response'].usage_metadata

        # Complete a structured log entry.
        entry = dict(
            severity="INFO",
            message={"request": contents, "response": response.text,
                     "input_characters": metadata.prompt_token_count, "output_characters": metadata.candidates_token_count},
            # Log viewer accesses 'component' as jsonPayload.component'.
            component="explore-assistant-metadata",
        )
        logging.info(entry)
        return response.text
    except Exception as e:
        logging.error(f"FALLBACK ERROR: Error in fallback execution: {str(e)}")
        return f"An error occurred: {str(e)}"


def handle_options_request(request):
    return "", 204, get_response_headers(request)


# Function for Google Cloud Function - this is the main entry point
@functions_framework.http
def cloud_function_entrypoint(request):
    logging.debug("Request received by cloud_function_entrypoint")
    
    if request.method == "OPTIONS":
        logging.debug("Handling OPTIONS request")
        return handle_options_request(request)

    try:
        # Parse the incoming request JSON
        incoming_request = request.get_json()
        logging.debug(f"Received request with keys: {list(incoming_request.keys())}")
        
        # Check for input_test.json format (with "prompt" field)
        if "prompt" in incoming_request:
            contents = incoming_request.get("prompt")
            standard_fields = incoming_request.get("standard_fields")
            parameters = incoming_request.get("parameters", {})
            logging.debug("Found input_test.json format with 'prompt' field")
        else:
            # Standard format with "contents" field
            contents = incoming_request.get("contents")
            standard_fields = incoming_request.get("standard_fields")
            parameters = incoming_request.get("parameters", {})
            logging.debug("Using standard input format with 'contents' field")
        
        if contents is None:
            logging.error("Missing 'contents' or 'prompt' parameter")
            return "Missing 'contents' or 'prompt' parameter", 400, get_response_headers(request)
            
        logging.debug(f"Processing request with content: {contents[:100]}...")
        if standard_fields:
            logging.debug(f"Standard fields provided: {standard_fields}")

        # if not has_valid_signature(request):
        #     return "Invalid signature", 403, get_response_headers(request)

        # Generate response with the workflow
        response_text = generate_looker_query(contents, parameters, standard_fields=standard_fields)
        logging.debug(f"Generated response: {response_text[:100]}...")
        return Response(response_text, status=200, headers=get_response_headers(request))
    
    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return Response(f"Error processing request: {str(e)}", 
                       status=500, 
                       headers=get_response_headers(request))

# The Flask app is kept for local development only
# But in production Cloud Run, the functions-framework will be used directly
if __name__ == "__main__":
    # Local development environment detection - fixed to work with run_local.sh
    is_local = True  # Always use Flask when running main.py directly
    
    logging.info("Running in local development environment with Flask")
    app = Flask(__name__)
    CORS(app)
    
    @app.before_request
    def log_request_info():
        logging.debug("Incoming request to Flask app:")
        logging.debug(f"Headers: {request.headers}")
        body = request.get_data(as_text=True)
        logging.debug(f"Body: {body[:500]}..." if len(body) > 500 else f"Body: {body}")
        
    @app.route("/", methods=["POST", "OPTIONS"])
    def base():
        return cloud_function_entrypoint(request)
    
    # Added a health check endpoint
    @app.route("/health", methods=["GET"])
    def health():
        return "OK", 200
        
    # Add a root endpoint for easy checking in browser
    @app.route("/", methods=["GET"])
    def home():
        return "Looker Explore Assistant server is running", 200
        
    port = int(os.environ.get("PORT", 8000))
    logging.info(f"Starting Flask server on port {port}")
    print(f"\n* Running on http://localhost:{port}/ (Press CTRL+C to quit)")
    
    # Use threaded=True for better performance
    app.run(host="0.0.0.0", port=port, debug=True, threaded=True, use_reloader=False)
