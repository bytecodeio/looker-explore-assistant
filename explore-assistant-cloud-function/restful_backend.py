#!/usr/bin/env python3
"""
Looker Explore Assistant REST API Backend

Production-ready REST API server using Flask + Gunicorn for the Looker Explore Assistant.
Replaces mcp_server.py with a modern, modular architecture and production-ready deployment.

Features:
- Production WSGI server support (Gunicorn)
- Modern modular architecture using new modules
- Clean REST API endpoints with consistent patterns
- Proper error handling and logging
- Cloud Run optimized configuration
"""

import os
import json
import logging
import traceback
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urlencode

from flask import Flask, request, Response, jsonify, Blueprint
from flask_cors import CORS
from google.cloud import bigquery
from google.auth import default
from google.auth.transport.requests import Request
from google.oauth2 import service_account
import looker_sdk
from looker_sdk.rtl import api_settings

# Import from new modular architecture
from core.config import get_environment_config, VERTEX_MODEL, BQ_PROJECT_ID, BQ_DATASET_ID, EMBEDDING_MODEL
from core.auth import extract_user_info_from_token
from core.exceptions import ParameterGenerationError
from core.models import QueryParameters, GenerationResult
from vertex.client import call_vertex_ai_with_retry
from parameter_generation import generate_explore_params_from_query, validate_explore_parameters
from explore_selection import determine_explore_from_prompt
from vector_search.client import VectorSearchClient

# Import legacy utilities still needed
from llm_utils import parse_llm_response
from olympic_query_manager import OlympicQueryManager, QueryRank
from olympic_mcp_integration import OlympicMCPIntegration
from olympic_migration_manager import OlympicMigrationManager
from field_lookup_service import FieldValueLookupService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global configuration
BQ_PROJECT_ID = os.environ.get("BQ_PROJECT_ID", "your-bigquery-project-id")
BQ_DATASET_ID = os.environ.get("BQ_DATASET_ID", "looker_scratch")


