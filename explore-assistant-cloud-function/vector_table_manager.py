#!/usr/bin/env python3
"""
Vector Table Management for Field Discovery

This module handles the creation, population, and indexing of BigQuery tables
used for semantic field discovery. It processes Looker field metadata and
sample values to create vector embeddings for similarity search.
"""

import json
import logging
import os
import sys
import io
import time
import traceback
from typing import Dict, Any, List, Optional
from datetime import datetime

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    if os.path.exists('.env'):
        load_dotenv()
        logging.info("Loaded environment variables from .env file")
except ImportError:
    logging.info("python-dotenv not available, relying on system environment variables")

import looker_sdk
from google.cloud import bigquery

# Configure comprehensive logging with debug support
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Enable debug logging if environment variable is set
if os.environ.get('VECTOR_DEBUG', '').lower() in ['true', '1', 'yes']:
    logger.setLevel(logging.DEBUG)
    logging.getLogger('google.cloud.bigquery').setLevel(logging.DEBUG)
    logging.getLogger('looker_sdk').setLevel(logging.DEBUG)
    logger.info("Debug logging enabled via VECTOR_DEBUG environment variable")

# Environment configuration
PROJECT_ID = os.environ.get("PROJECT", "your-gcp-project-id")  # GCP project for connections
BQ_PROJECT_ID = os.environ.get("BQ_PROJECT_ID", "your-bigquery-project-id")  # BigQuery project
DATASET_ID = os.environ.get("BQ_DATASET_ID", "explore_assistant")
FIELD_VALUES_TABLE = "field_values_for_vectorization"
EMBEDDING_MODEL = "text_embedding_model"

