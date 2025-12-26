// FILE: utils/audio_utils.py
# utils/audio_utils.py
import logging
import os

logger = logging.getLogger(__name__)

def cleanup_temp_file(file_path: str):
    """
    Safely remove a temporary file.
    
    Args:
        file_path: Path to the temporary file to remove
    """
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.debug(f"Cleaned up temporary file: {file_path}")
        except OSError as e:
            logger.warning(f"Failed to clean up temporary file {file_path}: {e}")