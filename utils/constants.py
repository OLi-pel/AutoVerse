# utils/constants.py
import os
import sys
import logging

# --- Application Version ---
APP_VERSION = "1.0.1" 

# --- User-specific Application Data Directory ---
APP_NAME = "AutoVerse"

def get_app_data_dir():
    """Returns the appropriate user-specific data directory for the OS."""
    if sys.platform == "win32":
        # Windows
        return os.path.join(os.environ['APPDATA'], APP_NAME)
    elif sys.platform == "darwin":
        # macOS
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", APP_NAME)
    else:
        # Linux and other Unix-like systems
        return os.path.join(os.path.expanduser("~"), ".config", APP_NAME)

APP_USER_DATA_DIR = get_app_data_dir()

# --- Message types for queue ---
MSG_TYPE_STATUS = "status"
MSG_TYPE_PROGRESS = "progress"
MSG_TYPE_FINISHED = "finished" # Retained for single-file backward compatibility if needed
MSG_TYPE_BATCH_FILE_START = "batch_file_start"
MSG_TYPE_BATCH_COMPLETED = "batch_completed"

# --- Payload keys for messages ---
KEY_FINAL_STATUS = "final_status"
KEY_ERROR_MESSAGE = "error_message"
KEY_IS_EMPTY_RESULT = "is_empty_result"
KEY_BATCH_FILENAME = "filename"
KEY_BATCH_CURRENT_IDX = "current_idx"
KEY_BATCH_TOTAL_FILES = "total_files"
KEY_BATCH_ALL_RESULTS = "all_results"


# --- Specific status values ---
STATUS_SUCCESS = "SUCCESS"
STATUS_EMPTY = "EMPTY"
STATUS_ERROR = "ERROR"

# --- Default output file name ---
DEFAULT_OUTPUT_TEXT_FILE = "processed_output.txt" 
DEFAULT_CONFIG_FILE = os.path.join(APP_USER_DATA_DIR, 'config.ini')

# --- Special Labels ---
NO_SPEAKER_LABEL = "SPEAKER_NONE_INTERNAL"
EMPTY_SEGMENT_PLACEHOLDER = "[Double-click to edit text]"

# --- Logging Configuration ---
LOG_LEVEL_DEBUG = logging.DEBUG
LOG_LEVEL_INFO = logging.INFO
ACTIVE_LOG_LEVEL = LOG_LEVEL_DEBUG
LOG_FORMAT = '%(asctime)s %(levelname)-8s [%(threadName)s] [%(filename)s:%(lineno)d] %(funcName)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'