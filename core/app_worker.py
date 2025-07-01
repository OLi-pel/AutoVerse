# core/app_worker.py
import logging
import os
import sys
import tempfile
from moviepy.editor import VideoFileClip
from moviepy.config import change_settings # Import at module level
from core.audio_processor import AudioProcessor, ProcessedAudioResult
from utils import constants

# Set up a logger specifically for this worker. This is crucial for debugging.
logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv']

def _is_video_file(file_path):
    """Checks if a file is a video based on its extension."""
    return any(file_path.lower().endswith(ext) for ext in VIDEO_EXTENSIONS)

def _extract_audio(video_path):
    """
    Extracts audio from a video file and returns a temporary audio file path.
    This now assumes that the moviepy config has been set by the main worker function.
    """
    try:
        video = VideoFileClip(video_path)
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio_file:
            temp_path = temp_audio_file.name
        
        video.audio.write_audiofile(temp_path, codec='pcm_s16le')
        logger.info(f"Successfully extracted audio from {video_path} to {temp_path}")
        return temp_path
        
    except Exception as e:
        logger.error(f"Failed to extract audio from {video_path}: {e}")
        raise

# --- MODIFIED FUNCTION SIGNATURE ---
def processing_worker_function(queue, file_paths, options, cache_dir, dest_folder=None, ffmpeg_path=None):
    """
    This function runs in a separate process. It now configures its own logging
    and uses the ffmpeg_path provided by the main process.
    """
    # --- WORKER-SPECIFIC LOGGING SETUP ---
    # Since this is a new process, we must configure logging again.
    # We can log to a separate file for clarity.
    log_dir = os.path.join(constants.APP_USER_DATA_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, "worker.log")
    
    # Configure the logger for this process
    file_handler = logging.FileHandler(log_file_path, mode='w', encoding='utf-8')
    formatter = logging.Formatter(constants.LOG_FORMAT, datefmt=constants.LOG_DATE_FORMAT)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.setLevel(constants.ACTIVE_LOG_LEVEL)

    # --- THE DEFINITIVE FFMPEG FIX ---
    # If a specific path was passed from the main process, set it for moviepy.
    if ffmpeg_path:
        logger.info(f"Worker received ffmpeg path: {ffmpeg_path}")
        change_settings({"FFMPEG_BINARY": ffmpeg_path})
    else:
        logger.warning("No specific ffmpeg path received. Relying on system PATH.")

    try:
        def progress_callback(message, percentage=None):
            if percentage is not None:
                queue.put((constants.MSG_TYPE_PROGRESS, percentage))
            if message:
                queue.put((constants.MSG_TYPE_STATUS, message))

        def _map_ui_model_key_to_whisper_name(ui_model_key: str) -> str:
            mapping = {"tiny": "tiny", "base": "base", "small": "small", "medium": "medium", "large (recommended)": "large", "turbo": "small"}
            return mapping.get(ui_model_key, "large")

        processor_config = {
            'huggingface': {'use_auth_token': 'yes' if options['enable_diarization'] else 'no', 'hf_token': options['hf_token']},
            'transcription': {'model_name': _map_ui_model_key_to_whisper_name(options['model_key'])}
        }
        
        audio_processor = AudioProcessor(
            config=processor_config,
            progress_callback=progress_callback,
            enable_diarization=options['enable_diarization'],
            include_timestamps=options['include_timestamps'],
            include_end_times=options['include_end_times'],
            enable_auto_merge=options['auto_merge'],
            cache_dir=cache_dir
        )
        
        all_results = []
        total_files = len(file_paths)

        for idx, file_path in enumerate(file_paths):
            current_file_display_name = os.path.basename(file_path)
            queue.put((constants.MSG_TYPE_BATCH_FILE_START, {
                constants.KEY_BATCH_FILENAME: current_file_display_name,
                constants.KEY_BATCH_CURRENT_IDX: idx + 1,
                constants.KEY_BATCH_TOTAL_FILES: total_files
            }))
            
            audio_to_process = None
            temp_audio_path = None
            is_temp_file_used = False

            try:
                if _is_video_file(file_path):
                    progress_callback(f"Extracting audio from {current_file_display_name}...", 0)
                    temp_audio_path = _extract_audio(file_path)
                    audio_to_process = temp_audio_path
                    is_temp_file_used = True
                else:
                    audio_to_process = file_path

                if not audio_to_process:
                     raise ValueError("Could not determine audio source for processing.")
                
                result = audio_processor.process_audio(audio_to_process)
                result.source_file = file_path

                if result.status == constants.STATUS_SUCCESS:
                    model_name_key = options["model_key"].split(" ")[0]
                    base_name, _ = os.path.splitext(os.path.basename(file_path))
                    output_filename = f"{base_name}_{model_name_key}_transcription.txt"
                    
                    if total_files > 1 and dest_folder:
                        save_path = os.path.join(dest_folder, output_filename)
                        AudioProcessor.save_to_txt(save_path, result.data, result.is_plain_text_output)
                        result.output_path = save_path
                        progress_callback(f"Saved to {os.path.basename(save_path)}", 100)
                
                all_results.append(result)

            except Exception as e:
                logger.exception(f"An error occurred in the worker process for file: {file_path}.")
                error_result = ProcessedAudioResult(constants.STATUS_ERROR, message=f"Failed to process {current_file_display_name}: {e}")
                error_result.source_file = file_path
                all_results.append(error_result)
            
            finally:
                if is_temp_file_used and temp_audio_path and os.path.exists(temp_audio_path):
                    try:
                        os.remove(temp_audio_path)
                        logger.info(f"Successfully cleaned up temporary audio file: {temp_audio_path}")
                    except OSError as e:
                        logger.error(f"Failed to remove temporary file {temp_audio_path}: {e}")
        
        final_payload = {constants.KEY_BATCH_ALL_RESULTS: all_results}
        queue.put((constants.MSG_TYPE_BATCH_COMPLETED, final_payload))

    except Exception as e:
        logger.exception("A critical unhandled error occurred at the top level of the worker process.")
        error_result = ProcessedAudioResult(constants.STATUS_ERROR, message=str(e))
        # Ensure at least one result is sent back on catastrophic failure
        if 'all_results' not in locals() or not all_results:
             all_results = [error_result]
        queue.put(('finished', {constants.KEY_BATCH_ALL_RESULTS: all_results}))