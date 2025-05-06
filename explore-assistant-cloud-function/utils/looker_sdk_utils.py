import os
import logging
from looker_sdk import init40, error

def init_looker_sdk():
    """Initialize Looker SDK with proper certificate handling"""
    # Get SSL verification setting from environment with proper boolean conversion
    verify_ssl = os.environ.get('LOOKERSDK_VERIFY_SSL', 'true').lower()
    verify_ssl = verify_ssl == 'true' or verify_ssl == '1'
    
    if not verify_ssl:
        # Suppress certificate warnings if verification is disabled
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        logging.info("SSL certificate verification disabled")
    
    # Initialize the SDK with the environment variables
    try:
        sdk = init40()
        logging.debug("Looker SDK initialized successfully")
        return sdk
    except Exception as e:
        logging.error(f"Error initializing Looker SDK: {e}")
        raise
