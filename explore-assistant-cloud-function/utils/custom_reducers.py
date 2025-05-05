def add_explores(state, explores):
    state["explores"] = explores
    return state

def add_metadata(state, metadata):
    state["metadata"] = metadata
    return state

def set_model(state, model_name):
    """
    Set the model name to be used in the workflow
    
    Args:
        state: Current state dictionary
        model_name: Name of the model to use
        
    Returns:
        Updated state with model_name
    """
    state["model_name"] = model_name
    
    # If there's a model_manager in the state, update its default model
    if "model_manager" in state and hasattr(state["model_manager"], "set_default_model"):
        state["model_manager"].set_default_model(model_name)
        
    return state