class RestfulBackendError(Exception):
    """Custom exception for REST API errors"""
    def __init__(self, message: str, status_code: int = 500, details: Dict = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


def _construct_looker_explore_url(explore_id: str, generated_params: dict) -> str:
    """
    Construct a proper Looker explore URL from explore_id and parameters.
    
    Args:
        explore_id: In format "model:explore"
        generated_params: Dictionary of explore parameters
        
    Returns:
        str: Complete Looker explore URL with parameters
    """
    try:
        # Parse explore_id to get model and explore names
        if ':' in explore_id:
            model_name, explore_name = explore_id.split(':', 1)
        else:
            logger.warning(f"Invalid explore_id format: {explore_id}")
            return ""
        
        # Create a temporary Olympic migration manager instance for link generation
        migration_manager = OlympicMigrationManager(
            project_id=BQ_PROJECT_ID,
            dataset_id=BQ_DATASET_ID
        )
        
        # Generate the proper Looker URL
        looker_url = migration_manager._generate_looker_link(
            model_name=model_name,
            explore_name=explore_name,
            explore_params=generated_params
        )
        
        logger.info(f"Generated Looker URL: {looker_url}")
        return looker_url or ""
        
    except Exception as e:
        logger.error(f"Failed to construct Looker explore URL: {e}")
        return ""


def create_app() -> Flask:
    """
    Application factory for creating the Flask app.
    
    This pattern allows for better testing and configuration management.
    """
    app = Flask(__name__)
    
    # Load configuration
    config = get_environment_config()
    app.config.update(config)
    
    # Enable CORS for all routes
    CORS(app)
    
    # Initialize services
    _initialize_services(app)
    
    # Register blueprints
    _register_blueprints(app)
    
    # Register error handlers
    _register_error_handlers(app)
    
    logger.info("✅ Restful backend application created successfully")
    return app


def _initialize_services(app: Flask) -> None:
    """Initialize external services and store in app context"""
    try:
        # Initialize BigQuery client
        app.bq_client = bigquery.Client(project=BQ_PROJECT_ID)
        logger.info("✅ BigQuery client initialized")
        
        # Initialize Olympic query manager
        app.olympic_manager = OlympicQueryManager(
            bq_client=app.bq_client,
            project_id=BQ_PROJECT_ID,
            dataset_id=BQ_DATASET_ID
        )
        logger.info("✅ Olympic query manager initialized")
        
        # Initialize field lookup service
        app.field_lookup = FieldValueLookupService()
        logger.info("✅ Field lookup service initialized")
        
        # Initialize vector search client
        app.vector_search = VectorSearchClient()
        logger.info("✅ Vector search client initialized")
        
        # Initialize Looker SDK
        _initialize_looker_sdk(app)
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        raise


def _initialize_looker_sdk(app: Flask) -> None:
    """Initialize Looker SDK with proper configuration"""
    try:
        # Get Looker configuration from environment
        looker_config = api_settings.ApiSettings(
            base_url=os.environ.get("LOOKER_BASE_URL"),
            client_id=os.environ.get("LOOKER_CLIENT_ID"),
            client_secret=os.environ.get("LOOKER_CLIENT_SECRET"),
            verify_ssl=True
        )
        
        app.looker_sdk = looker_sdk.init40(config_settings=looker_config)
        logger.info("✅ Looker SDK initialized")
        
    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize Looker SDK: {e}")
        app.looker_sdk = None


def _register_blueprints(app: Flask) -> None:
    """Register API blueprints"""
    
    # Main API blueprint
    api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')
    
    @api_v1.route('/query', methods=['POST', 'OPTIONS'])
    def handle_query():
        """Main query processing endpoint"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        
        import time
        start_time = time.time()
        debug_session_id = None
        
        try:
            # Extract request data
            data = request.get_json(force=True)
            if not data:
                raise RestfulBackendError("No JSON data provided", 400)
            
            # Check for debug mode
            debug_mode = data.get('debug', False) or request.args.get('debug', '').lower() == 'true'
            
            # Initialize debug logging if requested
            if debug_mode:
                from core.debug_logger import debug_logger
                debug_logger.enable_debug_mode()
                debug_session_id = debug_logger.start_debug_session(data)
                debug_logger.log_processing_step("request_received", {
                    "query": data.get('query', data.get('prompt', ''))[:100],
                    "explore_key": data.get('explore_key'),
                    "debug_mode": True
                })
            
            # Extract user info from auth header
            auth_header = request.headers.get('Authorization', '')
            user_info = extract_user_info_from_token(auth_header)
            
            # Process the query
            result = _process_query_request(data, auth_header, user_info, debug_mode=debug_mode)
            
            # Calculate processing time
            total_time_ms = (time.time() - start_time) * 1000
            
            # Build response
            response_data = {
                "success": True,
                "data": result,
                "timestamp": datetime.utcnow().isoformat(),
                "processing_time_ms": round(total_time_ms, 2)
            }
            
            # Add debug information if in debug mode
            if debug_mode and debug_session_id:
                from core.debug_logger import debug_logger
                # End debug session
                debug_logger.end_debug_session(
                    response_data=response_data,
                    success=True,
                    total_processing_time_ms=total_time_ms
                )
                
                # Add debug information to response
                response_data["debug_info"] = {
                    "session_id": debug_session_id,
                    "debug_log_url": f"/api/v1/debug/logs/{debug_session_id}",
                    "llm_interactions_count": len(debug_logger.current_session.llm_interactions) if debug_logger.current_session else 0,
                    "processing_steps_count": len(debug_logger.current_session.processing_steps) if debug_logger.current_session else 0,
                    "verbose_details": {
                        "total_processing_time_ms": total_time_ms,
                        "request_size_bytes": len(json.dumps(data)),
                        "response_size_bytes": len(json.dumps(response_data))
                    }
                }
                
                debug_logger.disable_debug_mode()
            
            return jsonify(response_data)
            
        except RestfulBackendError as e:
            # Handle debug mode for errors
            if debug_mode and debug_session_id:
                from core.debug_logger import debug_logger
                debug_logger.end_debug_session(
                    response_data={"error": e.message},
                    success=False,
                    error=e.message,
                    total_processing_time_ms=(time.time() - start_time) * 1000
                )
                debug_logger.disable_debug_mode()
            return _handle_api_error(e)
        except Exception as e:
            # Handle debug mode for unexpected errors
            if debug_mode and debug_session_id:
                from core.debug_logger import debug_logger
                debug_logger.end_debug_session(
                    response_data={"error": str(e)},
                    success=False,
                    error=str(e),
                    total_processing_time_ms=(time.time() - start_time) * 1000
                )
                debug_logger.disable_debug_mode()
            logger.error(f"Unexpected error in query endpoint: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Internal server error: {str(e)}", 500))
    
    @api_v1.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint for Cloud Run"""
        try:
            # Basic health checks
            health_status = {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "services": {
                    "bigquery": "unknown",
                    "vertex_ai": "unknown",
                    "looker_sdk": "unknown"
                }
            }
            
            # Check BigQuery
            try:
                list(app.bq_client.query("SELECT 1").result())
                health_status["services"]["bigquery"] = "healthy"
            except Exception:
                health_status["services"]["bigquery"] = "unhealthy"
            
            # Check Looker SDK
            if app.looker_sdk:
                try:
                    app.looker_sdk.me()
                    health_status["services"]["looker_sdk"] = "healthy"
                except Exception:
                    health_status["services"]["looker_sdk"] = "unhealthy"
            
            return jsonify(health_status)
            
        except Exception as e:
            return jsonify({
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }), 500
    
    @api_v1.route('/system-status', methods=['GET'])
    def system_status():
        """Get comprehensive system status"""
        try:
            # Initialize the system status service
            from core.system_status import SystemStatusService
            from core.config import BQ_PROJECT_ID, BQ_DATASET_ID
            
            status_service = SystemStatusService(
                bq_client=app.bq_client,
                project_id=BQ_PROJECT_ID,
                dataset_id=BQ_DATASET_ID
            )
            
            # Get comprehensive status
            status_data = status_service.get_comprehensive_status()
            
            return jsonify({
                "success": True,
                "data": status_data
            })
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return jsonify({
                "success": False,
                "error": str(e),
                "data": {
                    "system_status": "error",
                    "timestamp": datetime.utcnow().isoformat(),
                    "error_message": str(e)
                }
            }), 500
    
    @api_v1.route('/system-status/migration', methods=['GET'])
    def system_migration_status():
        """Get migration-specific system status"""
        try:
            # Initialize the system status service
            from core.system_status import SystemStatusService
            from core.config import BQ_PROJECT_ID, BQ_DATASET_ID
            
            status_service = SystemStatusService(
                bq_client=app.bq_client,
                project_id=BQ_PROJECT_ID,
                dataset_id=BQ_DATASET_ID
            )
            
            # Get migration status
            migration_data = status_service.get_migration_status()
            
            return jsonify({
                "success": True,
                "data": migration_data
            })
            
        except Exception as e:
            logger.error(f"Error getting migration status: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    @api_v1.route('/system-status/health', methods=['GET'])
    def quick_health_check():
        """Quick health check endpoint (lighter than full system status)"""
        try:
            from core.system_status import SystemStatusService
            from core.config import BQ_PROJECT_ID, BQ_DATASET_ID
            
            status_service = SystemStatusService(
                bq_client=app.bq_client,
                project_id=BQ_PROJECT_ID,
                dataset_id=BQ_DATASET_ID
            )
            
            # Get quick health check
            health_data = status_service.get_quick_health_check()
            
            return jsonify({
                "success": True,
                "data": health_data
            })
            
        except Exception as e:
            logger.error(f"Error in quick health check: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    @api_v1.route('/vertex-proxy', methods=['POST', 'OPTIONS'])
    def vertex_proxy():
        """Vertex AI API proxy endpoint"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        
        try:
            # Extract request data
            data = request.get_json(force=True)
            if not data:
                raise RestfulBackendError("No JSON data provided", 400)
            
            # Extract auth header
            auth_header = request.headers.get('Authorization', '')
            
            # Call Vertex AI
            result = call_vertex_ai_with_retry(
                data, 
                context="vertex_proxy",
                process_response=True
            )
            
            return jsonify({
                "success": True,
                "data": result,
                "timestamp": datetime.utcnow().isoformat()
            })
            
        except RestfulBackendError as e:
            return _handle_api_error(e)
        except Exception as e:
            logger.error(f"Vertex proxy error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Vertex AI error: {str(e)}", 500))

    @api_v1.route('/feedback/positive', methods=['POST', 'OPTIONS'])
    def submit_positive_feedback():
        """Submit positive feedback for a query"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        
        try:
            data = request.get_json(force=True)
            
            # Extract user info from auth header
            auth_header = request.headers.get('Authorization', '')
            user_info = extract_user_info_from_token(auth_header)
            user_email = user_info.get('email') or user_info.get('user_id') or 'unknown'
            
            # Extract required fields
            query_id = data.get('query_id')
            user_input = data.get('user_input') 
            response = data.get('response')
            explore_key = data.get('explore_key')
            feedback_notes = data.get('feedback_notes', '')
            
            if not all([query_id, user_input, response]):
                raise RestfulBackendError("query_id, user_input, and response are required", 400)
            
            # Store positive feedback in Olympic system
            # Use user_id parameter as per standardized implementation
            # But pass user_email value until schema migration is complete
            app.olympic_manager.add_feedback_query(
                explore_id=explore_key or "unknown",
                original_prompt=user_input,
                generated_params=json.loads(response) if isinstance(response, str) else response,
                share_url="",
                feedback_type="positive",
                user_id=user_email,  # Pass email as user_id which will be stored in user_email field
                user_comment=feedback_notes
            )
            
            return jsonify({
                "success": True,
                "message": "Positive feedback submitted successfully"
            })
            
        except Exception as e:
            logger.error(f"Positive feedback submission error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Failed to submit positive feedback: {str(e)}", 500))

    @api_v1.route('/feedback/negative', methods=['POST', 'OPTIONS'])
    def submit_negative_feedback():
        """Submit negative feedback for a query"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        
        try:
            data = request.get_json(force=True)
            
            # Extract user info from auth header
            auth_header = request.headers.get('Authorization', '')
            user_info = extract_user_info_from_token(auth_header)
            user_email = user_info.get('email') or user_info.get('user_id') or 'unknown'
            
            # Extract required fields
            query_id = data.get('query_id')
            user_input = data.get('user_input')
            response = data.get('response') 
            explore_key = data.get('explore_key')
            issues = data.get('issues', [])
            improvement_suggestions = data.get('improvement_suggestions', '')
            
            if not all([query_id, user_input, response]):
                raise RestfulBackendError("query_id, user_input, and response are required", 400)
            
            # Combine issues and suggestions into feedback notes
            feedback_notes = f"Issues: {', '.join(issues)}"
            if improvement_suggestions:
                feedback_notes += f"\nSuggestions: {improvement_suggestions}"
            
            # Store negative feedback in Olympic system
            # Use user_id parameter as per standardized implementation
            # But pass user_email value until schema migration is complete
            app.olympic_manager.add_feedback_query(
                explore_id=explore_key or "unknown",
                original_prompt=user_input,
                generated_params=json.loads(response) if isinstance(response, str) else response,
                share_url="",
                feedback_type="negative", 
                user_id=user_email,  # Pass email as user_id which will be stored in user_email field
                user_comment=feedback_notes
            )
            
            return jsonify({
                "success": True,
                "message": "Negative feedback submitted successfully"
            })
            
        except Exception as e:
            logger.error(f"Negative feedback submission error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Failed to submit negative feedback: {str(e)}", 500))

    @api_v1.route('/feedback', methods=['POST', 'OPTIONS'])
    def submit_general_feedback():
        """Submit general feedback for a query (supports all feedback types)"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        
        try:
            data = request.get_json(force=True)
            
            # Extract user info from auth header
            auth_header = request.headers.get('Authorization', '')
            user_info = extract_user_info_from_token(auth_header)
            user_email = user_info.get('email') or user_info.get('user_id') or 'unknown'
            
            # Extract required fields
            explore_id = data.get('explore_id')
            original_prompt = data.get('original_prompt')
            generated_params = data.get('generated_params')
            share_url = data.get('share_url', '')
            feedback_type = data.get('feedback_type')
            user_comment = data.get('user_comment', '')
            suggested_improvements = data.get('suggested_improvements')
            issues = data.get('issues', [])
            query_id = data.get('query_id')
            
            # Debug logging to check share_url
            logger.info(f"DEBUG: Received share_url: {share_url}")
            logger.info(f"DEBUG: Generated params: {type(generated_params)} - {generated_params}")
            
            if not all([explore_id, original_prompt, feedback_type]):
                raise RestfulBackendError("explore_id, original_prompt, and feedback_type are required", 400)
            
            # Convert generated_params to dict if it's a string
            params_dict = generated_params if isinstance(generated_params, dict) else json.loads(generated_params) if generated_params else {}
            
            # Construct proper Looker explore URL from the parameters
            constructed_share_url = _construct_looker_explore_url(explore_id, params_dict)
            if constructed_share_url:
                share_url = constructed_share_url
                logger.info(f"Using constructed share_url: {share_url}")
            else:
                logger.warning(f"Failed to construct URL, using provided share_url: {share_url}")
            
            # Prepare feedback notes based on type
            feedback_notes = user_comment
            if feedback_type == 'negative' and issues:
                feedback_notes = f"Issues: {', '.join(issues)}"
                if user_comment:
                    feedback_notes += f"\nComment: {user_comment}"
                if suggested_improvements:
                    feedback_notes += f"\nSuggestions: {suggested_improvements}"
            elif suggested_improvements and isinstance(suggested_improvements, str):
                if feedback_notes:
                    feedback_notes += f"\nSuggestions: {suggested_improvements}"
                else:
                    feedback_notes = f"Suggestions: {suggested_improvements}"
            
            # Store feedback in Olympic system
            # Use user_id parameter as per standardized implementation
            # But pass user_email value until schema migration is complete
            app.olympic_manager.add_feedback_query(
                explore_id=explore_id,
                original_prompt=original_prompt,
                generated_params=params_dict,
                share_url=share_url,
                feedback_type=feedback_type,
                user_id=user_email,  # Pass email as user_id which will be stored in user_email field
                user_comment=feedback_notes,
                query_id=query_id
            )
            
            return jsonify({
                "success": True,
                "status": "success",
                "message": f"{feedback_type.capitalize()} feedback submitted successfully"
            })
            
        except Exception as e:
            logger.error(f"General feedback submission error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Failed to submit feedback: {str(e)}", 500))

    @api_v1.route('/feedback/history', methods=['GET', 'OPTIONS'])
    def get_feedback_history():
        """Get feedback history with optional filters"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        
        try:
            # Get query parameters
            explore_id = request.args.get('explore_id')
            user_id = request.args.get('user_id')
            feedback_type = request.args.get('feedback_type')
            limit = int(request.args.get('limit', 20))
            
            # For now, return mock data since there's no specific history method in Olympic manager
            # This would need to be implemented in the Olympic system
            history = []
            
            return jsonify({
                "success": True,
                "data": history,
                "feedback_history": history,  # For backward compatibility
                "total": len(history)
            })
            
        except Exception as e:
            logger.error(f"Feedback history error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Failed to get feedback history: {str(e)}", 500))

    @api_v1.route('/feedback/stats', methods=['GET', 'OPTIONS'])
    def get_feedback_stats():
        """Get feedback statistics"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        
        try:
            # Use Olympic manager to get query stats (which includes feedback data)
            stats = app.olympic_manager.get_query_stats() if hasattr(app.olympic_manager, 'get_query_stats') else {}
            
            return jsonify({
                "success": True,
                "data": stats,
                "query_statistics": stats  # For backward compatibility
            })
            
        except Exception as e:
            logger.error(f"Feedback stats error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Failed to get feedback stats: {str(e)}", 500))

    @api_v1.route('/areas', methods=['GET', 'OPTIONS'])
    def get_areas():
        """Get available areas from BigQuery"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        
        try:
            # Get areas from BigQuery
            query = f"""
            SELECT DISTINCT area, explore_key, description
            FROM `{BQ_PROJECT_ID}.explore_assistant.areas`
            ORDER BY area
            """
            
            results = list(app.bq_client.query(query))
            areas_data = [
                {
                    "area": row.area,
                    "explore_key": row.explore_key, 
                    "description": row.description
                }
                for row in results
            ]
            
            return jsonify({
                "success": True,
                "data": areas_data,
                "areas": areas_data  # For compatibility with frontend expectations
            })
            
        except Exception as e:
            logger.error(f"Areas query error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Failed to get areas: {str(e)}", 500))
    
    # Register the blueprint
    app.register_blueprint(api_v1)
    
    # Add admin endpoints
    _register_admin_endpoints(app)
    
    # Add debug endpoints
    _register_debug_endpoints(app)
    
    # Add legacy endpoints for compatibility
    _register_legacy_endpoints(app)


def _register_admin_endpoints(app: Flask) -> None:
    """Register admin endpoints"""
    
    admin_bp = Blueprint('admin', __name__, url_prefix='/api/v1/admin')
    
    @admin_bp.route('/queries/<table_name>', methods=['GET', 'OPTIONS'])
    def get_queries(table_name: str):
        """Get queries from specified table"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        
        try:
            # Validate table name
            if table_name not in ['bronze', 'silver', 'gold']:
                raise RestfulBackendError(f"Invalid table name: {table_name}", 400)
            
            # Get queries using Olympic manager
            queries = app.olympic_manager.get_queries_by_rank(
                QueryRank[table_name.upper()]
            )
            
            return jsonify({
                "success": True,
                "data": queries,
                "table": table_name,
                "count": len(queries)
            })
            
        except RestfulBackendError as e:
            return _handle_api_error(e)
        except Exception as e:
            logger.error(f"Admin queries error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Failed to get queries: {str(e)}", 500))
    
    @admin_bp.route('/promote', methods=['POST', 'OPTIONS'])
    def promote_query():
        """Promote a query to higher rank"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        
        try:
            data = request.get_json(force=True)
            if not data:
                raise RestfulBackendError("No JSON data provided", 400)

            query_id = data.get('query_id')
            target_rank = data.get('target_rank', '').upper()

            if not query_id:
                raise RestfulBackendError("query_id is required", 400)

            if target_rank not in ['BRONZE', 'SILVER', 'GOLD']:
                raise RestfulBackendError("target_rank must be BRONZE, SILVER, or GOLD", 400)

            # Initialize Olympic service
            from core.olympic_service import OlympicOperationsService, QueryRank
            from core.config import BQ_PROJECT_ID, BQ_DATASET_ID

            olympic_service = OlympicOperationsService(
                bq_client=app.bq_client,
                project_id=BQ_PROJECT_ID,
                dataset_id=BQ_DATASET_ID
            )

            # Only include promotion_reason if present and non-empty (not blank/whitespace)
            promote_kwargs = dict(
                query_id=query_id,
                target_rank=QueryRank[target_rank],
                promoted_by=data.get('promoted_by', 'unknown')
            )
            if (
                'promotion_reason' in data
                and data['promotion_reason']
                and str(data['promotion_reason']).strip()
            ):
                promote_kwargs['promotion_reason'] = data['promotion_reason']

            # Promote using shared service
            result = olympic_service.promote_query(**promote_kwargs)

            # If result contains an error, return 400
            if not result or (isinstance(result, dict) and result.get('error')):
                error_msg = result.get('error', 'Failed to promote query') if isinstance(result, dict) else 'Failed to promote query'
                return _handle_api_error(RestfulBackendError(error_msg, 400))

            return jsonify({
                "success": True,
                "data": result,
                "message": f"Query {query_id} promoted to {target_rank}"
            })

        except RestfulBackendError as e:
            return _handle_api_error(e)
        except Exception as e:
            logger.error(f"Query promotion error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Failed to promote query: {str(e)}", 500))
    
    @admin_bp.route('/queries/bronze', methods=['POST', 'OPTIONS'])
    def add_bronze_query():
        """Add a bronze query to the Olympic system"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        
        try:
            data = request.get_json(force=True)
            if not data:
                raise RestfulBackendError("No JSON data provided", 400)
            
            # Extract required fields
            explore_id = data.get('explore_id')
            input_text = data.get('input')
            output_data = data.get('output')
            link = data.get('link')
            user_email = data.get('user_email')
            
            # Validate required fields
            if not all([explore_id, input_text, output_data, link, user_email]):
                raise RestfulBackendError(
                    "explore_id, input, output, link, and user_email are required", 400
                )
            
            # Initialize Olympic service
            from core.olympic_service import OlympicOperationsService
            from core.config import BQ_PROJECT_ID, BQ_DATASET_ID
            
            olympic_service = OlympicOperationsService(
                bq_client=app.bq_client,
                project_id=BQ_PROJECT_ID,
                dataset_id=BQ_DATASET_ID
            )
            
            # Add bronze query
            result = olympic_service.add_bronze_query(
                explore_id=explore_id,
                input_text=input_text,
                output_data=output_data,
                link=link,
                user_email=user_email,
                session_id=data.get('session_id')
            )
            
            if not result.get('success'):
                raise RestfulBackendError(result.get('error', 'Failed to add bronze query'), 500)
            
            return jsonify({
                "success": True,
                "data": result,
                "message": "Bronze query added successfully"
            })
            
        except RestfulBackendError as e:
            return _handle_api_error(e)
        except Exception as e:
            logger.error(f"Add bronze query error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Failed to add bronze query: {str(e)}", 500))
    
    @admin_bp.route('/queries/silver', methods=['POST', 'OPTIONS'])
    def add_silver_query():
        """Add a silver query to the Olympic system"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        
        try:
            data = request.get_json(force=True)
            if not data:
                raise RestfulBackendError("No JSON data provided", 400)
            
            # Extract required fields
            explore_id = data.get('explore_id')
            input_text = data.get('input')
            output_data = data.get('output')
            link = data.get('link')
            user_id = data.get('user_id')
            feedback_type = data.get('feedback_type')
            
            # Validate required fields
            if not all([explore_id, input_text, output_data, link, user_id, feedback_type]):
                raise RestfulBackendError(
                    "explore_id, input, output, link, user_id, and feedback_type are required", 400
                )
            
            # Initialize Olympic service
            from core.olympic_service import OlympicOperationsService
            from core.config import BQ_PROJECT_ID, BQ_DATASET_ID
            
            olympic_service = OlympicOperationsService(
                bq_client=app.bq_client,
                project_id=BQ_PROJECT_ID,
                dataset_id=BQ_DATASET_ID
            )
            
            # Add silver query
            result = olympic_service.add_silver_query(
                explore_id=explore_id,
                input_text=input_text,
                output_data=output_data,
                link=link,
                user_email=user_email,
                feedback_type=feedback_type,
                conversation_history=data.get('conversation_history')
            )
            
            if not result.get('success'):
                raise RestfulBackendError(result.get('error', 'Failed to add silver query'), 500)
            
            return jsonify({
                "success": True,
                "data": result,
                "message": "Silver query added successfully"
            })
            
        except RestfulBackendError as e:
            return _handle_api_error(e)
        except Exception as e:
            logger.error(f"Add silver query error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Failed to add silver query: {str(e)}", 500))
    
    @admin_bp.route('/queries/<query_id>', methods=['DELETE', 'OPTIONS'])
    def delete_query(query_id: str):
        """Delete a query from the Olympic system"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        
        try:
            data = request.get_json(force=True) or {}
            deleted_by = data.get('deleted_by', 'unknown')
            
            # Initialize Olympic service
            from core.olympic_service import OlympicOperationsService
            from core.config import BQ_PROJECT_ID, BQ_DATASET_ID
            
            olympic_service = OlympicOperationsService(
                bq_client=app.bq_client,
                project_id=BQ_PROJECT_ID,
                dataset_id=BQ_DATASET_ID
            )
            
            # Delete query
            result = olympic_service.delete_query(
                query_id=query_id,
                deleted_by=deleted_by
            )
            
            if not result.get('success'):
                raise RestfulBackendError(result.get('error', 'Failed to delete query'), 500)
            
            return jsonify({
                "success": True,
                "data": result,
                "message": f"Query {query_id} deleted successfully"
            })
            
        except RestfulBackendError as e:
            return _handle_api_error(e)
        except Exception as e:
            logger.error(f"Delete query error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Failed to delete query: {str(e)}", 500))
    
    @admin_bp.route('/stats', methods=['GET', 'OPTIONS'])
    def get_query_stats():
        """Get Olympic query statistics"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        
        try:
            # Initialize Olympic service
            from core.olympic_service import OlympicOperationsService
            from core.config import BQ_PROJECT_ID, BQ_DATASET_ID
            
            olympic_service = OlympicOperationsService(
                bq_client=app.bq_client,
                project_id=BQ_PROJECT_ID,
                dataset_id=BQ_DATASET_ID
            )
            
            # Get query stats
            stats = olympic_service.get_query_stats()
            
            return jsonify({
                "success": True,
                "data": stats
            })
            
        except Exception as e:
            logger.error(f"Get query stats error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Failed to get query stats: {str(e)}", 500))
    
    # --- Custom: Disqualified Queries Endpoint ---
    @admin_bp.route('/queries/disqualified', methods=['GET', 'OPTIONS'])
    def get_disqualified_queries():
        """Get queries with rank 'disqualified' from the Olympic system"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        try:
            # Use OlympicQueryManager directly (for legacy/compat)
            queries = app.olympic_manager.get_queries_by_rank(QueryRank.DISQUALIFIED)
            return jsonify({
                "success": True,
                "data": queries,
                "table": "disqualified",
                "count": len(queries)
            })
        except Exception as e:
            logger.error(f"Get disqualified queries error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Failed to get disqualified queries: {str(e)}", 500))

    # --- Custom: Olympic Migration Endpoint ---
    @admin_bp.route('/migrate', methods=['POST', 'OPTIONS'])
    def perform_olympic_migration():
        """Perform migration to the Olympic system (unified table)"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        try:
            data = request.get_json(force=True) or {}
            preserve_data = data.get('preserve_data', True)
            verify_migration = data.get('verify_migration', True)
            # Use OlympicMCPIntegration for migration logic
            migration_manager = OlympicMCPIntegration(
                bq_client=app.bq_client,
                project_id=BQ_PROJECT_ID,
                dataset_id=BQ_DATASET_ID
            )
            # The MCP method is async, but we can call it synchronously for Flask
            import asyncio
            migration_result = asyncio.run(
                migration_manager.handle_migrate_to_olympic_system({
                    'preserve_data': preserve_data,
                    'verify_migration': verify_migration
                })
            )
            return jsonify({
                "success": True,
                "data": migration_result
            })
        except Exception as e:
            logger.error(f"Olympic migration error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Failed to perform migration: {str(e)}", 500))

    @admin_bp.route('/olympic/update-links', methods=['POST', 'OPTIONS'])
    def update_olympic_links():
        """Update existing Olympic table records with generated Looker links"""
        if request.method == 'OPTIONS':
            return _handle_cors()
            
        try:
            logger.info("Starting Olympic link update...")
            
            # Get request parameters
            data = request.get_json(force=True) or {}
            force_regenerate = data.get('force_regenerate', False)
            
            # Initialize migration manager for link updating
            migration_manager = OlympicMigrationManager(
                bq_client=app.bq_client,
                project_id=BQ_PROJECT_ID,
                dataset_id=BQ_DATASET_ID
            )
            
            # Update links
            result = migration_manager.update_olympic_links(force_regenerate=force_regenerate)
            
            return jsonify({
                "success": result["success"],
                "data": result,
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Olympic link update error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Failed to update links: {str(e)}", 500))

    # --- Vector Search Management Endpoints ---
    @admin_bp.route('/vector-search/status', methods=['GET', 'OPTIONS'])
    def get_vector_search_status():
        """Get comprehensive vector search system status"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        try:
            from vector_table_manager import VectorTableManager
            vector_manager = VectorTableManager()
            
            # Get comprehensive status
            status = {
                "timestamp": datetime.utcnow().isoformat(),
                "system_status": "unknown",
                "components": {
                    "bigquery_connection": "unknown",
                    "embedding_model": "unknown",
                    "field_values_table": "unknown",
                    "vector_index": "unknown"
                },
                "statistics": {},
                "recommendations": []
            }
            
            # Check BigQuery connection
            try:
                list(app.bq_client.query("SELECT 1").result())
                status["components"]["bigquery_connection"] = "operational"
            except Exception as e:
                status["components"]["bigquery_connection"] = "failed"
                status["recommendations"].append(f"BigQuery connection failed: {str(e)}")
            
            # Check embedding model by trying to use it
            try:
                logger.info(f"🔍 Checking embedding model: {BQ_PROJECT_ID}.{BQ_DATASET_ID}.{EMBEDDING_MODEL}")
                # Try to use the model with a simple embedding generation query
                model_query = f"""
                SELECT 1 as test_query
                FROM ML.GENERATE_TEXT_EMBEDDING(
                    MODEL `{BQ_PROJECT_ID}.{BQ_DATASET_ID}.{EMBEDDING_MODEL}`,
                    (SELECT 'test' as content),
                    STRUCT('SEMANTIC_SIMILARITY' as task_type)
                )
                LIMIT 1
                """
                logger.info(f"🔍 Executing embedding model test query: {model_query}")
                results = list(app.bq_client.query(model_query).result())
                logger.info(f"✅ Embedding model test successful")
                status["components"]["embedding_model"] = "operational"
            except Exception as e:
                logger.error(f"❌ Embedding model check failed: {str(e)}")
                error_str = str(e).lower()
                if "not found" in error_str or "does not exist" in error_str:
                    logger.info("🔍 Embedding model not found - marking as missing")
                    status["components"]["embedding_model"] = "missing"
                    status["recommendations"].append("Text embedding model needs to be created")
                else:
                    logger.info("🔍 Embedding model exists but failed - marking as failed")
                    status["components"]["embedding_model"] = "failed"
                    status["recommendations"].append(f"Failed to check embedding model: {str(e)}")
            
            # Check field values table and get statistics
            try:
                table_stats = vector_manager.get_table_stats()
                if "error" in table_stats:
                    status["components"]["field_values_table"] = "missing"
                    status["recommendations"].append("Field values table needs to be created")
                else:
                    status["components"]["field_values_table"] = "operational"
                    status["statistics"] = table_stats
            except Exception as e:
                status["components"]["field_values_table"] = "failed"
                status["recommendations"].append(f"Failed to check field values table: {str(e)}")
            
            # Check vector index (optional) - skip for now as INFORMATION_SCHEMA.VECTOR_INDEXES may not be available
            try:
                # For now, just mark as optional since vector indexes are not critical
                status["components"]["vector_index"] = "optional"
            except Exception:
                status["components"]["vector_index"] = "optional"
            
            # Determine overall system status
            component_values = list(status["components"].values())
            if "failed" in component_values:
                status["system_status"] = "degraded"
            elif "missing" in component_values:
                status["system_status"] = "needs_setup"
            elif all(v in ["operational", "optional"] for v in component_values):
                status["system_status"] = "operational"
                if not status["recommendations"]:
                    status["recommendations"].append("Vector search system is fully operational")
            else:
                status["system_status"] = "partial"
            
            return jsonify({
                "success": True,
                "data": status
            })
            
        except Exception as e:
            logger.error(f"Vector search status error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Failed to get vector search status: {str(e)}", 500))
    
    @admin_bp.route('/vector-search/setup', methods=['POST', 'OPTIONS'])
    def setup_vector_search_system():
        """Setup the complete vector search system"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        try:
            data = request.get_json(force=True) or {}
            force_refresh = data.get('force_refresh', False)
            focus_explore = data.get('focus_explore')
            
            from vector_table_manager import VectorTableManager
            vector_manager = VectorTableManager()
            
            setup_result = {
                "started_at": datetime.utcnow().isoformat(),
                "steps": [],
                "success": False,
                "errors": [],
                "statistics": {}
            }
            
            try:
                # Step 1: Create embedding model
                setup_result["steps"].append("Creating embedding model...")
                logger.info("Setting up embedding model...")
                model_success = vector_manager.create_embedding_model()
                if model_success:
                    setup_result["steps"].append("✅ Embedding model created successfully")
                else:
                    setup_result["errors"].append("❌ Failed to create embedding model")
                    if not force_refresh:
                        raise Exception("Embedding model creation failed")
                
                # Step 2: Create field values table
                setup_result["steps"].append("Creating field values table from Looker explores...")
                logger.info(f"Creating field values table (focus_explore: {focus_explore})")
                table_success = vector_manager.create_field_values_table_from_looker_explores(focus_explore)
                if table_success:
                    setup_result["steps"].append("✅ Field values table created successfully")
                else:
                    setup_result["errors"].append("❌ Failed to create field values table")
                    raise Exception("Field values table creation failed")
                
                # Step 3: Create vector index
                setup_result["steps"].append("Creating vector index...")
                logger.info("Creating vector index...")
                index_success = vector_manager.create_vector_index()
                if index_success:
                    setup_result["steps"].append("✅ Vector index created successfully")
                else:
                    setup_result["steps"].append("⚠️ Vector index creation skipped (not enough data or optional)")
                
                # Step 4: Get final statistics
                setup_result["steps"].append("Gathering final statistics...")
                final_stats = vector_manager.get_table_stats()
                setup_result["statistics"] = final_stats
                
                if "error" not in final_stats:
                    setup_result["steps"].append(f"✅ Setup complete! Indexed {final_stats.get('total_rows', 0)} field values across {final_stats.get('unique_explores', 0)} explores")
                    setup_result["success"] = True
                else:
                    setup_result["errors"].append("Failed to get final statistics")
                
            except Exception as e:
                setup_result["errors"].append(f"Setup failed: {str(e)}")
                logger.error(f"Vector search setup failed: {e}")
            
            setup_result["completed_at"] = datetime.utcnow().isoformat()
            
            return jsonify({
                "success": setup_result["success"],
                "data": setup_result,
                "message": "Vector search system setup completed" if setup_result["success"] else "Vector search system setup failed"
            })
            
        except Exception as e:
            logger.error(f"Vector search setup error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Failed to setup vector search system: {str(e)}", 500))

    app.register_blueprint(admin_bp)


def _register_debug_endpoints(app: Flask) -> None:
    """Register debug endpoints for LLM interaction logging and debug session retrieval"""
    
    debug_bp = Blueprint('debug', __name__, url_prefix='/api/v1/debug')
    
    @debug_bp.route('/logs/<session_id>', methods=['GET', 'OPTIONS'])
    def get_debug_log(session_id: str):
        """Retrieve a debug log by session ID"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        
        try:
            from core.debug_logger import debug_logger
            
            # Validate session ID format
            if not session_id.startswith('debug_'):
                raise RestfulBackendError("Invalid debug session ID format", 400)
            
            # Retrieve the debug session
            debug_session = debug_logger.get_debug_session(session_id)
            
            if not debug_session:
                raise RestfulBackendError("Debug session not found", 404)
            
            # Add some metadata for the response
            response_data = {
                "success": True,
                "debug_session": debug_session,
                "session_id": session_id,
                "retrieved_at": datetime.utcnow().isoformat(),
                "summary": {
                    "total_llm_interactions": len(debug_session.get('llm_interactions', [])),
                    "total_processing_steps": len(debug_session.get('processing_steps', [])),
                    "total_processing_time_ms": debug_session.get('total_processing_time_ms', 0),
                    "request_was_successful": debug_session.get('success', False)
                }
            }
            
            return jsonify(response_data)
            
        except RestfulBackendError as e:
            return _handle_api_error(e)
        except Exception as e:
            logger.error(f"Debug log retrieval error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Failed to retrieve debug log: {str(e)}", 500))
    
    @debug_bp.route('/stats', methods=['GET', 'OPTIONS'])
    def get_debug_stats():
        """Get debug logging system statistics"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        
        try:
            from core.debug_logger import debug_logger
            
            stats = debug_logger.get_debug_stats()
            
            return jsonify({
                "success": True,
                "data": stats,
                "timestamp": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Debug stats error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Failed to get debug stats: {str(e)}", 500))
    
    @debug_bp.route('/cleanup', methods=['POST', 'OPTIONS'])
    def cleanup_debug_logs():
        """Clean up old debug logs"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        
        try:
            data = request.get_json() or {}
            max_age_hours = data.get('max_age_hours', 24)
            
            # Validate max_age_hours
            if not isinstance(max_age_hours, (int, float)) or max_age_hours <= 0:
                raise RestfulBackendError("max_age_hours must be a positive number", 400)
            
            from core.debug_logger import debug_logger
            
            deleted_count = debug_logger.cleanup_old_logs(max_age_hours=max_age_hours)
            
            return jsonify({
                "success": True,
                "data": {
                    "deleted_files": deleted_count,
                    "max_age_hours": max_age_hours,
                    "cleanup_completed_at": datetime.utcnow().isoformat()
                },
                "message": f"Cleaned up {deleted_count} debug log files older than {max_age_hours} hours"
            })
            
        except RestfulBackendError as e:
            return _handle_api_error(e)
        except Exception as e:
            logger.error(f"Debug cleanup error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Failed to cleanup debug logs: {str(e)}", 500))
    
    @debug_bp.route('/test', methods=['POST', 'OPTIONS'])
    def test_debug_mode():
        """Test endpoint to verify debug logging functionality"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        
        try:
            data = request.get_json() or {}
            test_query = data.get('test_query', 'Test debug query for system verification')
            
            # Force debug mode for this test
            test_data = {
                'query': test_query,
                'debug': True,
                'explore_key': 'test:debug_explore'
            }
            
            # Extract user info from auth header
            auth_header = request.headers.get('Authorization', '')
            user_info = extract_user_info_from_token(auth_header)
            
            # Initialize debug session manually
            from core.debug_logger import debug_logger
            debug_logger.enable_debug_mode()
            session_id = debug_logger.start_debug_session(test_data)
            
            # Log some test steps
            debug_logger.log_processing_step("test_step_1", {
                "action": "debug_test_initiated",
                "query": test_query
            })
            
            # Simulate an LLM interaction
            debug_logger.log_llm_interaction(
                context="debug_test",
                request_data={"test_request": "This is a test LLM request"},
                response_data={"test_response": "This is a test LLM response"},
                processing_time_ms=100.0,
                token_usage={"prompt_tokens": 50, "total_tokens": 75}
            )
            
            debug_logger.log_processing_step("test_step_2", {
                "action": "debug_test_completed",
                "session_id": session_id
            })
            
            # End debug session
            response_data = {
                "test_result": "Debug logging test completed successfully",
                "session_id": session_id
            }
            
            debug_logger.end_debug_session(
                response_data=response_data,
                success=True,
                total_processing_time_ms=150.0
            )
            
            debug_logger.disable_debug_mode()
            
            return jsonify({
                "success": True,
                "data": {
                    "test_completed": True,
                    "debug_session_id": session_id,
                    "debug_log_url": f"/api/v1/debug/logs/{session_id}",
                    "test_query": test_query
                },
                "message": "Debug logging test completed successfully"
            })
            
        except Exception as e:
            logger.error(f"Debug test error: {traceback.format_exc()}")
            return _handle_api_error(RestfulBackendError(f"Debug test failed: {str(e)}", 500))
    
    app.register_blueprint(debug_bp)


def _register_legacy_endpoints(app: Flask) -> None:
    """Register legacy endpoints for backward compatibility"""
    
    @app.route('/', methods=['POST', 'OPTIONS'])
    def legacy_root():
        """Legacy root endpoint for backward compatibility"""
        if request.method == 'OPTIONS':
            return _handle_cors()
        
        # Redirect to new API endpoint
        return handle_query()
    
    @app.route('/health', methods=['GET'])
    def legacy_health():
        """Legacy health endpoint"""
        return health_check()
    


def _process_query_request(data: Dict[str, Any], auth_header: str, user_info: Dict[str, Any], debug_mode: bool = False) -> Dict[str, Any]:
    """Process a query request using the new modular architecture"""
    import time
    
    # Initialize debug logger if in debug mode
    debug_logger = None
    if debug_mode:
        from core.debug_logger import debug_logger as dl
        debug_logger = dl
    
    # Extract query parameters
    query_text = data.get('query', data.get('prompt', ''))
    if not query_text:
        raise RestfulBackendError("Query text is required", 400)

    conversation_context = data.get('conversation_context', '')
    explore_key = data.get('explore_key')

    # Extract additional context with safe defaults
    restricted_explore_keys = data.get('restricted_explore_keys') or []
    golden_queries = data.get('golden_queries') or {}
    semantic_models = data.get('semantic_models') or {}

    logger.info(f"🚀 Processing query: {query_text[:100]}...")
    logger.info(f"restricted_explore_keys from request: {restricted_explore_keys}")
    logger.info(f"golden_queries from request: {type(golden_queries)}")
    logger.info(f"semantic_models from request: {type(semantic_models)}")

    if debug_logger:
        debug_logger.log_processing_step("query_extraction", {
            "query_text": query_text,
            "conversation_context_present": bool(conversation_context),
            "explore_key_provided": bool(explore_key),
            "restricted_explores_count": len(restricted_explore_keys) if restricted_explore_keys else 0,
            "golden_queries_type": type(golden_queries).__name__,
            "semantic_models_type": type(semantic_models).__name__
        })

    try:
        # Step 1: Determine explore if not provided
        if not explore_key:
            step_start = time.time()
            
            if debug_logger:
                debug_logger.log_processing_step("explore_determination_start", {
                    "available_explores": restricted_explore_keys or [],
                    "method": "ai_selection"
                })
            
            explore_key = determine_explore_from_prompt(
                auth_header=auth_header,
                prompt=query_text,
                golden_queries=golden_queries,
                conversation_context=conversation_context,
                restricted_explore_keys=restricted_explore_keys,
                semantic_models=semantic_models,
                debug_mode=debug_mode
            )
            
            step_time = (time.time() - step_start) * 1000
            
            if debug_logger:
                debug_logger.log_processing_step("explore_determination_complete", {
                    "selected_explore": explore_key,
                    "method": "ai_selection"
                }, step_time)

            if not explore_key:
                raise RestfulBackendError("Could not determine appropriate explore", 400)

        # Step 2: Generate parameters using new modular system
        step_start = time.time()
        
        if debug_logger:
            debug_logger.log_processing_step("parameter_generation_start", {
                "target_explore": explore_key,
                "vector_search_enabled": True,
                "golden_queries_available": bool(golden_queries)
            })
        
        result = generate_explore_params_from_query(
            auth_header=auth_header,
            query=query_text,
            explore_key=explore_key,
            golden_queries=golden_queries,
            semantic_models=semantic_models,
            conversation_context=conversation_context,
            current_explore={},
            debug_mode=debug_mode
        )
        
        step_time = (time.time() - step_start) * 1000
        
        if debug_logger:
            debug_logger.log_processing_step("parameter_generation_complete", {
                "success": bool(result),
                "generation_method": result.get('generation_method') if result else None,
                "vector_search_used_count": len(result.get('vector_search_used', [])) if result else 0
            }, step_time)

        if not result:
            raise RestfulBackendError("Failed to generate query parameters", 500)

        # Step 3: Extract validated parameters (already processed by generator)
        step_start = time.time()
        
        # Defensive extraction - ensure we get a valid dictionary
        explore_params = result.get('explore_params')
        if not explore_params or not isinstance(explore_params, dict):
            logger.error(f"❌ Invalid explore_params from generator: {type(explore_params)}")
            raise RestfulBackendError("Invalid parameters returned from parameter generator", 500)
        
        validated_params = explore_params
        
        step_time = (time.time() - step_start) * 1000
        
        if debug_logger:
            debug_logger.log_processing_step("parameter_validation_complete", {
                "field_count": len(validated_params.get('fields', [])),
                "filter_count": len(validated_params.get('filters', {})),
                "sort_count": len(validated_params.get('sorts', [])),
                "limit": validated_params.get('limit')
            }, step_time)

        # Step 4: Store query for learning (Olympic system)
        step_start = time.time()
        
        _store_query_for_learning(query_text, explore_key, validated_params, user_info)
        
        step_time = (time.time() - step_start) * 1000
        
        if debug_logger:
            debug_logger.log_processing_step("olympic_storage_complete", {
                "stored_in_olympic_system": True
            }, step_time)

        # Build comprehensive response
        response_data = {
            "explore_key": explore_key,
            "parameters": validated_params,
            "generation_metadata": {
                "model_used": result.get('model_used', VERTEX_MODEL),
                "vector_search_used": result.get('vector_search_used', []),
                "vector_search_summary": result.get('vector_search_summary', {}),
                "generation_method": result.get('generation_method', 'modular_pipeline')
            },
            "user_info": {
                "email": user_info.get('email'),
                "user_id": user_info.get('user_id')
            }
        }
        
        # Add verbose debug information if in debug mode
        if debug_mode:
            response_data["debug_details"] = {
                "processing_pipeline": [
                    "query_extraction",
                    "explore_determination" if not data.get('explore_key') else "explore_provided",
                    "parameter_generation_with_vector_search",
                    "parameter_validation",
                    "olympic_system_storage"
                ],
                "context_analysis": {
                    "query_length": len(query_text),
                    "conversation_context_length": len(conversation_context),
                    "restricted_explores_applied": bool(restricted_explore_keys),
                    "golden_queries_available": bool(golden_queries),
                    "semantic_models_available": bool(semantic_models)
                },
                "generation_details": {
                    "vector_search_hits": len(result.get('vector_search_used', [])),
                    "field_context_available": result.get('field_context_available', False),
                    "golden_examples_used": result.get('golden_examples_used', 0)
                }
            }
        
        return response_data

    except ParameterGenerationError as e:
        raise RestfulBackendError(f"Parameter generation failed: {e.message}", 400, {"explore_key": e.explore_key})
    except Exception as e:
        logger.error(f"Query processing error: {traceback.format_exc()}")
        raise RestfulBackendError(f"Query processing failed: {str(e)}", 500)


def _get_available_explores() -> List[str]:
    """Get list of available explores (placeholder implementation)"""
    # This would integrate with your Looker SDK to get actual explores
    return [
        "ecommerce:order_items",
        "ecommerce:users", 
        "ecommerce:events"
    ]


def _get_golden_queries_for_explore(explore_key: str) -> Dict[str, Any]:
    """Get golden queries for a specific explore"""
    try:
        return app.olympic_manager.get_golden_queries_for_explore(explore_key)
    except Exception as e:
        logger.warning(f"Failed to get golden queries for {explore_key}: {e}")
        return {}


def _get_semantic_models() -> Dict[str, Any]:
    """Get semantic models (placeholder implementation)"""
    # This would load your semantic models from storage
    return {}


def _store_query_for_learning(query: str, explore_key: str, params: Dict, user_info: Dict) -> None:
    """Store query in Olympic system for learning"""
    try:
        # Convert parameters to JSON string for storage
        output_str = json.dumps(params) if params else "{}"

        # Use user_email for bronze queries, user_id for feedback (handled elsewhere)
        user_email = user_info.get('email', 'unknown')
        app.olympic_manager.add_bronze_query(  # type: ignore[attr-defined]
            explore_id=explore_key,
            input_text=query,
            output=output_str,
            link="",
            user_email=user_email,
            query_run_count=1
        )
        logger.info(f"✅ Stored bronze query for learning: {explore_key}")
    except Exception as e:
        logger.warning(f"Failed to store query for learning: {e}")
def _handle_cors() -> Response:
    """Handle CORS preflight requests"""
    response = Response()
    response.headers.update({
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With',
        'Access-Control-Max-Age': '3600'
    })
    return response


def _handle_api_error(error: RestfulBackendError) -> Tuple[Response, int]:
    """Handle API errors consistently"""
    response_data = {
        "success": False,
        "error": {
            "message": error.message,
            "details": error.details
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    
    logger.error(f"API Error {error.status_code}: {error.message}")
    return jsonify(response_data), error.status_code


def _register_error_handlers(app: Flask) -> None:
    """Register global error handlers"""
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "success": False,
            "error": {
                "message": "Endpoint not found",
                "details": {"path": request.path}
            }
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({
            "success": False,
            "error": {
                "message": "Internal server error",
                "details": {}
            }
        }), 500


# Create the application instance for Gunicorn
app = create_app()


def handle_query():
    """Helper function for legacy compatibility"""
    # This calls the actual API endpoint
    from flask import current_app
    with current_app.test_request_context():
        return current_app.view_functions['api_v1.handle_query']()


def health_check():
    """Helper function for legacy compatibility"""
    from flask import current_app
    with current_app.test_request_context():
        return current_app.view_functions['api_v1.health_check']()


if __name__ == "__main__":
    # Only for local development - Gunicorn will use the app instance above
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🚀 Starting development server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=True)