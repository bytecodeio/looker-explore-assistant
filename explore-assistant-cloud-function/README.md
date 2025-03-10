This cloud function provides an API for generating Looker queries using the Vertex AI Gemini Pro model. It allows users to input natural language descriptions of data queries, which the function then converts into Looker Explore URLs or query suggestions using a generative AI model.

## How It Works

The cloud function integrates with Vertex AI and utilizes the `GenerativeModel` class to generate content based on input parameters. Here's a step-by-step breakdown of its operation:

1. **Environment Setup**: The function initializes with the Vertex AI environment, requiring `PROJECT` and `REGION` environment variables to be set for connecting to the Vertex AI services.

2. **Query Generation**: The core functionality lies in the `generate_looker_query` function, which accepts a natural language query (`contents`) and optional parameters (`parameters`) to customize the AI generation process.

3. **Parameter Configuration**: It uses default parameters for the AI model (like `temperature`, `max_output_tokens`, `top_p`, `top_k`) which can be overridden by the request's parameters.

4. **Model Invocation**: The Gemini Pro model is then invoked to generate the Looker query based on the provided contents and parameters.

5. **Logging**: Metadata from the generation process, including input and output token counts, is logged for monitoring and debugging purposes.

6. **API Endpoints**: The function can be deployed as a Flask web server or as a Google Cloud Function. It handles `POST` requests to the main endpoint, where it expects a JSON payload with `contents` and optional `parameters`.

7. **CORS Handling**: Cross-Origin Resource Sharing (CORS) is configured to allow web clients from different origins to interact with the API.

8. **Execution Environment**: When executed, the script checks if it's running in a Google Cloud Function environment and acts accordingly; otherwise, it starts a Flask web server for local development or testing.

9. **Endpoint Security**: We are using a simple shared secret approach to securing the endpoint. The request body is checked against the supplied signature in the X-Signature header. We aren't yet guarding against replay attacks with nonces.

## Local Development

To set up and run the function locally, follow these steps:

1. Create a virtual environment and activate it:

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

2. Navigate to the project directory and install the required dependencies:

    ```bash
    cd explore-assistant-cloud-function
    pip3 install -r requirements.txt
    ```

3. Run the function locally by executing the main script:

    ```bash
    PROJECT=XXXX LOCATION=us-central-1 VERTEX_CF_AUTH_TOKEN=$(cat ../.vertex_cf_auth_token) python main.py
    ```

4. Test calling the endpoint locally with a custom query and parameter declaration
   
   ```bash
     python test.py
   ```

This setup allows developers to test and modify the function in a local environment before deploying it to a cloud function service.

## Setting up Looker API Credentials

1. Get your API credentials from Looker:
   - Log into Looker as an admin
   - Go to Admin > Users
   - Find your user and click "Edit"
   - Under "API3 Keys", generate a new key

2. Set up your credentials:

   Option 1: Environment Variables (Recommended)
   ```bash
   export LOOKERSDK_CLIENT_ID="your_client_id"
   export LOOKERSDK_CLIENT_SECRET="your_client_secret"
   ```

   Option 2: Update looker.ini file:
   - Copy the example looker.ini file
   - Fill in your client_id and client_secret

3. Verify SSL settings:
   - For development, SSL verification is disabled by default
   - For production, set LOOKERSDK_VERIFY_SSL=true

## Model configuration

By default, the cloud function will use a default model. However, you may want to test out different Gemini models are they are released. We have made the model name configurable via an environment variable. 

In development, you can run the main script with a new MODEL_NAME variable:


## Testing

### Basic Testing
To run basic tests using the Flask development server:

1. Start the local server:
   ```bash
   python explore-assistant-cloud-function/main.py
   ```
   The server will start on http://localhost:8000

2. Run the simple test script:
   ```bash
   python explore-assistant-cloud-function/test.py
   ```
   Make sure you have the `.vertex_cf_auth_token` file in the parent directory.

### Comprehensive Testing
For running the full test suite:

1. Prepare test questions in a CSV file:
   ```bash
   # Default location: documents/question_set.csv
   ```

2. Run the test suite:
   ```bash
   python explore-assistant-cloud-function/testing/test_runner.py \
     --questions path/to/question_set.csv \
     --output ./test_results \
     --looker-url https://your-looker-instance.com
   ```

   Optional arguments:
   - `--limit N`: Test only N questions
   - `--skip-visualizations`: Skip visualization tests
   - `--question-id ID`: Test a specific question
   - `--question-text "text"`: Test with custom question

   ex:
   ```bash
   cd explore-assistant-cloud-function
   export PYTHONPATH=$PYTHONPATH:.
   python testing/test_runner.py \
     --questions documents/question_set.csv \
     --output ./test_results \
     --looker-url https://looker.bytecode.io \     --limit 2
   ```

3. View results:
   - Test results will be saved in the specified output directory
   - Check `summary_report.html` and `detailed_report.html` for test results
   - Visualizations are stored in the `visualizations` subdirectory