class VectorTableManager:
    """Manages BigQuery tables for field value vectorization"""

    def __init__(self):
        logger.info("Initializing VectorTableManager...")

        # Validate environment configuration
        self._validate_environment()

        try:
            logger.debug(f"Creating BigQuery client for project: {BQ_PROJECT_ID}")
            self.bq_client = bigquery.Client(project=BQ_PROJECT_ID)
            logger.info(f"✅ BigQuery client initialized for project: {BQ_PROJECT_ID}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize BigQuery client: {e}")
            logger.error(f"Detailed error: {traceback.format_exc()}")
            raise

        self.looker_sdk = None
        self.stats = {
            'start_time': time.time(),
            'operations': [],
            'errors': [],
            'warnings': []
        }

        logger.info("VectorTableManager initialization complete")

    def _validate_environment(self):
        """Validate required environment variables and configuration"""
        logger.info("🔍 Validating environment configuration...")

        required_vars = {
            'PROJECT': PROJECT_ID,
            'BQ_PROJECT_ID': BQ_PROJECT_ID,
            'BQ_DATASET_ID': DATASET_ID
        }

        missing_vars = []
        for var_name, value in required_vars.items():
            if not value or value.startswith('your-'):
                missing_vars.append(var_name)
                logger.error(f"❌ {var_name} not set or using default value: {value}")
            else:
                logger.debug(f"✅ {var_name}: {value}")

        if missing_vars:
            error_msg = f"Missing required environment variables: {missing_vars}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Check Looker SDK variables
        looker_vars = {
            'LOOKERSDK_BASE_URL': os.environ.get('LOOKERSDK_BASE_URL'),
            'LOOKERSDK_CLIENT_ID': os.environ.get('LOOKERSDK_CLIENT_ID'),
            'LOOKERSDK_CLIENT_SECRET': os.environ.get('LOOKERSDK_CLIENT_SECRET')
        }

        missing_looker_vars = []
        for var_name, value in looker_vars.items():
            if not value:
                missing_looker_vars.append(var_name)
                logger.warning(f"⚠️ {var_name} not set")
            else:
                logger.debug(f"✅ {var_name}: {'*' * len(value) if 'SECRET' in var_name else value}")

        if missing_looker_vars:
            logger.warning(f"Missing Looker SDK variables: {missing_looker_vars}. Looker operations will fail.")

        logger.info("✅ Environment validation complete")

    def _log_operation(self, operation: str, success: bool, duration: Optional[float] = None, details: Optional[Dict[str, Any]] = None):
        """Log operation statistics"""
        op_log = {
            'operation': operation,
            'success': success,
            'timestamp': datetime.now().isoformat(),
            'duration_seconds': duration,
            'details': details or {}
        }

        self.stats['operations'].append(op_log)

        if success:
            logger.info(f"✅ {operation} completed successfully" + (f" in {duration:.2f}s" if duration else ""))
        else:
            logger.error(f"❌ {operation} failed" + (f" after {duration:.2f}s" if duration else ""))
            self.stats['errors'].append(op_log)

    def _log_warning(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log warning with context"""
        warning_log = {
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'context': context or {}
        }

        self.stats['warnings'].append(warning_log)
        logger.warning(f"⚠️ {message}")

        if context:
            logger.debug(f"Warning context: {context}")
        
    def get_looker_sdk(self, retry_on_failure: bool = True):
        """Initialize and return Looker SDK instance with retry logic"""
        if self.looker_sdk is not None:
            # Test if existing connection is still valid
            try:
                logger.debug("Testing existing Looker SDK connection...")
                test_start = time.time()
                self.looker_sdk.me()  # Test call - don't store result
                test_duration = time.time() - test_start
                logger.debug(f"Existing connection valid (test took {test_duration:.2f}s)")
                return self.looker_sdk
            except Exception as e:
                logger.warning(f"⚠️ Existing SDK connection failed: {e}")
                logger.debug("Clearing invalid SDK instance and reinitializing...")
                self.looker_sdk = None

        return self._initialize_looker_sdk_with_retry(retry_on_failure)

    def _initialize_looker_sdk_with_retry(self, retry_on_failure: bool = True, max_retries: int = 3, retry_delay: float = 1.0):
        """Initialize Looker SDK with retry logic to handle race conditions"""
        start_time = time.time()

        # Validate required environment variables exist (SDK will read them directly)
        required_env_vars = {
            'LOOKERSDK_BASE_URL': os.environ.get('LOOKERSDK_BASE_URL'),
            'LOOKERSDK_CLIENT_ID': os.environ.get('LOOKERSDK_CLIENT_ID'),
            'LOOKERSDK_CLIENT_SECRET': os.environ.get('LOOKERSDK_CLIENT_SECRET')
        }

        missing_vars = [var for var, value in required_env_vars.items() if not value]
        if missing_vars:
            error_msg = f"Missing required Looker SDK environment variables: {missing_vars}"
            logger.error(f"❌ {error_msg}")
            self._log_operation("looker_sdk_init", False, time.time() - start_time, {'error': error_msg})
            return None

        logger.info("🔌 Initializing Looker SDK connection...")
        logger.debug(f"Environment variables validated:")
        for var, value in required_env_vars.items():
            if 'SECRET' in var:
                logger.debug(f"  {var}: {'*' * 20}")
            elif 'CLIENT_ID' in var:
                logger.debug(f"  {var}: {value[:8] + '...' if value else 'None'}")
            else:
                logger.debug(f"  {var}: {value}")

        # Log optional environment variables
        optional_vars = ['LOOKERSDK_VERIFY_SSL', 'LOOKERSDK_TIMEOUT']
        for var in optional_vars:
            value = os.environ.get(var)
            if value:
                logger.debug(f"  {var}: {value}")

        for attempt in range(max_retries if retry_on_failure else 1):
            attempt_start = time.time()
            try:
                logger.debug(f"SDK initialization attempt {attempt + 1}/{max_retries if retry_on_failure else 1}")

                # Initialize SDK - this reads environment variables directly
                logger.debug("Calling looker_sdk.init40() - SDK will read environment variables directly...")
                sdk_instance = looker_sdk.init40()
                init_duration = time.time() - attempt_start
                logger.debug(f"SDK initialization call completed in {init_duration:.2f}s")

                # Log the actual SDK configuration for debugging
                try:
                    sdk_settings = sdk_instance.auth.settings
                    logger.debug(f"SDK initialized with base_url: {getattr(sdk_settings, 'base_url', 'unknown')}")
                except Exception as e:
                    logger.debug(f"Could not retrieve SDK settings: {e}")

                # Test the connection immediately with multiple validation steps
                logger.debug("Testing Looker connection with validation steps...")

                # Step 1: Basic me() call
                validation_start = time.time()
                user = sdk_instance.me()
                logger.debug(f"Step 1 - me() call successful in {time.time() - validation_start:.2f}s")

                # Step 2: Add a small delay and test again to catch race conditions
                time.sleep(0.1)  # 100ms delay
                validation_start = time.time()
                sdk_instance.me()  # Verification call - don't store result
                logger.debug(f"Step 2 - verification me() call successful in {time.time() - validation_start:.2f}s")

                # Step 3: Test with a simple API call
                validation_start = time.time()
                try:
                    # This is a lightweight call to test API functionality
                    sdk_instance.versions()  # Test call - don't store result
                    logger.debug(f"Step 3 - versions() call successful in {time.time() - validation_start:.2f}s")
                except Exception as version_error:
                    logger.debug(f"Step 3 - versions() call failed (not critical): {version_error}")

                # If we get here, the SDK is working properly
                self.looker_sdk = sdk_instance
                connection_duration = time.time() - start_time

                logger.info(f"✅ Connected to Looker as: {user.email} (took {connection_duration:.2f}s, attempt {attempt + 1})")
                logger.debug(f"User details: ID={user.id}, First={user.first_name}, Last={user.last_name}")

                # Get the actual SDK configuration for logging
                sdk_base_url = 'unknown'
                try:
                    sdk_base_url = getattr(sdk_instance.auth.settings, 'base_url', 'unknown')
                except:
                    # Fallback to environment variable if SDK settings not accessible
                    sdk_base_url = os.environ.get('LOOKERSDK_BASE_URL', 'unknown')

                self._log_operation("looker_sdk_init", True, connection_duration, {
                    'user_email': user.email,
                    'user_id': user.id,
                    'sdk_base_url': sdk_base_url,  # What SDK actually used
                    'attempt': attempt + 1,
                    'total_attempts': max_retries if retry_on_failure else 1
                })

                return self.looker_sdk

            except Exception as e:
                attempt_duration = time.time() - attempt_start
                logger.warning(f"⚠️ SDK initialization attempt {attempt + 1} failed after {attempt_duration:.2f}s: {e}")

                if attempt < max_retries - 1 and retry_on_failure:
                    logger.info(f"🔄 Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                else:
                    # Final failure
                    total_duration = time.time() - start_time
                    error_msg = f"Failed to initialize Looker SDK after {max_retries if retry_on_failure else 1} attempts: {e}"
                    logger.error(f"❌ {error_msg}")
                    logger.error(f"Full traceback from final attempt: {traceback.format_exc()}")

                    self._log_operation("looker_sdk_init", False, total_duration, {
                        'error': str(e),
                        'traceback': traceback.format_exc(),
                        'total_attempts': attempt + 1,
                        'max_retries': max_retries if retry_on_failure else 1
                    })

                    return None

        return None

    def _safe_looker_api_call(self, api_call_func, operation_name: str, max_retries: int = 3, retry_delay: float = 0.5):
        """Safely execute a Looker API call with retry logic to handle race conditions"""
        for attempt in range(max_retries):
            try:
                logger.debug(f"Executing {operation_name} (attempt {attempt + 1}/{max_retries})")
                result = api_call_func()
                logger.debug(f"{operation_name} successful on attempt {attempt + 1}")
                return result

            except Exception as e:
                logger.warning(f"{operation_name} attempt {attempt + 1} failed: {e}")

                # Check if this might be a connection issue that requires SDK reinitialization
                if any(keyword in str(e).lower() for keyword in ['connection', 'timeout', 'authentication', 'network']):
                    logger.warning(f"Detected potential connection issue in {operation_name}, reinitializing SDK...")
                    self.looker_sdk = None  # Force reinitialization
                    new_sdk = self.get_looker_sdk(retry_on_failure=True)
                    if new_sdk is None:
                        logger.error(f"Failed to reinitialize SDK for {operation_name}")
                        return None

                if attempt < max_retries - 1:
                    logger.debug(f"Retrying {operation_name} in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                else:
                    logger.error(f"All {max_retries} attempts failed for {operation_name}: {e}")
                    return None

        return None

    def reset_looker_connection(self) -> bool:
        """Force reset of Looker SDK connection - useful for debugging connection issues"""
        logger.info("🔄 Resetting Looker SDK connection...")
        self.looker_sdk = None
        sdk = self.get_looker_sdk(retry_on_failure=True)
        return sdk is not None

    def create_embedding_model(self) -> bool:
        """
        Create a remote model that connects to Vertex AI text embedding
        """
        start_time = time.time()
        logger.info("🤖 Creating remote text embedding model...")

        # Check if model already exists first
        try:
            logger.debug("Checking if embedding model already exists...")
            existing_model_query = f"""
            SELECT table_name
            FROM `{BQ_PROJECT_ID}.{DATASET_ID}.INFORMATION_SCHEMA.TABLES`
            WHERE table_name = 'text_embedding_model' AND table_type = 'MODEL'
            """

            result = list(self.bq_client.query(existing_model_query).result())
            if result:
                duration = time.time() - start_time
                logger.info(f"✅ Embedding model already exists (checked in {duration:.2f}s)")
                self._log_operation("create_embedding_model", True, duration, {'status': 'already_exists'})
                return True
            else:
                logger.debug("Embedding model does not exist, proceeding with creation...")

        except Exception as e:
            logger.debug(f"Could not check existing model (this is normal): {e}")

        # Try primary connection pattern
        try:
            logger.info(f"📡 Attempting to create model with primary connection pattern...")
            model_query = f"""
            CREATE OR REPLACE MODEL `{BQ_PROJECT_ID}.{DATASET_ID}.text_embedding_model`
            REMOTE WITH CONNECTION `{BQ_PROJECT_ID}.us-central1.vertex-ai`
            OPTIONS(ENDPOINT = 'text-embedding-004')
            """

            logger.debug(f"Primary model creation query:\n{model_query}")

            job = self.bq_client.query(model_query)
            logger.debug(f"Query job created: {job.job_id}")

            result = job.result()
            logger.debug(f"Query job completed: {job.state}")

            duration = time.time() - start_time
            logger.info(f"✅ Remote text embedding model created successfully (took {duration:.2f}s)")

            self._log_operation("create_embedding_model", True, duration, {
                'connection_pattern': 'primary',
                'job_id': job.job_id
            })

            return True

        except Exception as e:
            logger.warning(f"⚠️ Primary connection pattern failed: {e}")
            logger.debug(f"Primary pattern traceback: {traceback.format_exc()}")
            logger.info("🔄 Trying alternative connection pattern...")

            # Try with a different connection name pattern
            try:
                model_query = f"""
                CREATE OR REPLACE MODEL `{BQ_PROJECT_ID}.{DATASET_ID}.text_embedding_model`
                REMOTE WITH CONNECTION `us-central1.vertex-ai`
                OPTIONS(ENDPOINT = 'text-embedding-004')
                """

                logger.debug(f"Alternative model creation query:\n{model_query}")

                job = self.bq_client.query(model_query)
                logger.debug(f"Alternative query job created: {job.job_id}")

                result = job.result()
                logger.debug(f"Alternative query job completed: {job.state}")

                duration = time.time() - start_time
                logger.info(f"✅ Remote text embedding model created successfully with alternative connection (took {duration:.2f}s)")

                self._log_operation("create_embedding_model", True, duration, {
                    'connection_pattern': 'alternative',
                    'job_id': job.job_id,
                    'primary_error': str(e)
                })

                return True

            except Exception as e2:
                duration = time.time() - start_time
                logger.error(f"❌ Failed to create embedding model with both connection patterns")
                logger.error(f"Primary error: {e}")
                logger.error(f"Alternative error: {e2}")
                logger.error(f"Alternative traceback: {traceback.format_exc()}")

                logger.info("")
                logger.info("🔧 TROUBLESHOOTING STEPS:")
                logger.info("1. Ensure you have a BigQuery connection to Vertex AI:")
                logger.info(f"   bq mk --connection --connection_type=CLOUD_RESOURCE --project_id={BQ_PROJECT_ID} --location=us-central1 vertex-ai")
                logger.info("2. Verify the connection exists:")
                logger.info(f"   bq show --connection --project_id={BQ_PROJECT_ID} --location=us-central1 vertex-ai")
                logger.info("3. Check IAM permissions for Vertex AI access")
                logger.info("")

                self._log_operation("create_embedding_model", False, duration, {
                    'primary_error': str(e),
                    'alternative_error': str(e2),
                    'both_failed': True
                })

                return False
    
    def create_field_values_table_from_looker_explores(self) -> bool:
        """
        Create the field_values_for_vectorization table from Looker explore fields

        Returns:
            bool: True if successful, False otherwise
        """
        start_time = time.time()
        logger.info(f"📈 Creating field values table from Looker explores...")
        logger.info("🌐 Processing all explores with 'index' sets")

        try:
            sdk = self.get_looker_sdk(retry_on_failure=True)
            if sdk is None:
                error_msg = "Could not initialize Looker SDK after retries"
                logger.error(f"❌ {error_msg}")
                self._log_operation("create_field_values_table", False, time.time() - start_time, {'error': error_msg})
                return False
            field_entries = []
            
            
            # Step 1: Get all models and their explores
            logger.info("Fetching all LookML models and explores...")
            models_start = time.time()
            logger.debug("Fetching LookML models with SDK retry logic...")

            # Use retry logic for the models call since this is where the race condition often occurs
            models = self._safe_looker_api_call(
                lambda: sdk.all_lookml_models(
                    fields='name,explores',
                    exclude_empty='true',
                    exclude_hidden='true'
                ),
                operation_name="fetch_models",
                max_retries=3
            )

            if models is None:
                error_msg = "Failed to fetch models from Looker after retries"
                logger.error(f"❌ {error_msg}")
                self._log_operation("create_field_values_table", False, time.time() - start_time, {
                    'error': error_msg,
                    'stage': 'fetch_models_with_retries'
                })
                return False

            models_duration = time.time() - models_start
            logger.debug(f"Models fetch completed in {models_duration:.2f}s")
            
            if not models:
                error_msg = "No models found"
                logger.error(f"❌ {error_msg}")
                self._log_operation("create_field_values_table", False, time.time() - start_time, {
                    'error': error_msg,
                    'stage': 'fetch_models'
                })
                return False

            total_explores = sum(len(model.explores or []) for model in models)
            logger.info(f"🏢 Found {len(models)} models with {total_explores} total explores")
            logger.debug(f"Model details: {[(m.name, len(m.explores or [])) for m in models]}")
            
            # Step 2: For each explore, get detailed field information
            processed_explores = 0
            for model in models:
                model_name = model.name
                explores = model.explores or []
                
                for explore in explores:
                    explore_name = explore.name
                    processed_explores += 1
                    
                    try:
                        explore_key = f"{model_name}:{explore_name}"
                        explore_start = time.time()
                        logger.info(f"🔍 Processing explore {processed_explores}/{total_explores}: {explore_key}")

                        # Get detailed explore information with sets and fields
                        logger.debug(f"   📡 Fetching explore details for {explore_key}...")
                        if model_name is not None and explore_name is not None:
                            # Use retry logic for explore details fetch
                            explore_detail = self._safe_looker_api_call(
                                lambda: sdk.lookml_model_explore(
                                    lookml_model_name=model_name,
                                    explore_name=explore_name,
                                    fields='sets,fields'
                                ),
                                operation_name=f"fetch_explore_details_{explore_key}",
                                max_retries=2
                            )

                            if explore_detail is None:
                                logger.error(f"Failed to fetch explore details for {explore_key} after retries")
                                continue
                        else:
                            logger.error(f"Model name or explore name is None: model={model_name}, explore={explore_name}")
                            continue

                        explore_fetch_duration = time.time() - explore_start
                        logger.debug(f"   ⏱️ Explore fetch took {explore_fetch_duration:.2f}s")
                        
                        # Debug: Log basic explore info
                        logger.info(f"   📋 Explore detail loaded: has_sets={bool(explore_detail.sets)}, has_fields={bool(explore_detail.fields)}")
                        
                        # Find all 'index' sets (including view-prefixed ones like 'view.index')
                        index_sets = []
                        if explore_detail.sets:
                            logger.info(f"   📦 Found {len(explore_detail.sets)} sets in {explore_key}")
                            for set_info in explore_detail.sets:
                                logger.info(f"   📦   Set: {set_info.name} (value_count={len(set_info.value) if set_info.value else 0})")
                                # Check if set name is 'index' or ends with '.index'
                                if set_info.name and (set_info.name == 'index' or set_info.name.endswith('.index')):
                                    if set_info.value:  # Only include sets with values
                                        index_sets.append(set_info)
                                        logger.info(f"   ✅   Found index set: {set_info.name}")
                        else:
                            logger.info(f"   📦 No sets found in {explore_key}")
                        
                        if not index_sets:
                            logger.info(f"   ❌ No 'index' sets found in {explore_key}")
                            continue
                        
                        # Combine all index set values
                        all_index_fields = []
                        for index_set in index_sets:
                            all_index_fields.extend(index_set.value or [])
                        
                        if not all_index_fields:
                            logger.info(f"   ❌ All 'index' sets are empty in {explore_key}")
                            continue
                        
                        logger.info(f"   ✅ Found {len(index_sets)} 'index' sets with total {len(all_index_fields)} fields in {explore_key}")
                        logger.info(f"   📋 Combined index fields: {all_index_fields[:20]}{'...' if len(all_index_fields) > 20 else ''}")  # Show first 20
                        
                        # Get field details for all fields in the explore
                        all_fields = {}
                        if explore_detail.fields:
                            # Process dimensions
                            if explore_detail.fields.dimensions:
                                logger.info(f"   📊 Processing {len(explore_detail.fields.dimensions)} dimensions...")
                                for dimension in explore_detail.fields.dimensions:
                                    field_key = f"{dimension.view}.{dimension.name}" if dimension.view else dimension.name
                                    all_fields[field_key] = {
                                        'name': dimension.name,
                                        'view': dimension.view or 'unknown_view',
                                        'type': 'dimension',
                                        'description': dimension.description or '',
                                        'label': dimension.label or dimension.name,
                                        'sql_name': dimension.sql or dimension.name
                                    }
                                    logger.debug(f"   📊   Dimension: {field_key} (label={dimension.label}, desc={dimension.description})")
                            else:
                                logger.info(f"   📊 No dimensions found in {explore_key}")
                            
                            # Process measures
                            if explore_detail.fields.measures:
                                logger.info(f"   📈 Processing {len(explore_detail.fields.measures)} measures...")
                                for measure in explore_detail.fields.measures:
                                    field_key = f"{measure.view}.{measure.name}" if measure.view else measure.name
                                    all_fields[field_key] = {
                                        'name': measure.name,
                                        'view': measure.view or 'unknown_view',
                                        'type': 'measure',
                                        'description': measure.description or '',
                                        'label': measure.label or measure.name,
                                        'sql_name': measure.sql or measure.name
                                    }
                                    logger.debug(f"   📈   Measure: {field_key} (label={measure.label}, desc={measure.description})")
                            else:
                                logger.info(f"   📈 No measures found in {explore_key}")
                        else:
                            logger.info(f"   ❌ No fields found in {explore_key}")
                        
                        logger.info(f"   🔍 Total available fields: {len(all_fields)}")
                        
                        # Process fields from all 'index' sets
                        matched_fields = 0
                        for field_path in all_index_fields:
                            field_info = None
                            matched_key = None
                            
                            # Try multiple field key patterns to match
                            possible_keys = [field_path]  # Original path
                            
                            # If field_path contains a dot, try different patterns
                            if '.' in field_path:
                                parts = field_path.split('.')
                                if len(parts) == 2:  # e.g., "inventory_items.product_sku"
                                    view_name, field_name = parts
                                    # Try view.view.field pattern (common in joined explores)
                                    possible_keys.append(f"{view_name}.{view_name}.{field_name}")
                                    # Try view.field pattern
                                    possible_keys.append(f"{view_name}.{field_name}")
                            
                            # Try to match against available field keys
                            for possible_key in possible_keys:
                                if possible_key in all_fields:
                                    field_info = all_fields[possible_key]
                                    matched_key = possible_key
                                    break
                            
                            if field_info:
                                matched_fields += 1
                                
                                # For dimensions, get sample values from Looker data
                                if field_info['type'] == 'dimension':
                                    if model_name is not None and explore_name is not None:
                                        sample_values = self._get_dimension_sample_values(sdk, model_name, explore_name, field_info)
                                    else:
                                        logger.warning(f"Skipping dimension {field_info['name']} - model or explore name is None")
                                        sample_values = {field_info['label']: 1}
                                    
                                    logger.debug(f"   🔍   Sample values collected: {len(sample_values)} values")
                                    logger.debug(f"   🔍   Sample values preview: {list(sample_values.keys())[:5]}")
                                    
                                    # Create separate entries for each sample value
                                    for value, frequency in sample_values.items():
                                        # Create searchable text from field metadata and value
                                        searchable_text = f"{field_info['name']} {field_info['label']} {field_info['description']} {value} {model_name} {explore_name}"
                                        
                                        field_entry = {
                                            'model_name': model_name,
                                            'explore_name': explore_name,
                                            'view_name': field_info['view'],
                                            'field_name': field_info['name'],
                                            'field_type': field_info['type'],
                                            'field_description': field_info['description'],
                                            'field_value': str(value),  # Actual dimension value
                                            'value_frequency': frequency,
                                            'searchable_text': searchable_text
                                        }
                                        
                                        field_entries.append(field_entry)
                                        
                                        logger.debug(f"   ✅   Added dimension value: {field_path} → {matched_key} → {value} (freq={frequency})")
                                else:
                                    # For measures, just use the metadata
                                    searchable_text = f"{field_info['name']} {field_info['label']} {field_info['description']} {model_name} {explore_name}"
                                    
                                    field_entry = {
                                        'model_name': model_name,
                                        'explore_name': explore_name,
                                        'view_name': field_info['view'],
                                        'field_name': field_info['name'],
                                        'field_type': field_info['type'],
                                        'field_description': field_info['description'],
                                        'field_value': field_info['label'],  # Use label as sample value for measures
                                        'value_frequency': 1,
                                        'searchable_text': searchable_text
                                    }
                                    
                                    field_entries.append(field_entry)
                                    
                                    logger.debug(f"   ✅   Added measure: {field_path} → {matched_key} → {field_entry}")
                            else:
                                logger.warning(f"   ❌   Field {field_path} from index set not found in explore fields")
                                logger.debug(f"   🔍   Tried keys: {possible_keys}")
                                logger.debug(f"   🔍   Available field keys: {list(all_fields.keys())[:20]}...")  # Show first 20 for debugging
                        
                        logger.info(f"   ✅ Matched {matched_fields}/{len(all_index_fields)} fields from index sets in {explore_key}")
                    
                    except Exception as e:
                        logger.error(f"Error processing explore {model_name}:{explore_name}: {e}")
                        logger.error(f"Detailed error: {traceback.format_exc()}")
                        continue
            
            if not field_entries:
                logger.error("No field entries generated from Looker explores")
                return False
            
            logger.info(f"Generated {len(field_entries)} field entries from {processed_explores} explores")
            
            # Log details about the field entries
            if len(field_entries) > 0:
                logger.info(f"🔍 FIELD ENTRIES DEBUG:")
                logger.info(f"   Total entries: {len(field_entries)}")
                dimension_entries = [e for e in field_entries if e['field_type'] == 'dimension']
                measure_entries = [e for e in field_entries if e['field_type'] == 'measure']
                logger.info(f"   Dimension entries: {len(dimension_entries)}")
                logger.info(f"   Measure entries: {len(measure_entries)}")
                
                # Show a sample of entries
                for i, entry in enumerate(field_entries[:5]):
                    logger.info(f"   Entry {i+1}: {entry['field_type']} {entry['view_name']}.{entry['field_name']} = '{entry['field_value']}'")
                
                if len(field_entries) > 5:
                    logger.info(f"   ... and {len(field_entries) - 5} more entries")
            
            # Create table with embeddings
            return self._create_table_with_embeddings(field_entries)
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ Failed to create field values table from Looker explores: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")

            self._log_operation("create_field_values_table", False, duration, {
                'error': str(e),
                'traceback': traceback.format_exc(),
            })

            return False

    def _create_table_with_embeddings(self, field_entries: List[Dict[str, Any]]) -> bool:
        """Create the table with embeddings from field entries"""
        start_time = time.time()
        logger.info(f"🗺 Creating BigQuery table with {len(field_entries)} field entries...")

        try:
            # First, create a temporary table with the field data
            temp_table_id = f"{FIELD_VALUES_TABLE}_temp_{int(datetime.now().timestamp())}"
            temp_table_ref = self.bq_client.dataset(DATASET_ID).table(temp_table_id)
            
            # Define schema
            schema = [
                bigquery.SchemaField("model_name", "STRING"),
                bigquery.SchemaField("explore_name", "STRING"), 
                bigquery.SchemaField("view_name", "STRING"),
                bigquery.SchemaField("field_name", "STRING"),
                bigquery.SchemaField("field_type", "STRING"),
                bigquery.SchemaField("field_description", "STRING"),
                bigquery.SchemaField("field_value", "STRING"),
                bigquery.SchemaField("value_frequency", "INTEGER"),
                bigquery.SchemaField("searchable_text", "STRING"),
            ]
            
            # Create temporary table
            table = bigquery.Table(temp_table_ref, schema=schema)
            table = self.bq_client.create_table(table)
            logger.info(f"Created temporary table: {temp_table_id}")
            
            # Insert data
            job_config = bigquery.LoadJobConfig()
            job_config.source_format = bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
            
            # Convert field entries to newline-delimited JSON
            logger.debug("Converting field entries to JSON format...")
            json_data = '\n'.join([json.dumps(entry) for entry in field_entries])
            logger.debug(f"Generated {len(json_data)} characters of JSON data")

            # Use BytesIO instead of StringIO for proper encoding
            json_bytes = json_data.encode('utf-8')

            job = self.bq_client.load_table_from_file(
                io.BytesIO(json_bytes),
                temp_table_ref,
                job_config=job_config
            )
            job.result()
            
            logger.info(f"Loaded {len(field_entries)} rows into temporary table")
            
            # Create the final table with embeddings using the correct ML.GENERATE_EMBEDDING syntax
            final_query = f"""
            CREATE OR REPLACE TABLE `{BQ_PROJECT_ID}.{DATASET_ID}.{FIELD_VALUES_TABLE}` AS
            SELECT *
            FROM ML.GENERATE_EMBEDDING(
                MODEL `{BQ_PROJECT_ID}.{DATASET_ID}.text_embedding_model`,
                (
                    SELECT
                        *,
                        CONCAT(model_name, '.', explore_name, '.', view_name, '.', field_name) as field_location,
                        searchable_text as content
                    FROM `{BQ_PROJECT_ID}.{DATASET_ID}.{temp_table_id}`
                ),
                STRUCT(TRUE AS flatten_json_output)
            )
            """

            # Create query job config with explicit project
            query_job_config = bigquery.QueryJobConfig()

            job = self.bq_client.query(final_query, job_config=query_job_config)
            job.result()
            
            embedding_duration = time.time() - start_time
            logger.info(f"✅ Created final table with embeddings: {FIELD_VALUES_TABLE} (took {embedding_duration:.2f}s)")

            self._log_operation("create_table_with_embeddings", True, embedding_duration, {
                'field_entries_count': len(field_entries),
                'temp_table_id': temp_table_id
            })
            
            # Clean up temporary table
            self.bq_client.delete_table(temp_table_ref)
            logger.info(f"Cleaned up temporary table: {temp_table_id}")
            
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ Failed to create table with embeddings: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")

            self._log_operation("create_table_with_embeddings", False, duration, {
                'error': str(e),
                'traceback': traceback.format_exc(),
                'field_entries_count': len(field_entries)
            })

            return False
    
    def _get_dimension_sample_values(self, sdk, model_name: str, explore_name: str, field_info: Dict[str, Any]) -> Dict[str, int]:
        """Get sample values for a dimension by running a Looker query"""
        query_start_time = time.time()
        field_ref = f"{field_info['view']}.{field_info['name']}"

        logger.debug(f"🔍 Getting sample values for dimension: {field_ref}")

        try:
            # Construct the field reference for the query
            field_reference = f"{field_info['view']}.{field_info['name']}"
            
            # Handle duplicate prefixes like "products.products.brand" -> "products.brand"
            if field_reference.count('.') >= 2:
                # If there are 2+ periods, remove the first part (before first period)
                parts = field_reference.split('.', 1)  # Split only on first period
                if len(parts) == 2:
                    field_reference = parts[1]  # Use everything after first period
            
            # Print the field details for debugging
            logger.debug(f"   🔍   QUERY FIELD DEBUG:")
            logger.debug(f"       Model: {model_name}")
            logger.debug(f"       Explore: {explore_name}")
            logger.debug(f"       Original Field: {field_info['view']}.{field_info['name']}")
            logger.debug(f"       Cleaned Field Reference: {field_reference}")
            logger.debug(f"       Field Info: {field_info}")
            
            # Create a simple query to get top values for this dimension
            # Use a basic row count instead of a specific measure
            query_body = {
                "model": model_name,
                "view": explore_name,  # Quirky API: uses "view" even though it's an explore
                "fields": [field_reference],  # API uses "fields" not "dimensions"
                "sorts": [f"{field_reference}"],
                "limit": "5000",  # Get top 5000 values
                "vis_config": {"type": "table"}
            }
            
            logger.debug(f"   🔍   RAW API CALL - Query Body:")
            logger.debug(f"       {json.dumps(query_body, indent=8)}")
            
            # Log the actual API call details
            logger.debug(f"   📡 Making API request: POST /queries/run/json")
            logger.debug(f"   🔍   RAW API CALL - Making request:")
            logger.debug(f"       Method: POST")
            logger.debug(f"       Endpoint: /queries/run/json")
            logger.debug(f"       SDK Method: run_inline_query(result_format='json', body=...)")
            
            # Run the query
            api_call_start = time.time()
            try:
                query_result = sdk.run_inline_query(
                    result_format="json",
                    body=query_body
                )
                api_call_duration = time.time() - api_call_start
                logger.debug(f"   ⏱️ API call completed in {api_call_duration:.2f}s")
            except Exception as api_error:
                api_call_duration = time.time() - api_call_start
                logger.error(f"   ❌ API call failed after {api_call_duration:.2f}s: {api_error}")
                raise
            
            # Log the raw response
            logger.debug(f"   📝 Response type: {type(query_result)}, length: {len(query_result) if query_result else 'None'}")
            logger.debug(f"   🔍   RAW API RESPONSE:")
            logger.debug(f"       Response Type: {type(query_result)}")
            logger.debug(f"       Response Length: {len(query_result) if query_result else 'None'}")
            if query_result:
                # Show first 500 chars of response for debugging
                response_preview = str(query_result)[:500]
                logger.debug(f"       Response Preview (first 500 chars): {response_preview}")
                if len(str(query_result)) > 500:
                    logger.debug(f"       ... (response truncated, total length: {len(str(query_result))})")
            else:
                logger.debug(f"       Response: None/Empty")
            
            # Parse the results
            sample_values = {}
            if query_result:
                try:
                    data = json.loads(query_result)
                    
                    logger.debug(f"   📋 Parsed JSON - Type: {type(data)}, Length: {len(data) if hasattr(data, '__len__') else 'No length'}")
                    logger.debug(f"   🔍   PARSED JSON RESPONSE:")
                    logger.debug(f"       Data Type: {type(data)}")
                    logger.debug(f"       Data Length: {len(data) if hasattr(data, '__len__') else 'No length'}")
                    if isinstance(data, list) and len(data) > 0:
                        logger.debug(f"       First Row: {data[0]}")
                        logger.debug(f"       First Few Rows: {data[:3]}")
                    
                    for row in data:
                        # Handle dictionary format (expected from Looker API)
                        if isinstance(row, dict):
                            # Get the single field value from this row dictionary
                            for _, field_value in row.items():
                                if field_value is not None:
                                    value = str(field_value).strip()

                                    # Skip empty values
                                    if value and value.lower() not in ['null', 'n/a', '']:
                                        sample_values[value] = 1  # Default frequency
                        else:
                            # Fallback for list format (old format)
                            if len(row) >= 1 and row[0] is not None:
                                value = str(row[0]).strip()
                                
                                # Skip empty values
                                if value and value.lower() not in ['null', 'n/a', '']:
                                    sample_values[value] = 1  # Default frequency
                    
                    query_total_duration = time.time() - query_start_time
                    logger.debug(f"   ✅ Found {len(sample_values)} sample values for {field_reference} (total time: {query_total_duration:.2f}s)")
                    if sample_values:
                        top_values = list(sample_values.keys())[:5]
                        logger.debug(f"   📋   Top values: {top_values}")
                
                except Exception as e:
                    logger.warning(f"   ⚠️ JSON parsing failed for {field_reference}: {e}")
                    logger.error(f"   ⚠️   JSON PARSING ERROR for {field_reference}: {e}")
                    logger.error(f"   ⚠️   Raw response that failed to parse: {query_result}")
                    # Fallback to just the field label
                    sample_values = {field_info['label']: 1}
            
            # If no sample values found, use field metadata as fallback
            if not sample_values:
                sample_values = {field_info['label']: 1}
                logger.debug(f"   ℹ️ No sample values found for {field_reference}, using field label as fallback")
            
            return sample_values
            
        except Exception as e:
            query_duration = time.time() - query_start_time
            logger.warning(f"   ❌ Failed to get sample values for {field_ref} after {query_duration:.2f}s: {e}")
            logger.error(f"   ❌   FULL EXCEPTION for dimension {field_info['name']}: {e}")
            logger.error(f"   ❌   Query body: {json.dumps(query_body if 'query_body' in locals() else {}, indent=2)}")
            logger.error(f"   ❌   Traceback: {traceback.format_exc()}")

            # Return field label as fallback
            return {field_info['label']: 1}
    
    def create_vector_index(self) -> bool:
        """Create vector index for fast similarity search"""
        try:
            logger.info("Creating vector index...")
            
            # First check if we have enough rows for a vector index
            count_query = f"""
            SELECT COUNT(*) as total_rows 
            FROM `{BQ_PROJECT_ID}.{DATASET_ID}.{FIELD_VALUES_TABLE}`
            """
            count_result = self.bq_client.query(count_query).result()
            total_rows = next(count_result).total_rows
            
            if total_rows < 5000:
                logger.warning(f"Only {total_rows} rows in table. Vector index requires at least 5,000 rows.")
                logger.info("Will use VECTOR_SEARCH function directly instead of creating an index.")
                return True  # Consider this successful since we can still do vector search
            
            index_query = f"""
            CREATE VECTOR INDEX IF NOT EXISTS field_values_embedding_index
            ON `{BQ_PROJECT_ID}.{DATASET_ID}.{FIELD_VALUES_TABLE}`(ml_generate_embedding_result)
            OPTIONS (
                index_type = 'IVF',
                distance_type = 'COSINE'
            )
            """
            
            job = self.bq_client.query(index_query)
            job.result()
            
            logger.info("Successfully created vector index")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create vector index: {e}")
            # If it's a row count issue, still consider it successful
            if "smaller than min allowed" in str(e):
                logger.info("Will use VECTOR_SEARCH function directly instead of creating an index.")
                return True
            return False
    
    def _validate_system_prerequisites(self) -> bool:
        """Validate all system prerequisites before setup"""
        logger.info("🔍 Validating system prerequisites...")

        validation_passed = True

        # Check BigQuery client
        try:
            logger.debug("Testing BigQuery connection...")
            # Test with a simple query
            test_query = f"SELECT 1 as test"
            list(self.bq_client.query(test_query).result())  # Don't store result since we don't use it
            logger.debug("✅ BigQuery connection working")
        except Exception as e:
            logger.error(f"❌ BigQuery connection failed: {e}")
            validation_passed = False

        # Check dataset exists
        try:
            logger.debug(f"Checking if dataset {DATASET_ID} exists...")
            self.bq_client.get_dataset(DATASET_ID)  # Don't store result since we don't use it
            logger.debug(f"✅ Dataset {DATASET_ID} exists")
        except Exception as e:
            logger.error(f"❌ Dataset {DATASET_ID} does not exist: {e}")
            logger.info(f"You may need to create the dataset: bq mk --dataset {BQ_PROJECT_ID}:{DATASET_ID}")
            validation_passed = False

        # Check Looker SDK
        try:
            logger.debug("Testing Looker SDK connection...")
            sdk = self.get_looker_sdk(retry_on_failure=False)  # Don't retry during validation
            if sdk is None:
                logger.error("❌ Looker SDK connection failed")
                validation_passed = False
            else:
                logger.debug("✅ Looker SDK connection working")
        except Exception as e:
            logger.error(f"❌ Looker SDK validation failed: {e}")
            validation_passed = False

        if validation_passed:
            logger.info("✅ All system prerequisites validated successfully")
        else:
            logger.error("❌ System prerequisites validation failed")

        return validation_passed

    def setup_complete_system(self) -> bool:
        """Set up the complete vector search system"""
        start_time = time.time()
        logger.info("🚀 Setting up complete vector search system...")

        # Validate all prerequisites
        if not self._validate_system_prerequisites():
            return False

        try:
            
            # Step 1: Create embedding model
            if not self.create_embedding_model():
                return False
            
            # Step 2: Create field values table from Looker explores
            logger.info("Using Looker explores with 'index' sets to populate fields...")
            if not self.create_field_values_table_from_looker_explores():
                return False
            
            # Step 3: Create vector index
            if not self.create_vector_index():
                return False
            
            total_duration = time.time() - start_time
            logger.info(f"✅ Vector search system setup complete! (total time: {total_duration:.2f}s)")

            # Get final system stats
            try:
                stats = self.get_table_stats()
                logger.info(f"📊 Final system stats: {stats}")
            except Exception as stats_error:
                logger.warning(f"Could not retrieve final stats: {stats_error}")

            self._log_operation("setup_complete_system", True, total_duration, {
                'stats': stats if 'stats' in locals() else None
            })

            return True
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ Failed to setup vector search system: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")

            self._log_operation("setup_complete_system", False, duration, {
                'error': str(e),
                'traceback': traceback.format_exc(),
            })

            return False
    
    def update_field_values(self) -> bool:
        """Update field values table with latest Looker data"""
        try:
            logger.info("Updating field values table with latest Looker data...")
            return self.create_field_values_table_from_looker_explores()
            
        except Exception as e:
            logger.error(f"Failed to update field values: {e}")
            return False

    def _validate_field_entries(self, field_entries: List[Dict[str, Any]]) -> None:
        """Validate field entries for data quality issues"""
        logger.debug("🔍 Running data quality validation on field entries...")

        validation_issues = []

        # Check for required fields
        required_fields = ['model_name', 'explore_name', 'view_name', 'field_name', 'field_type', 'field_value', 'searchable_text']

        for i, entry in enumerate(field_entries):
            # Check for missing required fields
            missing_fields = [field for field in required_fields if field not in entry or not entry[field]]
            if missing_fields:
                validation_issues.append(f"Entry {i}: Missing required fields: {missing_fields}")

            # Check for suspicious field values
            if 'field_value' in entry:
                value = str(entry['field_value'])
                if len(value) > 1000:
                    validation_issues.append(f"Entry {i}: Field value too long ({len(value)} chars): {entry.get('field_name', 'unknown')}")
                if value.lower() in ['null', 'none', '', 'undefined']:
                    validation_issues.append(f"Entry {i}: Suspicious field value '{value}' for: {entry.get('field_name', 'unknown')}")

            # Check searchable text quality
            if 'searchable_text' in entry:
                text = str(entry['searchable_text'])
                if len(text) < 10:
                    validation_issues.append(f"Entry {i}: Searchable text too short for: {entry.get('field_name', 'unknown')}")

        # Summary statistics
        unique_models = len(set(e.get('model_name', '') for e in field_entries))
        unique_explores = len(set(f"{e.get('model_name', '')}.{e.get('explore_name', '')}" for e in field_entries))
        unique_views = len(set(e.get('view_name', '') for e in field_entries))
        unique_fields = len(set(f"{e.get('view_name', '')}.{e.get('field_name', '')}" for e in field_entries))

        logger.info(f"📊 Data quality summary:")
        logger.info(f"   Unique models: {unique_models}")
        logger.info(f"   Unique explores: {unique_explores}")
        logger.info(f"   Unique views: {unique_views}")
        logger.info(f"   Unique fields: {unique_fields}")
        logger.info(f"   Avg entries per field: {len(field_entries)/unique_fields:.1f}")

        if validation_issues:
            logger.warning(f"⚠️ Found {len(validation_issues)} data quality issues:")
            for issue in validation_issues[:10]:  # Show first 10 issues
                logger.warning(f"   {issue}")
            if len(validation_issues) > 10:
                logger.warning(f"   ... and {len(validation_issues) - 10} more issues")

            self._log_warning(f"Data quality validation found {len(validation_issues)} issues", {
                'total_issues': len(validation_issues),
                'total_entries': len(field_entries),
                'issue_rate': len(validation_issues) / len(field_entries) * 100
            })
        else:
            logger.info("✅ Data quality validation passed - no issues found")

    def get_operation_summary(self) -> Dict[str, Any]:
        """Get a summary of all operations performed"""
        return {
            'total_runtime': time.time() - self.stats['start_time'],
            'operations_count': len(self.stats['operations']),
            'successful_operations': len([op for op in self.stats['operations'] if op['success']]),
            'failed_operations': len(self.stats['errors']),
            'warnings_count': len(self.stats['warnings']),
            'operations': self.stats['operations'],
            'errors': self.stats['errors'],
            'warnings': self.stats['warnings']
        }

    def get_table_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector tables"""
        try:
            stats_query = f"""
            SELECT 
                COUNT(*) as total_rows,
                COUNT(DISTINCT field_location) as unique_fields,
                COUNT(DISTINCT CONCAT(model_name, ':', explore_name)) as unique_explores,
                COUNT(DISTINCT model_name) as unique_models
            FROM `{BQ_PROJECT_ID}.{DATASET_ID}.{FIELD_VALUES_TABLE}`
            """
            
            result = self.bq_client.query(stats_query).result()
            stats = next(result)
            
            return {
                "total_rows": stats.total_rows,
                "unique_fields": stats.unique_fields,
                "unique_explores": stats.unique_explores,
                "unique_models": stats.unique_models,
                "table_name": FIELD_VALUES_TABLE,
                "project_id": PROJECT_ID,
                "dataset_id": DATASET_ID
            }
            
        except Exception as e:
            logger.error(f"Failed to get table stats: {e}")
            return {"error": str(e)}

def main():
    """Main function for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage vector tables for field discovery")
    parser.add_argument("--action", choices=["setup", "update", "stats"], required=True,
                       help="Action to perform")
    
    args = parser.parse_args()
    
    manager = VectorTableManager()
    
    if args.action == "setup":
        success = manager.setup_complete_system()
        sys.exit(0 if success else 1)
    
    elif args.action == "update":
        success = manager.update_field_values()
        sys.exit(0 if success else 1)
    
    elif args.action == "stats":
        stats = manager.get_table_stats()
        print(json.dumps(stats, indent=2))

if __name__ == "__main__":
    main()
