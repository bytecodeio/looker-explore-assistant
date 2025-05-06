import os
import logging
import uuid
import time
import json
from typing import Dict, Any, Optional, List, Union

# Check if LangSmith is available
LANGSMITH_API_KEY = os.environ.get("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.environ.get("LANGSMITH_PROJECT", "looker-explore-assistant")
LANGSMITH_TRACING_ENABLED = LANGSMITH_API_KEY is not None

if LANGSMITH_TRACING_ENABLED:
    try:
        from langsmith import Client
        langsmith_client = Client(api_key=LANGSMITH_API_KEY)
        logging.info(f"LangSmith client initialized for project: {LANGSMITH_PROJECT}")
    except ImportError:
        logging.warning("LangSmith packages not installed. Using basic tracing.")
        LANGSMITH_TRACING_ENABLED = False
        langsmith_client = None
else:
    langsmith_client = None

# Store traces in memory when LangSmith is not available
_local_traces: Dict[str, List[Dict[str, Any]]] = {}

def create_run(name: str, inputs: Dict[str, Any] = None) -> str:
    """
    Create a new run for tracing workflow execution
    
    Args:
        name: Name of the run
        inputs: Input parameters for the run
        
    Returns:
        Run ID that can be used for subsequent tracing
    """
    run_id = str(uuid.uuid4())
    
    if LANGSMITH_TRACING_ENABLED and langsmith_client:
        try:
            inputs = inputs or {}
            # Use the correct method to create a run
            langsmith_client.create_run(
                name=name,
                run_id=run_id,
                inputs=inputs,
                run_type="chain",
                project_name=LANGSMITH_PROJECT,
                execution_order=1,
                tags=["looker-explore-assistant"]
            )
            logging.debug(f"Created LangSmith run: {run_id}")
        except Exception as e:
            logging.error(f"Error creating LangSmith run: {e}")
    else:
        # Store locally
        _local_traces[run_id] = [{
            "step": "run_created",
            "timestamp": time.time(),
            "name": name,
            "inputs": inputs
        }]
        
    return run_id

def trace_step(
    step_name: str, 
    data: Union[Dict[str, Any], str], 
    run_id: Optional[str] = None,
    is_error: bool = False
) -> None:
    """
    Record a trace for a workflow step
    
    Args:
        step_name: Name of the step
        data: Data associated with the step
        run_id: Run ID from create_run
        is_error: Whether this is an error step
    """
    if not run_id:
        run_id = "default"
        
    if isinstance(data, str):
        data = {"message": data}
        
    if LANGSMITH_TRACING_ENABLED and langsmith_client:
        try:
            # Convert data to JSON-serializable format
            serializable_data = json.loads(json.dumps(data, default=str))
            
            if is_error:
                # Update run with exception
                langsmith_client.update_run(
                    run_id=run_id,
                    error=serializable_data.get("message", "Unknown error"),
                    end_time=time.time()
                )
            else:
                # Add a trace using the correct method
                # LangSmith API changed - use correct approach based on current API
                try:
                    # Method 1: Using update_run to add outputs
                    langsmith_client.update_run(
                        run_id=run_id,
                        outputs={step_name: serializable_data}
                    )
                except Exception as e1:
                    try:
                        # Method 2: Using create_trace
                        from langsmith.schemas import Trace
                        trace = Trace(
                            run_id=run_id,
                            name=step_name,
                            inputs={"data": serializable_data},
                            outputs={}
                        )
                        langsmith_client.create_trace(trace)
                    except Exception as e2:
                        logging.error(f"Failed both update_run and create_trace: {e1} | {e2}")
                        # Add a simple note to the run
                        langsmith_client.update_run(
                            run_id=run_id,
                            notes=f"{step_name}: {json.dumps(serializable_data)[:100]}..."
                        )
        except Exception as e:
            logging.error(f"Error adding LangSmith trace: {e}")
    else:
        # Store locally
        if run_id not in _local_traces:
            _local_traces[run_id] = []
            
        _local_traces[run_id].append({
            "step": step_name,
            "timestamp": time.time(),
            "data": data,
            "is_error": is_error
        })

def get_trace(run_id: str) -> List[Dict[str, Any]]:
    """
    Get the trace for a run
    
    Args:
        run_id: Run ID
        
    Returns:
        List of trace steps
    """
    if LANGSMITH_TRACING_ENABLED and langsmith_client:
        try:
            run = langsmith_client.read_run(run_id)
            return run.get("traces", [])
        except Exception as e:
            logging.error(f"Error reading LangSmith run: {e}")
            return []
    else:
        return _local_traces.get(run_id, [])

def log_step(step_name: str, message: str, **kwargs) -> None:
    """
    Log a workflow step for easier debugging
    
    Args:
        step_name: Name of the step
        message: Message to log
        **kwargs: Additional data to include in the log
    """
    log_data = {
        "step": step_name,
        "message": message,
        **kwargs
    }
    logging.info(f"WORKFLOW: {step_name} - {message}")
    if kwargs:
        logging.debug(f"WORKFLOW DETAILS: {json.dumps(kwargs, default=str)}")
