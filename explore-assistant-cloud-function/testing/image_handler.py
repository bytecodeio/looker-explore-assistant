import os
import logging
from typing import Optional
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ImageHandler:
    """
    Handles visualization images for Looker Explore Assistant testing
    """
    
    def __init__(self, screenshot_dir: str = "./visualizations"):
        """
        Initialize the image handler
        
        Args:
            screenshot_dir: Directory to save visualization images
        """
        self.screenshot_dir = screenshot_dir
        # Create the directory if it doesn't exist
        os.makedirs(self.screenshot_dir, exist_ok=True)
    
    def save_image(self, image_data: bytes, filename: Optional[str] = None) -> str:
        """
        Save a visualization image to file
        
        Args:
            image_data: Binary image data
            filename: Optional filename, if not provided a timestamp will be used
            
        Returns:
            Path to the saved image file
        """
        if not image_data:
            logger.warning("No image data provided to save")
            return ""
            
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"vis_{timestamp}.png"
        
        # Ensure filename has .png extension
        if not filename.lower().endswith('.png'):
            filename += '.png'
            
        # Full path to save the image
        filepath = os.path.join(self.screenshot_dir, filename)
        
        try:
            # Write binary image data to file
            with open(filepath, 'wb') as f:
                f.write(image_data)
                
            logger.info(f"Saved visualization to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error saving image: {e}")
            return ""
    
    def get_image_path(self, filename: str) -> str:
        """
        Get the full path to an image file
        
        Args:
            filename: Image filename
            
        Returns:
            Full path to the image file
        """
        return os.path.join(self.screenshot_dir, filename)
import os
import base64
import logging
from typing import Optional
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ImageHandler:
    """
    Handles saving and encoding Looker visualization images for LLM evaluation
    """
    
    def __init__(self, screenshot_dir: Optional[str] = None):
        """
        Initialize the image handler
        
        Args:
            screenshot_dir: Directory to save visualization images
        """
        self.screenshot_dir = screenshot_dir or os.path.join(os.getcwd(), "visualizations")
        os.makedirs(self.screenshot_dir, exist_ok=True)
    
    def save_image(self, image_data: bytes, filename: Optional[str] = None) -> str:
        """
        Save image data to a file
        
        Args:
            image_data: Binary image data
            filename: Optional filename, if None a timestamp-based name will be used
            
        Returns:
            Path to the saved image file
        """
        if not image_data:
            logger.warning("No image data provided to save")
            return None
            
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"visualization_{timestamp}.png"
            
        filepath = os.path.join(self.screenshot_dir, filename)
        
        try:
            with open(filepath, "wb") as f:
                f.write(image_data)
            logger.info(f"Image saved to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error saving image: {e}")
            return None
    
    def encode_image_for_llm(self, image_data: bytes) -> Optional[str]:
        """
        Encode image data as base64 for sending to an LLM
        
        Args:
            image_data: Binary image data
            
        Returns:
            Base64-encoded string of the image, or None if encoding failed
        """
        if not image_data:
            logger.warning("No image data provided to encode")
            return None
            
        try:
            return base64.b64encode(image_data).decode("utf-8")
        except Exception as e:
            logger.error(f"Error encoding image: {e}")
            return None
    
    def load_image(self, image_path: str) -> Optional[bytes]:
        """
        Load image data from a file
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Binary image data, or None if loading failed
        """
        if not image_path or not os.path.exists(image_path):
            logger.warning(f"Image file not found: {image_path}")
            return None
            
        try:
            with open(image_path, "rb") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error loading image: {e}")
            return None
